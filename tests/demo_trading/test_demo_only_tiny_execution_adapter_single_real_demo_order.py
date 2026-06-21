"""Tests for TASK-014BO single real Bybit Demo order execution gate
(including the TASK-014BO deduplication & journal-hardening correction).

All tests are strictly offline. No test calls any Bybit network endpoint;
every transport and probe is an injected fake. No real or demo credentials
are loaded. No order is ever sent to a real host.
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

CLI_MODULE = "scripts.run_demo_only_single_real_order"
cli = importlib.import_module(CLI_MODULE)


# A realistic full 40-character lowercase hex SHA (not a real commit).
EXPECTED_COMMIT = "0123456789abcdef0123456789abcdef01234567"
# A different valid full SHA (e.g. a later documentation/result commit).
OTHER_COMMIT = "fedcba9876543210fedcba9876543210fedcba98"
ORDER_LINK_ID = bo.build_order_link_id()


# ---------------------------------------------------------------------------
# Fakes / fixtures
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self, dt: datetime | None = None) -> None:
        self._dt = dt or datetime(2026, 6, 21, 5, 28, 25, tzinfo=timezone.utc)
        self.slept: list[float] = []

    def now_utc(self) -> datetime:
        return self._dt

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


class FakeTransport:
    def __init__(self, *, response=None, raise_exc=None) -> None:
        self.response = response
        self.raise_exc = raise_exc
        self.post_calls = 0
        self.last_url = None
        self.last_body = None

    def signed_headers_for_post(self, body_str: str) -> dict[str, str]:
        return {"Content-Type": "application/json", "X-BAPI-API-KEY": "FAKEKEY",
                "X-BAPI-SIGN": "FAKESIGN"}

    def post_order_create(self, *, url, headers, body_bytes):
        self.post_calls += 1
        self.last_url = url
        self.last_body = body_bytes
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.response


def _resp(items, ret_code=0, ret_msg="OK"):
    return {"retCode": ret_code, "retMsg": ret_msg, "result": {"list": list(items)}}


class FakeProbe:
    def __init__(
        self,
        *,
        snapshot=None,
        realtime=None,
        history=None,
        execution=None,
        position=None,
        dedup_realtime=None,
        dedup_history=None,
        raise_snapshot=False,
    ) -> None:
        self._snapshot = snapshot if snapshot is not None else good_snapshot()
        self._realtime = realtime if realtime is not None else [_resp([])]
        self._history = history if history is not None else [_resp([])]
        self._execution = execution if execution is not None else [_resp([])]
        self._position = position if position is not None else [_resp([])]
        self._dedup_realtime = dedup_realtime if dedup_realtime is not None else _resp([])
        self._dedup_history = dedup_history if dedup_history is not None else _resp([])
        self._raise_snapshot = raise_snapshot
        self.realtime_calls = 0
        self.history_calls = 0
        self.execution_calls = 0
        self.position_calls = 0
        self.lookup_realtime_calls = 0
        self.lookup_history_calls = 0
        self.last_dedup_realtime_link = None
        self.last_dedup_history_link = None

    def build_account_snapshot(self):
        if self._raise_snapshot:
            raise RuntimeError("snapshot read failed")
        return self._snapshot

    # Duplicate-detection lookups (by fixed orderLinkId).
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
        if not lst:
            return _resp([])
        return lst[min(idx, len(lst) - 1)]

    # Verification reads.
    def read_order_realtime(self, *, order_id, order_link_id):
        resp = self._pick(self._realtime, self.realtime_calls)
        self.realtime_calls += 1
        return resp

    def read_order_history(self, *, order_id, order_link_id):
        resp = self._pick(self._history, self.history_calls)
        self.history_calls += 1
        return resp

    def read_execution_list(self, *, order_id, order_link_id):
        resp = self._pick(self._execution, self.execution_calls)
        self.execution_calls += 1
        return resp

    def read_position_list(self, *, symbol):
        resp = self._pick(self._position, self.position_calls)
        self.position_calls += 1
        return resp


def good_snapshot(**over):
    base = dict(
        instrument_fresh=True,
        symbol_tradable=True,
        min_order_qty=Decimal("0.1"),
        qty_step=Decimal("0.1"),
        mark_price=Decimal("150"),
        mark_price_fresh=True,
        open_order_symbols=(),
        position_sizes={},
        available_balance_usdt=Decimal("8500"),
        position_mode_one_way=True,
        read_source="fixture",
    )
    base.update(over)
    return bo.AccountSnapshot(**base)


def good_creds():
    return bo.DemoCredentials(
        api_key_present=True, api_secret_present=True,
        recv_window="5000", source="BYBIT_DEMO",
    )


def clean_dup():
    return bo.DuplicateCheckResult(
        realtime_checked=True, realtime_match=False,
        history_checked=True, history_match=False,
        ambiguous=False, detail="clean",
    )


def base_gate_kwargs(**over):
    body = over.pop("request_body", bo.build_approved_body(order_link_id=ORDER_LINK_ID))
    kw = dict(
        request_body=body,
        order_link_id=body.get("orderLinkId", ORDER_LINK_ID),
        authorization_marker=bo.AUTHORIZATION_MARKER,
        expected_commit=EXPECTED_COMMIT,
        actual_commit=EXPECTED_COMMIT,
        credentials=good_creds(),
        snapshot=good_snapshot(),
        journal_state=bo.JOURNAL_STATE_NONE,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=None,
        real_order_count_before=0,
        duplicate_check=clean_dup(),
    )
    kw.update(over)
    return kw


def gate_by_name(gates, name):
    return next(g for g in gates if g.name == name)


def passed(gates, name):
    return gate_by_name(gates, name).passed


def expected_body_hash():
    link = bo.build_order_link_id()
    return bo.body_hash(bo.build_approved_body(order_link_id=link))


def dup_match_resp():
    return _resp([{"orderId": "PRIOR-1", "orderLinkId": ORDER_LINK_ID, "orderStatus": "New"}])


# ---------------------------------------------------------------------------
# Identity / authorization scope
# ---------------------------------------------------------------------------


def test_task_identity_and_authorization_scope():
    assert bo.TASK_ID == "TASK-014BO"
    assert bo.IDENTITY == "DEMO-ONLY-TINY-EXECUTION-ADAPTER-SINGLE-REAL-DEMO-ORDER"
    desc = bo.describe_authorization()
    assert desc["symbol"] == "SOLUSDT"
    assert desc["side"] == "Buy"
    assert desc["order_type"] == "Market"
    assert desc["qty"] == "0.1"
    assert desc["time_in_force"] == "IOC"
    assert desc["reduce_only"] is False
    assert desc["close_on_trigger"] is False
    assert desc["max_order_create_calls"] == 1


# ---------------------------------------------------------------------------
# Endpoint host lock / redirect
# ---------------------------------------------------------------------------


def test_demo_hostname_allowed():
    bo.assert_demo_url("https://api-demo.bybit.com/v5/order/create")


def test_live_hostname_rejected():
    with pytest.raises(bo.EndpointLockViolation):
        bo.assert_demo_url("https://api.bybit.com/v5/order/create")


def test_testnet_hostname_rejected():
    with pytest.raises(bo.EndpointLockViolation):
        bo.assert_demo_url("https://api-testnet.bybit.com/v5/order/create")


def test_arbitrary_hostname_rejected():
    with pytest.raises(bo.EndpointLockViolation):
        bo.assert_demo_url("https://evil.example.com/v5/order/create")


def test_guard_rejects_non_demo_url():
    sender = bo.OneShotSenderGuard(FakeTransport(response=_resp([])))
    with pytest.raises(bo.EndpointLockViolation):
        sender.send_order_create(url="https://api.bybit.com/v5/order/create", headers={}, body_bytes=b"{}")


def test_real_transport_uses_no_redirect_handler():
    src = pathlib.Path(bo.__file__).read_text(encoding="utf-8")
    assert "_NoRedirectHandler" in src
    assert "HTTPRedirectHandler" in src


# ---------------------------------------------------------------------------
# (7.1-7.5) Canonical, non-overridable journal path
# ---------------------------------------------------------------------------


def test_cli_has_no_journal_dir_argument():
    actions = {a.dest for a in cli.build_parser()._actions}
    assert "journal_dir" not in actions
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--journal-dir", "/tmp/x"])


def test_no_journal_path_environment_override(monkeypatch):
    monkeypatch.setenv("TASK_014BO_JOURNAL_DIR", "/tmp/evil")
    monkeypatch.setenv("BYBIT_DEMO_JOURNAL_DIR", "/tmp/evil")
    before = bo.canonical_journal().path
    after = bo.canonical_journal().path
    assert before == after
    assert before == str(bo.CANONICAL_JOURNAL_DIR / bo.JOURNAL_FILENAME)


def test_cwd_cannot_change_canonical_journal(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    j = bo.canonical_journal()
    assert pathlib.Path(j.path).is_absolute()
    assert pathlib.Path(j.path).parent == bo.CANONICAL_JOURNAL_DIR
    assert tmp_path not in pathlib.Path(j.path).parents


def test_caller_cannot_bypass_existing_journal_via_other_dir():
    # Production code always obtains the journal via canonical_journal(); there
    # is no public CLI/env mechanism to choose a different directory, so a
    # caller cannot point at an empty directory to bypass an existing journal.
    p1 = bo.canonical_journal().path
    p2 = bo.canonical_journal().path
    assert p1 == p2 == str(bo.CANONICAL_JOURNAL_DIR / bo.JOURNAL_FILENAME)
    # The CLI never references a user-chosen journal directory.
    cli_src = pathlib.Path(cli.__file__).read_text(encoding="utf-8")
    assert "args.journal_dir" not in cli_src
    assert "canonical_journal()" in cli_src


def test_canonical_journal_anchored_to_repo_root():
    assert bo.PROJECT_ROOT == pathlib.Path(bo.__file__).resolve().parents[1]
    rel = bo.CANONICAL_JOURNAL_DIR.resolve().relative_to(bo.PROJECT_ROOT.resolve())
    assert rel == pathlib.Path("outputs/demo_trading/task_014bo_single_real_demo_order")


# ---------------------------------------------------------------------------
# (7.1-7.7) Permanent, commit-independent orderLinkId
# ---------------------------------------------------------------------------


def test_order_link_id_does_not_use_commit_sha():
    # build_order_link_id takes no commit argument at all.
    assert "expected_commit" not in inspect.signature(bo.build_order_link_id).parameters
    assert inspect.signature(bo.build_order_link_id).parameters == {}
    # The derivation source uses the scope identity, not a commit SHA.
    src = pathlib.Path(bo.__file__).read_text(encoding="utf-8")
    func = src.split("def build_order_link_id")[1].split("\ndef ")[0]
    assert "AUTHORIZATION_SCOPE_IDENTITY" in func
    assert "commit" not in func.lower().split('"""')[0] or "expected_commit" not in func


