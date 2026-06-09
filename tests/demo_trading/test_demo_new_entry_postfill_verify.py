"""
tests/demo_trading/test_demo_new_entry_postfill_verify.py
TASK-014M: Tests for src/demo_new_entry_postfill_verify.py and
           scripts/verify_demo_new_entry_postfill.py

Covers TASK-014M requirements M1-M17:
  M1.  detects ORDER_SENT (PASS when state is clean)
  M2.  detects symbol in positions; missing => fail closed
  M3.  detects missing stop_price (stop<=0) => fail closed
  M4.  detects qty mismatch (>1% relative)
  M5.  detects side mismatch
  M6.  detects entry-price stale mismatch (>5%)
  M7.  missing stop_price => fail_closed=True
  M8.  stale price mismatch => fail_closed=True
  M9.  no latest execution => fail_closed=True (CLI exit 1)
  M10. no latest readonly => fail_closed=True (CLI exit 1)
  M11. no secrets in report (no env values written)
  M12. no order endpoint called (structural)
  M13. no new order sent (structural)
  M14. emergency close preview for long: side=Sell + reduceOnly=True
  M15. emergency close preview is preview_only=True (never actually executed)
  M16. no import of main.py / src.risk / BybitExecutor / close-only sender / new-entry sender
  M17. no live endpoint fallback (no api.bybit.com / api.bytick.com hostnames in source)

Production-incident replay (SOLUSDT) integrated into M3/M6/M7/M8.

SAFETY: no real network calls; no real env reads; all I/O sandboxed.
"""
from __future__ import annotations

import ast
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_new_entry_postfill_verify import (
    ACTION_EMERGENCY_PREV,
    ACTION_MANUAL_UI,
    ACTION_NONE_REQUIRED,
    PostFillVerificationResult,
    QTY_MISMATCH_TOLERANCE_PCT,
    STALE_PRICE_DEVIATION_THRESHOLD_PCT,
    _derive_execution_status,
    _find_position,
    _find_review_entry_price,
    make_emergency_close_preview,
    verify_postfill,
)


_FIXED_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _execution(
    *,
    selected_symbol:   str   = "SOLUSDT",
    selected_side:     str   = "long",
    order_side:        str   = "Buy",
    selected_qty:      float = 4.0,
    order_sent:        bool  = True,
    execute_allowed:   bool  = True,
    execute_requested: bool  = True,
    order_id:          str   = "aae978ed-98f7-47cd-90ad-1f0c16b29213",
    timestamp_utc:     str   = "2026-06-09T11:00:00Z",
) -> dict[str, Any]:
    return {
        "timestamp":         timestamp_utc,
        "timestamp_utc":     timestamp_utc,
        "mode":              "execute_new_entry",
        "selected_symbol":   selected_symbol,
        "selected_side":     selected_side,
        "order_side":        order_side,
        "selected_qty":      selected_qty,
        "order_type":        "Market",
        "reduce_only":       False,
        "execute_requested": execute_requested,
        "execute_allowed":   execute_allowed,
        "order_sent":        order_sent,
        "order_response_status": "success" if order_sent else "",
        "order_id":          order_id if order_sent else "",
        "blocked_gates":     [],
    }


def _readonly_snapshot(
    *,
    positions: list[dict] | None = None,
    fail_closed: bool = False,
    demo_runtime_verified: bool = True,
    run_timestamp_utc: str = "2026-06-09T11:30:00Z",
) -> dict[str, Any]:
    if positions is None:
        positions = [
            {
                "symbol":      "SOLUSDT",
                "side":        "long",
                "quantity":    4.0,
                "entry_price": 66.47,
                "stop_price":  60.0,
            }
        ]
    return {
        "run_timestamp_utc":     run_timestamp_utc,
        "demo_runtime_verified": demo_runtime_verified,
        "fail_closed":           fail_closed,
        "positions":             positions,
    }


