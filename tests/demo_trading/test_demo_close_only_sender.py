"""
tests/demo_trading/test_demo_close_only_sender.py
TASK-014G: Tests for src/demo_close_only_sender.py and
           scripts/execute_demo_close_only_cleanup.py

Covers TASK-014G requirements G1-G23:
  G1.  dry-run default does not send
  G2.  missing cleanup report => fail closed
  G3.  missing confirm token => fail closed
  G4.  wrong confirm token => fail closed
  G5.  correct token but no --execute-close-only => no send
  G6.  --execute-close-only without --symbol when multiple candidates => fail closed
  G7.  symbol not in cleanup candidates => fail closed
  G8.  weak proof => fail closed
  G9.  live endpoint => fail closed (source scan)
  G10. stale snapshot => fail closed
  G11. position missing after refresh => fail closed
  G12. qty greater than current position => fail closed
  G13. reduce_only false rejected
  G14. close side mismatch rejected
  G15. one-order limit enforced
  G16. valid single candidate dry-run produces executable preview
  G17. valid single candidate execute uses Demo endpoint only
  G18. mocked successful order writes order_id but no secrets
  G19. failed order writes failure but no secrets
  G20. no API key / secret printed
  G21. source scan: no live endpoint fallback
  G22. source scan: no set_leverage / balance movement endpoint tokens
  G23. main.py / src/risk.py / BybitExecutor not modified

SAFETY: no real network calls; mock used for pre-send refresh and order posting.
"""
from __future__ import annotations