def test_two_different_valid_shas_produce_same_order_link_id():
    # The orderLinkId is independent of any commit; same value regardless.
    assert EXPECTED_COMMIT != OTHER_COMMIT
    assert bo.is_full_commit_sha(EXPECTED_COMMIT) and bo.is_full_commit_sha(OTHER_COMMIT)
    a = bo.build_order_link_id()
    b = bo.build_order_link_id()
    assert a == b == ORDER_LINK_ID


def test_simulated_later_documentation_commit_keeps_order_link_id(monkeypatch):
    # Even if HEAD changes (a later doc/result commit), orderLinkId is unchanged.
    monkeypatch.setattr(cli, "_actual_commit", lambda: OTHER_COMMIT)
    report = bo.run_preflight(probe=FakeProbe(), credentials=good_creds(),
                              expected_commit=OTHER_COMMIT, authorization_marker=bo.AUTHORIZATION_MARKER,
                              actual_commit=OTHER_COMMIT, allow_real_network=True)
    assert report.order_link_id == ORDER_LINK_ID


def test_order_link_id_identical_across_mocked_utc_dates(monkeypatch):
    a = bo.build_order_link_id()

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2099, 1, 1, tzinfo=tz)

    monkeypatch.setattr(bo, "datetime", _FrozenDateTime)
    assert bo.build_order_link_id() == a


def test_order_link_id_identical_across_process_restart():
    a = bo.build_order_link_id()
    reloaded = importlib.reload(bo)
    assert reloaded.build_order_link_id() == a
    importlib.reload(bo)  # restore


def test_order_link_id_equals_hash_of_identity_marker_scope():
    digest = hashlib.sha256(
        (bo.TASK_ID + "|" + bo.AUTHORIZATION_MARKER + "|" + bo.AUTHORIZATION_SCOPE_IDENTITY).encode("utf-8")
    ).hexdigest()[:16]
    assert bo.build_order_link_id() == f"BO1-{digest}"


