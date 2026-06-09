"""
tests/demo_trading/test_demo_new_entry_protection.py
TASK-014Q: Tests for src/demo_new_entry_protection.py and
           scripts/preview_demo_new_entry_protection.py.

Coverage map (Q-series; numbers cross-reference Rick's spec items 1-16):
  Q1  protected plan requires realtime_price_guard_verified=True
  Q2  missing stop_price => fail closed
  Q3  long stop must be below entry
  Q4  short stop must be above entry
  Q5  selected symbol not in payload => fail closed
  Q6  protected preview does not send order
  Q7  protected preview does not call stop endpoint
  Q8  no secrets in report (no env reads, no API key/secret strings in plan)
  Q9  no live endpoint fallback (module never references live host)
  Q10 no import main.py / src.risk.py / BybitExecutor (and no HTTP / hmac /
      os.environ / order endpoints invoked from this module)
  Q11 TASK-014L sender actual --execute-new-entry blocked when
      protected_entry_policy_missing
  Q12 TASK-014L dry-run still reports protected_entry_required=True
  Q13 legacy review without realtime guard remains blocked
  Q14 review with realtime guard but no protection still blocks actual execute
  Q15 no TP / leverage / transfer / withdraw / deposit references in module
  Q16 no emergency close triggered through this preview path
  + dataclass round-trip via to_dict()
  + endpoint group separation (order_create vs trading_stop vs read_only)
  + CLI smoke (missing review file => exit 1; report writer emits both
    JSON and Markdown)

SAFETY: no real network calls; pure-computation tests.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_new_entry_protection import (
    DEMO_ENDPOINT_FAMILY,
    ENDPOINT_GROUPS,
    G20_BLOCKED_GATE_NAME,
    ORDER_CREATE_ENDPOINT,
    PHASE_PRE_ENTRY_REVIEW,
    PROTECTED_ENTRY_STATUS_FAIL_CLOSED,
    PROTECTED_ENTRY_STATUS_PREVIEW_ONLY,
    READ_ONLY_ENDPOINTS,
    REASON_LONG_STOP_NOT_BELOW_ENTRY,
    REASON_MISSING_STOP_PRICE,
    REASON_REVIEW_FAIL_CLOSED,
    REASON_REVIEW_MISSING_REALTIME_GUARD,
    REASON_SHORT_STOP_NOT_ABOVE_ENTRY,
    REASON_STOP_ATTACH_NOT_IMPLEMENTED,
    REASON_SYMBOL_MISSING,
    REASON_SYMBOL_NOT_IN_PAYLOAD,
    STOP_ATTACH_ENDPOINT,
    ProtectedEntryPlan,
    build_protected_entry_plan,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TS = "2026-06-09T12:34:56Z"


def _accepted_payload(
    symbol: str       = "SOLUSDT",
    side: str         = "long",
    qty: float        = 12.0,
    entry: float      = 66.21,
    stop: float       = 62.9,
    order_side: str   = "Buy",
    preview_only: bool = True,
    reduce_only: bool  = False,
) -> dict[str, Any]:
    return {
        "symbol":                symbol,
        "side":                  order_side,
        "qty":                   qty,
        "order_type":            "Market",
        "reduce_only":           reduce_only,
        "preview_only":          preview_only,
        "order_sent":            False,
        "order_endpoint_called": False,
        "entry_reference_price": entry,
        "stop_price":            stop,
        "estimated_stop_risk_usd": 10.0,
        "estimated_notional_usd":  500.0,
    }


def _accepted_eval(
    symbol: str = "SOLUSDT",
    side: str = "long",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "symbol":   symbol,
        "side":    side,
        "payload": payload if payload is not None else _accepted_payload(
            symbol=symbol, side=side,
        ),
    }


def _good_review(
    realtime_price_guard_verified: bool = True,
    accepted_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Minimal review dict shaped to pass build_protected_entry_plan checks."""
    if accepted_candidates is None:
        accepted_candidates = [_accepted_eval()]
    return {
        "fail_closed":                    False,
        "demo_runtime_verified":          True,
        "proof_strength":                 "STRONG",
        "endpoint_family":                "bybit_demo",
        "account_mode":                   "demo",
        "position_details_source":        "real_readonly",
        "realtime_price_guard_verified":  realtime_price_guard_verified,
        "available_balance_usd":          5_000.0,
        "open_positions_count":           5,
        "timestamp":                      "2026-06-09T12:30:00Z",
        "accepted_candidates":            accepted_candidates,
    }


