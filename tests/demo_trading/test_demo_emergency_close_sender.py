"""
tests/demo_trading/test_demo_emergency_close_sender.py
TASK-014N: Tests for src/demo_emergency_close_sender.py and
           scripts/execute_demo_emergency_close.py

Covers TASK-014N requirements N1-N25:
  N1.  dry-run default does not send
  N2.  missing postfill report -> fail closed
  N3.  postfill not fail_closed -> fail closed
  N4.  no emergency_close_preview -> fail closed
  N5.  reason not missing_stop_price -> fail closed
  N6.  preview reduce_only=False -> fail closed
  N7.  wrong confirm token -> fail closed
  N8.  missing confirm token -> fail closed
  N9.  --execute-emergency-close without --symbol -> fail closed (CLI)
  N10. requested symbol mismatch vs preview -> fail closed
  N11. long preview uses Sell
  N12. short preview uses Buy
  N13. target missing after refresh -> fail closed
  N14. stop restored after refresh -> fail closed
  N15. close qty > live qty -> fail closed
  N16. valid SOLUSDT dry-run -> execute_allowed=True, order_sent=False
  N17. valid execute uses Demo endpoint only
  N18. mocked successful order writes order_id
  N19. failed order writes error but no secrets
  N20. report contains no secrets
  N21. no live endpoint fallback in source
  N22. no set_leverage / transfer / withdraw / deposit / trading_stop /
       stopLoss / takeProfit / triggerPrice in source
  N23. no import of main / src.risk / BybitExecutor
  N24. new-entry sender NOT imported / reused
  N25. one-order limit (single symbol per invocation)

SAFETY: no real network calls; mocks for pre-send refresh and order POST.
"""
from __future__ import annotations

import ast
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_emergency_close_sender import (
    CONFIRM_TOKEN_PREFIX,
    DemoEmergencyCloseSender,
    EmergencyCloseOrderResult,
    _expected_token,
    _ORDER_ENDPOINT,
)
from src.demo_readonly_client import (
    DEMO_BASE_URL,
    PROOF_MISSING,
    PROOF_STRONG,
    PROOF_WEAK,
    DemoReadOnlyClient,
    PositionSnapshot,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _emergency_close_preview(
    *,
    symbol:          str   = "SOLUSDT",
    position_side:   str   = "long",
    close_order_side:str   = "Sell",
    qty:             float = 4.0,
    reason:          str   = "missing_stop_price",
    preview_only:    bool  = True,
    reduce_only:     bool  = True,
    order_sent:      bool  = False,
    order_endpoint_called: bool = False,
    order_type:      str   = "Market",
) -> dict[str, Any]:
    return {
        "symbol":                  symbol,
        "position_side":           position_side,
        "close_order_side":        close_order_side,
        "order_type":              order_type,
        "qty":                     qty,
        "reference_entry_price":   66.47,
        "reduce_only":             reduce_only,
        "preview_only":            preview_only,
        "confirmation_required":   True,
        "order_sent":              order_sent,
        "order_endpoint_called":   order_endpoint_called,
        "no_orders_sent":          True,
        "no_position_modified":    True,
        "reason":                  reason,
        "next_required_task":      "TASK-014N_emergency_missing_stop_close_only_sender",
    }


def _postfill(
    *,
    fail_closed:        bool                  = True,
    recommended_action: str                   = "emergency_close_preview",
    preview:            dict[str, Any] | None = None,
    timestamp_utc:      str                   = "2026-06-09T12:00:00Z",
) -> dict[str, Any]:
    if preview is None:
        preview = _emergency_close_preview()
    return {
        "timestamp_utc":           timestamp_utc,
        "timestamp":               timestamp_utc,
        "mode":                    "postfill_verify",
        "fail_closed":             fail_closed,
        "recommended_action":      recommended_action,
        "emergency_close_preview": preview,
        "missing_stop_price":      True,
        "selected_symbol":         "SOLUSDT",
        "position_found":          True,
        "actual_side":             "long",
        "actual_qty":              4.0,
        "actual_entry_price":      66.47,
        "actual_stop_price":       0.0,
        "no_orders_sent":          True,
        "order_endpoint_called":   False,
        "no_position_modified":    True,
        "secret_value_observed":   False,
        "no_live_endpoint":        True,
        "no_batch_order":          True,
        "no_close_only_path":      True,
    }


def _fixed_now() -> datetime:
    return datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)