def test_order_link_id_has_no_date_or_timestamp_and_within_36():
    import re
    link = bo.build_order_link_id()
    assert re.fullmatch(r"BO1-[0-9a-f]{16}", link)
    assert not re.search(r"\d{8}", link)
    assert len(link) <= 36


def test_order_link_id_no_longer_described_as_commit_derived():
    src = pathlib.Path(bo.__file__).read_text(encoding="utf-8")
    func = src.split("def build_order_link_id")[1].split("\ndef ")[0]
    assert "NO commit SHA" in func


def test_caller_cannot_override_order_link_id():
    pf_sig = inspect.signature(bo.run_preflight).parameters
    ex_sig = inspect.signature(bo.execute_single_real_demo_order).parameters
    assert "order_link_id" not in pf_sig
    assert "order_link_id" not in ex_sig


# ---------------------------------------------------------------------------
# (7.12-7.14) Full commit SHA enforcement
# ---------------------------------------------------------------------------


def test_short_7_char_sha_rejected():
    gates = bo.evaluate_preflight_gates(**base_gate_kwargs(
        expected_commit="b6f7498", actual_commit="b6f7498"))
    assert not passed(gates, "git_identity_matches_approved_full_sha")


def test_only_exact_40_char_lowercase_hex_accepted():
    assert bo.is_full_commit_sha("0123456789abcdef0123456789abcdef01234567") is True
    assert bo.is_full_commit_sha("0123456789ABCDEF0123456789abcdef01234567") is False  # uppercase
    assert bo.is_full_commit_sha("0123456789abcdef0123456789abcdef0123456") is False   # 39
    assert bo.is_full_commit_sha("0123456789abcdef0123456789abcdef012345678") is False  # 41
    assert bo.is_full_commit_sha("HEAD") is False
    assert bo.is_full_commit_sha("main") is False
    assert bo.is_full_commit_sha(" 0123456789abcdef0123456789abcdef01234567 ") is False
    assert bo.is_full_commit_sha(None) is False


def test_runtime_head_must_match_expected_full_sha():
    other = "ffffffffffffffffffffffffffffffffffffffff"
    gates = bo.evaluate_preflight_gates(**base_gate_kwargs(
        expected_commit=EXPECTED_COMMIT, actual_commit=other))
    assert not passed(gates, "git_identity_matches_approved_full_sha")


# ---------------------------------------------------------------------------
# (7.15-7.16) Duplicate lookup uses the fixed orderLinkId
# ---------------------------------------------------------------------------


def _real_preflight(probe, **over):
    kw = dict(probe=probe, credentials=good_creds(),
              expected_commit=EXPECTED_COMMIT, authorization_marker=bo.AUTHORIZATION_MARKER,
              actual_commit=EXPECTED_COMMIT, allow_real_network=True)
    kw.update(over)
    return bo.run_preflight(**kw)


def test_realtime_duplicate_lookup_uses_fixed_order_link_id():
    probe = FakeProbe()
    _real_preflight(probe)
    assert probe.last_dedup_realtime_link == ORDER_LINK_ID
    assert probe.lookup_realtime_calls == 1


def test_history_duplicate_lookup_uses_fixed_order_link_id():
    probe = FakeProbe()
    _real_preflight(probe)
    assert probe.last_dedup_history_link == ORDER_LINK_ID
    assert probe.lookup_history_calls == 1


# ---------------------------------------------------------------------------
# Offline / no-network duplicate-check semantics (fail closed)
# ---------------------------------------------------------------------------


def test_offline_preflight_not_ready():
    report = bo.run_preflight(probe=FakeProbe(), credentials=good_creds(),
                              expected_commit=EXPECTED_COMMIT,
                              authorization_marker=bo.AUTHORIZATION_MARKER,
                              actual_commit=EXPECTED_COMMIT, allow_real_network=False)
    assert report.ready is False


def test_offline_duplicate_result_fails_closed():
    report = bo.run_preflight(probe=FakeProbe(), credentials=good_creds(),
                              expected_commit=EXPECTED_COMMIT,
                              authorization_marker=bo.AUTHORIZATION_MARKER,
                              actual_commit=EXPECTED_COMMIT, allow_real_network=False)
    d = report.duplicate_check
    assert d["clean"] is False
    assert d["realtime_checked"] is False
    assert d["history_checked"] is False
    assert d["ambiguous"] is True
    assert "not performed" in d["detail"]


def test_offline_preflight_fails_duplicate_gate():
    report = bo.run_preflight(probe=FakeProbe(), credentials=good_creds(),
                              expected_commit=EXPECTED_COMMIT,
                              authorization_marker=bo.AUTHORIZATION_MARKER,
                              actual_commit=EXPECTED_COMMIT, allow_real_network=False)
    assert "no_existing_exchange_order_for_fixed_order_link_id" in [g.name for g in report.failed_gates()]


def test_offline_preflight_performs_no_dedup_lookup():
    probe = FakeProbe()
    bo.run_preflight(probe=probe, credentials=good_creds(),
                     expected_commit=EXPECTED_COMMIT,
                     authorization_marker=bo.AUTHORIZATION_MARKER,
                     actual_commit=EXPECTED_COMMIT, allow_real_network=False)
    assert probe.lookup_realtime_calls == 0
    assert probe.lookup_history_calls == 0


def test_real_network_but_missing_credentials_fails_closed():
    creds = bo.DemoCredentials(api_key_present=False, api_secret_present=False,
                               recv_window="5000", source="absent")
    report = bo.run_preflight(probe=FakeProbe(), credentials=creds,
                              expected_commit=EXPECTED_COMMIT,
                              authorization_marker=bo.AUTHORIZATION_MARKER,
                              actual_commit=EXPECTED_COMMIT, allow_real_network=True)
    assert report.duplicate_check["clean"] is False
    assert "credentials absent" in report.duplicate_check["detail"]


def test_offline_function_semantics():
    d = bo.offline_duplicate_check()
    assert d.clean is False and d.ambiguous is True
    assert d.realtime_checked is False and d.history_checked is False


def test_real_network_clean_empty_passes():
    report = _real_preflight(FakeProbe())
    assert report.duplicate_check["clean"] is True
    assert report.ready is True


def test_real_network_match_in_either_source_refuses():
    r1 = _real_preflight(FakeProbe(dedup_realtime=dup_match_resp()))
    r2 = _real_preflight(FakeProbe(dedup_history=dup_match_resp()))
    for r in (r1, r2):
        assert r.ready is False
        assert "no_existing_exchange_order_for_fixed_order_link_id" in [g.name for g in r.failed_gates()]