def _build_plan(
    review: dict[str, Any] | None = None,
    symbol: str = "SOLUSDT",
    timestamp_utc: str = _TS,
) -> ProtectedEntryPlan:
    return build_protected_entry_plan(
        review=review if review is not None else _good_review(),
        symbol=symbol,
        timestamp_utc=timestamp_utc,
    )


# ---------------------------------------------------------------------------
# Q1 — Requires realtime_price_guard_verified=True
# ---------------------------------------------------------------------------

class TestQ1RequiresRealtimePriceGuard:
    def test_passes_when_verified_true(self):
        plan = _build_plan()
        assert plan.realtime_price_guard_verified is True
        assert REASON_REVIEW_MISSING_REALTIME_GUARD not in plan.blocked_reasons

    def test_blocks_when_verified_false(self):
        review = _good_review(realtime_price_guard_verified=False)
        plan = _build_plan(review=review)
        assert REASON_REVIEW_MISSING_REALTIME_GUARD in plan.blocked_reasons
        assert plan.protected_entry_status == PROTECTED_ENTRY_STATUS_FAIL_CLOSED

    def test_blocks_when_field_missing(self):
        review = _good_review()
        review.pop("realtime_price_guard_verified", None)
        plan = _build_plan(review=review)
        assert REASON_REVIEW_MISSING_REALTIME_GUARD in plan.blocked_reasons

    def test_execute_always_blocked_even_when_verified(self):
        plan = _build_plan()
        assert plan.protected_entry_execute_allowed is False
        assert plan.protected_entry_execute_reason == REASON_STOP_ATTACH_NOT_IMPLEMENTED


# ---------------------------------------------------------------------------
# Q2 — Missing stop_price => fail closed
# ---------------------------------------------------------------------------

class TestQ2MissingStopPrice:
    @pytest.mark.parametrize("stop", [0.0, 0, -1.0, None])
    def test_missing_or_zero_stop(self, stop):
        payload = _accepted_payload()
        if stop is None:
            payload.pop("stop_price")
        else:
            payload["stop_price"] = stop
        review = _good_review(accepted_candidates=[
            _accepted_eval(payload=payload),
        ])
        plan = _build_plan(review=review)
        assert REASON_MISSING_STOP_PRICE in plan.blocked_reasons
        assert plan.protected_entry_status == PROTECTED_ENTRY_STATUS_FAIL_CLOSED
        assert plan.protected_entry_execute_allowed is False


# ---------------------------------------------------------------------------
# Q3 — Long stop must be below entry
# ---------------------------------------------------------------------------

class TestQ3LongStopBelowEntry:
    def test_long_stop_above_entry_blocked(self):
        payload = _accepted_payload(side="long", order_side="Buy",
                                    entry=66.21, stop=70.0)
        review = _good_review(accepted_candidates=[
            _accepted_eval(side="long", payload=payload),
        ])
        plan = _build_plan(review=review)
        assert REASON_LONG_STOP_NOT_BELOW_ENTRY in plan.blocked_reasons
        assert plan.protected_entry_status == PROTECTED_ENTRY_STATUS_FAIL_CLOSED

    def test_long_stop_equal_to_entry_blocked(self):
        payload = _accepted_payload(side="long", order_side="Buy",
                                    entry=66.21, stop=66.21)
        review = _good_review(accepted_candidates=[
            _accepted_eval(side="long", payload=payload),
        ])
        plan = _build_plan(review=review)
        assert REASON_LONG_STOP_NOT_BELOW_ENTRY in plan.blocked_reasons

    def test_long_stop_below_entry_passes(self):
        plan = _build_plan()  # default SOLUSDT long, entry 66.21, stop 62.9
        assert REASON_LONG_STOP_NOT_BELOW_ENTRY not in plan.blocked_reasons