def _valid_token(now: datetime | None = None) -> str:
    return _expected_token(now or _fixed_now())


def _mock_ro_client(
    proof_strength:  str  = PROOF_STRONG,
    endpoint_family: str  = "bybit_demo",
    account_mode:    str  = "demo",
    positions:       list[PositionSnapshot] | None = None,
) -> DemoReadOnlyClient:
    """MagicMock DemoReadOnlyClient for pre-send refresh tests."""
    mock_client = MagicMock(spec=DemoReadOnlyClient)
    mock_proof  = MagicMock()
    mock_proof.proof_strength                = proof_strength
    mock_proof.endpoint_family               = endpoint_family
    mock_proof.account_mode                  = account_mode
    mock_proof.live_endpoint_fallback_detected = False
    mock_client.build_runtime_proof.return_value = mock_proof
    mock_wallet                                  = MagicMock()
    mock_wallet.available_balance_usd            = 6_968.07
    mock_client.get_wallet_balance.return_value  = mock_wallet
    if positions is None:
        positions = [
            PositionSnapshot("SOLUSDT", "long", 4.0, 66.47, None, 0.0, 3.0),
        ]
    mock_client.get_open_positions.return_value = positions
    return mock_client


def _write_postfill_to_dir(tmpdir: str, postfill: dict | None = None) -> Path:
    d = Path(tmpdir)
    content = postfill if postfill is not None else _postfill()
    (d / "latest_new_entry_postfill.json").write_text(
        json.dumps(content), encoding="utf-8"
    )
    return d


# ---------------------------------------------------------------------------
# N1. Dry-run default does not send
# ---------------------------------------------------------------------------

class TestN1DryRunDefault:
    def _result(self) -> EmergencyCloseOrderResult:
        sender = DemoEmergencyCloseSender()
        return sender.submit_one_emergency_close(
            postfill=_postfill(),
            symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False,
            _now=_fixed_now(),
        )

    def test_order_not_sent(self):
        assert self._result().order_sent is False

    def test_order_endpoint_called_false(self):
        assert self._result().order_endpoint_called is False

    def test_no_position_modified(self):
        assert self._result().no_position_modified is True

    def test_execute_allowed_true_when_gates_pass(self):
        assert self._result().execute_allowed is True

    def test_mode_dry_run(self):
        assert self._result().mode == "dry_run"

    def test_reduce_only_true(self):
        assert self._result().reduce_only is True

    def test_blocked_gates_empty(self):
        assert self._result().blocked_gates == []


# ---------------------------------------------------------------------------
# N2. Missing postfill report
# ---------------------------------------------------------------------------

class TestN2MissingPostfill:
    def test_missing_dict_blocks(self):
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill={}, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "postfill_report_missing" in r.blocked_gates
        assert r.execute_allowed is False

    def test_cli_exits_one(self):
        from scripts.execute_demo_emergency_close import run_execute
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = run_execute(
                symbol="SOLUSDT", confirm_token=_valid_token(),
                postfill_dir=Path(tmpdir),
            )
        assert rc == 1

    def test_load_returns_none_when_missing(self):
        from scripts.execute_demo_emergency_close import load_latest_postfill
        with tempfile.TemporaryDirectory() as tmpdir:
            assert load_latest_postfill(Path(tmpdir)) is None


# ---------------------------------------------------------------------------
# N3. Postfill not fail_closed
# ---------------------------------------------------------------------------

class TestN3PostfillNotFailClosed:
    def test_blocks(self):
        pf = _postfill(fail_closed=False)
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "postfill_not_fail_closed" in r.blocked_gates


# ---------------------------------------------------------------------------
# N4. No emergency_close_preview
# ---------------------------------------------------------------------------