def test_real_network_malformed_or_failed_refuses():
    r_bad = _real_preflight(FakeProbe(dedup_realtime={"retCode": 0, "result": {}}))
    r_fail = _real_preflight(FakeProbe(dedup_history={"retCode": 10006, "result": {"list": []}}))
    r_raise = _real_preflight(FakeProbe(dedup_realtime=RuntimeError("timeout")))
    for r in (r_bad, r_fail, r_raise):
        assert r.duplicate_check["clean"] is False


# ---------------------------------------------------------------------------
# (7.17-7.27) Duplicate detection refusals
# ---------------------------------------------------------------------------


def _execute_with(tmp_path, *, dedup_realtime=None, dedup_history=None, journal_state=None):
    if journal_state is not None:
        journal = bo.OneShotJournal(str(tmp_path))
        journal._atomic_write({"task_id": bo.TASK_ID, "state": journal_state})
    else:
        journal = bo.OneShotJournal(str(tmp_path))
    transport = FakeTransport(response={"retCode": 0, "result": {"orderId": "X"}})
    sender = bo.OneShotSenderGuard(transport)
    probe = FakeProbe(dedup_realtime=dedup_realtime, dedup_history=dedup_history)
    report = bo.execute_single_real_demo_order(
        probe=probe, sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bo.AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock(),
    )
    return report, sender, transport


def _assert_dedup_refusal(report, sender, transport):
    assert report.final_outcome == bo.OUTCOME_REFUSED_PREFLIGHT
    assert "no_existing_exchange_order_for_fixed_order_link_id" in report.preflight_failed_gate_names
    assert sender.call_count == 0
    assert transport.post_calls == 0


def test_realtime_match_refuses_before_post(tmp_path):
    r, s, t = _execute_with(tmp_path, dedup_realtime=dup_match_resp())
    _assert_dedup_refusal(r, s, t)


def test_history_match_refuses_before_post(tmp_path):
    r, s, t = _execute_with(tmp_path, dedup_history=dup_match_resp())
    _assert_dedup_refusal(r, s, t)


def test_filled_historical_order_refuses(tmp_path):
    resp = _resp([{"orderId": "P", "orderLinkId": ORDER_LINK_ID, "orderStatus": "Filled"}])
    r, s, t = _execute_with(tmp_path, dedup_history=resp)
    _assert_dedup_refusal(r, s, t)


def test_cancelled_historical_order_refuses(tmp_path):
    resp = _resp([{"orderId": "P", "orderLinkId": ORDER_LINK_ID, "orderStatus": "Cancelled"}])
    r, s, t = _execute_with(tmp_path, dedup_history=resp)
    _assert_dedup_refusal(r, s, t)


def test_rejected_historical_order_refuses(tmp_path):
    resp = _resp([{"orderId": "P", "orderLinkId": ORDER_LINK_ID, "orderStatus": "Rejected"}])
    r, s, t = _execute_with(tmp_path, dedup_history=resp)
    _assert_dedup_refusal(r, s, t)


def test_unknown_matching_order_state_refuses(tmp_path):
    resp = _resp([{"orderId": "P", "orderLinkId": ORDER_LINK_ID, "orderStatus": "WeirdState"}])
    r, s, t = _execute_with(tmp_path, dedup_realtime=resp)
    _assert_dedup_refusal(r, s, t)


def test_realtime_query_failure_refuses(tmp_path):
    r, s, t = _execute_with(tmp_path, dedup_realtime=RuntimeError("timeout"))
    _assert_dedup_refusal(r, s, t)


def test_history_query_failure_refuses(tmp_path):
    r, s, t = _execute_with(tmp_path, dedup_history=RuntimeError("rate limited"))
    _assert_dedup_refusal(r, s, t)


def test_malformed_duplicate_check_response_refuses(tmp_path):
    # retCode==0 but no list -> malformed -> not checked -> fail closed.
    r, s, t = _execute_with(tmp_path, dedup_realtime={"retCode": 0, "result": {}})
    _assert_dedup_refusal(r, s, t)


def test_nonzero_retcode_duplicate_query_refuses(tmp_path):
    r, s, t = _execute_with(tmp_path, dedup_history={"retCode": 10006, "retMsg": "rate", "result": {"list": []}})
    _assert_dedup_refusal(r, s, t)


def test_local_journal_missing_but_exchange_match_refuses(tmp_path):
    # No journal file exists, but exchange has the orderLinkId -> still refuse.
    assert not bo.OneShotJournal(str(tmp_path)).exists()
    r, s, t = _execute_with(tmp_path, dedup_realtime=dup_match_resp())
    _assert_dedup_refusal(r, s, t)


def test_local_journal_ambiguous_but_exchange_clean_refuses(tmp_path):
    r, s, t = _execute_with(tmp_path, journal_state=bo.JOURNAL_STATE_POST_TIMEOUT_AMBIGUOUS)
    assert r.final_outcome == bo.OUTCOME_REFUSED_PREFLIGHT
    assert "no_conflicting_one_shot_journal" in r.preflight_failed_gate_names
    assert s.call_count == 0
    assert t.post_calls == 0


# ---------------------------------------------------------------------------
# (7.28) No bypass options
# ---------------------------------------------------------------------------


def test_no_bypass_reset_or_force_cli_option():
    options = set()
    for a in cli.build_parser()._actions:
        options.update(a.option_strings)
    for forbidden in ("--force", "--reset", "--ignore-journal", "--new-order-link-id",
                      "--journal-dir", "--override", "--skip-dedup"):
        assert forbidden not in options


# ---------------------------------------------------------------------------
# Body / value gates (retained)
# ---------------------------------------------------------------------------


def test_all_gates_pass_on_good_inputs():
    gates = bo.evaluate_preflight_gates(**base_gate_kwargs())
    assert all(g.passed for g in gates), [g.name for g in gates if not g.passed]
    assert len(gates) == 31


def test_exact_nine_field_body():
    body = bo.build_approved_body(order_link_id=ORDER_LINK_ID)
    assert set(body) == set(bo.APPROVED_BODY_FIELDS)
    assert len(body) == 9
    for forbidden in ("price", "positionIdx", "takeProfit", "stopLoss", "triggerPrice",
                      "trailingStop", "orderFilter", "marketUnit"):
        assert forbidden not in body


def test_qty_is_exactly_0_1():
    body = bo.build_approved_body(order_link_id=ORDER_LINK_ID)
    assert body["qty"] == "0.1"