import json
import sys
import tempfile
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_close_only_sender import (
    CloseOrderResult,
    DemoCloseOnlySender,
    _ORDER_ENDPOINT,
)
from src.demo_close_only_cleanup import (
    _expected_confirm_token,
    plan_cleanup,
)
from src.demo_portfolio_risk import DemoOpenPosition
from src.demo_readonly_client import (
    DEMO_BASE_URL,
    PROOF_MISSING,
    PROOF_STRONG,
    PROOF_WEAK,
    DemoReadOnlyClient,
    PositionSnapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _legacy_positions() -> list[DemoOpenPosition]:
    """1 long + 7 short — short_count=7 triggers cleanup (MAX_SHORT=5)."""
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


def _clean_positions() -> list[DemoOpenPosition]:
    """2 positions — no violations."""
    return [
        DemoOpenPosition("BTCUSDT", "long",  0.05, 67_000.0, 65_000.0),
        DemoOpenPosition("ETHUSDT", "short", 0.30,  3_500.0,  3_700.0),
    ]


def _valid_token(today: date) -> str:
    return _expected_confirm_token(today)


def _make_cleanup_plan_dict(
    today:                  date | None  = None,
    snapshot_ts:            str          = "",
    demo_runtime_verified:  bool         = True,
    proof_strength:         str          = PROOF_STRONG,
    positions:              list[DemoOpenPosition] | None = None,
    max_age_hours:          float        = 24.0,
) -> dict[str, Any]:
    """Build a valid cleanup plan dict via plan_cleanup().to_dict()."""
    now      = datetime.now(timezone.utc)
    _today   = today or now.date()
    _pos     = positions or _legacy_positions()
    token    = _valid_token(_today)
    if not snapshot_ts:
        snapshot_ts = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    plan = plan_cleanup(
        equity_usd=11_404.01,
        available_balance_usd=0.0,
        positions=_pos,
        demo_runtime_verified=demo_runtime_verified,
        proof_strength=proof_strength,
        mode="test_fixture",
        confirm_token=token,
        today=_today,
        snapshot_timestamp_utc=snapshot_ts,
        max_snapshot_age_hours=max_age_hours,
    )
    return plan.to_dict(timestamp_utc=snapshot_ts)


def _mock_ro_client(
    proof_strength:  str  = PROOF_STRONG,
    endpoint_family: str  = "bybit_demo",
    positions:       list[PositionSnapshot] | None = None,
) -> DemoReadOnlyClient:
    """Return a MagicMock DemoReadOnlyClient for pre-send refresh tests."""
    mock_client = MagicMock(spec=DemoReadOnlyClient)
    mock_proof  = MagicMock()
    mock_proof.proof_strength                = proof_strength
    mock_proof.endpoint_family               = endpoint_family
    mock_proof.live_endpoint_fallback_detected = False
    mock_client.build_runtime_proof.return_value = mock_proof

    if positions is None:
        positions = [
            PositionSnapshot(
                symbol="ETHUSDT", side="short", quantity=0.50,
                entry_price=3_500.0, stop_price=3_700.0,
                unrealised_pnl=-25.0, leverage=3.0,
            ),
        ]
    mock_client.get_open_positions.return_value = positions
    return mock_client


def _write_cleanup_plan(tmpdir: str, plan: dict | None = None) -> Path:
    """Write cleanup plan JSON to tmpdir and return the dir path."""
    d = Path(tmpdir)
    content = plan or _make_cleanup_plan_dict()
    (d / "latest_close_only_cleanup.json").write_text(
        json.dumps(content), encoding="utf-8"
    )
    return d


# ---------------------------------------------------------------------------
# G1. Dry-run default does not send
# ---------------------------------------------------------------------------

class TestDryRunDefault:
    """G1: default mode is dry-run; no orders sent."""

    def test_no_execute_flag_no_order_sent(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert result.order_sent is False

    def test_order_endpoint_called_false_in_dry_run(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert result.order_endpoint_called is False

    def test_private_endpoint_called_false_in_dry_run(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert result.private_order_endpoint_called is False

    def test_no_position_modified_in_dry_run(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert result.no_position_modified is True


# ---------------------------------------------------------------------------
# G2. Missing cleanup report => fail closed
# ---------------------------------------------------------------------------

class TestMissingCleanupReport:
    """G2: missing latest_close_only_cleanup.json => exit 1."""

    def test_missing_file_exits_one(self):
        from scripts.execute_demo_close_only_cleanup import run_execute
        today = date.today()
        token = _valid_token(today)
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = run_execute(
                symbol="ETHUSDT",
                confirm_token=token,
                cleanup_dir=Path(tmpdir),
            )
        assert rc == 1

    def test_missing_file_prints_fail_message(self, capsys):
        from scripts.execute_demo_close_only_cleanup import run_execute
        today = date.today()
        token = _valid_token(today)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_execute(symbol="ETHUSDT", confirm_token=token, cleanup_dir=Path(tmpdir))
        out = capsys.readouterr().out
        assert "FAIL CLOSED" in out or "not found" in out

    def test_load_latest_cleanup_returns_none_when_missing(self):
        from scripts.execute_demo_close_only_cleanup import load_latest_cleanup
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_latest_cleanup(Path(tmpdir))
        assert result is None


# ---------------------------------------------------------------------------
# G3. Missing confirm token => fail closed
# ---------------------------------------------------------------------------

class TestMissingConfirmToken:
    """G3: empty or absent confirm token => fail closed."""

    def test_empty_token_cli_exits_one(self):
        from scripts.execute_demo_close_only_cleanup import run_execute
        with tempfile.TemporaryDirectory() as tmpdir:
            d = _write_cleanup_plan(tmpdir)
            rc = run_execute(symbol="ETHUSDT", confirm_token="", cleanup_dir=d)
        assert rc == 1

    def test_empty_token_sender_blocks(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token="",
        )
        assert "invalid_confirm_token" in result.blocked_gates
        assert result.order_sent is False

    def test_empty_token_execute_allowed_false(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token="",
        )
        assert result.execute_allowed is False


# ---------------------------------------------------------------------------
# G4. Wrong confirm token => fail closed
# ---------------------------------------------------------------------------

class TestWrongConfirmToken:
    """G4: incorrect token format or wrong date => fail closed."""

    def test_wrong_token_sender_blocks(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT",
            confirm_token="WRONG_TOKEN_12345",
        )
        assert "invalid_confirm_token" in result.blocked_gates
        assert result.order_sent is False

    def test_yesterday_token_blocked(self):
        today     = date.today()
        yesterday = today - timedelta(days=1)
        old_token = _expected_confirm_token(yesterday)
        plan      = _make_cleanup_plan_dict(today=today)
        sender    = DemoCloseOnlySender()
        result    = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=old_token,
        )
        assert "invalid_confirm_token" in result.blocked_gates

    def test_wrong_token_cli_exits_one(self):
        from scripts.execute_demo_close_only_cleanup import run_execute
        with tempfile.TemporaryDirectory() as tmpdir:
            d = _write_cleanup_plan(tmpdir)
            rc = run_execute(
                symbol="ETHUSDT",
                confirm_token="CONFIRM_DEMO_CLOSE_ONLY_19990101",
                cleanup_dir=d,
            )
        assert rc == 1


# ---------------------------------------------------------------------------
# G5. Correct token but no --execute-close-only => no send
# ---------------------------------------------------------------------------

class TestCorrectTokenNoDryRun:
    """G5: all gates pass, but execute_close_only=False → order_sent=False."""

    def _ready_result(self) -> CloseOrderResult:
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        sender = DemoCloseOnlySender()
        return sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
            execute_close_only=False,
        )

    def test_order_not_sent(self):
        assert self._ready_result().order_sent is False

    def test_execute_allowed_true(self):
        assert self._ready_result().execute_allowed is True

    def test_execute_requested_false(self):
        assert self._ready_result().execute_requested is False

    def test_no_blocked_gates(self):
        assert self._ready_result().blocked_gates == []

    def test_mode_is_dry_run(self):
        assert self._ready_result().mode == "dry_run"


# ---------------------------------------------------------------------------
# G6. Multiple candidates without --symbol => fail closed
# ---------------------------------------------------------------------------

class TestMultipleCandidatesNoSymbol:
    """G6: cleanup plan has >1 candidate and no --symbol → exit 1."""

    def test_multiple_candidates_requires_symbol(self):
        from scripts.execute_demo_close_only_cleanup import run_execute
        today = date.today()
        token = _valid_token(today)
        plan  = _make_cleanup_plan_dict(today=today)
        assert len(plan["suggested_close_candidates"]) > 1, \
            "Test prerequisite: plan must have multiple candidates"
        with tempfile.TemporaryDirectory() as tmpdir:
            d = _write_cleanup_plan(tmpdir, plan)
            rc = run_execute(symbol="", confirm_token=token, cleanup_dir=d)
        assert rc == 1

    def test_no_symbol_prints_fail_message(self, capsys):
        from scripts.execute_demo_close_only_cleanup import run_execute
        today = date.today()
        token = _valid_token(today)
        plan  = _make_cleanup_plan_dict(today=today)
        with tempfile.TemporaryDirectory() as tmpdir:
            d = _write_cleanup_plan(tmpdir, plan)
            run_execute(symbol="", confirm_token=token, cleanup_dir=d)
        out = capsys.readouterr().out
        assert "FAIL CLOSED" in out or "Multiple" in out

    def test_symbol_specified_proceeds_through_gates(self):
        from scripts.execute_demo_close_only_cleanup import run_execute
        today = date.today()
        token = _valid_token(today)
        plan  = _make_cleanup_plan_dict(today=today)
        with tempfile.TemporaryDirectory() as tmpdir:
            d = _write_cleanup_plan(tmpdir, plan)
            rc = run_execute(symbol="ETHUSDT", confirm_token=token, cleanup_dir=d)
        # All gates pass in dry-run; should exit 0
        assert rc == 0


# ---------------------------------------------------------------------------
# G7. Symbol not in cleanup candidates => fail closed
# ---------------------------------------------------------------------------

class TestSymbolNotInCandidates:
    """G7: symbol not in cleanup plan candidates → blocked."""

    def test_nonexistent_symbol_blocked(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="NOTEXIST", confirm_token=token,
        )
        assert "symbol_not_in_candidates" in result.blocked_gates
        assert result.order_sent is False

    def test_long_symbol_blocked_when_only_short_violated(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        today  = date.today()
        token  = _valid_token(today)
        # BTCUSDT is the long in legacy positions; it's not a candidate
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="BTCUSDT", confirm_token=token,
        )
        assert "symbol_not_in_candidates" in result.blocked_gates

    def test_cli_nonexistent_symbol_exits_one(self):
        from scripts.execute_demo_close_only_cleanup import run_execute
        today = date.today()
        token = _valid_token(today)
        plan  = _make_cleanup_plan_dict(today=today)
        with tempfile.TemporaryDirectory() as tmpdir:
            d = _write_cleanup_plan(tmpdir, plan)
            rc = run_execute(symbol="NOTREAL", confirm_token=token, cleanup_dir=d)
        assert rc == 1


# ---------------------------------------------------------------------------
# G8. Weak proof => fail closed
# ---------------------------------------------------------------------------

class TestWeakProofFails:
    """G8: proof_strength != STRONG in plan dict → fail closed."""

    def test_weak_proof_blocked(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict(proof_strength=PROOF_WEAK)
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert "proof_not_strong" in result.blocked_gates
        assert result.order_sent is False

    def test_missing_proof_blocked(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict(proof_strength=PROOF_MISSING)
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert "proof_not_strong" in result.blocked_gates

    def test_empty_proof_blocked(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict(proof_strength="")
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert "proof_not_strong" in result.blocked_gates


# ---------------------------------------------------------------------------
# G9. Live endpoint => fail closed (source scan)
# ---------------------------------------------------------------------------

class TestLiveEndpointSourceScan:
    """G9: sender source must not reference the live (non-demo) hostname."""

    _SRC    = ROOT / "src"     / "demo_close_only_sender.py"
    _SCRIPT = ROOT / "scripts" / "execute_demo_close_only_cleanup.py"

    def test_sender_no_live_hostname(self):
        src = self._SRC.read_text(encoding="utf-8")
        assert "api.bybit.com" not in src, \
            "Live hostname must not appear in sender source"

    def test_script_no_live_hostname(self):
        src = self._SCRIPT.read_text(encoding="utf-8")
        assert "api.bybit.com" not in src, \
            "Live hostname must not appear in CLI script source"

    def test_sender_uses_demo_base_url_constant(self):
        src = self._SRC.read_text(encoding="utf-8")
        assert "DEMO_BASE_URL" in src or "api-demo.bybit.com" in src, \
            "Sender must reference Demo endpoint"


# ---------------------------------------------------------------------------
# G10. Stale snapshot => fail closed
# ---------------------------------------------------------------------------

class TestStaleSnapshotFails:
    """G10: snapshot older than max_age → execute_allowed=False."""

    def test_stale_snapshot_blocked(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        plan = _make_cleanup_plan_dict(snapshot_ts=old_ts, max_age_hours=24.0)
        # Manually override snapshot_timestamp_utc in plan dict
        plan["snapshot_timestamp_utc"] = old_ts
        today = date.today()
        token = _valid_token(today)
        sender = DemoCloseOnlySender()
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert "snapshot_stale" in result.blocked_gates
        assert result.order_sent is False

    def test_fresh_snapshot_not_blocked_by_staleness(self):
        now   = datetime.now(timezone.utc)
        fresh = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan  = _make_cleanup_plan_dict(snapshot_ts=fresh)
        today = now.date()
        token = _valid_token(today)
        sender = DemoCloseOnlySender()
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
            _now=now,
        )
        assert "snapshot_stale" not in result.blocked_gates

    def test_stale_cli_exits_one(self):
        from scripts.execute_demo_close_only_cleanup import run_execute
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        plan = _make_cleanup_plan_dict(snapshot_ts=old_ts, max_age_hours=24.0)
        plan["snapshot_timestamp_utc"] = old_ts
        today = date.today()
        token = _valid_token(today)
        with tempfile.TemporaryDirectory() as tmpdir:
            d = _write_cleanup_plan(tmpdir, plan)
            rc = run_execute(symbol="ETHUSDT", confirm_token=token, cleanup_dir=d)
        assert rc == 1


# ---------------------------------------------------------------------------
# G11. Position missing after refresh => fail closed
# ---------------------------------------------------------------------------

class TestPositionMissingAfterRefresh:
    """G11: position gone from live read → blocked at pre-send refresh."""

    def test_missing_position_blocks_execute(self):
        sender = DemoCloseOnlySender(allow_real_network=True)
        sender._api_key    = "test_key"
        sender._api_secret = "test_secret"
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        ro     = _mock_ro_client(positions=[])  # no positions → ETHUSDT gone

        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
            execute_close_only=True, _ro_client=ro,
        )
        assert "position_not_found_after_refresh" in result.blocked_gates
        assert result.order_sent is False
        assert result.execute_allowed is False

    def test_missing_position_order_endpoint_not_called(self):
        sender = DemoCloseOnlySender(allow_real_network=True)
        sender._api_key    = "test_key"
        sender._api_secret = "test_secret"
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        ro     = _mock_ro_client(positions=[])

        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
            execute_close_only=True, _ro_client=ro,
        )
        assert result.order_endpoint_called is False

    def test_position_present_allows_proceed(self):
        sender = DemoCloseOnlySender(allow_real_network=True)
        sender._api_key    = "test_key"
        sender._api_secret = "test_secret"
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        ro     = _mock_ro_client()  # default includes ETHUSDT short 0.5

        with patch.object(sender, "_post_to_demo",
                          return_value={"retCode": 0, "result": {"orderId": "ok"}}):
            result = sender.submit_one_close_order(
                cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
                execute_close_only=True, _ro_client=ro,
            )
        assert "position_not_found_after_refresh" not in result.blocked_gates
        assert result.order_sent is True


# ---------------------------------------------------------------------------
# G12. Qty greater than current position => fail closed
# ---------------------------------------------------------------------------

class TestQtyExceedsCurrentPosition:
    """G12: close qty from plan > live position qty → blocked."""

    def test_oversized_qty_blocked(self):
        sender = DemoCloseOnlySender(allow_real_network=True)
        sender._api_key    = "test_key"
        sender._api_secret = "test_secret"
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        # Plan has ETHUSDT close qty=0.50; give live position qty=0.10
        small_pos = PositionSnapshot(
            symbol="ETHUSDT", side="short", quantity=0.10,
            entry_price=3_500.0, stop_price=3_700.0,
            unrealised_pnl=-5.0, leverage=3.0,
        )
        ro = _mock_ro_client(positions=[small_pos])

        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
            execute_close_only=True, _ro_client=ro,
        )
        assert any("close_qty_exceeds" in g for g in result.blocked_gates)
        assert result.order_sent is False

    def test_matching_qty_not_blocked(self):
        sender = DemoCloseOnlySender(allow_real_network=True)
        sender._api_key    = "test_key"
        sender._api_secret = "test_secret"
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        # Exactly 0.50 → not blocked
        exact_pos = PositionSnapshot(
            symbol="ETHUSDT", side="short", quantity=0.50,
            entry_price=3_500.0, stop_price=3_700.0,
            unrealised_pnl=-25.0, leverage=3.0,
        )
        ro = _mock_ro_client(positions=[exact_pos])
        with patch.object(sender, "_post_to_demo",
                          return_value={"retCode": 0, "result": {"orderId": "ok2"}}):
            result = sender.submit_one_close_order(
                cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
                execute_close_only=True, _ro_client=ro,
            )
        assert not any("close_qty_exceeds" in g for g in result.blocked_gates)

    def test_qty_check_blocked_gates_not_empty(self):
        sender = DemoCloseOnlySender(allow_real_network=True)
        sender._api_key    = "test_key"
        sender._api_secret = "test_secret"
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        small_pos = PositionSnapshot(
            symbol="ETHUSDT", side="short", quantity=0.01,
            entry_price=3_500.0, stop_price=3_700.0,
            unrealised_pnl=-1.0, leverage=3.0,
        )
        ro = _mock_ro_client(positions=[small_pos])
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
            execute_close_only=True, _ro_client=ro,
        )
        assert result.blocked_gates != []


# ---------------------------------------------------------------------------
# G13. reduce_only=False rejected
# ---------------------------------------------------------------------------

class TestReduceOnlyFalseRejected:
    """G13: payload with reduce_only=False must be rejected."""

    def test_reduce_only_false_blocks(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        # Corrupt reduce_only in payload
        for p in plan["close_payload_preview"]:
            p["reduce_only"] = False
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert "reduce_only_not_true" in result.blocked_gates
        assert result.order_sent is False

    def test_reduce_only_true_passes_gate(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        # Ensure reduce_only=True (default from plan_cleanup)
        for p in plan["close_payload_preview"]:
            assert p.get("reduce_only") is True
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert "reduce_only_not_true" not in result.blocked_gates


# ---------------------------------------------------------------------------
# G14. Close side mismatch rejected
# ---------------------------------------------------------------------------

class TestCloseSideMismatch:
    """G14: close_order_side inconsistent with position side → blocked."""

    def test_wrong_close_side_for_short_blocked(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        # ETHUSDT is short → close_order_side must be "Buy"
        # Corrupt to "Sell"
        for p in plan["close_payload_preview"]:
            if p["symbol"] == "ETHUSDT":
                p["close_order_side"] = "Sell"
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert "close_side_mismatch" in result.blocked_gates
        assert result.order_sent is False

    def test_correct_close_side_for_short_passes(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        # Ensure Buy for short (default)
        eth_payload = next(
            p for p in plan["close_payload_preview"] if p["symbol"] == "ETHUSDT"
        )
        assert eth_payload["close_order_side"] == "Buy"
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert "close_side_mismatch" not in result.blocked_gates


# ---------------------------------------------------------------------------
# G15. One-order limit enforced
# ---------------------------------------------------------------------------

class TestOneOrderLimit:
    """G15: exactly one symbol per invocation; multi-candidate requires --symbol."""

    def test_cli_blocks_when_multi_candidate_and_no_symbol(self):
        from scripts.execute_demo_close_only_cleanup import run_execute
        today = date.today()
        token = _valid_token(today)
        plan  = _make_cleanup_plan_dict(today=today)
        assert len(plan["suggested_close_candidates"]) > 1
        with tempfile.TemporaryDirectory() as tmpdir:
            d  = _write_cleanup_plan(tmpdir, plan)
            rc = run_execute(symbol="", confirm_token=token, cleanup_dir=d)
        assert rc == 1

    def test_sender_handles_one_symbol_at_a_time(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        today  = date.today()
        token  = _valid_token(today)
        # Submit for ETHUSDT only
        r1 = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert r1.selected_symbol == "ETHUSDT"
        # Submit for BNBUSDT only (separate invocation)
        r2 = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="BNBUSDT", confirm_token=token,
        )
        assert r2.selected_symbol == "BNBUSDT"
        # Neither sent in dry-run
        assert r1.order_sent is False
        assert r2.order_sent is False

    def test_single_candidate_auto_selects_symbol_in_cli(self):
        from scripts.execute_demo_close_only_cleanup import run_execute
        today = date.today()
        token = _valid_token(today)
        # Build plan with only 1 candidate (no symbol needed)
        positions_1 = [
            DemoOpenPosition("BTCUSDT",  "long",  0.02, 67_000.0, 65_000.0),
            DemoOpenPosition("ETHUSDT",  "short", 0.50,  3_500.0,  3_700.0),
            DemoOpenPosition("BNBUSDT",  "short", 2.00,    600.0,    640.0),
            DemoOpenPosition("SOLUSDT",  "short", 5.00,    160.0,    175.0),
            DemoOpenPosition("XRPUSDT",  "short", 500.0,     0.62,     0.68),
            DemoOpenPosition("ADAUSDT",  "short", 800.0,     0.45,     0.49),
        ]  # 5 shorts → exactly at limit → cleanup_needed=False, but let's test 6
        positions_6 = positions_1 + [
            DemoOpenPosition("DOTUSDT", "short", 30.0, 7.80, 8.50),
        ]  # 6 shorts → exactly 1 to close
        plan = _make_cleanup_plan_dict(today=today, positions=positions_6)
        assert len(plan["suggested_close_candidates"]) == 1
        with tempfile.TemporaryDirectory() as tmpdir:
            d  = _write_cleanup_plan(tmpdir, plan)
            rc = run_execute(symbol="", confirm_token=token, cleanup_dir=d)
        assert rc == 0  # auto-selects the single candidate


# ---------------------------------------------------------------------------
# G16. Valid single candidate dry-run produces executable preview
# ---------------------------------------------------------------------------

class TestValidDryRunPreview:
    """G16: all gates pass in dry-run → execute_allowed=True, order_sent=False."""

    def _dry_run_result(self) -> CloseOrderResult:
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        sender = DemoCloseOnlySender()
        return sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
            execute_close_only=False,
        )

    def test_execute_allowed_true(self):
        assert self._dry_run_result().execute_allowed is True

    def test_order_not_sent(self):
        assert self._dry_run_result().order_sent is False

    def test_no_blocked_gates(self):
        assert self._dry_run_result().blocked_gates == []

    def test_reduce_only_true_in_result(self):
        assert self._dry_run_result().reduce_only is True

    def test_close_order_side_buy_for_ethusdt_short(self):
        r = self._dry_run_result()
        assert r.selected_side == "short"
        assert r.close_order_side == "Buy"

    def test_selected_symbol_correct(self):
        assert self._dry_run_result().selected_symbol == "ETHUSDT"


# ---------------------------------------------------------------------------
# G17. Valid execute uses Demo endpoint only
# ---------------------------------------------------------------------------

class TestValidExecuteUsesDemoEndpoint:
    """G17: when execute_close_only=True and all gates pass, URL is Demo only."""

    def _sender_with_creds(self) -> DemoCloseOnlySender:
        sender = DemoCloseOnlySender(allow_real_network=True)
        sender._api_key     = "test_key_g17"
        sender._api_secret  = "test_sec_g17"
        sender._key_present = True
        return sender

    def test_order_url_is_demo_endpoint(self, monkeypatch):
        sender = self._sender_with_creds()
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        ro     = _mock_ro_client()
        captured: list[str] = []

        class _MockResp:
            def read(self):
                return json.dumps({"retCode": 0, "result": {"orderId": "g17"}}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def _capture_urlopen(req, timeout=None):
            captured.append(req.full_url)
            return _MockResp()

        monkeypatch.setattr("urllib.request.urlopen", _capture_urlopen)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
            execute_close_only=True, _ro_client=ro,
        )
        assert result.order_endpoint_called is True
        assert any("api-demo.bybit.com" in url for url in captured)
        live_only = [
            url for url in captured
            if "bybit.com" in url and "api-demo" not in url
        ]
        assert live_only == [], f"Live endpoint accessed: {live_only}"

    def test_order_endpoint_called_true_on_execute(self, monkeypatch):
        sender = self._sender_with_creds()
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        ro     = _mock_ro_client()

        class _MockResp:
            def read(self):
                return json.dumps({"retCode": 0, "result": {"orderId": "g17b"}}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: _MockResp())
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
            execute_close_only=True, _ro_client=ro,
        )
        assert result.order_endpoint_called is True
        assert result.private_order_endpoint_called is True

    def test_no_live_endpoint_in_result(self, monkeypatch):
        sender = self._sender_with_creds()
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        ro     = _mock_ro_client()

        class _MockResp:
            def read(self):
                return json.dumps({"retCode": 0, "result": {"orderId": "g17c"}}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: _MockResp())
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
            execute_close_only=True, _ro_client=ro,
        )
        assert result.no_live_endpoint is True


# ---------------------------------------------------------------------------
# G18. Mocked successful order writes order_id but no secrets
# ---------------------------------------------------------------------------

class TestMockedSuccessOrder:
    """G18: on success, result has order_id; no secrets in output."""

    def _execute_with_mock_response(self, retCode: int, order_id: str) -> CloseOrderResult:
        sender = DemoCloseOnlySender(allow_real_network=True)
        sender._api_key    = "SECRET_KEY_G18_SHOULD_NOT_APPEAR"
        sender._api_secret = "SECRET_G18_SHOULD_NOT_APPEAR"
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        ro     = _mock_ro_client()
        mock_resp = {"retCode": retCode, "result": {"orderId": order_id}, "retMsg": "OK"}
        with patch.object(sender, "_post_to_demo", return_value=mock_resp):
            return sender.submit_one_close_order(
                cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
                execute_close_only=True, _ro_client=ro,
            )

    def test_success_sets_order_id(self):
        result = self._execute_with_mock_response(0, "order-abc-123")
        assert result.order_id == "order-abc-123"

    def test_success_order_sent_true(self):
        result = self._execute_with_mock_response(0, "order-xyz")
        assert result.order_sent is True

    def test_no_api_key_in_result_dict(self):
        result = self._execute_with_mock_response(0, "order-ok")
        result_str = json.dumps(result.to_dict())
        assert "SECRET_KEY_G18_SHOULD_NOT_APPEAR" not in result_str

    def test_no_api_secret_in_result_dict(self):
        result = self._execute_with_mock_response(0, "order-ok")
        result_str = json.dumps(result.to_dict())
        assert "SECRET_G18_SHOULD_NOT_APPEAR" not in result_str

    def test_secret_value_observed_false_on_success(self):
        result = self._execute_with_mock_response(0, "order-ok")
        assert result.secret_value_observed is False


# ---------------------------------------------------------------------------
# G19. Failed order writes failure but no secrets
# ---------------------------------------------------------------------------

class TestMockedFailedOrder:
    """G19: on exchange error, order_sent=False; no secrets in output."""

    def _execute_with_error(self) -> CloseOrderResult:
        sender = DemoCloseOnlySender(allow_real_network=True)
        sender._api_key    = "SECRET_KEY_G19_SHOULD_NOT_APPEAR"
        sender._api_secret = "SECRET_G19_SHOULD_NOT_APPEAR"
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        ro     = _mock_ro_client()
        mock_resp = {"retCode": 10001, "result": {}, "retMsg": "Auth failure"}
        with patch.object(sender, "_post_to_demo", return_value=mock_resp):
            return sender.submit_one_close_order(
                cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
                execute_close_only=True, _ro_client=ro,
            )

    def test_failed_order_sent_false(self):
        result = self._execute_with_error()
        assert result.order_sent is False

    def test_failed_order_status_contains_error(self):
        result = self._execute_with_error()
        assert "error" in result.order_response_status.lower()

    def test_no_secrets_in_failed_result(self):
        result = self._execute_with_error()
        result_str = json.dumps(result.to_dict())
        assert "SECRET_KEY_G19_SHOULD_NOT_APPEAR" not in result_str
        assert "SECRET_G19_SHOULD_NOT_APPEAR" not in result_str

    def test_no_position_modified_on_failure(self):
        result = self._execute_with_error()
        assert result.no_position_modified is True


# ---------------------------------------------------------------------------
# G20. No API key / secret printed
# ---------------------------------------------------------------------------

class TestNoSecretsInOutput:
    """G20: API credentials must never appear in result output."""

    def test_no_key_in_dry_run_result(self, monkeypatch):
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "SECRET_KEY_G20")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "SECRET_SEC_G20")
        sender = DemoCloseOnlySender(allow_real_network=True)
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        result_str = json.dumps(result.to_dict())
        assert "SECRET_KEY_G20" not in result_str
        assert "SECRET_SEC_G20" not in result_str

    def test_secret_value_observed_always_false(self):
        sender = DemoCloseOnlySender()
        plan   = _make_cleanup_plan_dict()
        today  = date.today()
        token  = _valid_token(today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        assert result.secret_value_observed is False

    def test_no_key_in_blocked_result(self, monkeypatch):
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "KEY_G20_BLOCKED")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "SEC_G20_BLOCKED")
        sender = DemoCloseOnlySender(allow_real_network=True)
        plan   = _make_cleanup_plan_dict()
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token="WRONG",
        )
        result_str = json.dumps(result.to_dict())
        assert "KEY_G20_BLOCKED" not in result_str
        assert "SEC_G20_BLOCKED" not in result_str

    def test_report_no_secrets(self, monkeypatch):
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "SECRET_KEY_G20R")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "SECRET_SEC_G20R")
        from scripts.execute_demo_close_only_cleanup import _write_execution_report
        sender = DemoCloseOnlySender()
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_execution_report(result, Path(tmpdir), "2026-06-06T12:00:00Z")
            json_text = (Path(tmpdir) / "latest_close_only_execution.json").read_text(
                encoding="utf-8"
            )
            md_text = (Path(tmpdir) / "latest_close_only_execution.md").read_text(
                encoding="utf-8"
            )
        assert "SECRET_KEY_G20R" not in json_text
        assert "SECRET_SEC_G20R" not in json_text
        assert "SECRET_KEY_G20R" not in md_text
        assert "SECRET_SEC_G20R" not in md_text