class TestN4NoEmergencyPreview:
    def test_blocks_when_preview_none(self):
        pf = _postfill()
        pf["emergency_close_preview"] = None
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "emergency_close_preview_missing" in r.blocked_gates

    def test_blocks_when_preview_empty(self):
        pf = _postfill(preview={})
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "emergency_close_preview_missing" in r.blocked_gates


# ---------------------------------------------------------------------------
# N5. Reason not missing_stop_price
# ---------------------------------------------------------------------------

class TestN5WrongReason:
    def test_blocks(self):
        pv = _emergency_close_preview(reason="some_other_reason")
        pf = _postfill(preview=pv)
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "preview_reason_not_missing_stop_price" in r.blocked_gates


# ---------------------------------------------------------------------------
# N6. Preview reduce_only=False
# ---------------------------------------------------------------------------

class TestN6PreviewReduceOnlyFalse:
    def test_blocks(self):
        pv = _emergency_close_preview(reduce_only=False)
        pf = _postfill(preview=pv)
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "preview_reduce_only_must_be_true" in r.blocked_gates

    def test_preview_only_false_blocks(self):
        pv = _emergency_close_preview(preview_only=False)
        pf = _postfill(preview=pv)
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "preview_only_must_be_true" in r.blocked_gates

    def test_preview_order_sent_true_blocks(self):
        pv = _emergency_close_preview(order_sent=True)
        pf = _postfill(preview=pv)
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "preview_order_sent_must_be_false" in r.blocked_gates


# ---------------------------------------------------------------------------
# N7. Wrong confirm token
# ---------------------------------------------------------------------------

class TestN7WrongConfirmToken:
    def test_yesterday_blocked(self):
        now       = _fixed_now()
        yesterday = now - timedelta(days=1)
        sender    = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=_postfill(), symbol="SOLUSDT",
            confirm_token=_expected_token(yesterday),
            execute_emergency_close=False, _now=now,
        )
        assert "confirm_token_date_mismatch" in r.blocked_gates

    def test_invalid_format_blocked(self):
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=_postfill(), symbol="SOLUSDT",
            confirm_token="NOT_A_VALID_TOKEN",
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "invalid_confirm_token_format" in r.blocked_gates

    def test_new_entry_token_blocked(self):
        """New-entry sender's token must not authorise emergency close."""
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=_postfill(), symbol="SOLUSDT",
            confirm_token="CONFIRM_DEMO_NEW_ENTRY_20260609",
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "invalid_confirm_token_format" in r.blocked_gates


# ---------------------------------------------------------------------------
# N8. Missing confirm token
# ---------------------------------------------------------------------------

class TestN8MissingConfirmToken:
    def test_empty_token_blocks(self):
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=_postfill(), symbol="SOLUSDT",
            confirm_token="",
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "missing_confirm_token" in r.blocked_gates


# ---------------------------------------------------------------------------
# N9. --execute-emergency-close without --symbol (CLI)
# ---------------------------------------------------------------------------

class TestN9MissingSymbolCLI:
    def test_cli_exits_one(self):
        from scripts.execute_demo_emergency_close import run_execute
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_postfill_to_dir(tmpdir)
            rc = run_execute(
                symbol="", confirm_token=_valid_token(),
                postfill_dir=Path(tmpdir),
            )
        assert rc == 1

    def test_sender_blocks_missing_symbol(self):
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=_postfill(), symbol="",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "missing_symbol" in r.blocked_gates


# ---------------------------------------------------------------------------
# N10. Requested symbol mismatch vs preview
# ---------------------------------------------------------------------------

class TestN10SymbolMismatch:
    def test_blocks(self):
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=_postfill(), symbol="BTCUSDT",   # preview symbol is SOLUSDT
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "symbol_mismatch_vs_preview" in r.blocked_gates


# ---------------------------------------------------------------------------
# N11. Long preview uses Sell
# ---------------------------------------------------------------------------

