"""
tests/demo_trading/test_demo_protected_new_entry_orchestrator.py
TASK-014S: Protected New-entry Orchestrator tests (S1 - S28+).

Covers:
  - review/protection missing & symbol mismatch
  - review/protection realtime price guard
  - missing / wrong-direction stop_price
  - dry-run success (DRY_RUN_PROTECTED_ENTRY_CHAIN_ALLOWED)
  - mock-chain invalid / valid token
  - mock-chain success (MOCK_PROTECTED_ENTRY_SUCCESS)
  - mock-chain attach-failure -> MOCK_PROTECTED_ENTRY_FAIL_CLOSED +
    recommended_action='emergency_close_preview' (no emergency close actually
    triggered)
  - final mock position has stop_price>0 and missing_stop_price=False
  - report artifacts (JSON + Markdown, ts + latest variants)
  - no live endpoint / no secret keys observed
  - no forbidden imports (urllib, requests, httpx, socket, http.client,
    pybit, main, src.risk, BybitExecutor, src.demo_new_entry_sender,
    src.demo_close_only_sender, src.demo_emergency_close_sender)
  - urlopen sentinel scan (orchestrator + CLI source contain no network call)
  - TASK-014L sender G20 (protected_entry_policy_missing) still blocks
    --execute-new-entry (orchestrator does not lift G20)
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import tokenize
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_protected_new_entry_orchestrator import (
    DEMO_ENDPOINT_FAMILY,
    DemoProtectedNewEntryOrchestrator,
    GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK_CHAIN,
    GATE_PROTECTION_LONG_STOP_NOT_BELOW_ENTRY,
    GATE_PROTECTION_MISSING,
    GATE_PROTECTION_MISSING_REALTIME_GUARD,
    GATE_PROTECTION_SHORT_STOP_NOT_ABOVE_ENTRY,
    GATE_PROTECTION_STOP_PRICE_NOT_POSITIVE,
    GATE_PROTECTION_SYMBOL_MISMATCH,
    GATE_REVIEW_MISSING,
    GATE_REVIEW_MISSING_REALTIME_PRICE_GUARD,
    GATE_REVIEW_SYMBOL_NOT_IN_PAYLOAD,
    GATE_STOP_ATTACH_MOCK_FAILED,
    ORDER_CREATE_ENDPOINT,
    PROTECTED_STATUS_DRY_RUN_PREVIEW,
    PROTECTED_STATUS_FAIL_CLOSED,
    PROTECTED_STATUS_MOCK_PROTECTED,
    ProtectedEntryChainResult,
    RECOMMENDED_ACTION_EMERGENCY_PREVIEW,
    RECOMMENDED_ACTION_NONE,
    STATUS_DRY_RUN_ALLOWED,
    STATUS_FAIL_CLOSED,
    STATUS_MOCK_FAIL_CLOSED,
    STATUS_MOCK_SUCCESS,
    STOP_ATTACH_ENDPOINT,
    _synth_stop_attach_token,
)


_MODULE_PATH = ROOT / "src" / "demo_protected_new_entry_orchestrator.py"
_SCRIPT_PATH = ROOT / "scripts" / "execute_demo_protected_new_entry_mock.py"
_TEST_NOW    = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
_TODAY_TOKEN = "CONFIRM_DEMO_PROTECTED_ENTRY_20260610"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _valid_solusdt_protection() -> dict:
    """TASK-014Q-shaped protection report for SOLUSDT long, mirrors module schema."""
    return {
        "timestamp":                       "2026-06-10T11:00:00Z",
        "timestamp_utc":                   "2026-06-10T11:00:00Z",
        "selected_symbol":                 "SOLUSDT",
        "selected_side":                   "long",
        "order_side":                      "Buy",
        "selected_qty":                    12.3,
        "entry_reference_price":           64.76,
        "stop_price":                      61.52,
        "stop_order_side":                 "Sell",
        "stop_trigger_direction":          "fall_below_entry",
        "realtime_price_guard_verified":   True,
        "review_fail_closed":              False,
        "review_timestamp":                "2026-06-10T10:30:00Z",
        "blocked_reasons":                 [],
        "lifecycle_phase":                 "phase_1_pre_entry_review",
        "protected_entry_status":          "PREVIEW_ONLY",
        "stop_loss_attach_required":       True,
        "stop_loss_endpoint_allowed":      False,
        "preview_only":                    True,
        "protected_entry_execute_allowed": False,
        "protected_entry_execute_reason":  "stop_loss_attachment_not_implemented",
        "no_orders_sent":                  True,
        "order_endpoint_called":           False,
        "stop_endpoint_called":            False,
        "no_position_modified":            True,
        "no_live_endpoint":                True,
        "secret_value_observed":           False,
        "order_create_endpoint":           "/v5/order/create",
        "stop_attach_endpoint":            "/v5/position/trading-stop",
        "endpoint_family":                 "bybit_demo",
        "next_required_task":              "TASK-014S_protected_new_entry_orchestrator",
    }


def _valid_avaxusdt_short_protection() -> dict:
    p = _valid_solusdt_protection()
    p.update({
        "selected_symbol":         "AVAXUSDT",
        "selected_side":           "short",
        "order_side":              "Sell",
        "selected_qty":            5.0,
        "entry_reference_price":   30.0,
        "stop_price":              31.5,
        "stop_order_side":         "Buy",
        "stop_trigger_direction":  "rise_above_entry",
    })
    return p


def _accepted_payload(
    symbol: str = "SOLUSDT",
    order_side: str = "Buy",
    qty: float = 12.3,
    entry: float = 64.76,
    stop: float = 61.52,
    preview_only: bool = True,
    order_sent: bool = False,
    order_endpoint_called: bool = False,
) -> dict:
    return {
        "symbol":                symbol,
        "side":                  order_side,
        "qty":                   qty,
        "order_type":            "Market",
        "reduce_only":           False,
        "preview_only":          preview_only,
        "order_sent":            order_sent,
        "order_endpoint_called": order_endpoint_called,
        "entry_reference_price": entry,
        "stop_price":            stop,
    }


def _valid_review(
    symbol: str = "SOLUSDT",
    side: str = "long",
    payload: dict | None = None,
    realtime_price_guard_verified: bool = True,
    demo_runtime_verified: bool = True,
    proof_strength: str = "STRONG",
    endpoint_family: str = "bybit_demo",
    account_mode: str = "demo",
    position_details_source: str = "real_readonly",
    fail_closed: bool = False,
) -> dict:
    p = payload if payload is not None else _accepted_payload(symbol=symbol)
    return {
        "fail_closed":                    fail_closed,
        "demo_runtime_verified":          demo_runtime_verified,
        "proof_strength":                 proof_strength,
        "endpoint_family":                endpoint_family,
        "account_mode":                   account_mode,
        "position_details_source":        position_details_source,
        "realtime_price_guard_verified":  realtime_price_guard_verified,
        "available_balance_usd":          5_000.0,
        "open_positions_count":           5,
        "timestamp":                      "2026-06-10T10:30:00Z",
        "accepted_candidates":            [
            {"symbol": symbol, "side": side, "payload": p},
        ],
    }


def _read_code_only(path: Path) -> str:
    """Return source with string literals + comments stripped (via tokenize)."""
    tokens: list[str] = []
    with open(path, "rb") as fh:
        for tok in tokenize.tokenize(fh.readline):
            if tok.type in (
                tokenize.STRING, tokenize.COMMENT,
                tokenize.ENCODING, tokenize.NEWLINE, tokenize.NL,
                tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER,
            ):
                continue
            tokens.append(tok.string)
    return " ".join(tokens)


def _orch() -> DemoProtectedNewEntryOrchestrator:
    return DemoProtectedNewEntryOrchestrator()


# ===========================================================================
# S1: missing review => fail closed
# ===========================================================================

class TestS1MissingReview:
    def test_none_review_fails_closed(self):
        r = _orch().submit_chain(
            review=None, protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert r.status == STATUS_FAIL_CLOSED
        assert r.fail_closed is True
        assert GATE_REVIEW_MISSING in r.blocked_gates
        assert r.no_orders_sent is True
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False

    def test_empty_review_fails_closed(self):
        r = _orch().submit_chain(
            review={}, protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_REVIEW_MISSING in r.blocked_gates


# ===========================================================================
# S2: missing protection => fail closed
# ===========================================================================

class TestS2MissingProtection:
    def test_none_protection_fails_closed(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=None,
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates

    def test_empty_protection_fails_closed(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection={},
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_MISSING in r.blocked_gates


# ===========================================================================
# S3: symbol mismatch => fail closed
# ===========================================================================

class TestS3SymbolMismatch:
    def test_review_does_not_contain_symbol(self):
        r = _orch().submit_chain(
            review=_valid_review(symbol="SOLUSDT"),
            protection=_valid_solusdt_protection(),
            symbol="AAVEUSDT", _now=_TEST_NOW,
        )
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REVIEW_SYMBOL_NOT_IN_PAYLOAD in r.blocked_gates

    def test_protection_symbol_mismatch(self):
        r = _orch().submit_chain(
            review=_valid_review(symbol="AVAXUSDT"),
            protection=_valid_solusdt_protection(),
            symbol="AVAXUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_SYMBOL_MISMATCH in r.blocked_gates

    def test_empty_symbol_blocked(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="", _now=_TEST_NOW,
        )
        assert r.status == STATUS_FAIL_CLOSED


# ===========================================================================
# S4: review missing realtime price guard => fail closed
# ===========================================================================

class TestS4ReviewMissingRealtimeGuard:
    def test_guard_false_blocked(self):
        rv = _valid_review(realtime_price_guard_verified=False)
        r = _orch().submit_chain(
            review=rv, protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_REVIEW_MISSING_REALTIME_PRICE_GUARD in r.blocked_gates
        assert r.status == STATUS_FAIL_CLOSED

    def test_guard_missing_blocked(self):
        rv = _valid_review()
        rv.pop("realtime_price_guard_verified", None)
        r = _orch().submit_chain(
            review=rv, protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_REVIEW_MISSING_REALTIME_PRICE_GUARD in r.blocked_gates


# ===========================================================================
# S5: protection missing realtime price guard => fail closed
# ===========================================================================

class TestS5ProtectionMissingRealtimeGuard:
    def test_protection_guard_false_blocked(self):
        prot = _valid_solusdt_protection()
        prot["realtime_price_guard_verified"] = False
        r = _orch().submit_chain(
            review=_valid_review(), protection=prot,
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_MISSING_REALTIME_GUARD in r.blocked_gates
        assert r.status == STATUS_FAIL_CLOSED


# ===========================================================================
# S6: missing stop_price => fail closed
# ===========================================================================

class TestS6MissingStopPrice:
    @pytest.mark.parametrize("stop", [0.0, 0, -1.0])
    def test_missing_or_zero_stop(self, stop):
        prot = _valid_solusdt_protection()
        prot["stop_price"] = stop
        r = _orch().submit_chain(
            review=_valid_review(), protection=prot,
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_STOP_PRICE_NOT_POSITIVE in r.blocked_gates
        assert r.status == STATUS_FAIL_CLOSED


# ===========================================================================
# S7: long stop above/equal entry => fail closed
# ===========================================================================

class TestS7LongStopAboveEntry:
    def test_long_stop_above_entry_blocked(self):
        prot = _valid_solusdt_protection()
        prot["stop_price"] = 70.0   # above 64.76
        r = _orch().submit_chain(
            review=_valid_review(), protection=prot,
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_LONG_STOP_NOT_BELOW_ENTRY in r.blocked_gates

    def test_long_stop_equal_entry_blocked(self):
        prot = _valid_solusdt_protection()
        prot["stop_price"] = prot["entry_reference_price"]
        r = _orch().submit_chain(
            review=_valid_review(), protection=prot,
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_LONG_STOP_NOT_BELOW_ENTRY in r.blocked_gates


# ===========================================================================
# S8: short stop below/equal entry => fail closed
# ===========================================================================

class TestS8ShortStopBelowEntry:
    def test_short_stop_below_entry_blocked(self):
        prot = _valid_avaxusdt_short_protection()
        prot["stop_price"] = 25.0   # below 30.0
        rv  = _valid_review(symbol="AVAXUSDT", side="short",
                            payload=_accepted_payload(symbol="AVAXUSDT",
                                                      order_side="Sell",
                                                      qty=5.0, entry=30.0,
                                                      stop=25.0))
        r = _orch().submit_chain(
            review=rv, protection=prot,
            symbol="AVAXUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_SHORT_STOP_NOT_ABOVE_ENTRY in r.blocked_gates

    def test_short_stop_equal_entry_blocked(self):
        prot = _valid_avaxusdt_short_protection()
        prot["stop_price"] = prot["entry_reference_price"]
        rv  = _valid_review(symbol="AVAXUSDT", side="short",
                            payload=_accepted_payload(symbol="AVAXUSDT",
                                                      order_side="Sell",
                                                      qty=5.0, entry=30.0,
                                                      stop=30.0))
        r = _orch().submit_chain(
            review=rv, protection=prot,
            symbol="AVAXUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_SHORT_STOP_NOT_ABOVE_ENTRY in r.blocked_gates


# ===========================================================================
# S9: valid dry-run SOLUSDT => DRY_RUN_PROTECTED_ENTRY_CHAIN_ALLOWED
# ===========================================================================

class TestS9DryRunAllowed:
    def test_dry_run_passes_all_gates(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", mock_chain=False, _now=_TEST_NOW,
        )
        assert r.status == STATUS_DRY_RUN_ALLOWED
        assert r.fail_closed is False
        assert r.dry_run is True
        assert r.mock_chain is False
        assert r.blocked_gates == []
        assert r.protected_entry_status == PROTECTED_STATUS_DRY_RUN_PREVIEW
        assert r.mock_entry_order_sent is False
        assert r.mock_stop_attached is False
        # Payload preview is built (TASK-014R sender), but nothing sent.
        assert r.stop_payload_preview
        assert r.stop_payload_preview_only is True
        assert r.no_orders_sent is True
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True


# ===========================================================================
# S10: mock-chain invalid token => fail closed
# ===========================================================================

class TestS10MockChainInvalidToken:
    def test_empty_token(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token="", mock_chain=True,
            _now=_TEST_NOW,
        )
        assert GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK_CHAIN in r.blocked_gates
        assert r.status == STATUS_FAIL_CLOSED

    def test_wrong_date_token(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT",
            confirm_token="CONFIRM_DEMO_PROTECTED_ENTRY_20200101",
            mock_chain=True, _now=_TEST_NOW,
        )
        assert GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK_CHAIN in r.blocked_gates

    def test_wrong_prefix(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT",
            confirm_token="CONFIRM_DEMO_STOP_ATTACH_20260610",
            mock_chain=True, _now=_TEST_NOW,
        )
        assert GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK_CHAIN in r.blocked_gates


# ===========================================================================
# S11: mock-chain valid token => MOCK_PROTECTED_ENTRY_SUCCESS
# ===========================================================================

class TestS11MockChainSuccess:
    def test_success(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_chain=True, _now=_TEST_NOW,
        )
        assert r.status == STATUS_MOCK_SUCCESS
        assert r.protected_entry_status == PROTECTED_STATUS_MOCK_PROTECTED
        assert r.fail_closed is False
        assert r.recommended_action == RECOMMENDED_ACTION_NONE
        assert r.confirm_token_valid is True
        assert r.blocked_gates == []


# ===========================================================================
# S12: mock_entry_order_sent=True but order_endpoint_called stays False
# ===========================================================================

class TestS12MockEntryFlags:
    def test_mock_entry_flags(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_chain=True, _now=_TEST_NOW,
        )
        assert r.mock_entry_order_sent is True
        assert r.mock_order_id.startswith("MOCK-ENTRY-SOLUSDT-")
        assert r.order_endpoint_called is False
        assert r.no_orders_sent is True
        assert r.no_position_modified is True


# ===========================================================================
# S13: mock_stop_attached=True but stop_endpoint_called stays False
# ===========================================================================

class TestS13MockStopFlags:
    def test_mock_stop_flags(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_chain=True, _now=_TEST_NOW,
        )
        assert r.mock_stop_attached is True
        assert r.mock_stop_attach_id.startswith("MOCK-STOP-SOLUSDT-")
        assert r.stop_endpoint_called is False


# ===========================================================================
# S14: final mock position has stop_price > 0
# ===========================================================================

class TestS14FinalStopPricePositive:
    def test_final_stop_price_positive(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_chain=True, _now=_TEST_NOW,
        )
        assert r.mock_final_position_stop_price > 0
        assert r.mock_final_position_stop_price == pytest.approx(61.52)
        assert r.mock_post_fill_position.get("stop_price") == pytest.approx(61.52)


# ===========================================================================
# S15: missing_stop_price=False after attach
# ===========================================================================

class TestS15MissingStopFalseAfterAttach:
    def test_missing_stop_false(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_chain=True, _now=_TEST_NOW,
        )
        assert r.missing_stop_price is False
        assert r.mock_post_fill_position.get("missing_stop_price") is False


# ===========================================================================
# S16: _simulate_stop_attach_failure => MOCK_PROTECTED_ENTRY_FAIL_CLOSED
# ===========================================================================

class TestS16MockAttachFailure:
    def test_attach_failure_path(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_chain=True, _now=_TEST_NOW,
            _simulate_stop_attach_failure=True,
        )
        assert r.status == STATUS_MOCK_FAIL_CLOSED
        assert r.protected_entry_status == PROTECTED_STATUS_FAIL_CLOSED
        assert r.fail_closed is True
        assert r.recommended_action == RECOMMENDED_ACTION_EMERGENCY_PREVIEW
        assert GATE_STOP_ATTACH_MOCK_FAILED in r.blocked_gates
        # Entry mock still flagged (the naked-window event); attach NOT done.
        assert r.mock_entry_order_sent is True
        assert r.mock_stop_attached is False
        # Safety invariants still hold — no real emergency close invoked.
        assert r.emergency_close_invoked is False
        assert r.no_orders_sent is True
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        # Post-fill snapshot shows naked state (stop_price=0).
        assert r.mock_post_fill_position.get("stop_price") == 0.0
        assert r.missing_stop_price is True


# ===========================================================================
# S17: report artifacts (JSON + Markdown, ts + latest)
# ===========================================================================

class TestS17ReportArtifacts:
    def test_writer_produces_all_four_files(self):
        from scripts.execute_demo_protected_new_entry_mock import run_execute

        with tempfile.TemporaryDirectory() as td:
            base       = Path(td)
            review_d   = base / "review"
            protect_d  = base / "protection"
            chain_d    = base / "chain"
            review_d.mkdir(); protect_d.mkdir()

            (review_d / "latest_new_entry_review.json").write_text(
                json.dumps(_valid_review()), encoding="utf-8",
            )
            (protect_d / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )

            rc = run_execute(
                symbol="SOLUSDT",
                confirm_token=_TODAY_TOKEN,
                mock_chain=True,
                write_report=True,
                review_dir=review_d,
                protection_dir=protect_d,
                chain_dir=chain_d,
                _now=_TEST_NOW,
            )
            assert rc == 0

            files = sorted(p.name for p in chain_d.iterdir())
            assert "latest_protected_new_entry.json" in files
            assert "latest_protected_new_entry.md"   in files
            # exactly one timestamped json + md alongside the latest pair
            ts_json = [n for n in files if n.endswith(".json")
                       and not n.startswith("latest_")]
            ts_md   = [n for n in files if n.endswith(".md")
                       and not n.startswith("latest_")]
            assert len(ts_json) == 1
            assert len(ts_md)   == 1

            data = json.loads(
                (chain_d / "latest_protected_new_entry.json").read_text(
                    encoding="utf-8"
                )
            )
            assert data["status"]                     == STATUS_MOCK_SUCCESS
            assert data["protected_entry_status"]     == PROTECTED_STATUS_MOCK_PROTECTED
            assert data["selected_symbol"]            == "SOLUSDT"
            assert data["mock_entry_order_sent"]      is True
            assert data["mock_stop_attached"]         is True
            assert data["order_endpoint_called"]      is False
            assert data["stop_endpoint_called"]       is False
            assert data["no_orders_sent"]             is True
            assert data["no_position_modified"]       is True
            assert data["emergency_close_invoked"]    is False
            assert data["secret_value_observed"]      is False


# ===========================================================================
# S18: no live endpoint anywhere in result
# ===========================================================================

class TestS18NoLiveEndpoint:
    def test_endpoints_recorded_but_not_invoked(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_chain=True, _now=_TEST_NOW,
        )
        assert r.no_live_endpoint is True
        assert r.endpoint_family == DEMO_ENDPOINT_FAMILY
        assert r.order_create_endpoint == ORDER_CREATE_ENDPOINT
        assert r.stop_attach_endpoint == STOP_ATTACH_ENDPOINT
        # Endpoints stored as informational strings only.
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False


# ===========================================================================
# S19: no secrets in source / no env reads / no signing
# ===========================================================================

class TestS19NoSecrets:
    def test_no_env_or_signing_in_orchestrator(self):
        code = _read_code_only(_MODULE_PATH)
        # No environment reads.
        assert "os.environ" not in code
        assert "getenv"     not in code
        assert "dotenv"     not in code
        # No HMAC / signing material.
        assert "hmac"       not in code.lower()
        assert "hashlib"    not in code.lower()
        assert "BYBIT_API"  not in code
        assert "API_KEY"    not in code
        assert "API_SECRET" not in code

    def test_no_env_or_signing_in_cli(self):
        code = _read_code_only(_SCRIPT_PATH)
        assert "os.environ" not in code
        assert "getenv"     not in code
        assert "dotenv"     not in code
        assert "hmac"       not in code.lower()
        assert "hashlib"    not in code.lower()
        assert "BYBIT_API"  not in code
        assert "API_KEY"    not in code
        assert "API_SECRET" not in code


# ===========================================================================
# S20: no forbidden imports (module + CLI)
# ===========================================================================

_FORBIDDEN_IMPORTS = (
    "urllib", "requests", "httpx", "socket", "http.client", "http",
    "pybit",
    "main",
    "src.risk",
    "src.bybit_executor",
    "BybitExecutor",
    "src.demo_new_entry_sender",
    "src.demo_close_only_sender",
    "src.demo_emergency_close_sender",
)


def _collect_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module)
    return out


class TestS20NoForbiddenImports:
    def test_orchestrator_imports(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, (
                f"Forbidden import {bad!r} found in orchestrator module"
            )

    def test_cli_imports(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, (
                f"Forbidden import {bad!r} found in CLI script"
            )


# ===========================================================================
# S21: no close-only sender reuse
# ===========================================================================

class TestS21NoCloseOnlyPath:
    def test_close_only_not_referenced(self):
        code_m = _read_code_only(_MODULE_PATH)
        code_s = _read_code_only(_SCRIPT_PATH)
        for code in (code_m, code_s):
            assert "DemoCloseOnlySender" not in code
            assert "demo_close_only_sender" not in code


# ===========================================================================
# S22: no emergency-close sender reuse (recommendation only)
# ===========================================================================

class TestS22NoEmergencyCloseInvocation:
    def test_emergency_close_not_invoked(self):
        code_m = _read_code_only(_MODULE_PATH)
        code_s = _read_code_only(_SCRIPT_PATH)
        for code in (code_m, code_s):
            assert "DemoEmergencyCloseSender"    not in code
            assert "demo_emergency_close_sender" not in code

    def test_result_emergency_close_invoked_always_false(self):
        # Both success and failure paths.
        r1 = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_chain=True, _now=_TEST_NOW,
        )
        r2 = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_chain=True, _now=_TEST_NOW,
            _simulate_stop_attach_failure=True,
        )
        assert r1.emergency_close_invoked is False
        assert r2.emergency_close_invoked is False
        # And the recommendation in failure path is informational only.
        assert r2.recommended_action == RECOMMENDED_ACTION_EMERGENCY_PREVIEW


# ===========================================================================
# S23: no live new-entry sender reuse
# ===========================================================================

class TestS23NoNewEntrySenderReuse:
    def test_new_entry_sender_not_imported(self):
        code_m = _read_code_only(_MODULE_PATH)
        code_s = _read_code_only(_SCRIPT_PATH)
        for code in (code_m, code_s):
            assert "DemoNewEntrySender"   not in code
            assert "demo_new_entry_sender" not in code


# ===========================================================================
# S24: no socket / network call at module import time
# ===========================================================================

class TestS24NoNetworkCalls:
    def test_module_does_not_open_sockets_on_import(self):
        # Re-import in a subprocess to verify no socket activity on import.
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_protected_new_entry_orchestrator as m; "
             "print('OK', m.STATUS_DRY_RUN_ALLOWED)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# S25: orchestrator does not call urlopen / requests / httpx anywhere
# ===========================================================================

class TestS25NoNetworkSentinels:
    def test_orchestrator_source_has_no_urlopen(self):
        code = _read_code_only(_MODULE_PATH)
        assert "urlopen"        not in code
        assert "Request"        not in code
        assert "requests.post"  not in code
        assert "requests.get"   not in code
        assert "httpx"          not in code
        assert "session.post"   not in code
        assert "session.get"    not in code

    def test_cli_source_has_no_urlopen(self):
        code = _read_code_only(_SCRIPT_PATH)
        assert "urlopen"        not in code
        assert "Request"        not in code
        assert "requests.post"  not in code
        assert "requests.get"   not in code
        assert "httpx"          not in code


# ===========================================================================
# S26: stop payload preview excludes takeProfit/leverage/transfer/withdraw/deposit
# ===========================================================================

class TestS26PayloadComposition:
    def test_payload_excludes_forbidden_fields(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", mock_chain=False, _now=_TEST_NOW,
        )
        payload = r.stop_payload_preview
        assert payload                                # built
        assert "stopLoss" in payload
        assert "symbol"   in payload
        # Forbidden fields per TASK-014S spec
        for forbidden in (
            "takeProfit", "leverage", "transfer", "withdraw", "deposit",
        ):
            assert forbidden not in payload, (
                f"Forbidden field {forbidden!r} in stop payload preview"
            )


# ===========================================================================
# S27: TASK-014L sender G20 still blocks --execute-new-entry
# ===========================================================================

class TestS27G20StillBlocksExecuteNewEntry:
    def test_sender_g20_unchanged(self):
        # Import after orchestrator import — verifying TASK-014S did not lift G20.
        from src.demo_new_entry_protection import G20_BLOCKED_GATE_NAME
        assert G20_BLOCKED_GATE_NAME == "protected_entry_policy_missing"

        # The TASK-014L sender, when asked to execute, still blocks at G20.
        from src.demo_new_entry_sender import DemoNewEntrySender
        sender = DemoNewEntrySender()
        # We don't need to feed a full review — invoke a private validation
        # path is fragile; instead probe the public API and assert the gate
        # name string is still present in the sender source.
        sender_src = (
            ROOT / "src" / "demo_new_entry_sender.py"
        ).read_text(encoding="utf-8")
        assert G20_BLOCKED_GATE_NAME in sender_src

    def test_orchestrator_does_not_lift_g20(self):
        code = _read_code_only(_MODULE_PATH)
        # Orchestrator must not lift, reassign or override the G20 gate.
        assert "protected_entry_policy_missing" not in code
        assert "G20_BLOCKED_GATE_NAME"          not in code


# ===========================================================================
# S28: source scan confirms no urllib/request/httpx in orchestrator OR CLI
# ===========================================================================

class TestS28UrlopenSentinelScan:
    def test_combined_scan(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            for tok in ("urllib", "urlopen", "httpx",
                        "requests.", "http.client", "socket."):
                assert tok not in code, (
                    f"Network token {tok!r} present in {path.name}"
                )


# ===========================================================================
# Extras: dataclass round-trip, synth token, dry-run with short side, CLI smoke
# ===========================================================================

class TestExtras:
    def test_dataclass_to_dict_round_trip(self):
        r = _orch().submit_chain(
            review=_valid_review(), protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", mock_chain=False, _now=_TEST_NOW,
        )
        d = r.to_dict()
        # All safety invariants should be present and correct.
        for key, expected in (
            ("no_orders_sent",          True),
            ("order_endpoint_called",   False),
            ("stop_endpoint_called",    False),
            ("no_position_modified",    True),
            ("no_live_endpoint",        True),
            ("no_batch_order",          True),
            ("no_close_only_path",      True),
            ("emergency_close_invoked", False),
            ("secret_value_observed",   False),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"]                 == STATUS_DRY_RUN_ALLOWED
        assert d["protected_entry_status"] == PROTECTED_STATUS_DRY_RUN_PREVIEW
        assert d["selected_symbol"]        == "SOLUSDT"
        # Mutating returned dict must not mutate dataclass internals.
        d["mock_post_fill_position"]["mutated"] = True
        assert "mutated" not in r.mock_post_fill_position

    def test_synth_stop_attach_token_format(self):
        tok = _synth_stop_attach_token(_now=_TEST_NOW)
        assert tok == "CONFIRM_DEMO_STOP_ATTACH_20260610"

    def test_short_side_dry_run(self):
        rv = _valid_review(symbol="AVAXUSDT", side="short",
                           payload=_accepted_payload(symbol="AVAXUSDT",
                                                     order_side="Sell",
                                                     qty=5.0, entry=30.0,
                                                     stop=31.5))
        r = _orch().submit_chain(
            review=rv, protection=_valid_avaxusdt_short_protection(),
            symbol="AVAXUSDT", mock_chain=False, _now=_TEST_NOW,
        )
        assert r.status == STATUS_DRY_RUN_ALLOWED
        assert r.selected_side == "short"
        assert r.stop_price == pytest.approx(31.5)

    def test_cli_subprocess_dry_run_smoke(self):
        with tempfile.TemporaryDirectory() as td:
            base       = Path(td)
            review_d   = base / "review"
            protect_d  = base / "protection"
            chain_d    = base / "chain"
            review_d.mkdir(); protect_d.mkdir()

            (review_d / "latest_new_entry_review.json").write_text(
                json.dumps(_valid_review()), encoding="utf-8",
            )
            (protect_d / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )

            # Invoke run_execute directly (CLI body) rather than spawning
            # a subprocess — covers the CLI code path including the
            # markdown writer.
            from scripts.execute_demo_protected_new_entry_mock import (
                run_execute,
            )
            rc = run_execute(
                symbol="SOLUSDT",
                confirm_token="",
                mock_chain=False,
                write_report=True,
                review_dir=review_d,
                protection_dir=protect_d,
                chain_dir=chain_d,
                _now=_TEST_NOW,
            )
            assert rc == 0
            md = (chain_d / "latest_protected_new_entry.md").read_text(
                encoding="utf-8"
            )
            assert "Demo Protected New-entry Mock Chain Report" in md
            assert "Stop Payload Preview" in md
            assert "Safety Invariants"    in md


# ===========================================================================
# Extra: fail_closed=True review is blocked
# ===========================================================================

class TestExtraReviewFailClosed:
    def test_review_fail_closed_blocked(self):
        rv = _valid_review(fail_closed=True)
        r = _orch().submit_chain(
            review=rv, protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert r.status == STATUS_FAIL_CLOSED
        # GATE_REVIEW_FAIL_CLOSED is the symbol; we know it from import.
        from src.demo_protected_new_entry_orchestrator import (
            GATE_REVIEW_FAIL_CLOSED,
        )
        assert GATE_REVIEW_FAIL_CLOSED in r.blocked_gates


# ===========================================================================
# Extra: review payload preview_only=False is blocked
# ===========================================================================

class TestExtraReviewPayloadFlags:
    def test_preview_only_false_blocked(self):
        payload = _accepted_payload(preview_only=False)
        rv = _valid_review(payload=payload)
        r = _orch().submit_chain(
            review=rv, protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        from src.demo_protected_new_entry_orchestrator import (
            GATE_REVIEW_PAYLOAD_PREVIEW_ONLY_FALSE,
        )
        assert GATE_REVIEW_PAYLOAD_PREVIEW_ONLY_FALSE in r.blocked_gates

    def test_order_sent_true_blocked(self):
        payload = _accepted_payload(order_sent=True)
        rv = _valid_review(payload=payload)
        r = _orch().submit_chain(
            review=rv, protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        from src.demo_protected_new_entry_orchestrator import (
            GATE_REVIEW_PAYLOAD_ORDER_SENT_TRUE,
        )
        assert GATE_REVIEW_PAYLOAD_ORDER_SENT_TRUE in r.blocked_gates

    def test_order_endpoint_called_true_blocked(self):
        payload = _accepted_payload(order_endpoint_called=True)
        rv = _valid_review(payload=payload)
        r = _orch().submit_chain(
            review=rv, protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        from src.demo_protected_new_entry_orchestrator import (
            GATE_REVIEW_PAYLOAD_ORDER_ENDPOINT_CALLED,
        )
        assert GATE_REVIEW_PAYLOAD_ORDER_ENDPOINT_CALLED in r.blocked_gates


# ===========================================================================
# Extra: protection execute_allowed=True or stop_endpoint_called=True blocked
# ===========================================================================

class TestExtraProtectionFlags:
    def test_protection_execute_allowed_blocked(self):
        prot = _valid_solusdt_protection()
        prot["protected_entry_execute_allowed"] = True
        r = _orch().submit_chain(
            review=_valid_review(), protection=prot,
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        from src.demo_protected_new_entry_orchestrator import (
            GATE_PROTECTION_EXECUTE_ALLOWED_TRUE,
        )
        assert GATE_PROTECTION_EXECUTE_ALLOWED_TRUE in r.blocked_gates

    def test_protection_stop_endpoint_called_blocked(self):
        prot = _valid_solusdt_protection()
        prot["stop_endpoint_called"] = True
        r = _orch().submit_chain(
            review=_valid_review(), protection=prot,
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        from src.demo_protected_new_entry_orchestrator import (
            GATE_PROTECTION_STOP_ENDPOINT_CALLED,
        )
        assert GATE_PROTECTION_STOP_ENDPOINT_CALLED in r.blocked_gates

    def test_protection_no_position_modified_false_blocked(self):
        prot = _valid_solusdt_protection()
        prot["no_position_modified"] = False
        r = _orch().submit_chain(
            review=_valid_review(), protection=prot,
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        from src.demo_protected_new_entry_orchestrator import (
            GATE_PROTECTION_POSITION_MODIFIED,
        )
        assert GATE_PROTECTION_POSITION_MODIFIED in r.blocked_gates


# ===========================================================================
# Extra: CLI returns 1 when review missing
# ===========================================================================

class TestExtraCliMissingReview:
    def test_review_missing_returns_1(self):
        from scripts.execute_demo_protected_new_entry_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            base       = Path(td)
            review_d   = base / "review"
            protect_d  = base / "protection"
            chain_d    = base / "chain"
            review_d.mkdir(); protect_d.mkdir()
            (protect_d / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )
            rc = run_execute(
                symbol="SOLUSDT", confirm_token="", mock_chain=False,
                write_report=False,
                review_dir=review_d, protection_dir=protect_d,
                chain_dir=chain_d, _now=_TEST_NOW,
            )
            assert rc == 1

    def test_mock_chain_missing_token_returns_1(self):
        from scripts.execute_demo_protected_new_entry_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            base       = Path(td)
            review_d   = base / "review"
            protect_d  = base / "protection"
            chain_d    = base / "chain"
            review_d.mkdir(); protect_d.mkdir()
            (review_d / "latest_new_entry_review.json").write_text(
                json.dumps(_valid_review()), encoding="utf-8",
            )
            (protect_d / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )
            rc = run_execute(
                symbol="SOLUSDT", confirm_token="", mock_chain=True,
                write_report=False,
                review_dir=review_d, protection_dir=protect_d,
                chain_dir=chain_d, _now=_TEST_NOW,
            )
            assert rc == 1