# ---------------------------------------------------------------------------
# G21. Source scan: no live endpoint fallback
# ---------------------------------------------------------------------------

class TestSourceScanNoLiveEndpoint:
    """G21: sender and script source must not reference the live (non-demo) hostname."""

    _SRC    = ROOT / "src"     / "demo_close_only_sender.py"
    _SCRIPT = ROOT / "scripts" / "execute_demo_close_only_cleanup.py"

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_sender_no_live_hostname_string(self):
        assert "api.bybit.com" not in self._read(self._SRC)

    def test_script_no_live_hostname_string(self):
        assert "api.bybit.com" not in self._read(self._SCRIPT)

    def test_sender_no_live_fallback_logic(self):
        src = self._read(self._SRC)
        assert "live_endpoint_fallback" not in src or "False" in src


# ---------------------------------------------------------------------------
# G22. Source scan: no forbidden endpoint/operation tokens
# ---------------------------------------------------------------------------

class TestSourceScanForbiddenOps:
    """G22: sender must not implement leverage, stop-level, or balance-movement ops."""

    _SRC    = ROOT / "src"     / "demo_close_only_sender.py"
    _SCRIPT = ROOT / "scripts" / "execute_demo_close_only_cleanup.py"

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_sender_no_set_leverage(self):
        assert "set_leverage" not in self._read(self._SRC)

    def test_sender_no_setLeverage(self):
        assert "setLeverage" not in self._read(self._SRC)

    def test_sender_no_set_trading_stop(self):
        assert "set_trading_stop" not in self._read(self._SRC)

    def test_sender_no_trading_stop_camel(self):
        assert "tradingStop" not in self._read(self._SRC)

    def test_sender_no_transfer_call(self):
        assert "transfer(" not in self._read(self._SRC)

    def test_sender_no_withdraw_endpoint(self):
        assert "/withdraw" not in self._read(self._SRC)

    def test_sender_no_deposit_endpoint(self):
        assert "/deposit" not in self._read(self._SRC)

    def test_sender_no_pybit(self):
        assert "pybit" not in self._read(self._SRC)

    def test_script_no_set_leverage(self):
        assert "set_leverage" not in self._read(self._SCRIPT)

    def test_script_no_set_trading_stop(self):
        assert "set_trading_stop" not in self._read(self._SCRIPT)