def _review(
    *,
    symbol: str = "SOLUSDT",
    entry_reference_price: float = 160.0,
    timestamp_utc: str = "2026-06-09T10:00:00Z",
) -> dict[str, Any]:
    return {
        "timestamp":          timestamp_utc,
        "accepted_candidates": [
            {
                "symbol":  symbol,
                "side":    "long",
                "payload": {
                    "symbol":                symbol,
                    "side":                  "Buy",
                    "qty":                   4.0,
                    "order_type":            "Market",
                    "reduce_only":           False,
                    "preview_only":          True,
                    "order_sent":            False,
                    "order_endpoint_called": False,
                    "entry_reference_price": entry_reference_price,
                    "estimated_stop_risk_usd": 40.0,
                },
            }
        ],
    }


# ---------------------------------------------------------------------------
# Helper-function unit tests
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_derive_status_order_sent(self):
        assert _derive_execution_status(_execution(order_sent=True)) == "ORDER_SENT"

    def test_derive_status_dry_run(self):
        ex = _execution(order_sent=False, execute_allowed=True,
                        execute_requested=False, order_id="")
        assert _derive_execution_status(ex) == "DRY_RUN_EXECUTE_ALLOWED"

    def test_derive_status_execute_failed(self):
        ex = _execution(order_sent=False, execute_allowed=True,
                        execute_requested=True, order_id="")
        assert _derive_execution_status(ex) == "EXECUTE_FAILED_AT_EXCHANGE"

    def test_derive_status_blocked(self):
        ex = _execution(order_sent=False, execute_allowed=False,
                        execute_requested=False, order_id="")
        assert _derive_execution_status(ex) == "BLOCKED"

    def test_derive_status_non_dict_returns_empty(self):
        assert _derive_execution_status(None) == ""
        assert _derive_execution_status("nope") == ""

    def test_find_position_matches(self):
        snap = _readonly_snapshot()
        pos = _find_position(snap, "SOLUSDT")
        assert pos is not None and pos["symbol"] == "SOLUSDT"

    def test_find_position_missing(self):
        snap = _readonly_snapshot()
        assert _find_position(snap, "BTCUSDT") is None

    def test_find_position_empty_symbol(self):
        assert _find_position(_readonly_snapshot(), "") is None

    def test_find_review_entry_price(self):
        rev = _review(entry_reference_price=160.0)
        assert _find_review_entry_price(rev, "SOLUSDT") == 160.0

    def test_find_review_entry_price_missing(self):
        rev = _review()
        assert _find_review_entry_price(rev, "BTCUSDT") == 0.0

    def test_find_review_entry_price_none(self):
        assert _find_review_entry_price(None, "SOLUSDT") == 0.0


# ---------------------------------------------------------------------------
# M1. Detects ORDER_SENT (PASS on a clean state)
# ---------------------------------------------------------------------------

class TestM1DetectsOrderSent:
    def _clean_result(self) -> PostFillVerificationResult:
        ex   = _execution()
        snap = _readonly_snapshot()
        rev  = _review(entry_reference_price=66.0)  # actual=66.47 -> dev ~0.7% (under 5%)
        return verify_postfill(ex, snap, rev, now=_FIXED_NOW)

    def test_status_recognised(self):
        assert self._clean_result().last_execution_status == "ORDER_SENT"

    def test_clean_state_passes(self):
        r = self._clean_result()
        assert r.fail_closed is False
        assert r.fail_closed_reasons == []
        assert r.recommended_action == ACTION_NONE_REQUIRED

    def test_not_order_sent_fails_closed(self):
        ex = _execution(order_sent=False, execute_allowed=True,
                        execute_requested=False, order_id="")
        r  = verify_postfill(ex, _readonly_snapshot(), _review(), now=_FIXED_NOW)
        assert r.fail_closed is True
        assert any("last_execution_status_not_order_sent" in s
                   for s in r.fail_closed_reasons)


# ---------------------------------------------------------------------------
# M2. Detects symbol in positions; missing -> fail closed
# ---------------------------------------------------------------------------

