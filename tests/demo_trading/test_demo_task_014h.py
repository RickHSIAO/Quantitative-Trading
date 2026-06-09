"""
tests/demo_trading/test_demo_task_014h.py
TASK-014H: Persist real Demo position details through smoke / reconciliation /
           cleanup / sender pipeline.

The bug TASK-014H fixes:
  TASK-014D real read-only smoke returned 8 real Demo short positions
  (AIXBTUSDT, ENAUSDT, BOMEUSDT, EDUUSDT, MERLUSDT, XAUTUSDT, POLYXUSDT,
  TIAUSDT), but TASK-014E reconciliation reported "position details from
  fixture" and emitted fixture candidates (ETHUSDT / BNBUSDT) that do not
  exist on the real Demo account. TASK-014F / G then proposed closing
  symbols that the exchange will reject.

Requirements verified (H1-H13):
  H1.  real-readonly smoke JSON has positions details + position_details_source
       + no_orders_sent=True + positions_count + timestamp
  H2.  smoke JSON / MD contain no API secrets
  H3.  reconciliation `--from-latest-readonly-smoke` loads real positions
       from the JSON when smoke source is real_readonly
  H4.  reconciliation fails closed when real smoke lacks positions details
       (reason=missing_real_position_details)
  H5.  reconciliation never falls back to fixture positions in real_readonly
       mode (no fixture symbols leak into the candidate set)
  H6.  cleanup candidates are drawn from reconciliation real positions only
  H7.  cleanup with fixture-symbol candidates that do not exist in the real
       smoke is impossible (the gate blocks them)
  H8.  sender dry-run fails when the requested symbol is not in the real
       positions set
  H9.  sender dry-run execute_allowed=True only when
       position_details_source=real_readonly
  H10. all written reports (smoke, reconciliation, cleanup, execution)
       include position_details_source
  H11. order endpoint is never called (order_endpoint_called=False) in any
       dry-run scenario in this test module
  H12. JSON + MD reports contain no API key / secret bytes
  H13. main.py, src/risk.py, and BybitExecutor classes are NOT modified by
       TASK-014H (structural check against forbidden imports / strings)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_close_only_cleanup import _expected_confirm_token, plan_cleanup
from src.demo_close_only_sender import DemoCloseOnlySender
from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import DemoOpenPosition
from src.demo_position_reconcile import reconcile
from src.demo_readonly_client import PROOF_STRONG, DemoReadOnlyClient


def _permissive_rules(symbols: list[str]) -> dict[str, InstrumentRules]:
    return {
        s: InstrumentRules(
            symbol=s, qty_step=0.001, min_qty=0.001, max_qty=0.0,
            tick_size=0.0001, min_notional=5.0,
            price_precision=4, qty_precision=3,
        )
        for s in symbols
    }


# ---------------------------------------------------------------------------
# Fixtures: the 8 real Demo short positions observed by TASK-014D
# ---------------------------------------------------------------------------

_REAL_DEMO_SYMBOLS = [
    "AIXBTUSDT", "ENAUSDT", "BOMEUSDT", "EDUUSDT",
    "MERLUSDT", "XAUTUSDT", "POLYXUSDT", "TIAUSDT",
]


def _real_demo_positions() -> list[DemoOpenPosition]:
    return [
        DemoOpenPosition("AIXBTUSDT", "short", 100.0,    0.50,    0.55),
        DemoOpenPosition("ENAUSDT",   "short", 1000.0,   0.80,    0.85),
        DemoOpenPosition("BOMEUSDT",  "short", 5000.0,   0.01,    0.012),
        DemoOpenPosition("EDUUSDT",   "short", 800.0,    1.20,    1.30),
        DemoOpenPosition("MERLUSDT",  "short", 400.0,    2.40,    2.60),
        DemoOpenPosition("XAUTUSDT",  "short", 0.4,      2400.0,  2500.0),
        DemoOpenPosition("POLYXUSDT", "short", 1500.0,   0.30,    0.34),
        DemoOpenPosition("TIAUSDT",   "short", 50.0,     5.40,    5.80),
    ]


def _legacy_fixture_positions() -> list[DemoOpenPosition]:
    """The (wrong) fixture set that bug TASK-014H eliminates from real flow."""
    return [
        DemoOpenPosition("BTCUSDT",  "long",  0.02,   67_000.0, 65_000.0),
        DemoOpenPosition("ETHUSDT",  "short", 0.50,    3_500.0,  3_700.0),
        DemoOpenPosition("BNBUSDT",  "short", 2.00,      600.0,    640.0),
        DemoOpenPosition("SOLUSDT",  "short", 5.00,      160.0,    175.0),
        DemoOpenPosition("XRPUSDT",  "short", 500.00,      0.62,     0.68),
        DemoOpenPosition("ADAUSDT",  "short", 800.00,      0.45,     0.49),
        DemoOpenPosition("DOTUSDT",  "short",  30.00,      7.80,     8.50),
        DemoOpenPosition("LINKUSDT", "short",  20.00,     14.50,    16.00),
    ]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _valid_token(today: date) -> str:
    return _expected_confirm_token(today)


# ---------------------------------------------------------------------------
# H1. Real-readonly smoke JSON persists positions details
# ---------------------------------------------------------------------------

class TestH1RealReadonlySmokePersistsPositions:
    """H1: smoke JSON includes positions array + provenance + safety fields."""

    def _run_preview(self, tmp: Path, monkeypatch) -> Path:
        import scripts.preview_demo_readonly_runtime as mod
        out_dir = tmp / "readonly_smoke"
        out_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(mod, "_OUTPUT_DIR", out_dir, raising=True)
        mod.run_preview(use_real_network=False, write_report=True)
        return out_dir / "latest_smoke.json"

    def test_smoke_json_exists(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            jp = self._run_preview(Path(tmp), monkeypatch)
            assert jp.exists()

    def test_smoke_json_has_positions_array(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            jp = self._run_preview(Path(tmp), monkeypatch)
            data = json.loads(jp.read_text(encoding="utf-8"))
            assert isinstance(data.get("positions"), list)

    def test_smoke_json_has_position_details_source(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            jp = self._run_preview(Path(tmp), monkeypatch)
            data = json.loads(jp.read_text(encoding="utf-8"))
            assert "position_details_source" in data

    def test_smoke_json_has_safety_flags(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            jp = self._run_preview(Path(tmp), monkeypatch)
            data = json.loads(jp.read_text(encoding="utf-8"))
            assert data.get("no_orders_sent") is True

    def test_smoke_json_has_positions_count(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            jp = self._run_preview(Path(tmp), monkeypatch)
            data = json.loads(jp.read_text(encoding="utf-8"))
            assert "positions_count" in data

    def test_smoke_json_has_timestamp(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            jp = self._run_preview(Path(tmp), monkeypatch)
            data = json.loads(jp.read_text(encoding="utf-8"))
            assert "timestamp" in data


# ---------------------------------------------------------------------------
# H2. Smoke JSON / MD contain no secrets
# ---------------------------------------------------------------------------

class TestH2SmokeNoSecrets:
    """H2: secret-shaped strings never appear in smoke JSON or MD output."""

    _FORBIDDEN = ("BYBIT_DEMO_API_SECRET", "X-BAPI-SIGN")

    def _emit(self, tmp: Path, monkeypatch) -> tuple[Path, Path]:
        import scripts.preview_demo_readonly_runtime as mod
        out_dir = tmp / "readonly_smoke"
        out_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(mod, "_OUTPUT_DIR", out_dir, raising=True)
        mod.run_preview(use_real_network=False, write_report=True)
        return (
            out_dir / "latest_smoke.json",
            out_dir / "latest_smoke.md",
        )

    def test_json_contains_no_secret_tokens(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            jp, _ = self._emit(Path(tmp), monkeypatch)
            txt = jp.read_text(encoding="utf-8")
            for tok in self._FORBIDDEN:
                assert tok not in txt

    def test_md_contains_no_secret_tokens(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            _, mp = self._emit(Path(tmp), monkeypatch)
            if mp.exists():
                txt = mp.read_text(encoding="utf-8")
                for tok in self._FORBIDDEN:
                    assert tok not in txt


# ---------------------------------------------------------------------------
# H3. Reconciliation reads real positions from smoke JSON
# ---------------------------------------------------------------------------

class TestH3ReconciliationReadsRealPositions:
    """H3: --from-latest-readonly-smoke loads real positions when present."""

    def _write_real_smoke(self, tmp: Path) -> Path:
        d = tmp / "readonly_smoke"
        d.mkdir(parents=True, exist_ok=True)
        positions = [
            {
                "symbol": p.symbol, "side": p.side,
                "quantity": p.quantity, "entry_price": p.entry_price,
                "stop_price": p.stop_price,
                "notional_usd": p.quantity * p.entry_price,
                "source": "real_readonly",
            }
            for p in _real_demo_positions()
        ]
        (d / "latest_smoke.json").write_text(json.dumps({
            "demo_runtime_verified": True,
            "proof_strength": PROOF_STRONG,
            "equity_usd": 11_404.01,
            "available_balance_usd": 0.0,
            "no_orders_sent": True,
            "position_details_source": "real_readonly",
            "positions_count": len(positions),
            "timestamp": _now_iso(),
            "positions": positions,
            "instrument_rules": {
                p["symbol"]: {
                    "qty_step": 0.001, "min_qty": 0.001,
                    "tick_size": 0.0001, "min_notional": 5.0,
                }
                for p in positions
            },
        }), encoding="utf-8")
        return d

    def test_reconciliation_picks_up_real_symbols(self):
        from scripts.preview_demo_position_reconcile import run_preview
        with tempfile.TemporaryDirectory() as tmp:
            smoke_dir = self._write_real_smoke(Path(tmp))
            out_dir   = Path(tmp) / "reconciliation"
            rc = run_preview(
                mode="from_latest_smoke",
                smoke_dir=smoke_dir,
                reconcile_dir=out_dir,
                write_report=True,
            )
            assert rc in (0, 1)
            j = json.loads((out_dir / "latest_reconciliation.json").read_text(encoding="utf-8"))
            assert j.get("position_details_source") == "real_readonly"
            syms = sorted(p["symbol"] for p in j.get("positions", []))
            assert syms == sorted(_REAL_DEMO_SYMBOLS)

    def test_reconciliation_excludes_fixture_symbols(self):
        from scripts.preview_demo_position_reconcile import run_preview
        with tempfile.TemporaryDirectory() as tmp:
            smoke_dir = self._write_real_smoke(Path(tmp))
            out_dir   = Path(tmp) / "reconciliation"
            run_preview(
                mode="from_latest_smoke",
                smoke_dir=smoke_dir,
                reconcile_dir=out_dir,
                write_report=True,
            )
            j = json.loads((out_dir / "latest_reconciliation.json").read_text(encoding="utf-8"))
            syms = {p["symbol"] for p in j.get("positions", [])}
            assert "ETHUSDT" not in syms
            assert "BNBUSDT" not in syms


# ---------------------------------------------------------------------------
# H4. Real-readonly smoke missing positions => reconciliation fails closed
# ---------------------------------------------------------------------------

class TestH4ReconciliationFailClosedWhenRealSmokeLacksPositions:
    """H4: when smoke source=real_readonly but positions absent, fail closed."""

    def _write_smoke_missing_positions(self, tmp: Path) -> Path:
        d = tmp / "readonly_smoke"
        d.mkdir(parents=True, exist_ok=True)
        (d / "latest_smoke.json").write_text(json.dumps({
            "demo_runtime_verified": True,
            "proof_strength": PROOF_STRONG,
            "equity_usd": 11_404.01,
            "available_balance_usd": 0.0,
            "no_orders_sent": True,
            "position_details_source": "real_readonly",
            "positions_count": 0,
            "timestamp": _now_iso(),
            # positions key intentionally absent
        }), encoding="utf-8")
        return d

    def test_fail_closed_returns_one(self, capsys):
        from scripts.preview_demo_position_reconcile import run_preview
        with tempfile.TemporaryDirectory() as tmp:
            smoke_dir = self._write_smoke_missing_positions(Path(tmp))
            rc = run_preview(
                mode="from_latest_smoke",
                smoke_dir=smoke_dir,
                reconcile_dir=Path(tmp) / "reconciliation",
                write_report=False,
            )
            assert rc == 1
            out = capsys.readouterr().out
            assert "missing_real_position_details" in out


# ---------------------------------------------------------------------------
# H5. No fixture fallback in real_readonly mode
# ---------------------------------------------------------------------------

class TestH5NoFixtureFallbackInRealReadonly:
    """H5: in real_readonly mode, fixture positions never appear in output."""

    def test_reconciliation_carries_provenance(self):
        positions = _real_demo_positions()
        result = reconcile(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=positions,
            instrument_rules=_permissive_rules(_REAL_DEMO_SYMBOLS),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="real_readonly",
        )
        assert result.position_details_source == "real_readonly"

    def test_reconciliation_dict_includes_real_symbols(self):
        positions = _real_demo_positions()
        result = reconcile(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=positions,
            instrument_rules=_permissive_rules(_REAL_DEMO_SYMBOLS),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="real_readonly",
        )
        d    = result.to_dict()
        syms = {p["symbol"] for p in d.get("positions", [])}
        assert syms == set(_REAL_DEMO_SYMBOLS)
        assert "ETHUSDT" not in syms
        assert "BNBUSDT" not in syms


# ---------------------------------------------------------------------------
# H6. Cleanup candidates come from real positions
# ---------------------------------------------------------------------------

class TestH6CleanupCandidatesFromRealPositions:
    """H6: cleanup candidate set is exactly the real positions."""

    def test_candidates_are_real_symbols(self):
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_real_demo_positions(),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="real_readonly",
        )
        cand_syms = {c.symbol for c in plan.suggested_close_candidates}
        assert cand_syms.issubset(set(_REAL_DEMO_SYMBOLS))


# ---------------------------------------------------------------------------
# H7. Fixture-symbol candidates never reach execute path
# ---------------------------------------------------------------------------

class TestH7FixtureCandidatesBlocked:
    """H7: cleanup plan sourced from fixture => execute_ready=False."""

    def test_fixture_source_blocks_execute_ready(self):
        now      = datetime.now(timezone.utc)
        today    = now.date()
        fresh_ts = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_legacy_fixture_positions(),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            confirm_token=_valid_token(today),
            today=today,
            snapshot_timestamp_utc=fresh_ts,
            max_snapshot_age_hours=24.0,
            _now=now,
            position_details_source="fixture",
        )
        assert plan.execute_ready is False
        assert plan.source_position_details_is_real is False


# ---------------------------------------------------------------------------
# H8. Sender dry-run rejects symbol not in real positions
# ---------------------------------------------------------------------------

class TestH8SenderRejectsSymbolNotInRealPositions:
    """H8: --symbol pointing at a non-existent position is blocked."""

    def _build_plan(self, source: str = "real_readonly") -> dict:
        now      = datetime.now(timezone.utc)
        today    = now.date()
        fresh_ts = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_real_demo_positions(),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            confirm_token=_valid_token(today),
            today=today,
            snapshot_timestamp_utc=fresh_ts,
            max_snapshot_age_hours=24.0,
            _now=now,
            position_details_source=source,
        )
        return plan.to_dict(timestamp_utc=fresh_ts)

    def test_eth_blocked_when_not_in_real_positions(self):
        plan = self._build_plan(source="real_readonly")
        sender = DemoCloseOnlySender(allow_real_network=False)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT",
            confirm_token=_valid_token(datetime.now(timezone.utc).date()),
            execute_close_only=False,
        )
        assert result.execute_allowed is False
        assert "symbol_not_in_candidates" in result.blocked_gates

    def test_bnb_blocked_when_not_in_real_positions(self):
        plan = self._build_plan(source="real_readonly")
        sender = DemoCloseOnlySender(allow_real_network=False)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="BNBUSDT",
            confirm_token=_valid_token(datetime.now(timezone.utc).date()),
            execute_close_only=False,
        )
        assert result.execute_allowed is False
        assert "symbol_not_in_candidates" in result.blocked_gates


# ---------------------------------------------------------------------------
# H9. Sender execute_allowed=True only with real_readonly source
# ---------------------------------------------------------------------------

class TestH9SenderExecuteAllowedOnlyForRealReadonly:
    """H9: execute_allowed=True requires position_details_source=real_readonly."""

    def _plan(self, source: str) -> dict:
        now      = datetime.now(timezone.utc)
        today    = now.date()
        fresh_ts = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_real_demo_positions(),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            confirm_token=_valid_token(today),
            today=today,
            snapshot_timestamp_utc=fresh_ts,
            max_snapshot_age_hours=24.0,
            _now=now,
            position_details_source=source,
        )
        return plan.to_dict(timestamp_utc=fresh_ts)

    def test_fixture_source_blocks_execute_allowed(self):
        plan   = self._plan(source="fixture")
        sender = DemoCloseOnlySender(allow_real_network=False)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="AIXBTUSDT",
            confirm_token=_valid_token(datetime.now(timezone.utc).date()),
            execute_close_only=False,
        )
        assert result.execute_allowed is False
        assert "position_details_source_not_real_readonly" in result.blocked_gates

    def test_real_readonly_source_allows_dry_run_execute_allowed(self):
        plan   = self._plan(source="real_readonly")
        sender = DemoCloseOnlySender(allow_real_network=False)
        # Pick a real symbol that ranks high enough to be a candidate.
        candidates = plan.get("suggested_close_candidates", [])
        assert candidates, "expected at least one real candidate"
        sym = candidates[0]["symbol"]
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol=sym,
            confirm_token=_valid_token(datetime.now(timezone.utc).date()),
            execute_close_only=False,
        )
        assert result.execute_allowed is True
        assert result.order_endpoint_called is False
        assert result.order_sent is False


# ---------------------------------------------------------------------------
# H10. Reports include position_details_source
# ---------------------------------------------------------------------------

class TestH10ReportsIncludeProvenance:
    """H10: emitted reports record position_details_source."""

    def test_reconciliation_to_dict_includes_provenance(self):
        result = reconcile(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_real_demo_positions(),
            instrument_rules=_permissive_rules(_REAL_DEMO_SYMBOLS),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="real_readonly",
        )
        assert result.to_dict().get("position_details_source") == "real_readonly"

    def test_cleanup_to_dict_includes_provenance(self):
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_real_demo_positions(),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="real_readonly",
        )
        d = plan.to_dict()
        assert d.get("position_details_source") == "real_readonly"
        assert d.get("source_position_details_is_real") is True

    def test_close_order_result_includes_provenance(self):
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_real_demo_positions(),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="real_readonly",
        ).to_dict()
        sender = DemoCloseOnlySender(allow_real_network=False)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="AIXBTUSDT",
            confirm_token="anything",
            execute_close_only=False,
        )
        d = result.to_dict()
        assert "position_details_source" in d
        assert "source_position_details_is_real" in d


# ---------------------------------------------------------------------------
# H11. Order endpoint never called in any TASK-014H dry-run
# ---------------------------------------------------------------------------

class TestH11OrderEndpointNeverCalled:
    """H11: order_endpoint_called=False across all dry-run paths."""

    def test_real_readonly_path_no_endpoint_call(self):
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_real_demo_positions(),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="real_readonly",
        ).to_dict()
        sender = DemoCloseOnlySender(allow_real_network=False)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="AIXBTUSDT",
            confirm_token="anything", execute_close_only=False,
        )
        assert result.order_endpoint_called is False
        assert result.private_order_endpoint_called is False
        assert result.order_sent is False

    def test_fixture_path_no_endpoint_call(self):
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_legacy_fixture_positions(),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="fixture",
        ).to_dict()
        sender = DemoCloseOnlySender(allow_real_network=False)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT",
            confirm_token="anything", execute_close_only=False,
        )
        assert result.order_endpoint_called is False
        assert result.order_sent is False


# ---------------------------------------------------------------------------
# H12. No secrets in JSON / MD across pipeline
# ---------------------------------------------------------------------------

class TestH12NoSecretsInReports:
    """H12: reports never contain secret-shaped strings."""

    _FORBIDDEN_TOKENS = (
        "X-BAPI-SIGN",
        "BYBIT_DEMO_API_SECRET",
    )

    def test_reconciliation_dict_has_no_secret_tokens(self):
        result = reconcile(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_real_demo_positions(),
            instrument_rules=_permissive_rules(_REAL_DEMO_SYMBOLS),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="real_readonly",
        )
        txt = json.dumps(result.to_dict())
        for tok in self._FORBIDDEN_TOKENS:
            assert tok not in txt

    def test_cleanup_dict_has_no_secret_tokens(self):
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_real_demo_positions(),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="real_readonly",
        )
        txt = json.dumps(plan.to_dict(), default=str)
        for tok in self._FORBIDDEN_TOKENS:
            assert tok not in txt

    def test_close_order_result_has_no_secret_tokens(self):
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_real_demo_positions(),
            demo_runtime_verified=True,
            proof_strength=PROOF_STRONG,
            position_details_source="real_readonly",
        ).to_dict()
        sender = DemoCloseOnlySender(allow_real_network=False)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="AIXBTUSDT",
            confirm_token="anything", execute_close_only=False,
        )
        txt = json.dumps(result.to_dict())
        for tok in self._FORBIDDEN_TOKENS:
            assert tok not in txt


# ---------------------------------------------------------------------------
# H13. main.py / src/risk.py / BybitExecutor NOT modified
# ---------------------------------------------------------------------------

class TestH13UntouchedFiles:
    """H13: TASK-014H scope did not touch the listed core files."""

    def test_main_not_imported_by_h_modules(self):
        for rel in (
            "src/demo_position_reconcile.py",
            "src/demo_close_only_cleanup.py",
            "src/demo_close_only_sender.py",
            "scripts/preview_demo_readonly_runtime.py",
            "scripts/preview_demo_position_reconcile.py",
            "scripts/preview_demo_close_only_cleanup.py",
            "scripts/execute_demo_close_only_cleanup.py",
        ):
            txt = (ROOT / rel).read_text(encoding="utf-8")
            assert "from main" not in txt
            assert "import main" not in txt

    def test_risk_not_imported_by_h_modules(self):
        for rel in (
            "src/demo_position_reconcile.py",
            "src/demo_close_only_cleanup.py",
            "src/demo_close_only_sender.py",
            "scripts/preview_demo_readonly_runtime.py",
            "scripts/preview_demo_position_reconcile.py",
            "scripts/preview_demo_close_only_cleanup.py",
            "scripts/execute_demo_close_only_cleanup.py",
        ):
            txt = (ROOT / rel).read_text(encoding="utf-8")
            assert "from src.risk" not in txt
            assert "import src.risk" not in txt

    def test_bybit_executor_not_imported_by_h_modules(self):
        for rel in (
            "src/demo_position_reconcile.py",
            "src/demo_close_only_cleanup.py",
            "src/demo_close_only_sender.py",
            "scripts/preview_demo_readonly_runtime.py",
            "scripts/preview_demo_position_reconcile.py",
            "scripts/preview_demo_close_only_cleanup.py",
            "scripts/execute_demo_close_only_cleanup.py",
        ):
            txt = (ROOT / rel).read_text(encoding="utf-8")
            assert "BybitExecutor" not in txt
            assert "from src.exchange" not in txt
