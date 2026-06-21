"""Tests for TASK-014BP single reduce-only close gate.

All tests are strictly offline. No test contacts Bybit; every transport and
probe is an injected fake. No real or demo credentials are loaded. No order is
ever sent to a real host.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import inspect
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_only_tiny_execution_adapter_single_real_demo_order as bo
from src import demo_only_single_reduce_only_close as bp

CLI_MODULE = "scripts.run_demo_only_single_reduce_only_close"
cli = importlib.import_module(CLI_MODULE)


EXPECTED_COMMIT = "0123456789abcdef0123456789abcdef01234567"
OTHER_COMMIT = "fedcba9876543210fedcba9876543210fedcba98"
ORDER_LINK_ID = bp.build_close_order_link_id()


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self, dt=None):
        self._dt = dt or datetime(2026, 6, 21, 6, 0, 0, tzinfo=timezone.utc)

    def now_utc(self):
        return self._dt

    def sleep(self, seconds):
        pass


class FakeTransport:
    def __init__(self, *, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.post_calls = 0

    def signed_headers_for_post(self, body_str):
        return {"Content-Type": "application/json", "X-BAPI-API-KEY": "FAKE", "X-BAPI-SIGN": "FAKE"}

    def post_order_create(self, *, url, headers, body_bytes):
        self.post_calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.response


def _resp(items, ret_code=0, ret_msg="OK"):
    return {"retCode": ret_code, "retMsg": ret_msg, "result": {"list": list(items)}}


class FakeCloseProbe:
    def __init__(self, *, snapshot=None, dedup_realtime=None, dedup_history=None,
                 realtime=None, history=None, execution=None, position=None, raise_snapshot=False):
        self._snapshot = snapshot if snapshot is not None else good_snapshot()
        self._dedup_realtime = dedup_realtime if dedup_realtime is not None else _resp([])
        self._dedup_history = dedup_history if dedup_history is not None else _resp([])
        self._realtime = realtime if realtime is not None else [_resp([])]
        self._history = history if history is not None else [_resp([])]
        self._execution = execution if execution is not None else [_resp([])]
        self._position = position if position is not None else [_resp([])]
        self._raise_snapshot = raise_snapshot
        self.snapshot_calls = 0
        self.lookup_realtime_calls = 0
        self.lookup_history_calls = 0
        self.realtime_calls = 0
        self.history_calls = 0
        self.execution_calls = 0
        self.position_calls = 0
        self.last_dedup_realtime_link = None
        self.last_dedup_history_link = None

    def build_close_snapshot(self):
        self.snapshot_calls += 1
        if self._raise_snapshot:
            raise RuntimeError("snapshot read failed")
        return self._snapshot

    def lookup_order_link_realtime(self, *, order_link_id):
        self.lookup_realtime_calls += 1
        self.last_dedup_realtime_link = order_link_id
        if isinstance(self._dedup_realtime, Exception):
            raise self._dedup_realtime
        return self._dedup_realtime

    def lookup_order_link_history(self, *, order_link_id):
        self.lookup_history_calls += 1
        self.last_dedup_history_link = order_link_id
        if isinstance(self._dedup_history, Exception):
            raise self._dedup_history
        return self._dedup_history

    def _pick(self, lst, idx):
        return lst[min(idx, len(lst) - 1)] if lst else _resp([])

    def read_order_realtime(self, *, order_id, order_link_id):
        r = self._pick(self._realtime, self.realtime_calls)
        self.realtime_calls += 1
        return r

    def read_order_history(self, *, order_id, order_link_id):
        r = self._pick(self._history, self.history_calls)
        self.history_calls += 1
        return r

    def read_execution_list(self, *, order_id, order_link_id):
        r = self._pick(self._execution, self.execution_calls)
        self.execution_calls += 1
        return r

    def read_position_list(self, *, symbol):
        r = self._pick(self._position, self.position_calls)
        self.position_calls += 1
        return r


def good_snapshot(**over):
    base = dict(
        instrument_fresh=True, symbol_tradable=True,
        min_order_qty=Decimal("0.1"), qty_step=Decimal("0.1"),
        long_size=Decimal("0.1"), short_size=None, long_row_count=1,
        position_mode_one_way=True, ambiguous=False, read_source="fixture",
    )
    base.update(over)
    return bp.ClosePositionSnapshot(**base)


def good_creds():
    return bo.DemoCredentials(api_key_present=True, api_secret_present=True,
                              recv_window="5000", source="BYBIT_DEMO")


def good_source_journal(**over):
    base = dict(state=bp.SOURCE_REQUIRED_JOURNAL_STATE, conclusion=bp.SOURCE_RESULT,
                order_id=bp.SOURCE_ORDER_ID, order_link_id=bp.SOURCE_ORDER_LINK_ID)
    base.update(over)
    return base


def clean_dup():
    return bo.DuplicateCheckResult(realtime_checked=True, realtime_match=False,
                                   history_checked=True, history_match=False,
                                   ambiguous=False, detail="clean")


def base_gate_kwargs(**over):
    body = over.pop("request_body", bp.build_close_body(order_link_id=ORDER_LINK_ID))
    kw = dict(
        request_body=body, order_link_id=body.get("orderLinkId", ORDER_LINK_ID),
        authorization_marker=bp.CLOSE_AUTHORIZATION_MARKER,
        expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        credentials=good_creds(), snapshot=good_snapshot(),
        source_journal=good_source_journal(), journal_state=bp.CLOSE_STATE_NONE,
        execution_flags={"mode": "execute_once", "execute_one_reduce_only_close": True},
        expected_body_hash=None, duplicate_check=clean_dup(), real_order_count_before=0,
    )
    kw.update(over)
    return kw


def passed(gates, name):
    return next(g for g in gates if g.name == name).passed


def expected_body_hash():
    return bp.body_hash(bp.build_close_body(order_link_id=bp.build_close_order_link_id()))


def dup_match_resp():
    return _resp([{"orderId": "DUP", "orderLinkId": ORDER_LINK_ID, "orderStatus": "New"}])


# ---------------------------------------------------------------------------
# 1. Identity / authorization
# ---------------------------------------------------------------------------


def test_task_and_authorization_identity():
    assert bp.TASK_ID == "TASK-014BP"
    assert bp.IDENTITY == "DEMO-ONLY-SINGLE-REDUCE-ONLY-CLOSE"
    d = bp.describe_close_authorization()
    assert d["side"] == "Sell" and d["reduce_only"] is True and d["close_on_trigger"] is False
    assert d["qty"] == "0.1" and d["symbol"] == "SOLUSDT"
    assert d["source_order_id"] == "77173918-71f6-4829-91c9-025bd8cd76fa"
    assert d["source_order_link_id"] == "BO1-4696d511edf11b50"
    assert d["source_result"] == "DEMO_ORDER_FILLED_VERIFIED"
    assert "reduceOnly Market 平倉單" in bp.AUTHORIZATION_QUOTE


# ---------------------------------------------------------------------------
# 2-4. Host lock / redirect
# ---------------------------------------------------------------------------


def test_demo_host_allowed():
    bp.assert_demo_url("https://api-demo.bybit.com/v5/order/create")


def test_live_testnet_arbitrary_host_rejected():
    for url in ("https://api.bybit.com/v5/order/create",
                "https://api-testnet.bybit.com/v5/order/create",
                "https://evil.example.com/x"):
        with pytest.raises(bo.EndpointLockViolation):
            bp.assert_demo_url(url)


def test_redirect_rejected_during_execute(tmp_path):
    transport = FakeTransport(raise_exc=bo.RedirectRejected("redirect"))
    sender = bo.OneShotSenderGuard(transport)
    journal = bp.CloseOneShotJournal(str(tmp_path))
    report = bp.execute_single_reduce_only_close(
        probe=FakeCloseProbe(), sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, source_journal=good_source_journal(),
        expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bp.CLOSE_AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_reduce_only_close": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock())
    assert report.close_journal_state == bp.CLOSE_POST_REJECTED_BEFORE_NETWORK
    assert report.final_outcome == bp.OUTCOME_POST_FAILED
    assert sender.call_count == 1


# ---------------------------------------------------------------------------
# 5-10. Body
# ---------------------------------------------------------------------------


def test_exact_nine_field_close_body():
    body = bp.build_close_body(order_link_id=ORDER_LINK_ID)
    assert set(body) == set(bp.APPROVED_BODY_FIELDS) and len(body) == 9
    for forbidden in ("price", "positionIdx", "takeProfit", "stopLoss", "triggerPrice",
                      "trailingStop", "orderFilter", "marketUnit"):
        assert forbidden not in body


def test_all_gates_pass_on_good_inputs():
    gates = bp.evaluate_close_preflight_gates(**base_gate_kwargs())
    assert all(g.passed for g in gates), [g.name for g in gates if not g.passed]
    assert len(gates) == 32


def test_side_must_be_sell():
    body = bp.build_close_body(order_link_id=ORDER_LINK_ID)
    assert body["side"] == "Sell"
    body["side"] = "Buy"
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(request_body=body)), "side_is_sell")


def test_qty_must_be_0_1():
    body = bp.build_close_body(order_link_id=ORDER_LINK_ID)
    assert body["qty"] == "0.1"


def test_reduce_only_must_be_true():
    body = bp.build_close_body(order_link_id=ORDER_LINK_ID)
    assert body["reduceOnly"] is True
    body["reduceOnly"] = False
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(request_body=body)), "reduce_only_is_true")


def test_close_on_trigger_must_be_false():
    body = bp.build_close_body(order_link_id=ORDER_LINK_ID)
    body["closeOnTrigger"] = True
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(request_body=body)), "close_on_trigger_is_false")


def test_additional_body_field_refused():
    body = bp.build_close_body(order_link_id=ORDER_LINK_ID)
    body["positionIdx"] = 0
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(request_body=body)),
                      "body_has_exactly_nine_approved_fields")


# ---------------------------------------------------------------------------
# 11-13. Permanent close orderLinkId
# ---------------------------------------------------------------------------


def test_close_order_link_id_commit_date_independent(monkeypatch):
    import re
    a = bp.build_close_order_link_id()
    assert re.fullmatch(r"BC1-[0-9a-f]{16}", a)
    assert not re.search(r"\d{8}", a)
    assert len(a) <= 36

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2099, 1, 1, tzinfo=tz)

    monkeypatch.setattr(bp, "datetime", _FrozenDateTime, raising=False)
    assert bp.build_close_order_link_id() == a
    reloaded = importlib.reload(bp)
    assert reloaded.build_close_order_link_id() == a
    importlib.reload(bp)


def test_close_order_link_id_equals_hash_of_identity_marker_scope():
    digest = hashlib.sha256(
        (bp.TASK_ID + "|" + bp.CLOSE_AUTHORIZATION_MARKER + "|" + bp.CLOSE_AUTHORIZATION_SCOPE_IDENTITY).encode("utf-8")
    ).hexdigest()[:16]
    assert bp.build_close_order_link_id() == f"BC1-{digest}"


def test_caller_cannot_override_close_order_link_id():
    assert "order_link_id" not in inspect.signature(bp.run_close_preflight).parameters
    assert "order_link_id" not in inspect.signature(bp.execute_single_reduce_only_close).parameters
    assert inspect.signature(bp.build_close_order_link_id).parameters == {}


# ---------------------------------------------------------------------------
# 13. Canonical journal not overridable
# ---------------------------------------------------------------------------


def test_canonical_close_journal_not_overridable(monkeypatch, tmp_path):
    monkeypatch.setenv("TASK_014BP_JOURNAL_DIR", "/tmp/evil")
    p1 = bp.canonical_close_journal().path
    p2 = bp.canonical_close_journal().path
    assert p1 == p2 == str(bp.CANONICAL_CLOSE_JOURNAL_DIR / bp.CLOSE_JOURNAL_FILENAME)
    rel = bp.CANONICAL_CLOSE_JOURNAL_DIR.resolve().relative_to(bp.PROJECT_ROOT.resolve())
    assert rel == pathlib.Path("outputs/demo_trading/task_014bp_single_reduce_only_close")
    cli_src = pathlib.Path(cli.__file__).read_text(encoding="utf-8")
    assert "canonical_close_journal()" in cli_src
    actions = {a.dest for a in cli.build_parser()._actions}
    assert "journal_dir" not in actions


# ---------------------------------------------------------------------------
# 14-18. Source opening-position verification
# ---------------------------------------------------------------------------


def test_missing_opening_journal_refused():
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(source_journal=None)),
                      "source_opening_journal_exists")


def test_wrong_opening_state_refused():
    sj = good_source_journal(state="POST_RESPONSE_RECEIVED")
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(source_journal=sj)),
                      "source_journal_state_is_post_result_verified")


def test_wrong_opening_conclusion_refused():
    sj = good_source_journal(conclusion="DEMO_ORDER_OUTCOME_AMBIGUOUS")
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(source_journal=sj)),
                      "source_conclusion_is_demo_order_filled_verified")


def test_wrong_source_order_id_refused():
    sj = good_source_journal(order_id="00000000-0000-0000-0000-000000000000")
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(source_journal=sj)),
                      "source_order_id_matches")


def test_wrong_source_order_link_id_refused():
    sj = good_source_journal(order_link_id="BO1-deadbeefdeadbeef")
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(source_journal=sj)),
                      "source_order_link_id_matches")


# ---------------------------------------------------------------------------
# 19-25. Position verification
# ---------------------------------------------------------------------------


def test_missing_current_position_refused():
    snap = good_snapshot(long_size=None, long_row_count=0)
    g = bp.evaluate_close_preflight_gates(**base_gate_kwargs(snapshot=snap))
    assert not passed(g, "exactly_one_solusdt_long_position")
    assert not passed(g, "position_side_is_buy")


def test_position_zero_refused():
    snap = good_snapshot(long_size=Decimal("0"), long_row_count=1)
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "position_size_is_exactly_0_1")


def test_position_below_0_1_refused():
    snap = good_snapshot(long_size=Decimal("0.05"))
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "position_size_is_exactly_0_1")


def test_position_above_0_1_refused():
    snap = good_snapshot(long_size=Decimal("0.2"))
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "position_size_is_exactly_0_1")


def test_short_position_refused():
    snap = good_snapshot(short_size=Decimal("0.1"))
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "no_solusdt_short_position")


def test_hedge_mode_incompatibility_refused():
    snap = good_snapshot(position_mode_one_way=False)
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "position_mode_one_way_compatible")


def test_multiple_ambiguous_position_rows_refused():
    snap = good_snapshot(ambiguous=True)
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "no_ambiguous_solusdt_position_rows")
    snap2 = good_snapshot(long_row_count=2)
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(snapshot=snap2)),
                      "exactly_one_solusdt_long_position")


# ---------------------------------------------------------------------------
# 26-28. Duplicate detection
# ---------------------------------------------------------------------------


def test_realtime_close_duplicate_refused():
    dc = bo.DuplicateCheckResult(realtime_checked=True, realtime_match=True,
                                 history_checked=True, history_match=False, ambiguous=False, detail="rt")
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(duplicate_check=dc)),
                      "realtime_has_no_close_order_link_id")


def test_history_close_duplicate_refused():
    dc = bo.DuplicateCheckResult(realtime_checked=True, realtime_match=False,
                                 history_checked=True, history_match=True, ambiguous=False, detail="h")
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(duplicate_check=dc)),
                      "history_has_no_close_order_link_id")


def test_duplicate_query_failure_refused():
    dc = bp.offline_duplicate_check("query failed")
    g = bp.evaluate_close_preflight_gates(**base_gate_kwargs(duplicate_check=dc))
    assert not passed(g, "both_duplicate_sources_checked_and_valid")
    assert not passed(g, "no_active_task_014bp_close_order")


# ---------------------------------------------------------------------------
# 29-30. Offline / help no-network
# ---------------------------------------------------------------------------


def test_offline_preflight_fails_closed_and_no_http():
    probe = FakeCloseProbe()
    report = bp.run_close_preflight(
        probe=probe, credentials=good_creds(), expected_commit=EXPECTED_COMMIT,
        authorization_marker=bp.CLOSE_AUTHORIZATION_MARKER, source_journal=good_source_journal(),
        actual_commit=EXPECTED_COMMIT, allow_real_network=False)
    assert report.ready is False
    assert report.duplicate_check["clean"] is False
    assert report.position_evidence == {"authenticated_position_check": "not performed"}
    assert probe.snapshot_calls == 0
    assert probe.lookup_realtime_calls == 0 and probe.lookup_history_calls == 0


def test_cli_help_no_network():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_demo_only_single_reduce_only_close.py"), "--help"],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert "preflight" in result.stdout
    assert "--journal-dir" not in result.stdout


def test_default_cli_is_offline_preflight(capsys):
    args = cli.build_parser().parse_args([])
    assert args.mode == "preflight" and args.allow_real_network is False
    rc = cli.main(["--json-only"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "preflight"
    assert payload["ready"] is False
    assert rc == cli.EXIT_NOT_READY


# ---------------------------------------------------------------------------
# 31-36. Journal / marker / flag / commit / hash
# ---------------------------------------------------------------------------


def test_existing_close_journal_refused():
    assert not passed(bp.evaluate_close_preflight_gates(
        **base_gate_kwargs(journal_state=bp.CLOSE_STATE_ARMED_BEFORE_CLOSE_POST)),
        "no_conflicting_close_journal")


def test_missing_marker_refused():
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(authorization_marker=None)),
                      "close_authorization_marker_matches")


def test_wrong_marker_refused():
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(authorization_marker="WRONG")),
                      "close_authorization_marker_matches")


def test_missing_execute_flag_refused():
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(execution_flags={})),
                      "execution_flags_match")


def test_short_or_malformed_commit_refused():
    assert not passed(bp.evaluate_close_preflight_gates(
        **base_gate_kwargs(expected_commit="a4879e4", actual_commit="a4879e4")),
        "git_identity_matches_approved_full_sha")
    assert bp.is_full_commit_sha("HEAD") is False
    assert bp.is_full_commit_sha(EXPECTED_COMMIT.upper()) is False


def test_body_hash_mismatch_refused():
    assert not passed(bp.evaluate_close_preflight_gates(**base_gate_kwargs(expected_body_hash="deadbeef")),
                      "request_body_hash_matches")


# ---------------------------------------------------------------------------
# 37-46. Execute-once
# ---------------------------------------------------------------------------


def _execute(tmp_path, *, probe=None, transport=None, source_journal=None):
    journal = bp.CloseOneShotJournal(str(tmp_path))
    transport = transport or FakeTransport(response={"retCode": 0, "result": {"orderId": "C-1"}})
    sender = bo.OneShotSenderGuard(transport)
    probe = probe if probe is not None else FakeCloseProbe(
        realtime=[_resp([{"orderId": "C-1", "orderStatus": "Filled", "cumExecQty": "0.1"}])],
        position=[_resp([])])
    report = bp.execute_single_reduce_only_close(
        probe=probe, sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, source_journal=source_journal if source_journal is not None else good_source_journal(),
        expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bp.CLOSE_AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_reduce_only_close": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock())
    return report, sender, transport, probe


def test_execute_reruns_position_and_duplicate_lookups(tmp_path):
    report, sender, transport, probe = _execute(tmp_path)
    assert probe.snapshot_calls == 1
    assert probe.lookup_realtime_calls == 1 and probe.lookup_history_calls == 1
    assert report.final_outcome == bp.OUTCOME_FILLED_ZERO


def test_position_changed_after_preflight_refuses_before_arm(tmp_path):
    probe = FakeCloseProbe(snapshot=good_snapshot(long_size=Decimal("0.05")))
    report, sender, transport, _ = _execute(tmp_path, probe=probe)
    assert report.final_outcome == bp.OUTCOME_REFUSED_PREFLIGHT
    assert sender.call_count == 0 and transport.post_calls == 0
    assert not bp.CloseOneShotJournal(str(tmp_path)).exists()


def test_duplicate_after_preflight_refuses_before_arm(tmp_path):
    probe = FakeCloseProbe(dedup_realtime=dup_match_resp())
    report, sender, transport, _ = _execute(tmp_path, probe=probe)
    assert report.final_outcome == bp.OUTCOME_REFUSED_PREFLIGHT
    assert sender.call_count == 0 and transport.post_calls == 0
    assert not bp.CloseOneShotJournal(str(tmp_path)).exists()


def test_position_already_zero_refuses(tmp_path):
    probe = FakeCloseProbe(snapshot=good_snapshot(long_size=Decimal("0"), long_row_count=1))
    report, sender, transport, _ = _execute(tmp_path, probe=probe)
    assert report.final_outcome == bp.OUTCOME_REFUSED_PREFLIGHT
    assert sender.call_count == 0


def test_approved_fake_path_posts_exactly_once(tmp_path):
    report, sender, transport, probe = _execute(tmp_path)
    assert sender.call_count == 1 and transport.post_calls == 1
    assert report.post_count == 1


def test_sender_never_called_twice():
    transport = FakeTransport(response=_resp([]))
    sender = bo.OneShotSenderGuard(transport)
    url = bo.DEMO_BASE_URL + bo.ORDER_CREATE_PATH
    sender.send_order_create(url=url, headers={}, body_bytes=b"{}")
    with pytest.raises(bo.SenderInvokedTwice):
        sender.send_order_create(url=url, headers={}, body_bytes=b"{}")


def test_timeout_ambiguous_no_retry(tmp_path):
    t = FakeTransport(raise_exc=bo.TransportTimeout("timed out"))
    report, sender, transport, _ = _execute(tmp_path, transport=t)
    assert report.close_journal_state == bp.CLOSE_POST_TIMEOUT_AMBIGUOUS
    assert report.final_outcome == bp.OUTCOME_AMBIGUOUS
    assert report.no_retry_performed is True and sender.call_count == 1


def test_connection_failure_ambiguous_no_retry(tmp_path):
    t = FakeTransport(raise_exc=bo.TransportConnectionError("reset"))
    report, sender, transport, _ = _execute(tmp_path, transport=t)
    assert report.close_journal_state == bp.CLOSE_POST_EXCEPTION_AMBIGUOUS
    assert sender.call_count == 1


def test_malformed_response_ambiguous_no_retry(tmp_path):
    t = FakeTransport(raise_exc=bo.SingleRealDemoOrderError("malformed"))
    report, sender, transport, _ = _execute(tmp_path, transport=t)
    assert report.close_journal_state == bp.CLOSE_RESULT_UNVERIFIED
    assert report.outcome_ambiguous is True and sender.call_count == 1


def test_nonzero_retcode_one_attempt_no_retry(tmp_path):
    t = FakeTransport(response={"retCode": 110017, "retMsg": "reduce-only error", "result": {}})
    report, sender, transport, _ = _execute(tmp_path, transport=t)
    assert report.post_ret_code == 110017
    assert report.final_outcome == bp.OUTCOME_POST_FAILED
    assert sender.call_count == 1 and report.real_close_sent is False


# ---------------------------------------------------------------------------
# 47-51. Verification classification
# ---------------------------------------------------------------------------


def test_filled_qty_0_1_position_zero_complete_closure(tmp_path):
    probe = FakeCloseProbe(
        realtime=[_resp([{"orderId": "C-1", "orderStatus": "Filled", "cumExecQty": "0.1"}])],
        position=[_resp([])])
    report, sender, transport, _ = _execute(tmp_path, probe=probe)
    assert report.final_outcome == bp.OUTCOME_FILLED_ZERO
    assert report.verification["position_is_zero"] is True


def test_filled_but_residual_long_not_complete(tmp_path):
    probe = FakeCloseProbe(
        realtime=[_resp([{"orderId": "C-1", "orderStatus": "Filled", "cumExecQty": "0.05"}])],
        position=[_resp([{"symbol": "SOLUSDT", "side": "Buy", "size": "0.05"}])])
    report, sender, transport, _ = _execute(tmp_path, probe=probe)
    assert report.final_outcome == bp.OUTCOME_PARTIAL_RESIDUAL


def test_partial_fill_never_triggers_second_order(tmp_path):
    probe = FakeCloseProbe(
        realtime=[_resp([{"orderId": "C-1", "orderStatus": "PartiallyFilledCanceled", "cumExecQty": "0.05"}])],
        position=[_resp([{"symbol": "SOLUSDT", "side": "Buy", "size": "0.05"}])])
    report, sender, transport, _ = _execute(tmp_path, probe=probe)
    assert report.final_outcome == bp.OUTCOME_PARTIAL_RESIDUAL
    assert sender.call_count == 1 and transport.post_calls == 1


def test_cancelled_rejected_pending_classifications(tmp_path):
    cancelled = FakeCloseProbe(realtime=[_resp([{"orderId": "C-1", "orderStatus": "Cancelled"}])],
                               position=[_resp([{"symbol": "SOLUSDT", "side": "Buy", "size": "0.1"}])])
    r1, *_ = _execute(tmp_path / "a", probe=cancelled)
    assert r1.final_outcome == bp.OUTCOME_CANCELLED_REMAINS
    rejected = FakeCloseProbe(realtime=[_resp([{"orderId": "C-1", "orderStatus": "Rejected"}])])
    r2, *_ = _execute(tmp_path / "b", probe=rejected)
    assert r2.final_outcome == bp.OUTCOME_REJECTED
    pending = FakeCloseProbe(realtime=[_resp([{"orderId": "C-1", "orderStatus": "New"}])])
    r3, *_ = _execute(tmp_path / "c", probe=pending)
    assert r3.final_outcome == bp.OUTCOME_ACCEPTED_PENDING


def test_post_close_short_position_is_critical(tmp_path):
    probe = FakeCloseProbe(
        realtime=[_resp([{"orderId": "C-1", "orderStatus": "Filled", "cumExecQty": "0.1"}])],
        position=[_resp([{"symbol": "SOLUSDT", "side": "Sell", "size": "0.1"}])])
    report, sender, transport, _ = _execute(tmp_path, probe=probe)
    assert report.final_outcome == bp.OUTCOME_CRITICAL_SHORT


# ---------------------------------------------------------------------------
# 52-58. Safety scans / verification-no-post / journal
# ---------------------------------------------------------------------------


def test_verification_reads_never_post(tmp_path):
    report, sender, transport, probe = _execute(tmp_path)
    assert transport.post_calls == 1


SRC_TEXT = pathlib.Path(bp.__file__).read_text(encoding="utf-8")
CLI_TEXT = pathlib.Path(cli.__file__).read_text(encoding="utf-8")


def _import_lines(text):
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith(("import ", "from "))]


def test_no_automatic_close_loop_or_retry():
    assert bp.RETRY_ENABLED is False and bp.SCHEDULER_ENABLED is False
    for token in ("import tenacity", "import backoff", "@retry", "while True"):
        assert token not in SRC_TEXT


def test_no_live_executor_or_main_or_risk_import():
    for ln in _import_lines(SRC_TEXT) + _import_lines(CLI_TEXT):
        assert "executors.bybit" not in ln and "BybitExecutor" not in ln
        assert "src.risk" not in ln
        assert not ln.startswith("import main") and not ln.startswith("from main ")
    assert "BybitExecutor(" not in SRC_TEXT


def test_no_secret_serialization(tmp_path):
    report, *_ = _execute(tmp_path)
    blob = json.dumps(report.to_dict())
    for forbidden in ("X-BAPI-SIGN", "BYBIT_DEMO_API_SECRET", "api_secret", "X-BAPI-API-KEY"):
        assert forbidden not in blob


def test_frozen_report_dataclasses():
    for c in (bp.ClosePreflightReport, bp.CloseReport, bp.CloseVerificationResult,
              bp.ClosePositionSnapshot):
        assert dataclasses.is_dataclass(c)
    snap = good_snapshot()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.long_size = Decimal("9")  # type: ignore[misc]


def test_atomic_close_journal_behavior(tmp_path):
    journal = bp.CloseOneShotJournal(str(tmp_path))
    assert journal.state() == bp.CLOSE_STATE_NONE
    journal.arm_close(body_hash_value="h", order_link_id=ORDER_LINK_ID,
                      expected_commit=EXPECTED_COMMIT, preflight_summary={"ok": True}, clock=FakeClock())
    assert journal.state() == bp.CLOSE_STATE_ARMED_BEFORE_CLOSE_POST
    assert not (tmp_path / (bp.CLOSE_JOURNAL_FILENAME + ".tmp")).exists()
    with pytest.raises(bo.JournalStateConflict):
        journal.arm_close(body_hash_value="h", order_link_id=ORDER_LINK_ID,
                          expected_commit=EXPECTED_COMMIT, preflight_summary={}, clock=FakeClock())


def test_existing_close_journal_blocks_execute(tmp_path):
    journal = bp.CloseOneShotJournal(str(tmp_path))
    journal._atomic_write({"task_id": bp.TASK_ID, "state": bp.CLOSE_RESULT_VERIFIED})
    transport = FakeTransport(response={"retCode": 0, "result": {"orderId": "C-2"}})
    sender = bo.OneShotSenderGuard(transport)
    report = bp.execute_single_reduce_only_close(
        probe=FakeCloseProbe(), sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, source_journal=good_source_journal(),
        expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bp.CLOSE_AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_reduce_only_close": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock())
    assert report.final_outcome == bp.OUTCOME_REFUSED_PREFLIGHT
    assert sender.call_count == 0 and transport.post_calls == 0


# ---------------------------------------------------------------------------
# 59-61. CLI execute refusals / report writer / docs
# ---------------------------------------------------------------------------


def test_cli_execute_once_without_real_network_refused():
    rc = cli.main(["--mode", "execute_once", "--execute-one-reduce-only-close",
                   "--authorization-marker", bp.CLOSE_AUTHORIZATION_MARKER,
                   "--expected-commit", EXPECTED_COMMIT, "--request-body-hash", "x"])
    assert rc == cli.EXIT_SAFETY


def test_cli_has_no_bypass_options():
    options = set()
    for a in cli.build_parser()._actions:
        options.update(a.option_strings)
    for forbidden in ("--force", "--reset", "--ignore-journal", "--new-order-link-id",
                      "--journal-dir", "--qty", "--side", "--reduce-only"):
        assert forbidden not in options


def test_report_writer_json_and_markdown(tmp_path):
    paths = cli._write_reports(str(tmp_path), "task_014bp_close_preflight", {"task_id": bp.TASK_ID})
    for key in ("json", "json_latest", "md", "md_latest"):
        assert pathlib.Path(paths[key]).exists()


def test_documentation_mentions_task_014bp():
    for rel in ("README.md", "docs/research/commands/NEXT_ACTION.md",
                "docs/research/commands/COMMAND_LOG.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "TASK-014BP" in text
        assert "reduceOnly" in text or "reduce-only" in text.lower()


def test_final_command_template_no_journal_dir_and_full_sha():
    cmd = cli._manual_command(expected_commit=EXPECTED_COMMIT, body_hash="abc")
    assert "--journal-dir" not in cmd
    assert "--execute-one-reduce-only-close" in cmd
    assert f"--expected-commit {EXPECTED_COMMIT}" in cmd
    short = cli._manual_command(expected_commit="a4879e4", body_hash="abc")
    assert "<FULL_40_CHARACTER" in short