class TestN11LongUsesSell:
    def test_passes(self):
        pv = _emergency_close_preview(position_side="long", close_order_side="Sell")
        pf = _postfill(preview=pv)
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert r.position_side == "long"
        assert r.close_order_side == "Sell"
        assert "close_order_side_mismatch_vs_position_side" not in r.blocked_gates

    def test_long_wrong_side_blocks(self):
        pv = _emergency_close_preview(position_side="long", close_order_side="Buy")
        pf = _postfill(preview=pv)
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "close_order_side_mismatch_vs_position_side" in r.blocked_gates


# ---------------------------------------------------------------------------
# N12. Short preview uses Buy
# ---------------------------------------------------------------------------

class TestN12ShortUsesBuy:
    def test_passes(self):
        pv = _emergency_close_preview(
            symbol="LINKUSDT", position_side="short",
            close_order_side="Buy", qty=100.0,
        )
        pf = _postfill(preview=pv)
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="LINKUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert r.position_side == "short"
        assert r.close_order_side == "Buy"
        assert "close_order_side_mismatch_vs_position_side" not in r.blocked_gates

    def test_short_wrong_side_blocks(self):
        pv = _emergency_close_preview(
            symbol="LINKUSDT", position_side="short",
            close_order_side="Sell", qty=100.0,
        )
        pf = _postfill(preview=pv)
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=pf, symbol="LINKUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert "close_order_side_mismatch_vs_position_side" in r.blocked_gates


# ---------------------------------------------------------------------------
# N13. Target missing after refresh
# ---------------------------------------------------------------------------

class TestN13TargetMissingAfterRefresh:
    def test_blocks(self):
        # Refresh returns NO positions => target missing
        ro = _mock_ro_client(positions=[])
        sender = DemoEmergencyCloseSender(allow_real_network=True)
        with patch.object(sender, "_post_to_demo") as mock_post:
            r = sender.submit_one_emergency_close(
                postfill=_postfill(), symbol="SOLUSDT",
                confirm_token=_valid_token(),
                execute_emergency_close=True,
                _now=_fixed_now(), _ro_client=ro,
            )
            mock_post.assert_not_called()
        assert "target_position_missing" in r.blocked_gates
        assert r.order_sent is False
        assert r.order_endpoint_called is False


# ---------------------------------------------------------------------------
# N14. Stop restored after refresh
# ---------------------------------------------------------------------------

class TestN14StopRestoredAfterRefresh:
    def test_blocks(self):
        ro = _mock_ro_client(positions=[
            PositionSnapshot("SOLUSDT", "long", 4.0, 66.47, 60.0, 0.0, 3.0),
        ])
        sender = DemoEmergencyCloseSender(allow_real_network=True)
        with patch.object(sender, "_post_to_demo") as mock_post:
            r = sender.submit_one_emergency_close(
                postfill=_postfill(), symbol="SOLUSDT",
                confirm_token=_valid_token(),
                execute_emergency_close=True,
                _now=_fixed_now(), _ro_client=ro,
            )
            mock_post.assert_not_called()
        assert "stop_restored_no_emergency_close_needed" in r.blocked_gates
        assert r.order_sent is False


# ---------------------------------------------------------------------------
# N15. close qty > live qty
# ---------------------------------------------------------------------------

class TestN15QtyExceedsLive:
    def test_blocks_when_preview_qty_exceeds_live(self):
        # preview qty = 4.0 but live has only 1.0
        ro = _mock_ro_client(positions=[
            PositionSnapshot("SOLUSDT", "long", 1.0, 66.47, None, 0.0, 3.0),
        ])
        sender = DemoEmergencyCloseSender(allow_real_network=True)
        with patch.object(sender, "_post_to_demo") as mock_post:
            r = sender.submit_one_emergency_close(
                postfill=_postfill(), symbol="SOLUSDT",
                confirm_token=_valid_token(),
                execute_emergency_close=True,
                _now=_fixed_now(), _ro_client=ro,
            )
            mock_post.assert_not_called()
        assert any(g.startswith("refresh_close_qty_exceeds_live_qty")
                   for g in r.blocked_gates)

    def test_side_mismatch_blocks(self):
        ro = _mock_ro_client(positions=[
            PositionSnapshot("SOLUSDT", "short", 4.0, 66.47, None, 0.0, 3.0),
        ])
        sender = DemoEmergencyCloseSender(allow_real_network=True)
        with patch.object(sender, "_post_to_demo") as mock_post:
            r = sender.submit_one_emergency_close(
                postfill=_postfill(), symbol="SOLUSDT",
                confirm_token=_valid_token(),
                execute_emergency_close=True,
                _now=_fixed_now(), _ro_client=ro,
            )
            mock_post.assert_not_called()
        assert any(g.startswith("refresh_side_mismatch")
                   for g in r.blocked_gates)