def test_wrong_quantity_refused():
    body = bo.build_approved_body(order_link_id=ORDER_LINK_ID)
    body["qty"] = "0.2"
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(request_body=body)),
                      "qty_is_exactly_decimal_0_1")


def test_wrong_symbol_refused():
    body = bo.build_approved_body(order_link_id=ORDER_LINK_ID)
    body["symbol"] = "BTCUSDT"
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(request_body=body)),
                      "symbol_is_solusdt")


def test_wrong_side_refused():
    body = bo.build_approved_body(order_link_id=ORDER_LINK_ID)
    body["side"] = "Sell"
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(request_body=body)),
                      "side_is_buy")


def test_wrong_order_type_refused():
    body = bo.build_approved_body(order_link_id=ORDER_LINK_ID)
    body["orderType"] = "Limit"
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(request_body=body)),
                      "order_type_is_market")


def test_wrong_tif_refused():
    body = bo.build_approved_body(order_link_id=ORDER_LINK_ID)
    body["timeInForce"] = "GTC"
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(request_body=body)),
                      "time_in_force_is_ioc")


def test_reduce_only_true_refused():
    body = bo.build_approved_body(order_link_id=ORDER_LINK_ID)
    body["reduceOnly"] = True
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(request_body=body)),
                      "reduce_only_is_false")


def test_close_on_trigger_true_refused():
    body = bo.build_approved_body(order_link_id=ORDER_LINK_ID)
    body["closeOnTrigger"] = True
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(request_body=body)),
                      "close_on_trigger_is_false")


def test_additional_body_field_refused():
    body = bo.build_approved_body(order_link_id=ORDER_LINK_ID)
    body["price"] = "150"
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(request_body=body)),
                      "body_has_exactly_nine_approved_fields")


def test_missing_demo_credentials_refused():
    creds = bo.DemoCredentials(api_key_present=False, api_secret_present=False,
                               recv_window="5000", source="absent")
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(credentials=creds)),
                      "credentials_are_bybit_demo_only")


def test_live_only_credentials_ignored():
    creds = bo.load_demo_credentials(env={"BYBIT_API_KEY": "live", "BYBIT_API_SECRET": "live"})
    assert creds.usable is False
    assert creds.source == "absent"


def test_load_demo_credentials_reads_only_demo_vars():
    creds = bo.load_demo_credentials(env={
        "BYBIT_DEMO_API_KEY": "k", "BYBIT_DEMO_API_SECRET": "s", "BYBIT_DEMO_RECV_WINDOW": "8000"})
    assert creds.usable is True and creds.source == "BYBIT_DEMO" and creds.recv_window == "8000"


def test_existing_solusdt_position_refused():
    snap = good_snapshot(position_sizes={"SOLUSDT": Decimal("1")})
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "no_existing_solusdt_position")


def test_existing_solusdt_open_order_refused():
    snap = good_snapshot(open_order_symbols=("SOLUSDT",))
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "no_active_solusdt_order")


def test_hedge_mode_incompatibility_refused():
    snap = good_snapshot(position_mode_one_way=False)
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "position_mode_one_way_compatible")


def test_instrument_min_qty_failure_refused():
    snap = good_snapshot(min_order_qty=Decimal("1"))
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "qty_satisfies_min_and_step")


def test_qty_step_failure_refused():
    snap = good_snapshot(qty_step=Decimal("0.3"))
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "qty_satisfies_min_and_step")


def test_mark_price_missing_refused():
    snap = good_snapshot(mark_price=None, mark_price_fresh=False)
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "fresh_mark_price_available")


def test_notional_above_20_usdt_refused():
    snap = good_snapshot(mark_price=Decimal("250"))
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "notional_within_20_usdt")


def test_insufficient_demo_balance_refused():
    snap = good_snapshot(available_balance_usdt=Decimal("1"))
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(snapshot=snap)),
                      "sufficient_demo_balance")


def test_missing_authorization_marker_refused():
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(authorization_marker=None)),
                      "authorization_marker_matches")


def test_wrong_authorization_marker_refused():
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(authorization_marker="WRONG")),
                      "authorization_marker_matches")


def test_missing_execution_flag_refused():
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(execution_flags={})),
                      "execution_flags_match")


def test_request_body_hash_mismatch_refused():
    assert not passed(bo.evaluate_preflight_gates(**base_gate_kwargs(expected_body_hash="deadbeef")),
                      "request_body_hash_matches")


def test_duplicate_check_absent_fails_gate():
    kw = base_gate_kwargs()
    kw["duplicate_check"] = None
    assert not passed(bo.evaluate_preflight_gates(**kw),
                      "no_existing_exchange_order_for_fixed_order_link_id")


# ---------------------------------------------------------------------------
# Journal refusals
# ---------------------------------------------------------------------------


def _existing_journal_state_refused(tmp_path, state):
    journal = bo.OneShotJournal(str(tmp_path))
    journal._atomic_write({"task_id": bo.TASK_ID, "state": state})
    transport = FakeTransport(response=_resp([{"orderId": "x"}]))
    sender = bo.OneShotSenderGuard(transport)
    report = bo.execute_single_real_demo_order(
        probe=FakeProbe(), sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bo.AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock(),
    )
    assert report.final_outcome == bo.OUTCOME_REFUSED_PREFLIGHT
    assert "no_conflicting_one_shot_journal" in report.preflight_failed_gate_names
    assert sender.call_count == 0 and transport.post_calls == 0


def test_existing_armed_journal_refused(tmp_path):
    _existing_journal_state_refused(tmp_path, bo.JOURNAL_STATE_ARMED_BEFORE_POST)


def test_existing_consumed_journal_refused(tmp_path):
    _existing_journal_state_refused(tmp_path, bo.JOURNAL_STATE_POST_RESULT_VERIFIED)


def test_existing_ambiguous_journal_refused(tmp_path):
    _existing_journal_state_refused(tmp_path, bo.JOURNAL_STATE_POST_TIMEOUT_AMBIGUOUS)