# ---------------------------------------------------------------------------
# Q4 — Short stop must be above entry
# ---------------------------------------------------------------------------

class TestQ4ShortStopAboveEntry:
    def test_short_stop_below_entry_blocked(self):
        payload = _accepted_payload(symbol="AVAXUSDT", side="short",
                                    order_side="Sell",
                                    entry=20.0, stop=18.0)
        review = _good_review(accepted_candidates=[
            _accepted_eval(symbol="AVAXUSDT", side="short", payload=payload),
        ])
        plan = _build_plan(review=review, symbol="AVAXUSDT")
        assert REASON_SHORT_STOP_NOT_ABOVE_ENTRY in plan.blocked_reasons

    def test_short_stop_equal_to_entry_blocked(self):
        payload = _accepted_payload(symbol="AVAXUSDT", side="short",
                                    order_side="Sell",
                                    entry=20.0, stop=20.0)
        review = _good_review(accepted_candidates=[
            _accepted_eval(symbol="AVAXUSDT", side="short", payload=payload),
        ])
        plan = _build_plan(review=review, symbol="AVAXUSDT")
        assert REASON_SHORT_STOP_NOT_ABOVE_ENTRY in plan.blocked_reasons

    def test_short_stop_above_entry_passes(self):
        payload = _accepted_payload(symbol="AVAXUSDT", side="short",
                                    order_side="Sell",
                                    entry=20.0, stop=21.5)
        review = _good_review(accepted_candidates=[
            _accepted_eval(symbol="AVAXUSDT", side="short", payload=payload),
        ])
        plan = _build_plan(review=review, symbol="AVAXUSDT")
        assert REASON_SHORT_STOP_NOT_ABOVE_ENTRY not in plan.blocked_reasons
        assert plan.selected_side == "short"
        assert plan.order_side == "Sell"
        assert plan.stop_order_side == "Buy"


# ---------------------------------------------------------------------------
# Q5 — Selected symbol not in payload => fail closed
# ---------------------------------------------------------------------------

class TestQ5SymbolNotInPayload:
    def test_missing_symbol_fail_closed(self):
        plan = _build_plan(symbol="")
        assert REASON_SYMBOL_MISSING in plan.blocked_reasons
        assert plan.protected_entry_status == PROTECTED_ENTRY_STATUS_FAIL_CLOSED

    def test_unknown_symbol_fail_closed(self):
        plan = _build_plan(symbol="DOGEUSDT")  # not in default accepted list
        assert REASON_SYMBOL_NOT_IN_PAYLOAD in plan.blocked_reasons
        assert plan.protected_entry_status == PROTECTED_ENTRY_STATUS_FAIL_CLOSED


# ---------------------------------------------------------------------------
# Q6 — Protected preview does not send order
# ---------------------------------------------------------------------------

class TestQ6PreviewDoesNotSendOrder:
    def test_no_orders_sent(self):
        plan = _build_plan()
        assert plan.no_orders_sent is True
        assert plan.order_endpoint_called is False
        assert plan.no_position_modified is True


# ---------------------------------------------------------------------------
# Q7 — Protected preview does not call stop endpoint
# ---------------------------------------------------------------------------

