"""SR-101C: unit tests for the pure versioned TradeHistory contract.

Covers validation, v1 GROSS-basis enforcement, canonical ordering, deterministic
duplicate handling, cutoff filtering, Kelly eligibility, the three fingerprints,
serialization round-trip, and process/hash-seed independence. No Kelly math is
duplicated here; the contract only selects and fingerprints the input list.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.strategy_core.trade_history import (  # noqa: E402
    CompletenessStatus,
    ConflictingDuplicateError,
    PnlBasis,
    SourceType,
    TradeHistoryRecord,
    TradeHistorySnapshot,
    TradeHistoryValidationError,
    UnsupportedPnlBasisError,
    SCHEMA_VERSION_V1,
)


# ── builders ─────────────────────────────────────────────────────────────────
def _rec(**kw) -> TradeHistoryRecord:
    base = dict(
        symbol="BTCUSDT",
        strategy_family="trend",
        exit_timestamp="2026-01-01T00:00:00+00:00",
        direction=1,
        quantity="1.0",
        entry_price="100.0",
        exit_price="110.0",
        gross_pnl="10.0",
        fee="0.5",
        net_pnl="9.5",
        close_reason="TP",
        order_id="",
        source="FIXTURE",
        sequence_number=0,
    )
    base.update(kw)
    return TradeHistoryRecord(**base)


def _snap(records=(), *, pnl_basis="GROSS", completeness="COMPLETE",
          source_type="FIXTURE", **kw) -> TradeHistorySnapshot:
    base = dict(
        schema_version=SCHEMA_VERSION_V1,
        strategy_family="trend",
        strategy_spec_version="v1",
        pnl_basis=pnl_basis,
        source_type=source_type,
        source_reference="fixture://x",
        generated_at="2026-02-01T00:00:00+00:00",
        snapshot_cutoff_timestamp=None,
        completeness_status=completeness,
        records=records,
        warnings=(),
    )
    base.update(kw)
    return TradeHistorySnapshot(**base)


# ── 1 & 2. empty snapshots ─────────────────────────────────────────────────
def test_empty_complete_snapshot_is_valid():
    s = _snap(records=())
    assert s.record_count == 0
    assert s.kelly_eligible_count == 0
    assert s.selected_kelly_pnls == ()
    assert s.completeness_status is CompletenessStatus.COMPLETE
    # fingerprints are still computable over empty content
    assert s.kelly_input_fingerprint.startswith("sha256:")


def test_empty_pilot_snapshot_can_be_complete_and_empty():
    s = _snap(records=(), source_type="EMPTY_PILOT", completeness="COMPLETE")
    assert s.source_type is SourceType.EMPTY_PILOT
    assert s.completeness_status is CompletenessStatus.COMPLETE
    assert s.record_count == 0


# ── 3 & 4. basis enforcement ────────────────────────────────────────────────
def test_v1_gross_snapshot_validates():
    s = _snap(records=(_rec(),), pnl_basis="GROSS")
    assert s.pnl_basis is PnlBasis.GROSS
    assert s.to_dict()["pnl_basis"] == "GROSS"


def test_v1_net_snapshot_is_rejected():
    with pytest.raises(UnsupportedPnlBasisError):
        _snap(records=(_rec(),), pnl_basis="NET")
    # also rejected via the enum instance form
    with pytest.raises(UnsupportedPnlBasisError):
        _snap(records=(_rec(),), pnl_basis=PnlBasis.NET)


# ── 5. symbol normalization ─────────────────────────────────────────────────
def test_symbol_normalization_is_deterministic():
    assert _rec(symbol="BTCUSDT").symbol == "BYBIT:BTCUSDT.P"
    assert _rec(symbol="btcusdt").symbol == "BYBIT:BTCUSDT.P"
    assert _rec(symbol="  ethusdt ").symbol == "BYBIT:ETHUSDT.P"
    # already system form is idempotent
    assert _rec(symbol="BYBIT:BTCUSDT.P").symbol == "BYBIT:BTCUSDT.P"
    assert _rec(symbol="bybit:btcusdt.p").symbol == "BYBIT:BTCUSDT.P"


# ── 6 & 7. input order independence ─────────────────────────────────────────
def _order_fixture():
    r1 = _rec(exit_timestamp="2026-01-01T00:00:00+00:00", sequence_number=1,
              gross_pnl="10.0", order_id="A")
    r2 = _rec(exit_timestamp="2026-01-02T00:00:00+00:00", sequence_number=2,
              gross_pnl="-5.0", order_id="B")
    r3 = _rec(exit_timestamp="2026-01-03T00:00:00+00:00", sequence_number=3,
              gross_pnl="7.0", order_id="C")
    return r1, r2, r3


def test_input_order_does_not_affect_canonical_order():
    r1, r2, r3 = _order_fixture()
    forward = _snap(records=(r1, r2, r3))
    shuffled = _snap(records=(r3, r1, r2))
    fwd_ids = [r.order_id for r in forward.canonical_records]
    shf_ids = [r.order_id for r in shuffled.canonical_records]
    assert fwd_ids == shf_ids == ["A", "B", "C"]


def test_input_order_does_not_affect_kelly_fingerprint():
    r1, r2, r3 = _order_fixture()
    forward = _snap(records=(r1, r2, r3))
    shuffled = _snap(records=(r3, r1, r2))
    assert forward.kelly_input_fingerprint == shuffled.kelly_input_fingerprint
    assert forward.history_data_fingerprint == shuffled.history_data_fingerprint


# ── 8 & 9. duplicates ────────────────────────────────────────────────────────
def test_identical_duplicates_deduplicate():
    a = _rec(order_id="DUP1", gross_pnl="10.0")
    b = _rec(order_id="DUP1", gross_pnl="10.0")
    s = _snap(records=(a, b))
    assert s.record_count == 1
    assert any("deduplicated" in w for w in s.warnings)


def test_conflicting_duplicate_raises():
    a = _rec(order_id="DUP2", gross_pnl="10.0")
    b = _rec(order_id="DUP2", gross_pnl="-3.0")   # same key, different Kelly PnL
    with pytest.raises(ConflictingDuplicateError):
        _snap(records=(a, b))


def test_duplicate_detection_is_order_independent():
    a = _rec(order_id="DUP3", gross_pnl="10.0")
    b = _rec(order_id="DUP3", gross_pnl="-3.0")
    with pytest.raises(ConflictingDuplicateError):
        _snap(records=(a, b))
    with pytest.raises(ConflictingDuplicateError):
        _snap(records=(b, a))


# ── 10. cutoff ───────────────────────────────────────────────────────────────
def test_cutoff_excludes_future_records():
    past = _rec(exit_timestamp="2026-01-01T00:00:00+00:00", order_id="PAST",
                gross_pnl="4.0")
    future = _rec(exit_timestamp="2026-06-01T00:00:00+00:00", order_id="FUT",
                  gross_pnl="9.0")
    s = _snap(records=(past, future),
              snapshot_cutoff_timestamp="2026-03-01T00:00:00+00:00")
    ids = [r.order_id for r in s.canonical_records]
    assert ids == ["PAST"]
    assert any("post-cutoff" in w for w in s.warnings)
    # original input records are not mutated / not dropped from .records
    assert {r.order_id for r in s.records} == {"PAST", "FUT"}


# ── 11 & 12. Kelly eligibility ──────────────────────────────────────────────
def test_zero_gross_pnl_remains_kelly_eligible():
    z = _rec(order_id="ZERO", gross_pnl="0.0")
    s = _snap(records=(z,))
    assert s.kelly_eligible_count == 1
    assert s.selected_kelly_pnls == (Decimal("0.0"),)


def test_none_gross_pnl_is_not_kelly_eligible():
    n = _rec(order_id="NONE", gross_pnl=None)
    s = _snap(records=(n,))
    assert s.record_count == 1            # still a provenance record
    assert s.kelly_eligible_count == 0
    assert s.selected_kelly_pnls == ()


def test_missing_exit_timestamp_is_not_kelly_eligible():
    r = _rec(order_id="NOTS", exit_timestamp=None, gross_pnl="5.0")
    s = _snap(records=(r,))
    assert s.record_count == 1
    assert s.kelly_eligible_count == 0


# ── 13. decimal serialization stability ─────────────────────────────────────
def test_decimal_serialization_is_stable():
    r = _rec(gross_pnl="10.50", fee="0.0001", quantity="0.100")
    d1 = r.to_dict()
    d2 = TradeHistoryRecord.from_dict(d1).to_dict()
    assert d1 == d2
    assert d1["gross_pnl"] == "10.50"        # no scientific notation, preserved
    assert d1["fee"] == "0.0001"
    assert d1["quantity"] == "0.100"
    # float input is routed through str -> clean decimal string (no binary artifact)
    assert _rec(gross_pnl=0.1).to_dict()["gross_pnl"] == "0.1"


# ── 14. snapshot round-trip ─────────────────────────────────────────────────
def test_snapshot_roundtrip_preserves_values_and_fingerprints():
    r1, r2, r3 = _order_fixture()
    s = _snap(records=(r1, r2, r3), warnings=("hello",),
              snapshot_cutoff_timestamp="2026-12-01T00:00:00+00:00")
    restored = TradeHistorySnapshot.from_dict(s.to_dict())

    assert restored.pnl_basis is s.pnl_basis
    assert restored.source_type is s.source_type
    assert restored.completeness_status is s.completeness_status
    assert restored.strategy_spec_version == s.strategy_spec_version
    assert restored.snapshot_cutoff_timestamp == s.snapshot_cutoff_timestamp
    assert [x.to_dict() for x in restored.canonical_records] == \
           [x.to_dict() for x in s.canonical_records]
    assert restored.selected_kelly_pnls == s.selected_kelly_pnls
    assert restored.kelly_input_fingerprint == s.kelly_input_fingerprint
    assert restored.history_data_fingerprint == s.history_data_fingerprint
    assert restored.provenance_fingerprint == s.provenance_fingerprint
    assert restored.warnings == s.warnings


# ── 15-20. fingerprint responsibility separation ────────────────────────────
def test_changing_fee_does_not_change_kelly_input_fingerprint():
    base = _snap(records=(_rec(order_id="X", fee="0.5"),))
    fee_changed = _snap(records=(_rec(order_id="X", fee="5.0"),))
    assert base.kelly_input_fingerprint == fee_changed.kelly_input_fingerprint


def test_changing_fee_changes_history_data_fingerprint():
    base = _snap(records=(_rec(order_id="X", fee="0.5"),))
    fee_changed = _snap(records=(_rec(order_id="X", fee="5.0"),))
    assert base.history_data_fingerprint != fee_changed.history_data_fingerprint


def test_changing_gross_pnl_changes_kelly_input_fingerprint():
    base = _snap(records=(_rec(order_id="X", gross_pnl="10.0"),))
    pnl_changed = _snap(records=(_rec(order_id="X", gross_pnl="11.0"),))
    assert base.kelly_input_fingerprint != pnl_changed.kelly_input_fingerprint


def test_changing_source_reference_does_not_change_kelly_fingerprint():
    base = _snap(records=(_rec(order_id="X"),), source_reference="a://1")
    ref_changed = _snap(records=(_rec(order_id="X"),), source_reference="b://2")
    assert base.kelly_input_fingerprint == ref_changed.kelly_input_fingerprint


def test_changing_source_reference_changes_provenance_fingerprint():
    base = _snap(records=(_rec(order_id="X"),), source_reference="a://1")
    ref_changed = _snap(records=(_rec(order_id="X"),), source_reference="b://2")
    assert base.provenance_fingerprint != ref_changed.provenance_fingerprint


def test_generated_at_does_not_affect_kelly_fingerprint():
    base = _snap(records=(_rec(order_id="X"),),
                 generated_at="2026-02-01T00:00:00+00:00")
    later = _snap(records=(_rec(order_id="X"),),
                  generated_at="2026-09-09T09:09:09+00:00")
    assert base.kelly_input_fingerprint == later.kelly_input_fingerprint
    assert base.provenance_fingerprint != later.provenance_fingerprint


# ── 21. status round-trips ───────────────────────────────────────────────────
def test_complete_partial_unknown_status_roundtrip():
    for status in ("COMPLETE", "PARTIAL", "UNKNOWN"):
        s = _snap(records=(_rec(),), completeness=status)
        restored = TradeHistorySnapshot.from_dict(s.to_dict())
        assert restored.completeness_status is CompletenessStatus(status)


# ── 22. repeat-call determinism ─────────────────────────────────────────────
def test_fingerprints_identical_across_repeated_calls():
    s = _snap(records=_order_fixture())
    assert s.kelly_input_fingerprint == s.kelly_input_fingerprint
    assert s.history_data_fingerprint == s.history_data_fingerprint
    assert s.provenance_fingerprint == s.provenance_fingerprint


# ── 23. process / hash-seed independence ────────────────────────────────────
_SUBPROCESS_SNIPPET = r"""
import sys
sys.path.insert(0, r"{root}")
from src.strategy_core.trade_history import (
    TradeHistoryRecord, TradeHistorySnapshot, SCHEMA_VERSION_V1)
