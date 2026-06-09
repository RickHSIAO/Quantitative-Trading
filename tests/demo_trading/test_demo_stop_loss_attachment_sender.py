"""
tests/demo_trading/test_demo_stop_loss_attachment_sender.py
TASK-014R: Demo Stop-loss Attachment Sender tests (R1 - R25).

Covers: gate failures (missing protection / symbol mismatch / missing
realtime guard / missing stop_price / wrong stop direction / invalid qty /
invalid token), valid dry-run payload preview, mock execution synthetic
envelope, payload composition (stopLoss + symbol but excludes
takeProfit / leverage / transfer / withdraw / deposit), no network at all,
no live endpoint, no secrets, no import of forbidden modules, and CLI
artifact writing.
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
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_stop_loss_attachment_sender import (
    DemoStopLossAttachmentSender,
    GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK,
    GATE_INVALID_ENTRY_REFERENCE_PRICE,
    GATE_INVALID_QTY,
    GATE_INVALID_SIDE,
    GATE_INVALID_STOP_ORDER_SIDE,
    GATE_LONG_STOP_NOT_BELOW_ENTRY,
    GATE_MISSING_REALTIME_PRICE_GUARD,
    GATE_MISSING_STOP_PRICE,
    GATE_ORDER_ENDPOINT_CALLED_TRUE,
    GATE_PROTECTION_PREVIEW_ONLY_FALSE,
    GATE_PROTECTION_REPORT_MISSING,
    GATE_PROTECTION_STATUS_NOT_PREVIEW_ONLY,
    GATE_REVIEW_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_MISMATCH,
    GATE_SHORT_STOP_NOT_ABOVE_ENTRY,
    GATE_STOP_ENDPOINT_CALLED_TRUE,
    GATE_STOP_LOSS_ATTACH_NOT_REQUIRED,
    GATE_UNEXPECTED_PROTECTED_ENTRY_EXECUTE,
    GATE_UNEXPECTED_STOP_LOSS_ENDPOINT_ALLOWED,
    STATUS_DRY_RUN_ALLOWED,
    STATUS_FAIL_CLOSED,
    STATUS_MOCK_BLOCKED,
    STATUS_MOCK_SUCCESS,
    STOP_ATTACH_ENDPOINT,
    DemoStopLossAttachmentSender as _SenderRef,  # alias for clarity
)


_MODULE_PATH = ROOT / "src" / "demo_stop_loss_attachment_sender.py"
_SCRIPT_PATH = ROOT / "scripts" / "execute_demo_stop_loss_attachment.py"
_TEST_NOW    = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
_TODAY_TOKEN = "CONFIRM_DEMO_STOP_ATTACH_20260609"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _valid_solusdt_protection() -> dict:
    """A TASK-014Q-shaped protection report for SOLUSDT long, mirrors module schema."""
    return {
        "timestamp":                       "2026-06-09T11:00:00Z",
        "timestamp_utc":                   "2026-06-09T11:00:00Z",
        "selected_symbol":                 "SOLUSDT",
        "selected_side":                   "long",
        "order_side":                      "Buy",
        "selected_qty":                    12.0,
        "entry_reference_price":           66.21,
        "stop_price":                      62.7,
        "stop_order_side":                 "Sell",
        "stop_trigger_direction":          "fall_below_entry",
        "realtime_price_guard_verified":   True,
        "review_fail_closed":              False,
        "review_timestamp":                "2026-06-09T10:30:00Z",
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
        "next_required_task":              "TASK-014R_stop_loss_attachment_sender",
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


def _read_code_only(path: Path) -> str:
    """Return source with string literals + comments stripped (via tokenize)."""
    tokens = []
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


# ---------------------------------------------------------------------------
# R1: missing protection report => fail closed
# ---------------------------------------------------------------------------

class TestR1MissingProtectionReport:
    def test_none_protection_fails_closed(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=None, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert result.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_REPORT_MISSING in result.blocked_gates
        assert result.stop_endpoint_called is False
        assert result.order_endpoint_called is False
        assert result.no_orders_sent is True

    def test_empty_dict_protection_fails_closed(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection={}, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_REPORT_MISSING in result.blocked_gates


# ---------------------------------------------------------------------------
# R2: symbol mismatch => fail closed
# ---------------------------------------------------------------------------

class TestR2SymbolMismatch:
    def test_symbol_mismatch_blocked(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(), symbol="AAVEUSDT",
            _now=_TEST_NOW,
        )
        assert GATE_SELECTED_SYMBOL_MISMATCH in result.blocked_gates
        assert result.status != STATUS_DRY_RUN_ALLOWED

    def test_empty_symbol_blocked(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(), symbol="",
            _now=_TEST_NOW,
        )
        assert GATE_SELECTED_SYMBOL_MISMATCH in result.blocked_gates


# ---------------------------------------------------------------------------
# R3: missing realtime guard => fail closed
# ---------------------------------------------------------------------------

class TestR3MissingRealtimeGuard:
    def test_guard_false_blocked(self):
        prot = _valid_solusdt_protection()
        prot["realtime_price_guard_verified"] = False
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_MISSING_REALTIME_PRICE_GUARD in result.blocked_gates

    def test_guard_missing_key_blocked(self):
        prot = _valid_solusdt_protection()
        del prot["realtime_price_guard_verified"]
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_MISSING_REALTIME_PRICE_GUARD in result.blocked_gates


# ---------------------------------------------------------------------------
# R4: missing stop_price => fail closed
# ---------------------------------------------------------------------------

class TestR4MissingStopPrice:
    @pytest.mark.parametrize("stop_value", [0.0, 0, -1.0, None])
    def test_missing_stop_price_blocked(self, stop_value):
        prot = _valid_solusdt_protection()
        prot["stop_price"] = stop_value
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_MISSING_STOP_PRICE in result.blocked_gates


# ---------------------------------------------------------------------------
# R5: long stop above/equal entry => fail closed
# ---------------------------------------------------------------------------

class TestR5LongStopMustBeBelowEntry:
    def test_long_stop_above_entry_blocked(self):
        prot = _valid_solusdt_protection()
        prot["stop_price"] = 70.0  # above entry 66.21
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_LONG_STOP_NOT_BELOW_ENTRY in result.blocked_gates

    def test_long_stop_equal_entry_blocked(self):
        prot = _valid_solusdt_protection()
        prot["stop_price"] = 66.21  # equal
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_LONG_STOP_NOT_BELOW_ENTRY in result.blocked_gates


# ---------------------------------------------------------------------------
# R6: short stop below/equal entry => fail closed
# ---------------------------------------------------------------------------

class TestR6ShortStopMustBeAboveEntry:
    def test_short_stop_below_entry_blocked(self):
        prot = _valid_avaxusdt_short_protection()
        prot["stop_price"] = 25.0  # below entry 30.0
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="AVAXUSDT", _now=_TEST_NOW,
        )
        assert GATE_SHORT_STOP_NOT_ABOVE_ENTRY in result.blocked_gates

    def test_short_stop_equal_entry_blocked(self):
        prot = _valid_avaxusdt_short_protection()
        prot["stop_price"] = 30.0
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="AVAXUSDT", _now=_TEST_NOW,
        )
        assert GATE_SHORT_STOP_NOT_ABOVE_ENTRY in result.blocked_gates

    def test_short_stop_above_entry_passes_direction_check(self):
        prot = _valid_avaxusdt_short_protection()
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="AVAXUSDT", _now=_TEST_NOW,
        )
        assert GATE_SHORT_STOP_NOT_ABOVE_ENTRY not in result.blocked_gates
        assert GATE_LONG_STOP_NOT_BELOW_ENTRY not in result.blocked_gates


# ---------------------------------------------------------------------------
# R7: invalid qty => fail closed
# ---------------------------------------------------------------------------

class TestR7InvalidQty:
    @pytest.mark.parametrize("qty", [0.0, 0, -1.0, "abc"])
    def test_invalid_qty_blocked(self, qty):
        prot = _valid_solusdt_protection()
        prot["selected_qty"] = qty
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_INVALID_QTY in result.blocked_gates

    def test_invalid_entry_price_blocked(self):
        prot = _valid_solusdt_protection()
        prot["entry_reference_price"] = 0.0
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_INVALID_ENTRY_REFERENCE_PRICE in result.blocked_gates


# ---------------------------------------------------------------------------
# R8: invalid token for mock => fail closed
# ---------------------------------------------------------------------------

class TestR8InvalidConfirmTokenForMock:
    def test_no_token_in_mock_mode_blocked(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token="",
            mock_execute_stop=True, _now=_TEST_NOW,
        )
        assert GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK in result.blocked_gates
        assert result.confirm_token_valid is False
        assert result.status == STATUS_MOCK_BLOCKED

    def test_wrong_token_format_in_mock_mode_blocked(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token="WRONG_TOKEN",
            mock_execute_stop=True, _now=_TEST_NOW,
        )
        assert GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK in result.blocked_gates

    def test_wrong_date_token_in_mock_mode_blocked(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT",
            confirm_token="CONFIRM_DEMO_STOP_ATTACH_20200101",
            mock_execute_stop=True, _now=_TEST_NOW,
        )
        assert GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK in result.blocked_gates

    def test_no_token_required_for_dry_run(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token="",
            mock_execute_stop=False, _now=_TEST_NOW,
        )
        assert GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK not in result.blocked_gates


# ---------------------------------------------------------------------------
# R9: valid dry-run SOLUSDT creates payload preview
# ---------------------------------------------------------------------------

class TestR9ValidDryRunPayloadPreview:
    def test_valid_dry_run_solusdt(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert result.blocked_gates == []
        assert result.status == STATUS_DRY_RUN_ALLOWED
        assert result.mode == "dry_run"
        assert result.payload_preview_only is True
        assert result.selected_symbol == "SOLUSDT"
        assert result.selected_side == "long"
        assert result.stop_order_side == "Sell"
        assert result.qty == 12.0
        assert result.entry_reference_price == 66.21
        assert result.stop_price == 62.7
        assert result.execute_requested is False
        assert result.mock_execute_requested is False
        assert result.mock_stop_attached is False


# ---------------------------------------------------------------------------
# R10: dry-run does not call stop endpoint
# ---------------------------------------------------------------------------

class TestR10DryRunNoStopEndpointCall:
    def test_dry_run_invariants(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert result.stop_endpoint_called is False
        assert result.order_endpoint_called is False
        assert result.no_orders_sent is True
        assert result.no_position_modified is True
        assert result.no_live_endpoint is True
        assert result.no_batch_order is True
        assert result.no_close_only_path is True

    def test_dry_run_does_not_open_socket(self, monkeypatch):
        """If we accidentally try to use urllib it would fail this test."""
        import urllib.request as urlreq
        sentinel = {"called": False}

        def _boom(*args, **kwargs):
            sentinel["called"] = True
            raise RuntimeError("urlopen should never be called")

        monkeypatch.setattr(urlreq, "urlopen", _boom, raising=True)
        DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert sentinel["called"] is False


# ---------------------------------------------------------------------------
# R11 / R12: mock-execute-stop does not call stop endpoint + MOCK_SUCCESS
# ---------------------------------------------------------------------------

class TestR11R12MockExecuteStop:
    def test_mock_execute_stop_no_socket(self, monkeypatch):
        import urllib.request as urlreq
        sentinel = {"called": False}

        def _boom(*args, **kwargs):
            sentinel["called"] = True
            raise RuntimeError("urlopen should never be called")

        monkeypatch.setattr(urlreq, "urlopen", _boom, raising=True)
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_execute_stop=True, _now=_TEST_NOW,
        )
        assert sentinel["called"] is False
        assert result.stop_endpoint_called is False
        assert result.order_endpoint_called is False
        assert result.no_position_modified is True
        assert result.no_orders_sent is True

    def test_mock_execute_returns_mock_success(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_execute_stop=True, _now=_TEST_NOW,
        )
        assert result.status == STATUS_MOCK_SUCCESS
        assert result.mode == "mock_execute_stop"
        assert result.mock_execute_requested is True
        assert result.mock_stop_attached is True
        assert result.mock_response.get("retCode") == 0
        assert result.mock_response.get("mock") is True
        assert "stop_attach_id" in result.mock_response.get("result", {})
        assert result.confirm_token_valid is True
        assert result.blocked_gates == []


# ---------------------------------------------------------------------------
# R13: payload includes stopLoss and symbol
# ---------------------------------------------------------------------------

class TestR13PayloadIncludesStopLossAndSymbol:
    def test_payload_keys_present(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        p = result.payload_preview
        assert p["symbol"] == "SOLUSDT"
        assert p["stopLoss"] == "62.7"
        assert p["category"] == "linear"
        assert p["tpslMode"] == "Full"
        assert p["slTriggerBy"] in ("MarkPrice", "LastPrice")
        assert "positionIdx" in p


# ---------------------------------------------------------------------------
# R14: payload excludes takeProfit
# ---------------------------------------------------------------------------

class TestR14PayloadExcludesTakeProfit:
    def test_takeprofit_not_in_payload(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        for k in result.payload_preview.keys():
            assert "take" not in k.lower()
            assert "tp" != k.lower()
            assert "tpsl" not in k.lower() or k == "tpslMode"  # tpslMode is allowed


# ---------------------------------------------------------------------------
# R15: payload excludes leverage
# ---------------------------------------------------------------------------

class TestR15PayloadExcludesLeverage:
    def test_leverage_not_in_payload(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        for k in result.payload_preview.keys():
            assert "leverage" not in k.lower()


# ---------------------------------------------------------------------------
# R16: payload excludes transfer/withdraw/deposit
# ---------------------------------------------------------------------------

class TestR16PayloadExcludesTransferWithdrawDeposit:
    def test_payload_no_transfer_words(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        for k in result.payload_preview.keys():
            kl = k.lower()
            assert "transfer" not in kl
            assert "withdraw" not in kl
            assert "deposit" not in kl


# ---------------------------------------------------------------------------
# R17: no order create endpoint called (code-only scan)
# ---------------------------------------------------------------------------

class TestR17NoOrderCreateEndpointCalled:
    def test_module_does_not_call_order_create(self):
        code = _read_code_only(_MODULE_PATH)
        # The constant ORDER_CREATE_ENDPOINT is defined as a string, but only
        # appears in the string literal "/v5/order/create" (filtered out) and
        # the bare name ORDER_CREATE_ENDPOINT in __all__.  We assert that no
        # network-call expressions reference it.
        assert "urlopen" not in code
        assert "requests" not in code
        assert "httpx" not in code
        assert "session.post" not in code
        assert "session.get" not in code

    def test_no_v5_order_create_call_expressions(self):
        # Walk AST and ensure no Call node has a string arg containing
        # "/v5/order/create" -- since the constant is never used in a Call.
        src = _MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for a in node.args:
                    if (isinstance(a, ast.Constant)
                            and isinstance(a.value, str)
                            and "/v5/order/create" in a.value):
                        pytest.fail("order-create endpoint passed to a Call")
                    if isinstance(a, ast.Name) and a.id == "ORDER_CREATE_ENDPOINT":
                        pytest.fail("ORDER_CREATE_ENDPOINT passed to a Call")


# ---------------------------------------------------------------------------
# R18: no live endpoint fallback
# ---------------------------------------------------------------------------

class TestR18NoLiveEndpointFallback:
    def test_no_live_host_string(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            src = path.read_text(encoding="utf-8")
            assert "api.bybit.com" not in src
            assert "api-testnet.bybit.com" not in src

    def test_module_no_socket_imports(self):
        src = _MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        forbidden = {"urllib", "urllib.request", "requests", "httpx",
                     "socket", "http.client"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden, (
                        f"forbidden import: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden, (
                    f"forbidden from-import: {node.module}"
                )


# ---------------------------------------------------------------------------
# R19: no secrets in report / no env reads / no signing
# ---------------------------------------------------------------------------

class TestR19NoSecrets:
    def test_no_env_reads_in_code(self):
        code = _read_code_only(_MODULE_PATH)
        assert "os.environ" not in code
        assert "getenv" not in code
        assert "dotenv" not in code

    def test_no_hmac_or_signing(self):
        code = _read_code_only(_MODULE_PATH)
        assert "hmac" not in code.lower()
        assert "X-BAPI-SIGN" not in code  # could be in strings; check code only
        assert "X_BAPI_SIGN" not in code

    def test_result_does_not_leak_secret_substrings(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT",
            confirm_token=_TODAY_TOKEN,
            mock_execute_stop=True, _now=_TEST_NOW,
        )
        blob = json.dumps(result.to_dict())
        assert "BYBIT_DEMO_API_KEY" not in blob
        assert "BYBIT_DEMO_API_SECRET" not in blob
        assert "X-BAPI-SIGN" not in blob
        assert "X-BAPI-API-KEY" not in blob
        # token in result is prefix-only
        assert _TODAY_TOKEN not in blob


# ---------------------------------------------------------------------------
# R20: no import main.py / src/risk.py / BybitExecutor
# ---------------------------------------------------------------------------

class TestR20NoForbiddenImports:
    @pytest.mark.parametrize("forbidden", [
        "main",
        "src.risk",
        "BybitExecutor",
        "pybit",
        "src.bybit_executor",
        "src.demo_close_only_sender",
        "src.demo_new_entry_sender",
        "src.demo_emergency_close_sender",
        "scripts.execute_demo_new_entry",
        "scripts.execute_demo_close_only",
        "scripts.execute_demo_emergency_close",
    ])
    def test_module_does_not_import(self, forbidden):
        src = _MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != forbidden
            elif isinstance(node, ast.ImportFrom):
                assert node.module != forbidden


# ---------------------------------------------------------------------------
# R21: no new-entry sender reuse
# ---------------------------------------------------------------------------

class TestR21NoNewEntrySenderReuse:
    def test_module_does_not_reuse_new_entry_sender(self):
        code = _read_code_only(_MODULE_PATH)
        assert "DemoNewEntrySender" not in code
        assert "submit_one_new_entry" not in code


# ---------------------------------------------------------------------------
# R22: no emergency close sender reuse
# ---------------------------------------------------------------------------

class TestR22NoEmergencyCloseSenderReuse:
    def test_module_does_not_reuse_emergency_close(self):
        code = _read_code_only(_MODULE_PATH)
        assert "EmergencyClose" not in code
        assert "demo_emergency_close" not in code


# ---------------------------------------------------------------------------
# R23: no close-only sender reuse
# ---------------------------------------------------------------------------

class TestR23NoCloseOnlySenderReuse:
    def test_module_does_not_reuse_close_only(self):
        code = _read_code_only(_MODULE_PATH)
        assert "CloseOnlySender" not in code
        assert "demo_close_only" not in code


# ---------------------------------------------------------------------------
# R24: report artifacts are written
# ---------------------------------------------------------------------------

class TestR24ReportArtifactsWritten:
    def test_cli_writes_json_and_md(self):
        from scripts.execute_demo_stop_loss_attachment import run_execute
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            prot_dir = base / "protection"
            prot_dir.mkdir()
            (prot_dir / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )
            att_dir = base / "attachment"
            rc = run_execute(
                symbol="SOLUSDT",
                confirm_token="",
                mock_execute_stop=False,
                write_report=True,
                protection_dir=prot_dir,
                attachment_dir=att_dir,
                _now=_TEST_NOW,
            )
            assert rc == 0
            assert (att_dir / "latest_stop_loss_attachment.json").exists()
            assert (att_dir / "latest_stop_loss_attachment.md").exists()
            data = json.loads(
                (att_dir / "latest_stop_loss_attachment.json")
                .read_text(encoding="utf-8")
            )
            assert data["selected_symbol"] == "SOLUSDT"
            assert data["status"] == STATUS_DRY_RUN_ALLOWED
            assert data["stop_endpoint_called"] is False
            assert data["order_endpoint_called"] is False
            assert data["mock_execute_requested"] is False

    def test_cli_missing_protection_returns_1(self):
        from scripts.execute_demo_stop_loss_attachment import run_execute
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            prot_dir = base / "missing_protection"
            prot_dir.mkdir()
            att_dir = base / "attachment"
            rc = run_execute(
                symbol="SOLUSDT",
                confirm_token="",
                mock_execute_stop=False,
                write_report=False,
                protection_dir=prot_dir,
                attachment_dir=att_dir,
                _now=_TEST_NOW,
            )
            assert rc == 1

    def test_cli_mock_execute_writes_mock_success(self):
        from scripts.execute_demo_stop_loss_attachment import run_execute
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            prot_dir = base / "protection"
            prot_dir.mkdir()
            (prot_dir / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )
            att_dir = base / "attachment"
            rc = run_execute(
                symbol="SOLUSDT",
                confirm_token=_TODAY_TOKEN,
                mock_execute_stop=True,
                write_report=True,
                protection_dir=prot_dir,
                attachment_dir=att_dir,
                _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads(
                (att_dir / "latest_stop_loss_attachment.json")
                .read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_MOCK_SUCCESS
            assert data["mock_stop_attached"] is True
            assert data["stop_endpoint_called"] is False
            assert data["no_position_modified"] is True


# ---------------------------------------------------------------------------
# R25: source scan confirms no urllib/request/httpx network call in mock mode
# ---------------------------------------------------------------------------

class TestR25SourceScanNoNetworkInMockMode:
    def test_code_only_scan_clean(self):
        code = _read_code_only(_MODULE_PATH)
        forbidden_tokens = (
            "urlopen", "urllib", "requests", "httpx",
            "http.client", "socket",
            "session.post", "session.get",
            "Session(", "urllib3",
        )
        for tok in forbidden_tokens:
            assert tok not in code, f"forbidden code token observed: {tok}"

    def test_script_no_socket_imports(self):
        src = _SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in {
                        "urllib", "urllib.request", "requests", "httpx",
                        "socket", "http.client",
                    }
            elif isinstance(node, ast.ImportFrom):
                assert node.module not in {
                    "urllib", "urllib.request", "requests", "httpx",
                    "socket", "http.client",
                }


# ---------------------------------------------------------------------------
# Extra: additional gate coverage to satisfy spec gates B-6/7
# ---------------------------------------------------------------------------

class TestExtraProtectionFlagsEnforced:
    def test_preview_only_false_blocked(self):
        prot = _valid_solusdt_protection()
        prot["preview_only"] = False
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_PREVIEW_ONLY_FALSE in result.blocked_gates

    def test_stop_loss_endpoint_allowed_true_blocked(self):
        prot = _valid_solusdt_protection()
        prot["stop_loss_endpoint_allowed"] = True
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_UNEXPECTED_STOP_LOSS_ENDPOINT_ALLOWED in result.blocked_gates

    def test_protected_entry_execute_allowed_true_blocked(self):
        prot = _valid_solusdt_protection()
        prot["protected_entry_execute_allowed"] = True
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_UNEXPECTED_PROTECTED_ENTRY_EXECUTE in result.blocked_gates

    def test_stop_loss_attach_not_required_blocked(self):
        prot = _valid_solusdt_protection()
        prot["stop_loss_attach_required"] = False
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_STOP_LOSS_ATTACH_NOT_REQUIRED in result.blocked_gates

    def test_review_fail_closed_true_blocked(self):
        prot = _valid_solusdt_protection()
        prot["review_fail_closed"] = True
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_REVIEW_FAIL_CLOSED in result.blocked_gates

    def test_protection_status_not_preview_only_blocked(self):
        prot = _valid_solusdt_protection()
        prot["protected_entry_status"] = "FAIL_CLOSED"
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_STATUS_NOT_PREVIEW_ONLY in result.blocked_gates

    def test_protection_order_endpoint_called_true_blocked(self):
        prot = _valid_solusdt_protection()
        prot["order_endpoint_called"] = True
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_ORDER_ENDPOINT_CALLED_TRUE in result.blocked_gates

    def test_protection_stop_endpoint_called_true_blocked(self):
        prot = _valid_solusdt_protection()
        prot["stop_endpoint_called"] = True
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_STOP_ENDPOINT_CALLED_TRUE in result.blocked_gates

    def test_invalid_stop_order_side_long_blocked(self):
        prot = _valid_solusdt_protection()
        prot["stop_order_side"] = "Buy"  # wrong for long
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_INVALID_STOP_ORDER_SIDE in result.blocked_gates

    def test_invalid_stop_order_side_short_blocked(self):
        prot = _valid_avaxusdt_short_protection()
        prot["stop_order_side"] = "Sell"  # wrong for short
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="AVAXUSDT", _now=_TEST_NOW,
        )
        assert GATE_INVALID_STOP_ORDER_SIDE in result.blocked_gates

    def test_invalid_side_blocked(self):
        prot = _valid_solusdt_protection()
        prot["selected_side"] = "sideways"
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_INVALID_SIDE in result.blocked_gates


# ---------------------------------------------------------------------------
# Extra: result.to_dict round-trips key invariants
# ---------------------------------------------------------------------------

class TestResultDictRoundTrip:
    def test_to_dict_has_safety_invariant_keys(self):
        result = DemoStopLossAttachmentSender().submit_stop_attachment(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        d = result.to_dict()
        for key in [
            "selected_symbol", "selected_side", "qty",
            "entry_reference_price", "stop_price", "stop_order_side",
            "stop_trigger_direction", "endpoint_family",
            "stop_attach_endpoint", "payload_preview",
            "execute_requested", "mock_execute_requested", "mock_stop_attached",
            "stop_endpoint_called", "order_endpoint_called",
            "no_orders_sent", "no_position_modified",
            "secret_value_observed", "blocked_gates", "status",
        ]:
            assert key in d
        assert d["stop_attach_endpoint"] == STOP_ATTACH_ENDPOINT


# ---------------------------------------------------------------------------
# Extra: CLI subprocess smoke (exit codes only; no network)
# ---------------------------------------------------------------------------

class TestCliSubprocessSmoke:
    def test_cli_runs_with_missing_protection_exits_1(self):
        env = os.environ.copy()
        env["PYTHONPATH"]       = str(ROOT)
        env["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run(
                [sys.executable, str(_SCRIPT_PATH),
                 "--from-latest-protection", "--symbol", "SOLUSDT"],
                cwd=td,
                env=env, capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
        assert result.returncode == 1
        assert "FAIL CLOSED" in result.stdout