# ---------------------------------------------------------------------------
# N16. Valid SOLUSDT dry-run
# ---------------------------------------------------------------------------

class TestN16ValidDryRun:
    def _result(self) -> EmergencyCloseOrderResult:
        sender = DemoEmergencyCloseSender()
        return sender.submit_one_emergency_close(
            postfill=_postfill(), symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )

    def test_execute_allowed_true(self):
        assert self._result().execute_allowed is True

    def test_order_sent_false(self):
        assert self._result().order_sent is False

    def test_selected_qty(self):
        assert self._result().selected_qty == 4.0

    def test_close_order_side_sell(self):
        assert self._result().close_order_side == "Sell"

    def test_preview_reason_passed_through(self):
        assert self._result().preview_reason == "missing_stop_price"


# ---------------------------------------------------------------------------
# N17. Valid execute uses Demo endpoint only
# ---------------------------------------------------------------------------

class TestN17ExecuteUsesDemoEndpoint:
    def test_post_url_uses_demo_base(self):
        ro = _mock_ro_client()
        captured_urls: list[str] = []

        def fake_urlopen(req, timeout=10):
            captured_urls.append(req.full_url)
            class _R:
                def __enter__(self): return self
                def __exit__(self, *a): return False
                def read(self):
                    return json.dumps({
                        "retCode": 0,
                        "result": {"orderId": "ec-001"},
                    }).encode("utf-8")
            return _R()

        sender = DemoEmergencyCloseSender(allow_real_network=True)
        # Need credentials for signing-headers branch; supply fakes
        sender._api_key    = "FAKE_KEY"
        sender._api_secret = "FAKE_SECRET"
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = sender.submit_one_emergency_close(
                postfill=_postfill(), symbol="SOLUSDT",
                confirm_token=_valid_token(),
                execute_emergency_close=True,
                _now=_fixed_now(), _ro_client=ro,
            )
        assert r.order_sent is True
        assert len(captured_urls) == 1
        assert captured_urls[0].startswith(DEMO_BASE_URL)
        assert _ORDER_ENDPOINT in captured_urls[0]
        assert "api.bybit.com" not in captured_urls[0]
        assert "api.bytick.com" not in captured_urls[0]


# ---------------------------------------------------------------------------
# N18. Mocked successful order writes order_id
# ---------------------------------------------------------------------------

class TestN18MockedSuccess:
    def test_order_id_set(self):
        ro = _mock_ro_client()
        sender = DemoEmergencyCloseSender(allow_real_network=True)
        with patch.object(
            sender, "_post_to_demo",
            return_value={"retCode": 0, "retMsg": "OK",
                          "result": {"orderId": "EC-XYZ-001"}},
        ):
            r = sender.submit_one_emergency_close(
                postfill=_postfill(), symbol="SOLUSDT",
                confirm_token=_valid_token(),
                execute_emergency_close=True,
                _now=_fixed_now(), _ro_client=ro,
            )
        assert r.order_sent is True
        assert r.order_id == "EC-XYZ-001"
        assert r.order_response_status == "success"
        assert r.no_position_modified is False
        assert r.order_endpoint_called is True
        assert r.blocked_gates == []


# ---------------------------------------------------------------------------
# N19. Failed order: error captured, no secrets
# ---------------------------------------------------------------------------