class TestQ7PreviewDoesNotCallStopEndpoint:
    def test_stop_endpoint_not_called(self):
        plan = _build_plan()
        assert plan.stop_endpoint_called is False
        assert plan.stop_loss_endpoint_allowed is False

    def test_stop_attach_endpoint_constant_demo_only(self):
        # The reserved endpoint string is announced as informational only.
        assert STOP_ATTACH_ENDPOINT == "/v5/position/trading-stop"

    def test_endpoint_groups_separate_order_stop_readonly(self):
        order_paths = set(ENDPOINT_GROUPS["order_create"])
        stop_paths  = set(ENDPOINT_GROUPS["trading_stop"])
        ro_paths    = set(ENDPOINT_GROUPS["read_only"])
        assert order_paths.isdisjoint(stop_paths)
        assert order_paths.isdisjoint(ro_paths)
        assert stop_paths.isdisjoint(ro_paths)
        assert ORDER_CREATE_ENDPOINT in order_paths
        assert STOP_ATTACH_ENDPOINT in stop_paths
        for ro in READ_ONLY_ENDPOINTS:
            assert ro in ro_paths


# ---------------------------------------------------------------------------
# Q8 — No secrets in report (no env reads, no API key strings in plan)
# ---------------------------------------------------------------------------

_PROT_SRC    = ROOT / "src"     / "demo_new_entry_protection.py"
_PROT_SCRIPT = ROOT / "scripts" / "preview_demo_new_entry_protection.py"


def _read_src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_code_only(path: Path) -> str:
    """Return module source with all string literals and comments stripped.

    Used to assert that *code* does not reference forbidden tokens, without
    false-positives on docstring text that merely *describes* what the
    module avoids.
    """
    import io
    import tokenize
    src   = _read_src(path)
    out:  list[str] = []
    tokens = tokenize.tokenize(io.BytesIO(src.encode("utf-8")).readline)
    for tok in tokens:
        if tok.type in (tokenize.STRING, tokenize.COMMENT, tokenize.ENCODING,
                        tokenize.NEWLINE, tokenize.NL, tokenize.INDENT,
                        tokenize.DEDENT, tokenize.ENDMARKER):
            continue
        out.append(tok.string)
    return " ".join(out)