rows = [(10.0, "A", "2026-01-01T00:00:00+00:00"),
        (-5.0, "B", "2026-01-02T00:00:00+00:00"),
        (7.0, "C", "2026-01-03T00:00:00+00:00")]
recs = [
    TradeHistoryRecord(symbol="BTCUSDT", strategy_family="trend",
        exit_timestamp=ts, gross_pnl=str(p), order_id=oid, sequence_number=i)
    for i, (p, oid, ts) in enumerate(rows, start=1)
]
s = TradeHistorySnapshot(
    schema_version=SCHEMA_VERSION_V1, strategy_family="trend",
    strategy_spec_version="v1", pnl_basis="GROSS", source_type="FIXTURE",
    source_reference="fixture://x", generated_at="2026-02-01T00:00:00+00:00",
    snapshot_cutoff_timestamp=None, completeness_status="COMPLETE", records=recs)
print(s.kelly_input_fingerprint)
print(s.history_data_fingerprint)
print(s.provenance_fingerprint)
"""


def _fingerprints_in_subprocess(hashseed: str):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hashseed
    snippet = _SUBPROCESS_SNIPPET.format(root=str(_ROOT))
    out = subprocess.run(
        [sys.executable, "-c", snippet],
        env=env, capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()


def test_fingerprints_independent_of_python_hash_seed():
    seed0 = _fingerprints_in_subprocess("0")
    seed1 = _fingerprints_in_subprocess("1")
    seed_rand = _fingerprints_in_subprocess("random")
    assert seed0 == seed1 == seed_rand
    assert all(fp.startswith("sha256:") for fp in seed0)


# ── 24. purity: no network / filesystem API in the module ───────────────────
def test_module_has_no_network_or_filesystem_api():
    src_path = _ROOT / "src" / "strategy_core" / "trade_history.py"
    text = src_path.read_text(encoding="utf-8")
    forbidden = ("import os", "import socket", "import urllib", "import requests",
                 "import http", "import pathlib", "from pathlib", "open(",
                 "socket.", "urllib", "requests.")
    offenders = [tok for tok in forbidden if tok in text]
    assert offenders == [], f"module references forbidden I/O API: {offenders}"

    import src.strategy_core.trade_history as mod
    for banned in ("os", "socket", "requests", "urllib", "open", "Path"):
        assert not hasattr(mod, banned), f"module exposes {banned}"


# ══ SR-101C-R1 hardening regressions ════════════════════════════════════════

# ── A. snapshot immutability ─────────────────────────────────────────────────
def test_snapshot_is_immutable_after_construction():
    s = _snap(records=(_rec(),))
    for name, value in (("_records", ()),
                        ("_strategy_family", "changed"),
                        ("_canonical_records", ()),
                        ("_pnl_basis", None),
                        ("new_attribute", 1)):
        with pytest.raises(AttributeError):
            setattr(s, name, value)
    with pytest.raises(AttributeError):
        del s._records


def test_snapshot_exposed_collections_are_tuples():
    s = _snap(records=(_rec(order_id="A"), _rec(order_id="B", exit_timestamp=None)))
    assert isinstance(s.records, tuple)
    assert isinstance(s.canonical_records, tuple)
    assert isinstance(s.kelly_eligible_records, tuple)
    assert isinstance(s.selected_kelly_pnls, tuple)
    assert isinstance(s.warnings, tuple)


# ── B. provenance-different duplicates fail closed ──────────────────────────
def test_identical_full_record_duplicate_deduplicates():
    a = _rec(order_id="ID", gross_pnl="10.0", fee="0.5", close_reason="TP")
    b = _rec(order_id="ID", gross_pnl="10.0", fee="0.5", close_reason="TP")
    s = _snap(records=(a, b))
    assert s.record_count == 1
    assert any("deduplicated identical" in w for w in s.warnings)


def test_same_key_and_gross_but_different_fee_raises():
    a = _rec(order_id="ID", gross_pnl="10.0", fee="0.5")
    b = _rec(order_id="ID", gross_pnl="10.0", fee="9.9")   # only fee differs
    with pytest.raises(ConflictingDuplicateError) as ei:
        _snap(records=(a, b))
    assert "fee" in str(ei.value)


def test_same_key_and_gross_but_different_close_reason_raises():
    a = _rec(order_id="ID", gross_pnl="10.0", close_reason="TP")
    b = _rec(order_id="ID", gross_pnl="10.0", close_reason="FLIP")
    with pytest.raises(ConflictingDuplicateError) as ei:
        _snap(records=(a, b))
    assert "close_reason" in str(ei.value)


def test_conflicting_provenance_duplicate_is_order_symmetric():
    a = _rec(order_id="ID", gross_pnl="10.0", fee="0.5")
    b = _rec(order_id="ID", gross_pnl="10.0", fee="9.9")
    with pytest.raises(ConflictingDuplicateError):
        _snap(records=(a, b))
    with pytest.raises(ConflictingDuplicateError):
        _snap(records=(b, a))


def test_valid_records_canonical_output_is_input_order_independent():
    r1, r2, r3 = _order_fixture()
    a = _snap(records=(r1, r2, r3))
    b = _snap(records=(r3, r2, r1))
    assert a.canonical_json() == b.canonical_json()
    assert a.kelly_input_fingerprint == b.kelly_input_fingerprint
    assert a.history_data_fingerprint == b.history_data_fingerprint
    assert a.provenance_fingerprint == b.provenance_fingerprint


# ── C. Kelly record identity distinguishes repeated logical trades ──────────
def test_same_symbol_sequence_gross_but_different_order_id_differ_in_kelly_fp():
    a = _snap(records=(_rec(order_id="OID-1", sequence_number=1, gross_pnl="10.0"),))
    b = _snap(records=(_rec(order_id="OID-2", sequence_number=1, gross_pnl="10.0"),))
    assert a.kelly_input_fingerprint != b.kelly_input_fingerprint


def test_no_order_id_different_exit_timestamp_differ_in_kelly_fp():
    a = _snap(records=(_rec(order_id="", exit_timestamp="2026-01-01T00:00:00+00:00",
                            gross_pnl="10.0"),))
    b = _snap(records=(_rec(order_id="", exit_timestamp="2026-01-02T00:00:00+00:00",
                            gross_pnl="10.0"),))
    assert a.kelly_input_fingerprint != b.kelly_input_fingerprint


def test_kelly_identity_change_fee_still_does_not_change_kelly_fp():
    a = _snap(records=(_rec(order_id="OID", fee="0.5"),))
    b = _snap(records=(_rec(order_id="OID", fee="7.7"),))
    assert a.kelly_input_fingerprint == b.kelly_input_fingerprint


def test_kelly_identity_input_order_still_does_not_change_kelly_fp():
    r1, r2, r3 = _order_fixture()
    a = _snap(records=(r1, r2, r3))
    b = _snap(records=(r2, r3, r1))
    assert a.kelly_input_fingerprint == b.kelly_input_fingerprint


# ── D. unambiguous timezone-aware timestamps ────────────────────────────────
def test_z_and_plus_zero_offset_normalize_identically():
    a = _snap(records=(_rec(order_id="X", exit_timestamp="2026-01-01T00:00:00Z"),))
    b = _snap(records=(_rec(order_id="X", exit_timestamp="2026-01-01T00:00:00+00:00"),))
    assert a.canonical_json() == b.canonical_json()
    assert a.history_data_fingerprint == b.history_data_fingerprint
    assert a.kelly_input_fingerprint == b.kelly_input_fingerprint


def test_non_utc_offset_normalizes_to_equivalent_utc_instant():
    # 2026-01-01T08:00:00+08:00 is the same instant as 2026-01-01T00:00:00Z
    offset = _snap(records=(_rec(order_id="X", exit_timestamp="2026-01-01T08:00:00+08:00"),))
    utc = _snap(records=(_rec(order_id="X", exit_timestamp="2026-01-01T00:00:00+00:00"),))
    assert offset.canonical_records[0].exit_timestamp == "2026-01-01T00:00:00+00:00"
    assert offset.canonical_json() == utc.canonical_json()
    assert offset.history_data_fingerprint == utc.history_data_fingerprint


def test_naive_iso_string_timestamp_is_rejected():
    with pytest.raises(TradeHistoryValidationError):
        _rec(exit_timestamp="2026-01-01T00:00:00")      # no offset -> naive
    with pytest.raises(TradeHistoryValidationError):
        _rec(entry_timestamp="2026-01-01T00:00:00")


def test_naive_datetime_timestamp_is_rejected():
    naive = datetime(2026, 1, 1, 0, 0, 0)               # tzinfo is None
    with pytest.raises(TradeHistoryValidationError):
        _rec(exit_timestamp=naive)
    aware = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert _rec(exit_timestamp=aware).exit_timestamp == "2026-01-01T00:00:00+00:00"


def test_naive_snapshot_scalar_timestamps_are_rejected():
    with pytest.raises(TradeHistoryValidationError):
        _snap(records=(_rec(),), generated_at="2026-02-01T00:00:00")
    with pytest.raises(TradeHistoryValidationError):
        _snap(records=(_rec(),), snapshot_cutoff_timestamp="2026-02-01T00:00:00")


def test_equivalent_instants_produce_identical_identity():
    a = _snap(records=(_rec(order_id="X", exit_timestamp="2026-03-01T12:00:00Z"),),
              generated_at="2026-04-01T00:00:00+00:00")
    b = _snap(records=(_rec(order_id="X", exit_timestamp="2026-03-01T20:00:00+08:00"),),
              generated_at="2026-04-01T00:00:00Z")
    assert a.kelly_input_fingerprint == b.kelly_input_fingerprint
    assert a.history_data_fingerprint == b.history_data_fingerprint
    assert a.provenance_fingerprint == b.provenance_fingerprint