class TestN19MockedFailure:
    def test_error_captured(self):
        ro = _mock_ro_client()
        sender = DemoEmergencyCloseSender(allow_real_network=True)
        sender._api_secret = "TOPSECRETSENTINEL"
        with patch.object(
            sender, "_post_to_demo",
            return_value={"retCode": 110001, "retMsg": "qty error",
                          "result": {}},
        ):
            r = sender.submit_one_emergency_close(
                postfill=_postfill(), symbol="SOLUSDT",
                confirm_token=_valid_token(),
                execute_emergency_close=True,
                _now=_fixed_now(), _ro_client=ro,
            )
        assert r.order_sent is False
        assert r.no_position_modified is True
        assert "110001" in r.order_response_status
        # Secret value must not appear in any field of result dict
        as_text = json.dumps(r.to_dict())
        assert "TOPSECRETSENTINEL" not in as_text


# ---------------------------------------------------------------------------
# N20. Report contains no secrets
# ---------------------------------------------------------------------------

class TestN20ReportNoSecrets:
    def test_dict_has_no_api_secret_keys(self):
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=_postfill(), symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        for k in r.to_dict():
            assert "api_secret" not in k.lower()
            assert "secret_key" not in k.lower()

    def test_written_report_no_env_sentinel(self):
        from scripts.execute_demo_emergency_close import run_execute
        os.environ["BYBIT_DEMO_API_SECRET"] = "EMERGENCY_SECRET_SENTINEL_001"
        try:
            with tempfile.TemporaryDirectory() as tmp_pf, \
                 tempfile.TemporaryDirectory() as tmp_out:
                _write_postfill_to_dir(tmp_pf)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    run_execute(
                        symbol="SOLUSDT",
                        confirm_token=_valid_token(),
                        write_report=True,
                        postfill_dir=Path(tmp_pf),
                        execution_dir=Path(tmp_out),
                    )
                for f in Path(tmp_out).glob("*"):
                    text = f.read_text(encoding="utf-8")
                    assert "EMERGENCY_SECRET_SENTINEL_001" not in text
        finally:
            os.environ.pop("BYBIT_DEMO_API_SECRET", None)


# ---------------------------------------------------------------------------
# N21. No live endpoint fallback in source
# ---------------------------------------------------------------------------

_SENDER_PATH = ROOT / "src" / "demo_emergency_close_sender.py"
_CLI_PATH    = ROOT / "scripts" / "execute_demo_emergency_close.py"


class TestN21NoLiveEndpoint:
    def test_sender_no_live_hostname(self):
        text = _SENDER_PATH.read_text(encoding="utf-8")
        assert "api.bybit.com" not in text
        assert "api.bytick.com" not in text

    def test_cli_no_live_hostname(self):
        text = _CLI_PATH.read_text(encoding="utf-8")
        assert "api.bybit.com" not in text
        assert "api.bytick.com" not in text

    def test_sender_no_batch_endpoint(self):
        text = _SENDER_PATH.read_text(encoding="utf-8")
        assert "/v5/order/create-batch" not in text


# ---------------------------------------------------------------------------
# N22. No leverage / TP / SL / triggerPrice / transfer / withdraw / deposit
# ---------------------------------------------------------------------------

class TestN22ForbiddenOperations:
    _FORBIDDEN = [
        "set_leverage", "setLeverage",
        "trading_stop", "tradingStop",
        "takeProfit", "stopLoss",
        "triggerPrice", "tpslMode",
        "/asset/transfer", "/withdraw", "/deposit",
        "pybit",
    ]

    def test_sender_source_clean(self):
        text = _SENDER_PATH.read_text(encoding="utf-8")
        for tok in self._FORBIDDEN:
            assert tok not in text, f"Forbidden token in sender: {tok}"

    def test_cli_source_clean(self):
        text = _CLI_PATH.read_text(encoding="utf-8")
        for tok in self._FORBIDDEN:
            assert tok not in text, f"Forbidden token in CLI: {tok}"


# ---------------------------------------------------------------------------
# N23. No import of main / src.risk / BybitExecutor
# ---------------------------------------------------------------------------