def _ast_imports(path: Path) -> list[str]:
    tree = ast.parse(_read_src(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                names.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for n in node.names:
                names.append(f"{mod}.{n.name}")
    return names


class TestQ8NoSecretsInOutput:
    def test_module_does_not_read_environment(self):
        code = _read_code_only(_PROT_SRC)
        assert "environ" not in code
        assert "getenv"  not in code

    def test_no_secret_strings_in_module(self):
        # Strings (incl. docstrings) ARE allowed in this module for the
        # endpoint allowlist constants.  The assertion is that no secret /
        # signing-header tokens appear anywhere in module source.
        src = _read_src(_PROT_SRC)
        for forbidden in ("X-BAPI-SIGN", "X-BAPI-API-KEY",
                          "BYBIT_DEMO_API_KEY", "BYBIT_DEMO_API_SECRET"):
            assert forbidden not in src

    def test_plan_to_dict_has_no_secret_field_names(self):
        plan = _build_plan()
        d    = plan.to_dict()
        forbidden = ["api_key", "api_secret", "bapi_sign", "x-bapi-sign",
                     "x_bapi_sign", "bybit_demo_api_key",
                     "bybit_demo_api_secret"]
        keys_lower = {k.lower() for k in d.keys()}
        for f in forbidden:
            assert f not in keys_lower

    def test_env_secrets_not_leaked_via_plan(self, monkeypatch):
        monkeypatch.setenv("BYBIT_DEMO_API_KEY", "ENV_KEY_NEVER_APPEAR_Q8")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "ENV_SEC_NEVER_APPEAR_Q8")
        plan = _build_plan()
        s    = json.dumps(plan.to_dict())
        assert "ENV_KEY_NEVER_APPEAR_Q8" not in s
        assert "ENV_SEC_NEVER_APPEAR_Q8" not in s


# ---------------------------------------------------------------------------
# Q9 — No live endpoint fallback
# ---------------------------------------------------------------------------

class TestQ9NoLiveEndpointFallback:
    def test_module_no_live_hostname(self):
        src = _read_src(_PROT_SRC)
        assert "api.bybit.com"          not in src
        assert "api-testnet.bybit.com"  not in src

    def test_script_no_live_hostname(self):
        src = _read_src(_PROT_SCRIPT)
        assert "api.bybit.com"          not in src
        assert "api-testnet.bybit.com"  not in src

    def test_plan_announces_demo_endpoint_family(self):
        plan = _build_plan()
        assert plan.endpoint_family == DEMO_ENDPOINT_FAMILY
        assert plan.no_live_endpoint is True


# ---------------------------------------------------------------------------
# Q10 — Forbidden imports / no HTTP / no order endpoint invocation
# ---------------------------------------------------------------------------

_FORBIDDEN_MODULES = (
    "main",
    "src.risk",
    "src.executor",
    "src.executors",
    "src.demo_close_only_sender",
    "src.demo_new_entry_sender",
    "src.demo_emergency_close_sender",
    "src.demo_new_entry_postfill_verify",
    "scripts.execute_demo_close_only_cleanup",
    "scripts.execute_demo_emergency_close",
    "scripts.execute_demo_new_entry",
    "pybit",
    "ccxt",
    "urllib",
    "urllib.request",
    "requests",
    "httpx",
    "hmac",
    "hashlib",
)


class TestQ10ForbiddenImports:
    @pytest.mark.parametrize("forbidden", _FORBIDDEN_MODULES)
    def test_module_does_not_import_forbidden(self, forbidden):
        imports = _ast_imports(_PROT_SRC)
        for name in imports:
            assert not name.startswith(forbidden), (
                f"Forbidden import in protection module: {name}"
            )

    def test_module_does_not_call_order_endpoint(self):
        code = _read_code_only(_PROT_SRC)
        # Endpoint string IS referenced (as STOP_ATTACH_ENDPOINT constant
        # in a string literal), but the code MUST NOT invoke it.
        assert "urlopen"           not in code
        assert "requests"          not in code
        assert "httpx"             not in code
        assert "BybitExecutor"     not in code


# ---------------------------------------------------------------------------
# Q11 + Q14 — TASK-014L actual --execute-new-entry blocked when protection missing
# ---------------------------------------------------------------------------

def _full_sender_review() -> dict[str, Any]:
    """Build a complete review the sender will pass through G1-G19."""
    # Re-use the existing TASK-014L sender test fixture builder so we
    # get a review that already passes every gate up to G19.
    from src.demo_instrument_rules import InstrumentRules
    from src.demo_new_entry_review import (
        NewEntryCandidate,
        review_new_entry_candidates,
    )
    from src.demo_portfolio_risk import DemoOpenPosition
    from src.demo_position_reconcile import reconcile

    rules = {
        "ETHUSDT":  InstrumentRules("ETHUSDT",  0.01, 0.01, 0, 0.05,   1.0, 2, 2),
        "BNBUSDT":  InstrumentRules("BNBUSDT",  0.01, 0.01, 0, 0.01,   1.0, 2, 2),
        "SOLUSDT":  InstrumentRules("SOLUSDT",  0.1,  0.1,  0, 0.01,   1.0, 2, 1),
        "AAVEUSDT": InstrumentRules("AAVEUSDT", 0.01, 0.01, 0, 0.01,   1.0, 2, 2),
        "XRPUSDT":  InstrumentRules("XRPUSDT",  1.0,  1.0,  0, 0.0001, 1.0, 4, 0),
        "ADAUSDT":  InstrumentRules("ADAUSDT",  1.0,  1.0,  0, 0.0001, 1.0, 4, 0),
    }
    rec = reconcile(
        equity_usd=11_560.91,
        available_balance_usd=7_048.86,
        positions=[
            DemoOpenPosition("ETHUSDT", "short", 0.10, 3_500.0, 3_700.0),
            DemoOpenPosition("BNBUSDT", "short", 0.50,   600.0,   640.0),
            DemoOpenPosition("SOLUSDT", "short", 1.00,   160.0,   175.0),
            DemoOpenPosition("XRPUSDT", "short", 100.0,    0.62,    0.68),
            DemoOpenPosition("ADAUSDT", "short", 200.0,    0.45,    0.49),
        ],
        instrument_rules=rules,
        full_kelly_fraction=0.60,
        demo_runtime_verified=True,
        proof_strength="STRONG",
        mode="real_readonly_snapshot",
        position_details_source="real_readonly",
    )
    cand = NewEntryCandidate(
        symbol="AAVEUSDT", side="long",
        entry_reference_price=120.0, stop_price=110.0,
        requested_risk_usd=30.0, score=1.0,
    )
    review = review_new_entry_candidates(
        reconciliation=rec,
        candidates=[cand],
        instrument_rules=rules,
        endpoint_family="bybit_demo",
        account_mode="demo",
        available_balance_usd_source="account.totalAvailableBalance",
    )
    d = review.to_dict(timestamp_utc="2026-06-09T12:00:00Z")
    d["realtime_price_guard_verified"] = True
    return d


def _today_token(now: datetime | None = None) -> str:
    n = now or datetime.now(timezone.utc)
    return f"CONFIRM_DEMO_NEW_ENTRY_{n.strftime('%Y%m%d')}"


class TestQ11SenderBlocksExecuteWhenProtectionMissing:
    """Default sender (protected_entry_policy_required=True) must refuse to
    submit a naked entry, even when every other gate passes."""

    def _make_ro_client_with_no_target_open(self) -> MagicMock:
        from src.demo_readonly_client import DemoReadOnlyClient, PositionSnapshot
        ro = MagicMock(spec=DemoReadOnlyClient)
        proof = MagicMock()
        proof.proof_strength  = "STRONG"
        proof.endpoint_family = "bybit_demo"
        proof.account_mode    = "demo"
        ro.build_runtime_proof.return_value = proof
        wallet = MagicMock()
        wallet.available_balance_usd        = 6_900.0
        wallet.available_balance_usd_source = "account.totalAvailableBalance"
        wallet.equity_usd                   = 10_900.0
        ro.get_wallet_balance.return_value  = wallet
        ro.get_open_positions.return_value  = [
            PositionSnapshot("ETHUSDT", "short", 0.1, 3500.0, 3700.0, 0.0, 3.0),
            PositionSnapshot("BNBUSDT", "short", 0.5,  600.0,  640.0, 0.0, 3.0),
            PositionSnapshot("XRPUSDT", "short", 100.0,  0.62,  0.68, 0.0, 3.0),
            PositionSnapshot("ADAUSDT", "short", 200.0,  0.45,  0.49, 0.0, 3.0),
            PositionSnapshot("SOLUSDT", "short", 1.0,  160.0, 175.0, 0.0, 3.0),
        ]
        return ro

    def test_execute_blocked_with_g20(self):
        from src.demo_new_entry_sender import DemoNewEntrySender
        review = _full_sender_review()
        now    = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
        token  = _today_token(now)
        ro     = self._make_ro_client_with_no_target_open()
        sender = DemoNewEntrySender(allow_real_network=True)
        sender._api_key    = "test_key_q11"
        sender._api_secret = "test_secret_q11"
        sender._key_present    = True
        sender._secret_present = True
        # protected_entry_policy_required defaults to True
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT", confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert G20_BLOCKED_GATE_NAME in r.blocked_gates
        assert r.execute_allowed is False
        assert r.order_sent is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.protected_entry_required is True

    def test_execute_blocked_does_not_touch_network(self, monkeypatch):
        """If G20 fires, the sender must not even reach pre-send refresh."""
        from src.demo_new_entry_sender import DemoNewEntrySender
        review = _full_sender_review()
        now    = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
        token  = _today_token(now)
        sender = DemoNewEntrySender(allow_real_network=True)
        sender._api_key    = "test_key_q11b"
        sender._api_secret = "test_secret_q11b"
        sender._key_present    = True
        sender._secret_present = True

        # Sentinel: any call to urlopen would explode.  G20 must fire BEFORE
        # the refresh attempts any network reads.
        def _explode(*args, **kwargs):
            raise AssertionError("urlopen must not be called when G20 fires")

        monkeypatch.setattr("urllib.request.urlopen", _explode)
        ro = self._make_ro_client_with_no_target_open()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT", confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert G20_BLOCKED_GATE_NAME in r.blocked_gates


class TestQ14ProtectionStillBlocksWithRealtimeGuard:
    def test_realtime_guard_verified_but_g20_still_blocks_execute(self):
        from src.demo_new_entry_sender import DemoNewEntrySender
        review = _full_sender_review()  # realtime_price_guard_verified=True
        now    = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
        token  = _today_token(now)
        sender = DemoNewEntrySender(allow_real_network=True)
        sender._api_key    = "test_key_q14"
        sender._api_secret = "test_secret_q14"
        sender._key_present    = True
        sender._secret_present = True

        # G19 (realtime guard) explicitly passes; G20 must still block.
        ro = TestQ11SenderBlocksExecuteWhenProtectionMissing()\
            ._make_ro_client_with_no_target_open()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT", confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert "missing_realtime_price_guard" not in r.blocked_gates
        assert G20_BLOCKED_GATE_NAME in r.blocked_gates


# ---------------------------------------------------------------------------
# Q12 — Dry-run still reports protected_entry_required=True
# ---------------------------------------------------------------------------

class TestQ12DryRunReportsProtectedEntryRequired:
    def test_dry_run_protected_entry_required_true(self):
        from src.demo_new_entry_sender import DemoNewEntrySender
        review = _full_sender_review()
        now    = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
        token  = _today_token(now)
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT", confirm_token=token,
            execute_new_entry=False, _now=now,
        )
        # Dry-run reports the required flag without blocking the dry-run path
        assert r.protected_entry_required is True
        assert r.order_sent is False
        assert r.order_endpoint_called is False
        # Dry-run with verified review passes — execute_allowed True
        assert r.execute_allowed is True

    def test_dry_run_protected_entry_required_in_dict(self):
        from src.demo_new_entry_sender import DemoNewEntrySender
        review = _full_sender_review()
        now    = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
        token  = _today_token(now)
        r = DemoNewEntrySender().submit_one_new_entry(
            review=review, symbol="AAVEUSDT", confirm_token=token,
            execute_new_entry=False, _now=now,
        )
        assert r.to_dict()["protected_entry_required"] is True