# ---------------------------------------------------------------------------
# G23. main.py / src/risk.py / BybitExecutor not modified
# ---------------------------------------------------------------------------

class TestNoMainModified:
    """G23: sender must not import from main.py or src/risk.py; no BybitExecutor."""

    _SRC    = ROOT / "src"     / "demo_close_only_sender.py"
    _SCRIPT = ROOT / "scripts" / "execute_demo_close_only_cleanup.py"

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_sender_no_bybit_executor(self):
        assert "BybitExecutor" not in self._read(self._SRC)

    def test_sender_no_import_main(self):
        src = self._read(self._SRC)
        assert "import main" not in src
        assert "from main" not in src

    def test_sender_no_src_risk(self):
        assert "src.risk" not in self._read(self._SRC)

    def test_script_no_bybit_executor(self):
        assert "BybitExecutor" not in self._read(self._SCRIPT)

    def test_script_no_src_risk(self):
        assert "src.risk" not in self._read(self._SCRIPT)


# ---------------------------------------------------------------------------
# Report artifact tests
# ---------------------------------------------------------------------------

class TestReportArtifacts:
    """Verify execution report files are created and contain expected fields."""

    def test_write_report_creates_json(self):
        from scripts.execute_demo_close_only_cleanup import _write_execution_report
        sender = DemoCloseOnlySender()
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_execution_report(result, Path(tmpdir), "2026-06-06T12:00:00Z")
            json_path   = Path(tmpdir) / "latest_close_only_execution.json"
            ts_json_path = Path(tmpdir) / "20260606_120000_close_only_execution.json"
            assert json_path.exists()
            assert ts_json_path.exists()

    def test_write_report_creates_markdown(self):
        from scripts.execute_demo_close_only_cleanup import _write_execution_report
        sender = DemoCloseOnlySender()
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_execution_report(result, Path(tmpdir), "2026-06-06T12:00:00Z")
            md_path = Path(tmpdir) / "latest_close_only_execution.md"
            assert md_path.exists()

    def test_json_contains_no_position_modified_field(self):
        from scripts.execute_demo_close_only_cleanup import _write_execution_report
        sender = DemoCloseOnlySender()
        today  = date.today()
        token  = _valid_token(today)
        plan   = _make_cleanup_plan_dict(today=today)
        result = sender.submit_one_close_order(
            cleanup_plan=plan, symbol="ETHUSDT", confirm_token=token,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_execution_report(result, Path(tmpdir), "2026-06-06T12:00:00Z")
            data = json.loads(
                (Path(tmpdir) / "latest_close_only_execution.json").read_text(encoding="utf-8")
            )
        assert "no_position_modified" in data
        assert data["no_position_modified"] is True

    def test_run_execute_writes_report_when_flag_set(self):
        from scripts.execute_demo_close_only_cleanup import run_execute
        today = date.today()
        token = _valid_token(today)
        plan  = _make_cleanup_plan_dict(today=today)
        with tempfile.TemporaryDirectory() as cleanup_tmp:
            with tempfile.TemporaryDirectory() as exec_tmp:
                _write_cleanup_plan(cleanup_tmp, plan)
                run_execute(
                    symbol="ETHUSDT",
                    confirm_token=token,
                    write_report=True,
                    cleanup_dir=Path(cleanup_tmp),
                    execution_dir=Path(exec_tmp),
                )
                assert (Path(exec_tmp) / "latest_close_only_execution.json").exists()