_FORBIDDEN_MODULE_IMPORTS = {
    "main",
    "src.risk",
}
_FORBIDDEN_NAME_IMPORTS = {"BybitExecutor"}


def _imports_in(path: Path) -> tuple[set[str], set[str]]:
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


class TestN23NoForbiddenImports:
    def test_sender_imports_clean(self):
        mods, names = _imports_in(_SENDER_PATH)
        for forbidden in _FORBIDDEN_MODULE_IMPORTS:
            assert forbidden not in mods, f"Forbidden import: {forbidden}"
        for forbidden in _FORBIDDEN_NAME_IMPORTS:
            assert forbidden not in names, f"Forbidden name import: {forbidden}"

    def test_cli_imports_clean(self):
        mods, names = _imports_in(_CLI_PATH)
        for forbidden in _FORBIDDEN_MODULE_IMPORTS:
            assert forbidden not in mods, f"Forbidden import: {forbidden}"
        for forbidden in _FORBIDDEN_NAME_IMPORTS:
            assert forbidden not in names, f"Forbidden name import: {forbidden}"


# ---------------------------------------------------------------------------
# N24. New-entry sender NOT imported / reused
# ---------------------------------------------------------------------------

_NEW_ENTRY_SENDER_IMPORTS = {
    "src.demo_new_entry_sender",
    "src.demo_close_only_sender",
    "scripts.execute_demo_new_entry",
    "scripts.execute_demo_close_only_cleanup",
}


class TestN24NoNewEntrySenderReuse:
    def test_sender_does_not_import_new_entry(self):
        mods, _ = _imports_in(_SENDER_PATH)
        for forbidden in _NEW_ENTRY_SENDER_IMPORTS:
            assert forbidden not in mods, \
                f"Emergency sender must not import {forbidden}"

    def test_cli_does_not_import_new_entry(self):
        mods, _ = _imports_in(_CLI_PATH)
        for forbidden in _NEW_ENTRY_SENDER_IMPORTS:
            assert forbidden not in mods, \
                f"Emergency CLI must not import {forbidden}"

    def test_source_does_not_reference_new_entry_sender_class(self):
        text = _SENDER_PATH.read_text(encoding="utf-8")
        assert "DemoNewEntrySender" not in text
        assert "DemoCloseOnlySender" not in text


# ---------------------------------------------------------------------------
# N25. One-order limit (single symbol per invocation)
# ---------------------------------------------------------------------------

class TestN25OneOrderLimit:
    def test_only_one_post_called_per_invocation(self):
        ro = _mock_ro_client()
        sender = DemoEmergencyCloseSender(allow_real_network=True)
        with patch.object(
            sender, "_post_to_demo",
            return_value={"retCode": 0, "retMsg": "OK",
                          "result": {"orderId": "ONLY-1"}},
        ) as mock_post:
            sender.submit_one_emergency_close(
                postfill=_postfill(), symbol="SOLUSDT",
                confirm_token=_valid_token(),
                execute_emergency_close=True,
                _now=_fixed_now(), _ro_client=ro,
            )
            assert mock_post.call_count == 1

    def test_request_body_is_single_symbol(self):
        ro = _mock_ro_client()
        sender = DemoEmergencyCloseSender(allow_real_network=True)
        captured: list[dict] = []

        def fake_post(body):
            captured.append(body)
            return {"retCode": 0, "retMsg": "OK",
                    "result": {"orderId": "X-1"}}

        with patch.object(sender, "_post_to_demo", side_effect=fake_post):
            sender.submit_one_emergency_close(
                postfill=_postfill(), symbol="SOLUSDT",
                confirm_token=_valid_token(),
                execute_emergency_close=True,
                _now=_fixed_now(), _ro_client=ro,
            )
        assert len(captured) == 1
        body = captured[0]
        # Body must be a single dict, NOT a list/batch
        assert isinstance(body, dict)
        assert body["symbol"] == "SOLUSDT"
        assert body["side"] == "Sell"
        assert body["reduceOnly"] is True
        assert body["closeOnTrigger"] is False
        assert body["orderType"] == "Market"
        assert body["category"] == "linear"
        # Forbidden keys must be absent
        for k in ("triggerPrice", "takeProfit", "stopLoss", "tpslMode",
                  "leverage", "transfer"):
            assert k not in body