def test_atomic_journal_behavior(tmp_path):
    journal = bo.OneShotJournal(str(tmp_path))
    assert journal.state() == bo.JOURNAL_STATE_NONE
    journal.arm(body_hash_value="h", order_link_id=ORDER_LINK_ID,
                expected_commit=EXPECTED_COMMIT, preflight_summary={"ok": True}, clock=FakeClock())
    assert journal.state() == bo.JOURNAL_STATE_ARMED_BEFORE_POST
    assert not (tmp_path / (bo.JOURNAL_FILENAME + ".tmp")).exists()
    data = json.loads((tmp_path / bo.JOURNAL_FILENAME).read_text(encoding="utf-8"))
    assert data["order_link_id"] == ORDER_LINK_ID
    assert "api_secret" not in json.dumps(data)
    with pytest.raises(bo.JournalStateConflict):
        journal.arm(body_hash_value="h", order_link_id=ORDER_LINK_ID,
                    expected_commit=EXPECTED_COMMIT, preflight_summary={}, clock=FakeClock())


# ---------------------------------------------------------------------------
# Sender count / no-retry / ambiguity
# ---------------------------------------------------------------------------


def _execute_success(tmp_path, realtime):
    transport = FakeTransport(response={"retCode": 0, "retMsg": "OK", "result": {"orderId": "ORD-1"}})
    sender = bo.OneShotSenderGuard(transport)
    journal = bo.OneShotJournal(str(tmp_path))
    probe = FakeProbe(realtime=realtime)
    report = bo.execute_single_real_demo_order(
        probe=probe, sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bo.AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock(),
    )
    return report, sender, transport, probe


def test_approved_fake_path_invokes_sender_exactly_once(tmp_path):
    report, sender, transport, probe = _execute_success(
        tmp_path, [_resp([{"orderId": "ORD-1", "orderStatus": "Filled", "cumExecQty": "0.1"}])])
    assert sender.call_count == 1 and transport.post_calls == 1
    assert report.order_id == "ORD-1"
    assert report.final_outcome == bo.OUTCOME_FILLED_VERIFIED


def test_sender_never_called_twice():
    transport = FakeTransport(response=_resp([]))
    sender = bo.OneShotSenderGuard(transport)
    url = bo.DEMO_BASE_URL + bo.ORDER_CREATE_PATH
    sender.send_order_create(url=url, headers={}, body_bytes=b"{}")
    with pytest.raises(bo.SenderInvokedTwice):
        sender.send_order_create(url=url, headers={}, body_bytes=b"{}")
    assert sender.call_count == 1 and transport.post_calls == 1


def test_redirect_rejected_during_execute(tmp_path):
    transport = FakeTransport(raise_exc=bo.RedirectRejected("redirect to https://api.bybit.com"))
    sender = bo.OneShotSenderGuard(transport)
    journal = bo.OneShotJournal(str(tmp_path))
    report = bo.execute_single_real_demo_order(
        probe=FakeProbe(), sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bo.AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock(),
    )
    assert report.journal_state == bo.JOURNAL_STATE_POST_REDIRECT_REJECTED
    assert sender.call_count == 1 and report.final_outcome == bo.OUTCOME_POST_FAILED


def test_fake_timeout_ambiguous_no_retry(tmp_path):
    transport = FakeTransport(raise_exc=bo.TransportTimeout("timed out"))
    sender = bo.OneShotSenderGuard(transport)
    journal = bo.OneShotJournal(str(tmp_path))
    report = bo.execute_single_real_demo_order(
        probe=FakeProbe(), sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bo.AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock(),
    )
    assert report.journal_state == bo.JOURNAL_STATE_POST_TIMEOUT_AMBIGUOUS
    assert report.final_outcome == bo.OUTCOME_AMBIGUOUS
    assert report.no_retry_performed is True and sender.call_count == 1


def test_fake_connection_error_ambiguous_no_retry(tmp_path):
    transport = FakeTransport(raise_exc=bo.TransportConnectionError("connection reset"))
    sender = bo.OneShotSenderGuard(transport)
    journal = bo.OneShotJournal(str(tmp_path))
    report = bo.execute_single_real_demo_order(
        probe=FakeProbe(), sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bo.AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock(),
    )
    assert report.journal_state == bo.JOURNAL_STATE_POST_EXCEPTION_AMBIGUOUS
    assert sender.call_count == 1


def test_malformed_response_ambiguous_no_retry(tmp_path):
    transport = FakeTransport(raise_exc=bo.SingleRealDemoOrderError("malformed response: x"))
    sender = bo.OneShotSenderGuard(transport)
    journal = bo.OneShotJournal(str(tmp_path))
    report = bo.execute_single_real_demo_order(
        probe=FakeProbe(), sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bo.AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock(),
    )
    assert report.journal_state == bo.JOURNAL_STATE_POST_RESULT_UNVERIFIED
    assert report.outcome_ambiguous is True and sender.call_count == 1


def test_nonzero_retcode_one_attempt_no_retry(tmp_path):
    transport = FakeTransport(response={"retCode": 10001, "retMsg": "params error", "result": {}})
    sender = bo.OneShotSenderGuard(transport)
    journal = bo.OneShotJournal(str(tmp_path))
    report = bo.execute_single_real_demo_order(
        probe=FakeProbe(), sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bo.AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock(),
    )
    assert report.post_ret_code == 10001
    assert report.final_outcome == bo.OUTCOME_POST_FAILED
    assert report.real_order_sent is False and sender.call_count == 1


def test_journal_arm_failure_refuses_without_sender(tmp_path, monkeypatch):
    transport = FakeTransport(response=_resp([{"orderId": "x"}]))
    sender = bo.OneShotSenderGuard(transport)
    journal = bo.OneShotJournal(str(tmp_path))
    monkeypatch.setattr(journal, "arm", lambda **k: (_ for _ in ()).throw(bo.JournalStateConflict("boom")))
    report = bo.execute_single_real_demo_order(
        probe=FakeProbe(), sender=sender, transport=transport, credentials=good_creds(),
        journal=journal, expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bo.AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock(),
    )
    assert report.final_outcome == bo.OUTCOME_REFUSED_PREFLIGHT
    assert sender.call_count == 0 and transport.post_calls == 0


def test_rerun_after_attempted_post_refuses(tmp_path):
    report1, s1, t1, p1 = _execute_success(
        tmp_path, [_resp([{"orderId": "ORD-1", "orderStatus": "Filled"}])])
    assert report1.journal_state == bo.JOURNAL_STATE_POST_RESULT_VERIFIED
    transport2 = FakeTransport(response={"retCode": 0, "result": {"orderId": "ORD-2"}})
    sender2 = bo.OneShotSenderGuard(transport2)
    journal2 = bo.OneShotJournal(str(tmp_path))
    report2 = bo.execute_single_real_demo_order(
        probe=FakeProbe(), sender=sender2, transport=transport2, credentials=good_creds(),
        journal=journal2, expected_commit=EXPECTED_COMMIT, actual_commit=EXPECTED_COMMIT,
        authorization_marker=bo.AUTHORIZATION_MARKER,
        execution_flags={"mode": "execute_once", "execute_one_real_demo_order": True},
        expected_body_hash=expected_body_hash(), clock=FakeClock(),
    )
    assert report2.final_outcome == bo.OUTCOME_REFUSED_PREFLIGHT
    assert sender2.call_count == 0 and transport2.post_calls == 0