class TestM2PositionPresence:
    def test_position_found_true(self):
        r = verify_postfill(_execution(), _readonly_snapshot(),
                            _review(entry_reference_price=66.0), now=_FIXED_NOW)
        assert r.position_found is True

    def test_position_missing_fails(self):
        snap = _readonly_snapshot(positions=[])
        r    = verify_postfill(_execution(), snap, _review(), now=_FIXED_NOW)
        assert r.position_found is False
        assert r.fail_closed is True
        assert any(s.startswith("position_not_found_after_fill")
                   for s in r.fail_closed_reasons)
        assert r.recommended_action == ACTION_MANUAL_UI


# ---------------------------------------------------------------------------
# M3. Detects missing stop_price (SOLUSDT incident replay)
# ---------------------------------------------------------------------------

class TestM3MissingStopPrice:
    def _result(self) -> PostFillVerificationResult:
        snap = _readonly_snapshot(positions=[{
            "symbol": "SOLUSDT", "side": "long", "quantity": 4.0,
            "entry_price": 66.47, "stop_price": 0.0,   # <-- the production incident
        }])
        rev = _review(entry_reference_price=66.0)
        return verify_postfill(_execution(), snap, rev, now=_FIXED_NOW)

    def test_missing_stop_price_flag(self):
        assert self._result().missing_stop_price is True

    def test_reason_present(self):
        assert "missing_stop_price" in self._result().fail_closed_reasons

    def test_action_manual_ui_without_emergency_flag(self):
        assert self._result().recommended_action == ACTION_MANUAL_UI


# ---------------------------------------------------------------------------
# M4. Detects qty mismatch (relative >1%)
# ---------------------------------------------------------------------------

class TestM4QtyMismatch:
    def test_within_tolerance_no_mismatch(self):
        snap = _readonly_snapshot(positions=[{
            "symbol": "SOLUSDT", "side": "long", "quantity": 4.005,
            "entry_price": 66.47, "stop_price": 60.0,
        }])
        r = verify_postfill(_execution(selected_qty=4.0), snap,
                            _review(entry_reference_price=66.0), now=_FIXED_NOW)
        assert r.qty_mismatch is False

    def test_over_tolerance_flagged(self):
        snap = _readonly_snapshot(positions=[{
            "symbol": "SOLUSDT", "side": "long", "quantity": 5.0,  # 25% bigger
            "entry_price": 66.47, "stop_price": 60.0,
        }])
        r = verify_postfill(_execution(selected_qty=4.0), snap,
                            _review(entry_reference_price=66.0), now=_FIXED_NOW)
        assert r.qty_mismatch is True
        assert any(s.startswith("qty_mismatch:") for s in r.fail_closed_reasons)
        assert r.fail_closed is True


# ---------------------------------------------------------------------------
# M5. Detects side mismatch
# ---------------------------------------------------------------------------

class TestM5SideMismatch:
    def test_long_sent_short_observed(self):
        snap = _readonly_snapshot(positions=[{
            "symbol": "SOLUSDT", "side": "short", "quantity": 4.0,
            "entry_price": 66.47, "stop_price": 70.0,
        }])
        r = verify_postfill(_execution(selected_side="long"), snap,
                            _review(entry_reference_price=66.0), now=_FIXED_NOW)
        assert r.side_mismatch is True
        assert r.fail_closed is True
        assert any(s.startswith("side_mismatch:") for s in r.fail_closed_reasons)


# ---------------------------------------------------------------------------
# M6. Detects entry-price stale mismatch (SOLUSDT incident replay: 160 vs 66.47)
# ---------------------------------------------------------------------------