# ---------------------------------------------------------------------------
# Structural invariants — always these values regardless of input
# ---------------------------------------------------------------------------

class TestStructuralInvariants:
    def test_dry_run_invariants(self):
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill=_postfill(), symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert r.no_live_endpoint is True
        assert r.no_batch_order is True
        assert r.no_new_entry_path is True
        assert r.no_close_only_sender_reused is True
        assert r.no_secrets is True
        assert r.secret_value_observed is False
        assert r.reduce_only is True

    def test_fail_closed_path_invariants(self):
        sender = DemoEmergencyCloseSender()
        r = sender.submit_one_emergency_close(
            postfill={}, symbol="SOLUSDT",
            confirm_token=_valid_token(),
            execute_emergency_close=False, _now=_fixed_now(),
        )
        assert r.no_live_endpoint is True
        assert r.no_batch_order is True
        assert r.no_new_entry_path is True
        assert r.no_close_only_sender_reused is True
        assert r.reduce_only is True
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True

    def test_successful_post_keeps_invariants(self):
        ro = _mock_ro_client()
        sender = DemoEmergencyCloseSender(allow_real_network=True)
        with patch.object(
            sender, "_post_to_demo",
            return_value={"retCode": 0, "result": {"orderId": "OK-1"}},
        ):
            r = sender.submit_one_emergency_close(
                postfill=_postfill(), symbol="SOLUSDT",
                confirm_token=_valid_token(),
                execute_emergency_close=True,
                _now=_fixed_now(), _ro_client=ro,
            )
        assert r.no_live_endpoint is True
        assert r.no_batch_order is True
        assert r.no_new_entry_path is True
        assert r.no_close_only_sender_reused is True
        assert r.reduce_only is True
        # only no_position_modified flips on actual success
        assert r.no_position_modified is False
        assert r.order_endpoint_called is True


# ---------------------------------------------------------------------------
# CLI integration — end-to-end with sandboxed dirs
# ---------------------------------------------------------------------------

class TestCLIIntegration:
    def test_dry_run_cli_writes_report(self):
        from scripts.execute_demo_emergency_close import run_execute
        with tempfile.TemporaryDirectory() as tmp_pf, \
             tempfile.TemporaryDirectory() as tmp_out:
            _write_postfill_to_dir(tmp_pf)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = run_execute(
                    symbol="SOLUSDT",
                    confirm_token=_valid_token(),
                    write_report=True,
                    postfill_dir=Path(tmp_pf),
                    execution_dir=Path(tmp_out),
                )
            assert rc == 0
            j = Path(tmp_out) / "latest_emergency_close_execution.json"
            m = Path(tmp_out) / "latest_emergency_close_execution.md"
            assert j.exists() and m.exists()
            data = json.loads(j.read_text(encoding="utf-8"))
            assert data["mode"] == "dry_run"
            assert data["order_sent"] is False
            assert data["execute_allowed"] is True
            assert data["blocked_gates"] == []
            assert data["reduce_only"] is True
            md = m.read_text(encoding="utf-8")
            assert "DRY_RUN_EXECUTE_ALLOWED" in md
            assert "SOLUSDT" in md

    def test_cli_fail_closed_returns_one(self):
        """Postfill report present but recommended_action != emergency_close_preview."""
        from scripts.execute_demo_emergency_close import run_execute
        pf = _postfill(recommended_action="manual_close_or_add_stop_in_bybit_demo_ui")
        with tempfile.TemporaryDirectory() as tmp_pf, \
             tempfile.TemporaryDirectory() as tmp_out:
            _write_postfill_to_dir(tmp_pf, pf)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = run_execute(
                    symbol="SOLUSDT",
                    confirm_token=_valid_token(),
                    write_report=True,
                    postfill_dir=Path(tmp_pf),
                    execution_dir=Path(tmp_out),
                )
            assert rc == 1