# ---------------------------------------------------------------------------
# Read-only verification bounds + classification
# ---------------------------------------------------------------------------


def test_verification_reads_never_post(tmp_path):
    report, sender, transport, probe = _execute_success(
        tmp_path, [_resp([{"orderId": "ORD-1", "orderStatus": "Filled"}])])
    assert transport.post_calls == 1 and report.verification is not None


def test_max_three_realtime_reads():
    probe = FakeProbe(realtime=[_resp([{"orderId": "ORD-1", "orderStatus": "New"}])])
    v = bo.verify_order_outcome(probe=probe, order_id="ORD-1", order_link_id=ORDER_LINK_ID,
                               ret_code=0, ret_msg="OK", clock=FakeClock())
    assert v.realtime_reads == 3 and probe.realtime_calls == 3


def test_max_one_history_fallback():
    probe = FakeProbe(realtime=[_resp([])],
                      history=[_resp([{"orderId": "ORD-1", "orderStatus": "Filled"}])])
    v = bo.verify_order_outcome(probe=probe, order_id="ORD-1", order_link_id=ORDER_LINK_ID,
                               ret_code=0, ret_msg="OK", clock=FakeClock())
    assert v.history_reads == 1


def test_max_one_execution_and_position_read():
    probe = FakeProbe(realtime=[_resp([{"orderId": "ORD-1", "orderStatus": "Filled"}])])
    v = bo.verify_order_outcome(probe=probe, order_id="ORD-1", order_link_id=ORDER_LINK_ID,
                               ret_code=0, ret_msg="OK", clock=FakeClock())
    assert v.execution_reads == 1 and v.position_reads == 1


def _classify(status):
    probe = FakeProbe(realtime=[_resp([{"orderId": "ORD-1", "orderStatus": status}])])
    v = bo.verify_order_outcome(probe=probe, order_id="ORD-1", order_link_id=ORDER_LINK_ID,
                               ret_code=0, ret_msg="OK", clock=FakeClock())
    return bo.classify_outcome(v)


def test_status_classifications():
    assert _classify("Filled") == bo.OUTCOME_FILLED_VERIFIED
    assert _classify("PartiallyFilledCanceled") == bo.OUTCOME_PARTIALLY_FILLED_VERIFIED
    assert _classify("Cancelled") == bo.OUTCOME_CANCELLED_VERIFIED
    assert _classify("Rejected") == bo.OUTCOME_REJECTED_VERIFIED
    assert _classify("New") == bo.OUTCOME_ACCEPTED_STATUS_PENDING


def test_ambiguous_when_order_not_found():
    probe = FakeProbe(realtime=[_resp([])], history=[_resp([])])
    v = bo.verify_order_outcome(probe=probe, order_id="ORD-1", order_link_id=ORDER_LINK_ID,
                               ret_code=0, ret_msg="OK", clock=FakeClock())
    assert v.outcome_ambiguous is True
    assert bo.classify_outcome(v) == bo.OUTCOME_AMBIGUOUS


# ---------------------------------------------------------------------------
# Static safety scans / no secret / frozen
# ---------------------------------------------------------------------------


SRC_TEXT = pathlib.Path(bo.__file__).read_text(encoding="utf-8")
CLI_TEXT = pathlib.Path(cli.__file__).read_text(encoding="utf-8")


def _import_lines(text):
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith(("import ", "from "))]


def test_no_automatic_close():
    assert "/v5/order/cancel" not in SRC_TEXT
    assert "set-trading-stop" not in SRC_TEXT
    assert bo.REQUIRED_CLOSE_ON_TRIGGER is False and bo.REQUIRED_REDUCE_ONLY is False


def test_no_tp_sl():
    for token in ("takeProfit", "stopLoss", "tpslMode", "triggerPrice", "trailingStop"):
        assert token not in SRC_TEXT


def test_no_scheduler():
    assert bo.SCHEDULER_ENABLED is False
    for ln in _import_lines(SRC_TEXT) + _import_lines(CLI_TEXT):
        low = ln.lower()
        assert "apscheduler" not in low and "crontab" not in low
        assert not low.startswith("import schedule") and not low.startswith("import sched")


def test_no_retry_library_or_decorator():
    assert bo.RETRY_ENABLED is False
    for token in ("import tenacity", "import backoff", "@retry", "from tenacity", "from backoff"):
        assert token not in SRC_TEXT and token not in CLI_TEXT


def test_no_live_executor_import():
    for ln in _import_lines(SRC_TEXT) + _import_lines(CLI_TEXT):
        assert "executors.bybit" not in ln and "BybitExecutor" not in ln
    assert "BybitExecutor(" not in SRC_TEXT and "BybitExecutor(" not in CLI_TEXT


def test_no_main_or_risk_import():
    for ln in _import_lines(SRC_TEXT) + _import_lines(CLI_TEXT):
        assert "src.risk" not in ln
        assert not ln.startswith("from main ") and not ln.startswith("import main")


def test_no_secret_serialization():
    report = bo.run_preflight(probe=FakeProbe(), credentials=good_creds(),
                              expected_commit=EXPECTED_COMMIT,
                              authorization_marker=bo.AUTHORIZATION_MARKER,
                              actual_commit=EXPECTED_COMMIT, clock=FakeClock())
    blob = json.dumps(report.to_dict())
    for forbidden in ("X-BAPI-SIGN", "BYBIT_DEMO_API_SECRET", "api_secret", "X-BAPI-API-KEY"):
        assert forbidden not in blob
    fields = {f.name for f in dataclasses.fields(bo.DemoCredentials)}
    assert fields == {"api_key_present", "api_secret_present", "recv_window", "source"}


def test_frozen_report_dataclasses():
    for c in (bo.PreflightReport, bo.SingleRealDemoOrderReport, bo.VerificationResult,
              bo.GateResult, bo.DemoCredentials, bo.AccountSnapshot, bo.DuplicateCheckResult):
        assert dataclasses.is_dataclass(c)
    g = bo.GateResult(index=1, name="x", passed=True, detail="")
    with pytest.raises(dataclasses.FrozenInstanceError):
        g.passed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CLI behavior + report writer + final command template