# ---------------------------------------------------------------------------
# Q13 — Legacy review without realtime guard remains blocked at G19
# ---------------------------------------------------------------------------

class TestQ13LegacyReviewStillBlocked:
    def test_legacy_review_blocked_g19(self):
        from src.demo_new_entry_sender import DemoNewEntrySender
        review = _full_sender_review()
        review["realtime_price_guard_verified"] = False
        now    = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
        token  = _today_token(now)
        sender = DemoNewEntrySender(allow_real_network=True)
        sender._api_key    = "test_key_q13"
        sender._api_secret = "test_secret_q13"
        # Even if a caller tried to bypass G20, the legacy review still
        # fails G19 — defense in depth.
        sender._protected_entry_policy_required = False
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT", confirm_token=token,
            execute_new_entry=True, _now=now,
        )
        assert "missing_realtime_price_guard" in r.blocked_gates
        assert r.order_sent is False
        assert r.execute_allowed is False


# ---------------------------------------------------------------------------
# Q15 — No TP / leverage / transfer / withdraw / deposit in module
# ---------------------------------------------------------------------------

class TestQ15NoForbiddenOps:
    def test_no_take_profit_or_set_leverage(self):
        code = _read_code_only(_PROT_SRC)
        assert "takeProfit"   not in code
        assert "setLeverage"  not in code
        assert "set_leverage" not in code

    def test_no_transfer_withdraw_deposit_in_code(self):
        # Code-only assertion: identifiers / function names / endpoints must
        # not reference transfer / withdraw / deposit anywhere in module code.
        code = _read_code_only(_PROT_SRC).lower()
        assert "transfer" not in code
        assert "withdraw" not in code
        assert "deposit"  not in code