class TestM6StalePriceMismatch:
    def _result(self) -> PostFillVerificationResult:
        # actual entry = 66.47, expected preview = 160 -> dev ~58.5% (massive)
        return verify_postfill(
            _execution(),
            _readonly_snapshot(),
            _review(entry_reference_price=160.0),
            now=_FIXED_NOW,
        )

    def test_stale_flag_set(self):
        assert self._result().stale_price_mismatch is True

    def test_deviation_recorded(self):
        r = self._result()
        assert r.entry_price_deviation_pct > STALE_PRICE_DEVIATION_THRESHOLD_PCT
        assert r.entry_price_deviation_pct > 50.0  # the production incident

    def test_reason_contains_dev_pct(self):
        r = self._result()
        assert any("stale_price_mismatch" in s for s in r.fail_closed_reasons)

    def test_within_threshold_not_flagged(self):
        # expected=68, actual=66.47 -> dev ~2.25% (below 5%)
        r = verify_postfill(_execution(), _readonly_snapshot(),
                            _review(entry_reference_price=68.0), now=_FIXED_NOW)
        assert r.stale_price_mismatch is False


# ---------------------------------------------------------------------------
# M7. Missing stop_price => fail_closed=True
# ---------------------------------------------------------------------------

class TestM7MissingStopFailsClosed:
    def test_fail_closed_true(self):
        snap = _readonly_snapshot(positions=[{
            "symbol": "SOLUSDT", "side": "long", "quantity": 4.0,
            "entry_price": 66.47, "stop_price": 0.0,
        }])
        r = verify_postfill(_execution(), snap,
                            _review(entry_reference_price=66.0), now=_FIXED_NOW)
        assert r.fail_closed is True
        assert r.new_entry_allowed is False


# ---------------------------------------------------------------------------
# M8. Stale price mismatch => fail_closed=True
# ---------------------------------------------------------------------------

class TestM8StaleFailsClosed:
    def test_fail_closed_true(self):
        r = verify_postfill(
            _execution(),
            _readonly_snapshot(positions=[{
                "symbol": "SOLUSDT", "side": "long", "quantity": 4.0,
                "entry_price": 66.47, "stop_price": 60.0,
            }]),
            _review(entry_reference_price=160.0),
            now=_FIXED_NOW,
        )
        assert r.fail_closed is True
        assert r.stale_price_mismatch is True
        assert r.new_entry_allowed is False


# ---------------------------------------------------------------------------
# M9. No latest execution => CLI exit 1
# ---------------------------------------------------------------------------

class TestM9NoLatestExecution:
    def test_verify_postfill_missing_execution(self):
        r = verify_postfill(None, _readonly_snapshot(), _review(),
                            now=_FIXED_NOW)
        assert r.fail_closed is True
        assert "execution_report_missing" in r.fail_closed_reasons

    def test_cli_exits_1(self):
        from scripts.verify_demo_new_entry_postfill import run_verify
        with tempfile.TemporaryDirectory() as tmp_exec, \
             tempfile.TemporaryDirectory() as tmp_ro,   \
             tempfile.TemporaryDirectory() as tmp_rev:
            rc = run_verify(
                execution_dir=Path(tmp_exec),  # empty -> missing
                readonly_dir=Path(tmp_ro),
                review_dir=Path(tmp_rev),
            )
        assert rc == 1


# ---------------------------------------------------------------------------
# M10. No latest readonly => CLI exit 1
# ---------------------------------------------------------------------------

class TestM10NoLatestReadonly:
    def test_verify_postfill_missing_readonly(self):
        r = verify_postfill(_execution(), None, _review(), now=_FIXED_NOW)
        assert r.fail_closed is True
        assert "readonly_snapshot_missing" in r.fail_closed_reasons

    def test_cli_exits_1_when_readonly_missing(self):
        from scripts.verify_demo_new_entry_postfill import run_verify
        with tempfile.TemporaryDirectory() as tmp_exec, \
             tempfile.TemporaryDirectory() as tmp_ro,   \
             tempfile.TemporaryDirectory() as tmp_rev:
            # Write only execution; leave readonly empty
            (Path(tmp_exec) / "latest_new_entry_execution.json").write_text(
                json.dumps(_execution()), encoding="utf-8"
            )
            rc = run_verify(
                execution_dir=Path(tmp_exec),
                readonly_dir=Path(tmp_ro),
                review_dir=Path(tmp_rev),
            )
        assert rc == 1