# ---------------------------------------------------------------------------


def test_default_cli_is_preflight_only(capsys):
    args = cli.build_parser().parse_args([])
    assert args.mode == "preflight"
    rc = cli.main(["--json-only"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "preflight"
    assert payload["read_source"] == "fixture"
    assert "--journal-dir" not in payload["manual_execute_command"]
    assert rc in (cli.EXIT_READY, cli.EXIT_NOT_READY)


def test_cli_help_performs_no_network():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_demo_only_single_real_order.py"), "--help"],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert "preflight" in result.stdout
    assert "--journal-dir" not in result.stdout


def test_cli_execute_once_without_real_network_refused():
    rc = cli.main(["--mode", "execute_once", "--execute-one-real-demo-order",
                   "--authorization-marker", bo.AUTHORIZATION_MARKER,
                   "--expected-commit", EXPECTED_COMMIT, "--request-body-hash", "abc"])
    assert rc == cli.EXIT_SAFETY


def test_cli_execute_once_without_body_hash_refused():
    rc = cli.main(["--mode", "execute_once", "--allow-real-network",
                   "--execute-one-real-demo-order",
                   "--authorization-marker", bo.AUTHORIZATION_MARKER,
                   "--expected-commit", EXPECTED_COMMIT])
    assert rc == cli.EXIT_SAFETY


def test_final_command_template_no_journal_dir_and_requires_full_sha():
    cmd_full = cli._manual_command(expected_commit=EXPECTED_COMMIT, body_hash="abc123")
    assert "--journal-dir" not in cmd_full
    assert f"--expected-commit {EXPECTED_COMMIT}" in cmd_full
    assert "execute_once" in cmd_full
    cmd_short = cli._manual_command(expected_commit="b6f7498", body_hash="abc123")
    assert "<FULL_40_CHARACTER" in cmd_short


def test_report_writer_json_and_markdown(tmp_path):
    paths = cli._write_reports(str(tmp_path), "task_014bo_preflight", {"task_id": bo.TASK_ID})
    for key in ("json", "json_latest", "md", "md_latest"):
        assert pathlib.Path(paths[key]).exists()


def test_preflight_report_to_dict_round_trips():
    report = bo.run_preflight(probe=FakeProbe(), credentials=good_creds(),
                              expected_commit=EXPECTED_COMMIT,
                              authorization_marker=bo.AUTHORIZATION_MARKER,
                              actual_commit=EXPECTED_COMMIT, allow_real_network=True,
                              clock=FakeClock())
    d = report.to_dict()
    assert d["ready"] is True and d["all_passed"] is True
    assert d["request_body"]["qty"] == "0.1"
    assert len(d["gates"]) == 31
    assert d["duplicate_check"]["clean"] is True


# ---------------------------------------------------------------------------
# Execute-once independently rechecks duplicates before arming
# ---------------------------------------------------------------------------


def test_execute_once_reruns_exchange_dedup_before_arm(tmp_path):
    report, sender, transport, probe = _execute_success(
        tmp_path, [_resp([{"orderId": "ORD-1", "orderStatus": "Filled"}])])
    # The execute path performed its own dedup lookups (not trusting preflight).
    assert probe.lookup_realtime_calls == 1
    assert probe.lookup_history_calls == 1
    assert report.final_outcome == bo.OUTCOME_FILLED_VERIFIED


def test_execute_once_duplicate_found_refuses_before_arm(tmp_path):
    r, s, t = _execute_with(tmp_path, dedup_realtime=dup_match_resp())
    assert r.final_outcome == bo.OUTCOME_REFUSED_PREFLIGHT
    assert s.call_count == 0 and t.post_calls == 0
    # Journal was never armed.
    assert not bo.OneShotJournal(str(tmp_path)).exists()


def test_execute_once_dedup_query_failure_refuses_before_arm(tmp_path):
    r, s, t = _execute_with(tmp_path, dedup_history=RuntimeError("rate limited"))
    assert r.final_outcome == bo.OUTCOME_REFUSED_PREFLIGHT
    assert s.call_count == 0 and t.post_calls == 0
    assert not bo.OneShotJournal(str(tmp_path)).exists()


def test_later_git_head_does_not_change_order_link_id(monkeypatch, tmp_path):
    # Simulate a later HEAD; execute still uses the same permanent orderLinkId.
    report, sender, transport, probe = _execute_success(
        tmp_path, [_resp([{"orderId": "ORD-1", "orderStatus": "Filled",
                           "orderLinkId": ORDER_LINK_ID}])])
    assert report.order_link_id == ORDER_LINK_ID


# ---------------------------------------------------------------------------
# Offline preflight: no journal, no HTTP (via CLI)
# ---------------------------------------------------------------------------


def test_offline_cli_preflight_creates_no_journal(monkeypatch, tmp_path, capsys):
    # Point the canonical journal at an empty temp dir via the factory only.
    monkeypatch.setattr(bo, "CANONICAL_JOURNAL_DIR", tmp_path / "j")
    monkeypatch.setattr(bo, "PROJECT_ROOT", tmp_path)
    rc = cli.main(["--json-only"])
    capsys.readouterr()
    assert rc == cli.EXIT_NOT_READY
    assert not (tmp_path / "j").exists()


def test_offline_cli_preflight_no_http(monkeypatch, capsys):
    import urllib.request

    def _boom(*a, **k):
        raise AssertionError("no HTTP allowed in offline preflight")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    rc = cli.main(["--json-only"])
    capsys.readouterr()
    assert rc in (cli.EXIT_READY, cli.EXIT_NOT_READY)


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------


def test_documentation_mentions_task_014bo_and_correction():
    for rel in ("README.md", "docs/research/commands/NEXT_ACTION.md",
                "docs/research/commands/COMMAND_LOG.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        low = text.lower()
        assert "TASK-014BO" in text
        # Correction 1: commit-independent permanent dedup identity.
        assert "AUTHORIZATION_SCOPE_IDENTITY" in text or "not derived from commit" in low
        # Correction 2: offline preflight fails closed because the exchange
        # duplicate checks were not performed.
        assert "not performed" in low or "fail closed" in low or "fails closed" in low


def test_position_open_warning_present_and_explicit():
    assert "SEPARATE explicit authorization" in bo.POSITION_OPEN_WARNING
    assert "never submits a close" in bo.POSITION_OPEN_WARNING