# ---------------------------------------------------------------------------
# Q16 — No emergency close triggered via this preview path
# ---------------------------------------------------------------------------

class TestQ16NoEmergencyClose:
    def test_module_does_not_import_emergency_close(self):
        imports = _ast_imports(_PROT_SRC)
        for name in imports:
            assert "emergency_close" not in name

    def test_script_does_not_import_emergency_close(self):
        imports = _ast_imports(_PROT_SCRIPT)
        for name in imports:
            assert "emergency_close" not in name


# ---------------------------------------------------------------------------
# Dataclass round-trip + lifecycle phase + preview-only status
# ---------------------------------------------------------------------------

class TestProtectedEntryPlanStructure:
    def test_to_dict_round_trip_keys(self):
        plan = _build_plan()
        d    = plan.to_dict()
        # Mandatory keys
        for k in (
            "timestamp_utc", "selected_symbol", "selected_side",
            "order_side", "selected_qty", "entry_reference_price",
            "stop_price", "stop_order_side", "stop_trigger_direction",
            "realtime_price_guard_verified", "review_fail_closed",
            "review_timestamp", "blocked_reasons", "lifecycle_phase",
            "protected_entry_status", "stop_loss_attach_required",
            "stop_loss_endpoint_allowed", "preview_only",
            "protected_entry_execute_allowed", "protected_entry_execute_reason",
            "no_orders_sent", "order_endpoint_called",
            "stop_endpoint_called", "no_position_modified",
            "no_live_endpoint", "secret_value_observed",
            "order_create_endpoint", "stop_attach_endpoint",
            "endpoint_family", "next_required_task",
        ):
            assert k in d

    def test_preview_only_status_for_valid_review(self):
        plan = _build_plan()
        assert plan.protected_entry_status == PROTECTED_ENTRY_STATUS_PREVIEW_ONLY
        assert plan.lifecycle_phase == PHASE_PRE_ENTRY_REVIEW

    def test_stop_trigger_direction_for_long(self):
        plan = _build_plan()
        assert plan.stop_trigger_direction == "fall_below_entry"
        assert plan.stop_order_side == "Sell"

    def test_review_fail_closed_propagated(self):
        review = _good_review()
        review["fail_closed"] = True
        plan = _build_plan(review=review)
        assert plan.review_fail_closed is True
        assert REASON_REVIEW_FAIL_CLOSED in plan.blocked_reasons