# ---------------------------------------------------------------------------
# M11. No secrets in report
# ---------------------------------------------------------------------------

class TestM11NoSecretsInReport:
    def test_no_env_secret_in_dict(self):
        os.environ["BYBIT_DEMO_API_SECRET_TEST_SENTINEL"] = "TOKEN-SECRET-SENTINEL-XYZ"
        try:
            r = verify_postfill(_execution(), _readonly_snapshot(),
                                _review(entry_reference_price=66.0), now=_FIXED_NOW)
            assert "TOKEN-SECRET-SENTINEL-XYZ" not in json.dumps(r.to_dict())
            assert r.secret_value_observed is False
        finally:
            os.environ.pop("BYBIT_DEMO_API_SECRET_TEST_SENTINEL", None)

    def test_no_secret_field_present(self):
        r = verify_postfill(_execution(), _readonly_snapshot(),
                            _review(entry_reference_price=66.0), now=_FIXED_NOW)
        d = r.to_dict()
        for k in d.keys():
            assert "api_secret" not in k.lower()
            assert "secret_key" not in k.lower()

    def test_written_report_has_no_secret_sentinel(self):
        from scripts.verify_demo_new_entry_postfill import run_verify
        os.environ["BYBIT_DEMO_API_SECRET_TEST_SENTINEL"] = "TOKEN-SECRET-SENTINEL-WRITTEN"
        try:
            with tempfile.TemporaryDirectory() as tmp_exec, \
                 tempfile.TemporaryDirectory() as tmp_ro,   \
                 tempfile.TemporaryDirectory() as tmp_rev,  \
                 tempfile.TemporaryDirectory() as tmp_out:
                (Path(tmp_exec) / "latest_new_entry_execution.json").write_text(
                    json.dumps(_execution()), encoding="utf-8"
                )
                (Path(tmp_ro) / "latest_smoke.json").write_text(
                    json.dumps(_readonly_snapshot()), encoding="utf-8"
                )
                (Path(tmp_rev) / "latest_new_entry_review.json").write_text(
                    json.dumps(_review(entry_reference_price=66.0)), encoding="utf-8"
                )
                run_verify(
                    write_report=True,
                    execution_dir=Path(tmp_exec),
                    readonly_dir=Path(tmp_ro),
                    review_dir=Path(tmp_rev),
                    postfill_dir=Path(tmp_out),
                )
                for f in Path(tmp_out).glob("*"):
                    text = f.read_text(encoding="utf-8")
                    assert "TOKEN-SECRET-SENTINEL-WRITTEN" not in text
        finally:
            os.environ.pop("BYBIT_DEMO_API_SECRET_TEST_SENTINEL", None)


# ---------------------------------------------------------------------------
# M12. No order endpoint called (structural)
# ---------------------------------------------------------------------------

class TestM12NoOrderEndpointCalled:
    def test_invariant_always_false(self):
        # try several different inputs
        for ex_kwargs, snap_kwargs in [
            ({}, {}),
            ({"order_sent": False}, {}),
            ({}, {"positions": []}),
        ]:
            r = verify_postfill(_execution(**ex_kwargs),
                                _readonly_snapshot(**snap_kwargs),
                                _review(entry_reference_price=66.0),
                                now=_FIXED_NOW)
            assert r.order_endpoint_called is False


# ---------------------------------------------------------------------------
# M13. No new order sent (structural)
# ---------------------------------------------------------------------------

class TestM13NoNewOrderSent:
    def test_no_orders_sent_invariant(self):
        r = verify_postfill(_execution(), _readonly_snapshot(),
                            _review(entry_reference_price=66.0),
                            emit_emergency_close_preview=True,
                            now=_FIXED_NOW)
        assert r.no_orders_sent is True
        assert r.no_position_modified is True


# ---------------------------------------------------------------------------
# M14. Emergency close preview for long: side=Sell + reduceOnly=True
# ---------------------------------------------------------------------------

