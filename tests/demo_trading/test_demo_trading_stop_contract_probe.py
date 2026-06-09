"""
tests/demo_trading/test_demo_trading_stop_contract_probe.py
TASK-014T: Demo Trading-stop Endpoint Contract Probe tests (T1 - T28+).

Covers contract preview / mock-permission / real-probe-guard paths,
payload validation, gate failures, source-scan safety (no urlopen / no
forbidden imports / no secrets), report artifacts, and the invariant
that TASK-014L sender G20 (protected_entry_policy_missing) still blocks
--execute-new-entry.
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

from src.demo_trading_stop_contract_probe import (
    BASE_URL_DEMO,
    CATEGORY_LINEAR,
    DemoTradingStopContractProbe,
    ENDPOINT_FAMILY,
    GATE_INVALID_CATEGORY,
    GATE_INVALID_CONFIRM_TOKEN,
    GATE_INVALID_POSITION_IDX,
    GATE_INVALID_SL_TRIGGER_BY,
    GATE_INVALID_TPSL_MODE,
    GATE_MISSING_STOP_LOSS,
    GATE_NON_POSITIVE_STOP_LOSS,
    GATE_PAYLOAD_INCLUDES_LEVERAGE,
    GATE_PAYLOAD_INCLUDES_LIVE_HOSTNAME,
    GATE_PAYLOAD_INCLUDES_ORDER_FIELDS,
    GATE_PAYLOAD_INCLUDES_ORDER_PATH,
    GATE_PAYLOAD_INCLUDES_TAKE_PROFIT,
    GATE_PAYLOAD_INCLUDES_TRANSFER,
    GATE_PROTECTION_REPORT_MISSING,
    GATE_REAL_PROBE_NOT_IMPL,
    GATE_SYMBOL_MISMATCH,
    MODE_MOCK_PERMISSION,
    MODE_PREVIEW,
    MODE_REAL_PERMISSION_PROBE,
    ORDER_CREATE_PATH,
    POSITION_IDX_ONE_WAY,
    SL_TRIGGER_LAST_PRICE,
    SL_TRIGGER_MARK_PRICE,
    STATUS_FAIL_CLOSED,
    STATUS_MOCK_PERMISSION_OK,
    STATUS_PREVIEW_OK,
    STATUS_REAL_PROBE_NOT_IMPL,
    TPSL_MODE_FULL,
    TRADING_STOP_METHOD,
    TRADING_STOP_PATH,
    TradingStopContractResult,
    build_payload_preview,
    validate_payload,
)


_MODULE_PATH = ROOT / "src" / "demo_trading_stop_contract_probe.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_trading_stop_contract.py"
_TEST_NOW    = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
_TODAY_TOKEN = "CONFIRM_DEMO_TRADING_STOP_PROBE_20260610"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _valid_solusdt_protection() -> dict:
    return {
        "timestamp":                       "2026-06-10T11:00:00Z",
        "timestamp_utc":                   "2026-06-10T11:00:00Z",
        "selected_symbol":                 "SOLUSDT",
        "selected_side":                   "long",
        "order_side":                      "Buy",
        "selected_qty":                    12.3,
        "entry_reference_price":           64.87,
        "stop_price":                      61.63,
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
        "next_required_task":              "TASK-014T_real_demo_trading_stop_endpoint_probe",
    }


def _read_code_only(path: Path) -> str:
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


def _probe() -> DemoTradingStopContractProbe:
    return DemoTradingStopContractProbe()


# ===========================================================================
# T1: valid SOLUSDT contract preview PASS
# ===========================================================================

class TestT1ContractPreviewOK:
    def test_solusdt_preview_ok(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert r.status == STATUS_PREVIEW_OK
        assert r.mode == MODE_PREVIEW
        assert r.selected_symbol == "SOLUSDT"
        assert r.stop_loss == pytest.approx(61.63)
        assert r.blocked_gates == []
        # Contract description
        assert r.endpoint_family == ENDPOINT_FAMILY
        assert r.path == TRADING_STOP_PATH
        assert r.method == TRADING_STOP_METHOD
        assert r.category == CATEGORY_LINEAR
        assert r.tpsl_mode == TPSL_MODE_FULL
        assert r.sl_trigger_by == SL_TRIGGER_MARK_PRICE
        assert r.position_idx == POSITION_IDX_ONE_WAY
        # Safety
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_orders_sent is True


# ===========================================================================
# T2: missing protection report => fail closed
# ===========================================================================

class TestT2MissingProtection:
    def test_none_protection(self):
        r = _probe().submit_contract_probe(
            protection=None, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_REPORT_MISSING in r.blocked_gates
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True

    def test_empty_protection(self):
        r = _probe().submit_contract_probe(
            protection={}, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_PROTECTION_REPORT_MISSING in r.blocked_gates


# ===========================================================================
# T3: symbol mismatch => fail closed
# ===========================================================================

class TestT3SymbolMismatch:
    def test_symbol_mismatch(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="AAVEUSDT", _now=_TEST_NOW,
        )
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SYMBOL_MISMATCH in r.blocked_gates

    def test_empty_symbol(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="", _now=_TEST_NOW,
        )
        assert GATE_SYMBOL_MISMATCH in r.blocked_gates


# ===========================================================================
# T4: missing stopLoss => fail closed
# ===========================================================================

class TestT4MissingStopLoss:
    def test_protection_missing_stop_price(self):
        prot = _valid_solusdt_protection()
        del prot["stop_price"]
        r = _probe().submit_contract_probe(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_NON_POSITIVE_STOP_LOSS in r.blocked_gates
        assert r.status == STATUS_FAIL_CLOSED

    def test_validate_payload_missing_stoploss(self):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=10.0)
        del payload["stopLoss"]
        assert GATE_MISSING_STOP_LOSS in validate_payload(payload)


# ===========================================================================
# T5: stopLoss <= 0 => fail closed
# ===========================================================================

class TestT5StopLossNonPositive:
    @pytest.mark.parametrize("stop", [0.0, 0, -1.0])
    def test_non_positive_stop(self, stop):
        prot = _valid_solusdt_protection()
        prot["stop_price"] = stop
        r = _probe().submit_contract_probe(
            protection=prot, symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert GATE_NON_POSITIVE_STOP_LOSS in r.blocked_gates


# ===========================================================================
# T6: invalid tpslMode => fail closed (validate_payload)
# ===========================================================================

class TestT6InvalidTpslMode:
    def test_invalid_tpsl_mode(self):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        payload["tpslMode"] = "Partial"
        gates = validate_payload(payload)
        assert GATE_INVALID_TPSL_MODE in gates


# ===========================================================================
# T7: invalid slTriggerBy => fail closed
# ===========================================================================

class TestT7InvalidSlTriggerBy:
    def test_invalid_trigger(self):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        payload["slTriggerBy"] = "IndexPrice"
        assert GATE_INVALID_SL_TRIGGER_BY in validate_payload(payload)

    def test_last_price_accepted(self):
        payload = build_payload_preview(
            symbol="SOLUSDT", stop_loss=61.63,
            sl_trigger_by=SL_TRIGGER_LAST_PRICE,
        )
        assert GATE_INVALID_SL_TRIGGER_BY not in validate_payload(payload)


# ===========================================================================
# T8: invalid positionIdx => fail closed
# ===========================================================================

class TestT8InvalidPositionIdx:
    @pytest.mark.parametrize("idx", [1, 2, -1])
    def test_invalid_position_idx(self, idx):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        payload["positionIdx"] = idx
        assert GATE_INVALID_POSITION_IDX in validate_payload(payload)


# ===========================================================================
# T9: payload excludes takeProfit
# ===========================================================================

class TestT9PayloadExcludesTakeProfit:
    def test_payload_default_excludes_tp(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        for key in ("takeProfit", "take_profit", "tpTriggerBy"):
            assert key not in r.payload_preview

    def test_validate_rejects_added_tp(self):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        payload["takeProfit"] = "70.0"
        assert GATE_PAYLOAD_INCLUDES_TAKE_PROFIT in validate_payload(payload)


# ===========================================================================
# T10: payload excludes leverage
# ===========================================================================

class TestT10PayloadExcludesLeverage:
    def test_payload_default_excludes_leverage(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        for key in ("leverage", "buyLeverage", "sellLeverage"):
            assert key not in r.payload_preview

    def test_validate_rejects_added_leverage(self):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        payload["leverage"] = "10"
        assert GATE_PAYLOAD_INCLUDES_LEVERAGE in validate_payload(payload)


# ===========================================================================
# T11: payload excludes transfer/withdraw/deposit
# ===========================================================================

class TestT11PayloadExcludesTransferFamily:
    @pytest.mark.parametrize("key,val",
        [("transfer", "1.0"), ("withdraw", "1.0"), ("deposit", "1.0"),
         ("transferAmount", "1.0"), ("withdrawAmount", "1.0"),
         ("depositAmount", "1.0")])
    def test_validate_rejects_funds_key(self, key, val):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        payload[key] = val
        assert GATE_PAYLOAD_INCLUDES_TRANSFER in validate_payload(payload)

    def test_default_excludes_transfer_family(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        for key in ("transfer", "withdraw", "deposit",
                    "transferAmount", "withdrawAmount", "depositAmount"):
            assert key not in r.payload_preview


# ===========================================================================
# T12: payload excludes side/qty/orderType
# ===========================================================================

class TestT12PayloadExcludesOrderFields:
    def test_default_excludes_order_fields(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        for key in ("side", "qty", "orderType", "order_type",
                    "price", "timeInForce", "reduceOnly"):
            assert key not in r.payload_preview

    @pytest.mark.parametrize("key,val",
        [("side", "Sell"), ("qty", "1"), ("orderType", "Market"),
         ("price", "60"), ("timeInForce", "GTC"), ("reduceOnly", True),
         ("order_type", "Market")])
    def test_validate_rejects_order_fields(self, key, val):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        payload[key] = val
        assert GATE_PAYLOAD_INCLUDES_ORDER_FIELDS in validate_payload(payload)


# ===========================================================================
# T13: no order-create endpoint in payload
# ===========================================================================

class TestT13NoOrderCreatePath:
    def test_validate_rejects_order_path_value(self):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        payload["category"] = CATEGORY_LINEAR  # keep valid
        payload["symbol"]   = ORDER_CREATE_PATH  # leak path into symbol value
        # ORDER_CREATE_PATH appears in a string value -> trips the gate.
        gates = validate_payload(payload)
        assert GATE_PAYLOAD_INCLUDES_ORDER_PATH in gates

    def test_default_payload_does_not_contain_order_path(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        for v in r.payload_preview.values():
            if isinstance(v, str):
                assert ORDER_CREATE_PATH not in v


# ===========================================================================
# T14: no live endpoint fallback
# ===========================================================================

class TestT14NoLiveEndpoint:
    def test_no_live_hostname_in_payload(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        # base_url is the demo host
        assert "api-demo.bybit.com" in r.base_url
        # No live hostname appears in any payload value
        for v in r.payload_preview.values():
            if isinstance(v, str):
                assert "api.bybit.com" not in v
                assert "api-testnet.bybit.com" not in v
        assert r.no_live_endpoint is True

    def test_validate_rejects_live_hostname_value(self):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        payload["symbol"] = "https://api.bybit.com/leak"
        assert GATE_PAYLOAD_INCLUDES_LIVE_HOSTNAME in validate_payload(payload)


# ===========================================================================
# T15: no secrets in report
# ===========================================================================

class TestT15NoSecretsInReport:
    def test_report_contains_no_secret_values(self):
        from scripts.preview_demo_trading_stop_contract import run_execute
        with tempfile.TemporaryDirectory() as td:
            base       = Path(td)
            protect_d  = base / "protection"
            contract_d = base / "contract"
            protect_d.mkdir()
            (protect_d / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )
            rc = run_execute(
                symbol="SOLUSDT", confirm_token="", mock_permission=False,
                allow_real_stop_probe=False, write_report=True,
                protection_dir=protect_d, contract_dir=contract_d,
                _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads(
                (contract_d / "latest_trading_stop_contract.json").read_text(
                    encoding="utf-8"
                )
            )
            assert data["secret_value_observed"] is False
            md = (contract_d / "latest_trading_stop_contract.md").read_text(
                encoding="utf-8"
            )
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API",
                              "X-BAPI-SIGN"):
                assert forbidden not in md


# ===========================================================================
# T16: no import of main.py / src/risk.py / BybitExecutor
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
    "src.demo_protected_new_entry_orchestrator",
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


class TestT16NoForbiddenImports:
    def test_module_imports(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, (
                f"Forbidden import {bad!r} in probe module"
            )

    def test_cli_imports(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, (
                f"Forbidden import {bad!r} in CLI script"
            )


# ===========================================================================
# T17: no close-only sender reuse
# ===========================================================================

class TestT17NoCloseOnlyReuse:
    def test_no_close_only(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoCloseOnlySender"   not in code
            assert "demo_close_only_sender" not in code


# ===========================================================================
# T18: no emergency-close sender called
# ===========================================================================

class TestT18NoEmergencyClose:
    def test_no_emergency_close(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoEmergencyCloseSender"   not in code
            assert "demo_emergency_close_sender" not in code

    def test_result_emergency_close_invoked_false(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert r.emergency_close_invoked is False


# ===========================================================================
# T19: no new-entry sender real execution called
# ===========================================================================

class TestT19NoNewEntrySender:
    def test_no_new_entry_sender(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoNewEntrySender"    not in code
            assert "demo_new_entry_sender" not in code


# ===========================================================================
# T20: no stop endpoint network call in preview mode
# ===========================================================================

class TestT20NoNetworkInPreview:
    def test_preview_no_network_calls(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True

    def test_module_does_not_open_sockets_on_import(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_trading_stop_contract_probe as m; "
             "print('OK', m.STATUS_PREVIEW_OK)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# T21: no stop endpoint network call in mock-permission mode
# ===========================================================================

class TestT21NoNetworkInMockPermission:
    def test_mock_permission_no_network(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_permission=True, _now=_TEST_NOW,
        )
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True


# ===========================================================================
# T22: mock-permission returns MOCK_TRADING_STOP_PERMISSION_OK
# ===========================================================================

class TestT22MockPermissionOK:
    def test_mock_permission_status(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            mock_permission=True, _now=_TEST_NOW,
        )
        assert r.status == STATUS_MOCK_PERMISSION_OK
        assert r.mode == MODE_MOCK_PERMISSION
        assert r.mock_permission_status is True
        assert r.mock_response["retCode"] == 0
        assert r.mock_response["mock"] is True
        assert r.mock_response["result"]["symbol"] == "SOLUSDT"
        assert r.blocked_gates == []


# ===========================================================================
# T23: --allow-real-stop-probe without implementation => REAL_PROBE_NOT_IMPL
# ===========================================================================

class TestT23RealProbeNotImplemented:
    def test_real_probe_returns_not_implemented(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
            allow_real_stop_probe=True, _now=_TEST_NOW,
        )
        assert r.status == STATUS_REAL_PROBE_NOT_IMPL
        assert r.mode == MODE_REAL_PERMISSION_PROBE
        assert r.real_probe_allowed is True
        assert r.real_probe_implemented is False
        assert GATE_REAL_PROBE_NOT_IMPL in r.blocked_gates
        # Safety invariants intact
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True


# ===========================================================================
# T24: invalid confirm token blocks real probe (and mock-permission)
# ===========================================================================

class TestT24InvalidConfirmToken:
    def test_real_probe_no_token(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token="",
            allow_real_stop_probe=True, _now=_TEST_NOW,
        )
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_INVALID_CONFIRM_TOKEN in r.blocked_gates

    def test_real_probe_wrong_date(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT",
            confirm_token="CONFIRM_DEMO_TRADING_STOP_PROBE_20200101",
            allow_real_stop_probe=True, _now=_TEST_NOW,
        )
        assert GATE_INVALID_CONFIRM_TOKEN in r.blocked_gates

    def test_real_probe_wrong_prefix(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT",
            confirm_token="CONFIRM_DEMO_STOP_ATTACH_20260610",
            allow_real_stop_probe=True, _now=_TEST_NOW,
        )
        assert GATE_INVALID_CONFIRM_TOKEN in r.blocked_gates

    def test_mock_permission_invalid_token(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", confirm_token="",
            mock_permission=True, _now=_TEST_NOW,
        )
        assert GATE_INVALID_CONFIRM_TOKEN in r.blocked_gates


# ===========================================================================
# T25: report artifacts written
# ===========================================================================

class TestT25ReportArtifacts:
    def test_writer_produces_all_files(self):
        from scripts.preview_demo_trading_stop_contract import run_execute
        with tempfile.TemporaryDirectory() as td:
            base       = Path(td)
            protect_d  = base / "protection"
            contract_d = base / "contract"
            protect_d.mkdir()
            (protect_d / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )
            rc = run_execute(
                symbol="SOLUSDT", confirm_token="", mock_permission=False,
                allow_real_stop_probe=False, write_report=True,
                protection_dir=protect_d, contract_dir=contract_d,
                _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in contract_d.iterdir())
            assert "latest_trading_stop_contract.json" in files
            assert "latest_trading_stop_contract.md"   in files
            ts_json = [n for n in files if n.endswith(".json")
                       and not n.startswith("latest_")]
            ts_md   = [n for n in files if n.endswith(".md")
                       and not n.startswith("latest_")]
            assert len(ts_json) == 1
            assert len(ts_md)   == 1
            data = json.loads(
                (contract_d / "latest_trading_stop_contract.json").read_text(
                    encoding="utf-8"
                )
            )
            assert data["status"] == STATUS_PREVIEW_OK
            assert data["selected_symbol"] == "SOLUSDT"
            assert data["path"] == TRADING_STOP_PATH
            assert data["method"] == TRADING_STOP_METHOD


# ===========================================================================
# T26: TASK-014L G20 still blocks --execute-new-entry
# ===========================================================================

class TestT26G20StillBlocks:
    def test_g20_constant_unchanged(self):
        from src.demo_new_entry_protection import G20_BLOCKED_GATE_NAME
        assert G20_BLOCKED_GATE_NAME == "protected_entry_policy_missing"

    def test_probe_does_not_lift_g20(self):
        code = _read_code_only(_MODULE_PATH)
        assert "protected_entry_policy_missing" not in code
        assert "G20_BLOCKED_GATE_NAME"          not in code


# ===========================================================================
# T27: source scan confirms no urllib/requests/httpx network call
# ===========================================================================

class TestT27UrlopenSentinelScan:
    def test_no_network_tokens_in_module_or_cli(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            for tok in ("urllib", "urlopen", "httpx",
                        "requests.", "http.client", "socket.",
                        "session.post", "session.get"):
                assert tok not in code, (
                    f"Network token {tok!r} present in {path.name}"
                )

    def test_no_env_or_signing_in_module(self):
        code = _read_code_only(_MODULE_PATH)
        assert "os.environ" not in code
        assert "getenv"     not in code
        assert "dotenv"     not in code
        assert "hmac"       not in code.lower()
        assert "hashlib"    not in code.lower()
        assert "BYBIT_API"  not in code
        assert "API_KEY"    not in code
        assert "API_SECRET" not in code


# ===========================================================================
# T28: full payload contract fields match TASK-014R stop attachment payload
# ===========================================================================

class TestT28PayloadMatchesTask014R:
    def test_keys_match_task_014r(self):
        from src.demo_stop_loss_attachment_sender import (
            _build_payload_preview as r_build_payload,
        )
        t_payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        r_payload = r_build_payload(symbol="SOLUSDT", stop_price=61.63)
        # Same keys, same values.
        assert set(t_payload.keys()) == set(r_payload.keys())
        for k in t_payload:
            assert t_payload[k] == r_payload[k], (
                f"Key {k!r} differs between TASK-014T and TASK-014R: "
                f"{t_payload[k]!r} vs {r_payload[k]!r}"
            )

    def test_endpoint_constants_match(self):
        from src.demo_stop_loss_attachment_sender import (
            STOP_ATTACH_ENDPOINT as R_STOP_PATH,
        )
        assert TRADING_STOP_PATH == R_STOP_PATH


# ===========================================================================
# Extras: dataclass round-trip, CLI exit codes, real-probe report artifact
# ===========================================================================

class TestExtras:
    def test_dataclass_to_dict_round_trip(self):
        r = _probe().submit_contract_probe(
            protection=_valid_solusdt_protection(),
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        d = r.to_dict()
        for key, expected in (
            ("stop_endpoint_called",    False),
            ("order_endpoint_called",   False),
            ("no_position_modified",    True),
            ("no_live_endpoint",        True),
            ("no_orders_sent",          True),
            ("no_batch_order",          True),
            ("no_close_only_path",      True),
            ("emergency_close_invoked", False),
            ("secret_value_observed",   False),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_PREVIEW_OK
        assert d["path"]   == TRADING_STOP_PATH
        d["payload_preview"]["mutated"] = True
        assert "mutated" not in r.payload_preview

    def test_cli_missing_protection_returns_1(self):
        from scripts.preview_demo_trading_stop_contract import run_execute
        with tempfile.TemporaryDirectory() as td:
            base       = Path(td)
            protect_d  = base / "protection"
            contract_d = base / "contract"
            protect_d.mkdir()
            rc = run_execute(
                symbol="SOLUSDT", confirm_token="", mock_permission=False,
                allow_real_stop_probe=False, write_report=False,
                protection_dir=protect_d, contract_dir=contract_d,
                _now=_TEST_NOW,
            )
            assert rc == 1

    def test_cli_missing_symbol_returns_1(self):
        from scripts.preview_demo_trading_stop_contract import run_execute
        with tempfile.TemporaryDirectory() as td:
            base       = Path(td)
            protect_d  = base / "protection"
            contract_d = base / "contract"
            protect_d.mkdir()
            (protect_d / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )
            rc = run_execute(
                symbol="", confirm_token="", mock_permission=False,
                allow_real_stop_probe=False, write_report=False,
                protection_dir=protect_d, contract_dir=contract_d,
                _now=_TEST_NOW,
            )
            assert rc == 1

    def test_cli_mock_permission_missing_token_returns_1(self):
        from scripts.preview_demo_trading_stop_contract import run_execute
        with tempfile.TemporaryDirectory() as td:
            base       = Path(td)
            protect_d  = base / "protection"
            contract_d = base / "contract"
            protect_d.mkdir()
            (protect_d / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )
            rc = run_execute(
                symbol="SOLUSDT", confirm_token="", mock_permission=True,
                allow_real_stop_probe=False, write_report=False,
                protection_dir=protect_d, contract_dir=contract_d,
                _now=_TEST_NOW,
            )
            assert rc == 1

    def test_real_probe_writes_report_with_status(self):
        from scripts.preview_demo_trading_stop_contract import run_execute
        with tempfile.TemporaryDirectory() as td:
            base       = Path(td)
            protect_d  = base / "protection"
            contract_d = base / "contract"
            protect_d.mkdir()
            (protect_d / "latest_new_entry_protection.json").write_text(
                json.dumps(_valid_solusdt_protection()), encoding="utf-8",
            )
            rc = run_execute(
                symbol="SOLUSDT", confirm_token=_TODAY_TOKEN,
                mock_permission=False, allow_real_stop_probe=True,
                write_report=True, protection_dir=protect_d,
                contract_dir=contract_d, _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads(
                (contract_d / "latest_trading_stop_contract.json").read_text(
                    encoding="utf-8"
                )
            )
            assert data["status"] == STATUS_REAL_PROBE_NOT_IMPL
            assert data["real_probe_allowed"] is True
            assert data["real_probe_implemented"] is False
            assert GATE_REAL_PROBE_NOT_IMPL in data["blocked_gates"]


# ===========================================================================
# Extra: invalid category gate
# ===========================================================================

class TestExtraInvalidCategory:
    def test_invalid_category_blocked(self):
        payload = build_payload_preview(symbol="SOLUSDT", stop_loss=61.63)
        payload["category"] = "spot"
        assert GATE_INVALID_CATEGORY in validate_payload(payload)