# ---------------------------------------------------------------------------
# CLI smoke: missing review file => exit 1; report writer emits files
# ---------------------------------------------------------------------------

class TestPreviewCliSmoke:
    def test_missing_review_returns_one(self):
        from scripts.preview_demo_new_entry_protection import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = run_preview(symbol="SOLUSDT", review_dir=Path(tmpdir))
        assert rc == 1

    def test_write_report_emits_json_and_md(self):
        from scripts.preview_demo_new_entry_protection import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            review = _good_review()
            (d / "latest_new_entry_review.json").write_text(
                json.dumps(review), encoding="utf-8"
            )
            outdir = d / "out"
            rc = run_preview(
                symbol="SOLUSDT",
                write_report=True,
                review_dir=d,
                protection_dir=outdir,
            )
            assert rc == 0
            assert (outdir / "latest_new_entry_protection.json").exists()
            assert (outdir / "latest_new_entry_protection.md").exists()
            txt = (outdir / "latest_new_entry_protection.json").read_text(
                encoding="utf-8"
            )
            data = json.loads(txt)
            assert data["selected_symbol"] == "SOLUSDT"
            assert data["protected_entry_execute_allowed"] is False
            assert data["stop_endpoint_called"] is False
            assert data["order_endpoint_called"] is False
            assert data["no_orders_sent"] is True