class TestM14EmergencyCloseLong:
    def test_long_preview_uses_sell(self):
        p = make_emergency_close_preview("SOLUSDT", "long", 4.0, 66.47)
        assert p["close_order_side"] == "Sell"
        assert p["reduce_only"] is True

    def test_short_preview_uses_buy(self):
        p = make_emergency_close_preview("LINKUSDT", "short", 100.0, 14.5)
        assert p["close_order_side"] == "Buy"
        assert p["reduce_only"] is True

    def test_emit_emergency_preview_on_missing_stop(self):
        snap = _readonly_snapshot(positions=[{
            "symbol": "SOLUSDT", "side": "long", "quantity": 4.0,
            "entry_price": 66.47, "stop_price": 0.0,
        }])
        r = verify_postfill(_execution(), snap,
                            _review(entry_reference_price=66.0),
                            emit_emergency_close_preview=True,
                            now=_FIXED_NOW)
        assert r.emergency_close_preview is not None
        assert r.emergency_close_preview["close_order_side"] == "Sell"
        assert r.emergency_close_preview["reduce_only"] is True
        assert r.recommended_action == ACTION_EMERGENCY_PREV


# ---------------------------------------------------------------------------
# M15. Emergency close preview is preview_only=True (never executed)
# ---------------------------------------------------------------------------

class TestM15EmergencyPreviewOnly:
    def test_preview_flags(self):
        p = make_emergency_close_preview("SOLUSDT", "long", 4.0, 66.47)
        assert p["preview_only"] is True
        assert p["order_sent"] is False
        assert p["order_endpoint_called"] is False
        assert p["no_orders_sent"] is True
        assert p["no_position_modified"] is True
        assert p["confirmation_required"] is True
        assert "TASK-014N" in p["next_required_task"]

    def test_no_emit_means_no_preview_dict(self):
        snap = _readonly_snapshot(positions=[{
            "symbol": "SOLUSDT", "side": "long", "quantity": 4.0,
            "entry_price": 66.47, "stop_price": 0.0,
        }])
        r = verify_postfill(_execution(), snap, _review(),
                            emit_emergency_close_preview=False,
                            now=_FIXED_NOW)
        assert r.emergency_close_preview is None


# ---------------------------------------------------------------------------
# M16. Source scan: no import of main / risk / BybitExecutor / close-only / sender
# ---------------------------------------------------------------------------

_FORBIDDEN_MODULE_IMPORTS = {
    "main",
    "src.risk",
    "src.demo_close_only_sender",
    "src.demo_new_entry_sender",
    "scripts.execute_demo_close_only_cleanup",
    "scripts.execute_demo_new_entry",
}
_FORBIDDEN_NAME_IMPORTS = {"BybitExecutor"}


def _imports_in(path: Path) -> tuple[set[str], set[str]]:
    """Return (set_of_imported_modules, set_of_imported_names)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods, names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module)
            for a in node.names:
                names.add(a.name)
    return mods, names


class TestM16NoForbiddenImports:
    MODULE_PATH = ROOT / "src" / "demo_new_entry_postfill_verify.py"
    CLI_PATH    = ROOT / "scripts" / "verify_demo_new_entry_postfill.py"

    def test_module_imports_clean(self):
        mods, names = _imports_in(self.MODULE_PATH)
        for forbidden in _FORBIDDEN_MODULE_IMPORTS:
            assert forbidden not in mods, f"Forbidden import: {forbidden}"
        for forbidden in _FORBIDDEN_NAME_IMPORTS:
            assert forbidden not in names, f"Forbidden name import: {forbidden}"

    def test_cli_imports_clean(self):
        mods, names = _imports_in(self.CLI_PATH)
        for forbidden in _FORBIDDEN_MODULE_IMPORTS:
            assert forbidden not in mods, f"Forbidden import: {forbidden}"
        for forbidden in _FORBIDDEN_NAME_IMPORTS:
            assert forbidden not in names, f"Forbidden name import: {forbidden}"


# ---------------------------------------------------------------------------
# M17. No live endpoint fallback (no api.bybit.com / api.bytick.com hostnames)
# ---------------------------------------------------------------------------

class TestM17NoLiveEndpoint:
    MODULE_PATH = ROOT / "src" / "demo_new_entry_postfill_verify.py"
    CLI_PATH    = ROOT / "scripts" / "verify_demo_new_entry_postfill.py"

    def test_module_has_no_live_hostnames(self):
        text = self.MODULE_PATH.read_text(encoding="utf-8")
        assert "api.bybit.com" not in text
        assert "api.bytick.com" not in text

    def test_cli_has_no_live_hostnames(self):
        text = self.CLI_PATH.read_text(encoding="utf-8")
        assert "api.bybit.com" not in text
        assert "api.bytick.com" not in text

    def test_module_has_no_order_endpoint_path(self):
        text = self.MODULE_PATH.read_text(encoding="utf-8")
        # The module must not reference any order POST paths.
        assert "/v5/order/create" not in text
        assert "/v5/order/create-batch" not in text

    def test_cli_has_no_order_endpoint_path(self):
        text = self.CLI_PATH.read_text(encoding="utf-8")
        assert "/v5/order/create" not in text
        assert "/v5/order/create-batch" not in text


# ---------------------------------------------------------------------------
# Structural invariants — always these values regardless of input
# ---------------------------------------------------------------------------

class TestStructuralInvariants:
    def test_clean_path_invariants(self):
        r = verify_postfill(_execution(), _readonly_snapshot(),
                            _review(entry_reference_price=66.0), now=_FIXED_NOW)
        assert r.no_orders_sent is True
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.secret_value_observed is False
        assert r.no_live_endpoint is True
        assert r.no_batch_order is True
        assert r.no_close_only_path is True
        assert r.new_entry_allowed is False

    def test_fail_closed_path_invariants(self):
        snap = _readonly_snapshot(positions=[])
        r    = verify_postfill(_execution(), snap, _review(), now=_FIXED_NOW)
        assert r.no_orders_sent is True
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.secret_value_observed is False
        assert r.no_live_endpoint is True
        assert r.no_batch_order is True
        assert r.no_close_only_path is True
        assert r.new_entry_allowed is False


# ---------------------------------------------------------------------------
# Production-incident replay (SOLUSDT) — full integration test
# ---------------------------------------------------------------------------

class TestProductionIncidentReplay:
    """
    VPS executed the first real Demo new-entry for SOLUSDT and post-fill
    discovered:
      - order_id  = aae978ed-98f7-47cd-90ad-1f0c16b29213
      - actual qty=4.0, entry_price=66.47, stop_price=0  (missing stop)
      - preview entry_reference_price = 160 vs actual 66.47 -> ~58% deviation

    This test verifies the new module catches both gates at once.
    """

    def _result(self) -> PostFillVerificationResult:
        ex   = _execution(selected_symbol="SOLUSDT", selected_side="long",
                          order_side="Buy", selected_qty=4.0, order_sent=True,
                          order_id="aae978ed-98f7-47cd-90ad-1f0c16b29213")
        snap = _readonly_snapshot(positions=[{
            "symbol": "SOLUSDT", "side": "long", "quantity": 4.0,
            "entry_price": 66.47, "stop_price": 0.0,
        }])
        rev  = _review(entry_reference_price=160.0)
        return verify_postfill(ex, snap, rev,
                               emit_emergency_close_preview=True,
                               now=_FIXED_NOW)

    def test_selected_symbol(self):
        assert self._result().selected_symbol == "SOLUSDT"

    def test_position_found(self):
        assert self._result().position_found is True

    def test_entry_price(self):
        assert abs(self._result().actual_entry_price - 66.47) < 1e-6

    def test_missing_stop_detected(self):
        assert self._result().missing_stop_price is True

    def test_stale_price_detected(self):
        assert self._result().stale_price_mismatch is True

    def test_deviation_about_58_percent(self):
        dev = self._result().entry_price_deviation_pct
        assert dev > 50.0  # should be ~58.5%

    def test_fail_closed(self):
        assert self._result().fail_closed is True

    def test_no_orders_sent(self):
        assert self._result().no_orders_sent is True
        assert self._result().order_endpoint_called is False

    def test_recommended_action_emergency_preview(self):
        assert self._result().recommended_action == ACTION_EMERGENCY_PREV

    def test_emergency_preview_long_uses_sell(self):
        p = self._result().emergency_close_preview
        assert p is not None
        assert p["close_order_side"] == "Sell"
        assert p["reduce_only"] is True
        assert p["preview_only"] is True
        assert p["qty"] == 4.0


# ---------------------------------------------------------------------------
# CLI integration — end-to-end with sandboxed dirs
# ---------------------------------------------------------------------------

class TestCLIIntegration:
    def _write_inputs(
        self,
        tmp_exec: Path,
        tmp_ro:   Path,
        tmp_rev:  Path,
        *,
        stop_price: float = 60.0,
        expected_entry: float = 66.0,
    ) -> None:
        (tmp_exec / "latest_new_entry_execution.json").write_text(
            json.dumps(_execution()), encoding="utf-8"
        )
        (tmp_ro / "latest_smoke.json").write_text(
            json.dumps(_readonly_snapshot(positions=[{
                "symbol": "SOLUSDT", "side": "long", "quantity": 4.0,
                "entry_price": 66.47, "stop_price": stop_price,
            }])),
            encoding="utf-8",
        )
        (tmp_rev / "latest_new_entry_review.json").write_text(
            json.dumps(_review(entry_reference_price=expected_entry)),
            encoding="utf-8",
        )

    def test_cli_pass_exits_zero(self):
        from scripts.verify_demo_new_entry_postfill import run_verify
        with tempfile.TemporaryDirectory() as tmp_exec, \
             tempfile.TemporaryDirectory() as tmp_ro,   \
             tempfile.TemporaryDirectory() as tmp_rev,  \
             tempfile.TemporaryDirectory() as tmp_out:
            self._write_inputs(Path(tmp_exec), Path(tmp_ro), Path(tmp_rev))
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = run_verify(
                    write_report=True,
                    execution_dir=Path(tmp_exec),
                    readonly_dir=Path(tmp_ro),
                    review_dir=Path(tmp_rev),
                    postfill_dir=Path(tmp_out),
                )
            assert rc == 0
            json_path = Path(tmp_out) / "latest_new_entry_postfill.json"
            md_path   = Path(tmp_out) / "latest_new_entry_postfill.md"
            assert json_path.exists()
            assert md_path.exists()
            data = json.loads(json_path.read_text(encoding="utf-8"))
            assert data["fail_closed"] is False
            md = md_path.read_text(encoding="utf-8")
            assert "PASS" in md

    def test_cli_fail_closed_still_exits_zero_when_inputs_present(self):
        """Result produced -> rc=0 even though verification fail-closed."""
        from scripts.verify_demo_new_entry_postfill import run_verify
        with tempfile.TemporaryDirectory() as tmp_exec, \
             tempfile.TemporaryDirectory() as tmp_ro,   \
             tempfile.TemporaryDirectory() as tmp_rev,  \
             tempfile.TemporaryDirectory() as tmp_out:
            # missing stop + stale price (SOLUSDT incident replay)
            self._write_inputs(Path(tmp_exec), Path(tmp_ro), Path(tmp_rev),
                               stop_price=0.0, expected_entry=160.0)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = run_verify(
                    write_report=True,
                    with_emergency_close_preview=True,
                    execution_dir=Path(tmp_exec),
                    readonly_dir=Path(tmp_ro),
                    review_dir=Path(tmp_rev),
                    postfill_dir=Path(tmp_out),
                )
            assert rc == 0
            md = (Path(tmp_out) / "latest_new_entry_postfill.md").read_text(
                encoding="utf-8"
            )
            assert "FAIL_CLOSED" in md
            assert "Emergency Close-only PREVIEW" in md
            assert "missing_stop_price" in md
            assert "stale_price_mismatch" in md
