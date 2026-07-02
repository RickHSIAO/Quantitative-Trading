"""SR-101D1: tests for the pure Live trade-history adapter.

Proves the adapter converts already-loaded ledger rows and same-process close
events into the contract objects without ever mislabeling ambiguous exchange /
legacy PnL as gross, with deterministic completeness and input-order-independent
canonical output. No I/O, no main.cmd_live.
"""
from __future__ import annotations

import subprocess
import sys
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
    TradeHistorySnapshot,
)
from src.strategy_core.live_trade_history_adapter import (  # noqa: E402
    LiveSourceCompleteness,
    LiveTradeHistoryAdapterError,
    adapt_live_history_rows,
    adapt_same_process_close_events,
)

_TS = "2026-01-01T00:00:00+00:00"
_GEN = "2026-02-01T00:00:00+00:00"


def _rows(rows, *, completeness=LiveSourceCompleteness.ATTESTED_COMPLETE, **kw):
    base = dict(
        strategy_family="trend",
        strategy_spec_version="v1",
        source_reference="ledger://live",
        source_completeness=completeness,
        generated_at=_GEN,
    )
    base.update(kw)
    # Persisted history is CLOSED trades: default each fixture row to an explicit
    # EXIT action unless the test provides its own action (non-mutating).
    prepared = [{**r, "action": r.get("action", "EXIT")} for r in rows]
    return adapt_live_history_rows(prepared, **base)


def _events(events, *, completeness=LiveSourceCompleteness.ATTESTED_COMPLETE, **kw):
    base = dict(
        strategy_family="trend",
        strategy_spec_version="v1",
        source_reference="live://close-events",
        source_completeness=completeness,
        generated_at=_GEN,
    )
    base.update(kw)
    return adapt_same_process_close_events(events, **base)


# ── 1. explicit gross ledger row is Kelly-eligible ──────────────────────────
def test_explicit_gross_ledger_row_is_kelly_eligible():
    s = _rows([{
        "symbol": "BTCUSDT", "direction": 1, "quantity": "1.0",
        "price": "110.0", "gross_pnl": "10.0", "fee": "0.5",
        "reason": "TP", "order_id": "OID1", "exit_timestamp": _TS,
    }])
    assert s.kelly_eligible_count == 1
    assert s.selected_kelly_pnls == (Decimal("10.0"),)
    assert s.source_type is SourceType.LIVE
    assert s.pnl_basis is PnlBasis.GROSS


def test_declared_gross_basis_plus_pnl_is_kelly_eligible():
    s = _rows([{
        "symbol": "BTCUSDT", "direction": 1, "quantity": "1.0",
        "pnl_basis": "GROSS", "pnl": "7.0", "order_id": "OID2",
        "exit_timestamp": _TS,
    }])
    assert s.kelly_eligible_count == 1
    assert s.selected_kelly_pnls == (Decimal("7.0"),)


# ── 2 & 3. same-process close event gross computation ───────────────────────
def test_close_event_computes_gross_for_long():
    s = _events([{
        "symbol": "BTCUSDT", "direction": 1, "quantity": "2",
        "entry_price": "100", "exit_price": "110",
        "order_id": "L1", "exit_timestamp": _TS,
    }])
    # (110 - 100) * 2 * 1 = 20
    assert s.selected_kelly_pnls == (Decimal("20"),)
    assert s.kelly_eligible_count == 1


def test_close_event_computes_gross_for_short():
    s = _events([{
        "symbol": "BTCUSDT", "direction": -1, "quantity": "2",
        "entry_price": "100", "exit_price": "90",
        "order_id": "S1", "exit_timestamp": _TS,
    }])
    # (90 - 100) * 2 * -1 = 20
    assert s.selected_kelly_pnls == (Decimal("20"),)
    assert s.kelly_eligible_count == 1


def test_close_event_side_maps_position_direction():
    long_s = _events([{
        "symbol": "BTCUSDT", "side": "Buy", "quantity": "1",
        "entry_price": "100", "exit_price": "105",
        "order_id": "B", "exit_timestamp": _TS,
    }])
    short_s = _events([{
        "symbol": "BTCUSDT", "side": "Sell", "quantity": "1",
        "entry_price": "100", "exit_price": "105",
        "order_id": "S", "exit_timestamp": _TS,
    }])
    assert long_s.selected_kelly_pnls == (Decimal("5"),)     # +5 for a long
    assert short_s.selected_kelly_pnls == (Decimal("-5"),)   # -5 for a short


# ── 4 & 5. ambiguous legacy PnL is never gross ──────────────────────────────
def test_ambiguous_pnl_only_row_is_not_kelly_eligible():
    s = _rows([{
        "symbol": "BTCUSDT", "direction": 1, "quantity": "1.0",
        "price": "110.0", "pnl": "10.0", "order_id": "AMB1",
        "exit_timestamp": _TS,
    }])
    assert s.record_count == 1               # retained as provenance
    assert s.kelly_eligible_count == 0
    assert any("ambiguous legacy PnL" in w for w in s.warnings)


def test_closed_pnl_only_row_is_not_treated_as_gross():
    s = _rows([{
        "symbol": "BTCUSDT", "direction": -1, "quantity": "1.0",
        "price": "90.0", "closedPnl": "13.3", "realizedPnl": "12.0",
        "order_id": "AMB2", "exit_timestamp": _TS,
    }])
    assert s.kelly_eligible_count == 0
    assert s.selected_kelly_pnls == ()
    assert any("closedPnl" in w for w in s.warnings)


# ── 6. fee does not alter gross or Kelly fingerprint ────────────────────────
def test_fee_does_not_alter_gross_or_kelly_fingerprint():
    a = _rows([{"symbol": "BTCUSDT", "direction": 1, "quantity": "1",
                "gross_pnl": "10.0", "fee": "0.5", "order_id": "F",
                "exit_timestamp": _TS}])
    b = _rows([{"symbol": "BTCUSDT", "direction": 1, "quantity": "1",
                "gross_pnl": "10.0", "fee": "9.9", "order_id": "F",
                "exit_timestamp": _TS}])
    assert a.selected_kelly_pnls == b.selected_kelly_pnls == (Decimal("10.0"),)
    assert a.kelly_input_fingerprint == b.kelly_input_fingerprint
    assert a.history_data_fingerprint != b.history_data_fingerprint


# ── 7 & 8. empty-input completeness ─────────────────────────────────────────
def test_trusted_complete_empty_history_is_complete_and_empty():
    s = _rows([], completeness=LiveSourceCompleteness.ATTESTED_COMPLETE)
    assert s.completeness_status is CompletenessStatus.COMPLETE
    assert s.record_count == 0
    assert s.source_type is SourceType.LIVE


def test_unattested_empty_input_is_unknown_not_complete():
    s = _rows([], completeness=LiveSourceCompleteness.UNKNOWN)
    assert s.completeness_status is CompletenessStatus.UNKNOWN
    loaded = _rows([], completeness=LiveSourceCompleteness.LOADED)
    assert loaded.completeness_status is CompletenessStatus.PARTIAL


# ── 9. mixed authoritative + ambiguous -> PARTIAL ───────────────────────────
def test_mixed_authoritative_and_ambiguous_rows_is_partial():
    s = _rows([
        {"symbol": "BTCUSDT", "direction": 1, "quantity": "1", "gross_pnl": "10.0",
         "order_id": "OK", "exit_timestamp": _TS},
        {"symbol": "ETHUSDT", "direction": 1, "quantity": "1", "pnl": "3.0",
         "order_id": "AMB", "exit_timestamp": _TS},
    ], completeness=LiveSourceCompleteness.ATTESTED_COMPLETE)
    assert s.completeness_status is CompletenessStatus.PARTIAL
    assert s.kelly_eligible_count == 1


# ── 10. invalid/missing authoritative timestamp cannot be Kelly-eligible ────
def test_authoritative_row_with_naive_timestamp_is_not_kelly_eligible():
    s = _rows([{
        "symbol": "BTCUSDT", "direction": 1, "quantity": "1",
        "gross_pnl": "10.0", "order_id": "NAIVE",
        "exit_timestamp": "2026-01-01T00:00:00",     # naive -> not usable
    }], completeness=LiveSourceCompleteness.ATTESTED_COMPLETE)
    assert s.kelly_eligible_count == 0
    assert s.completeness_status is CompletenessStatus.PARTIAL
    assert any("exit_timestamp" in w for w in s.warnings)


def test_authoritative_row_with_no_timestamp_is_not_kelly_eligible():
    s = _rows([{
        "symbol": "BTCUSDT", "direction": 1, "quantity": "1",
        "gross_pnl": "10.0", "order_id": "NOTS",
    }], completeness=LiveSourceCompleteness.ATTESTED_COMPLETE)
    assert s.kelly_eligible_count == 0
    assert s.completeness_status is CompletenessStatus.PARTIAL


# ── 11. epoch conversion is aware & deterministic ───────────────────────────
def test_epoch_ms_timestamp_is_timezone_aware_and_deterministic():
    # 2026-01-01T00:00:00Z == 1767225600000 ms
    epoch_ms = 1767225600000
    s = _events([{
        "symbol": "BTCUSDT", "direction": 1, "quantity": "1",
        "entry_price": "100", "exit_price": "110", "order_id": "E",
        "exit_timestamp": {"epoch_ms": epoch_ms},
    }])
    assert s.kelly_eligible_count == 1
    ts = s.canonical_records[0].exit_timestamp
    assert ts == "2026-01-01T00:00:00+00:00"
    # deterministic
    s2 = _events([{
        "symbol": "BTCUSDT", "direction": 1, "quantity": "1",
        "entry_price": "100", "exit_price": "110", "order_id": "E",
        "exit_timestamp": {"epoch_ms": epoch_ms},
    }])
    assert s.history_data_fingerprint == s2.history_data_fingerprint


def test_bare_int_timestamp_is_ambiguous_and_refused():
    s = _events([{
        "symbol": "BTCUSDT", "direction": 1, "quantity": "1",
        "entry_price": "100", "exit_price": "110", "order_id": "BARE",
        "exit_timestamp": 1767225600,     # bare int: ms or s? refuse to guess
    }])
    assert s.kelly_eligible_count == 0
    assert any("exit timestamp" in w for w in s.warnings)


# ── 12. ledger EXIT 'side' is the closing side; direction from 'direction' ──
def test_ledger_direction_taken_from_direction_field_not_reversed_side():
    # A held SHORT (direction=-1) EXIT ledger row carries side='Buy' (closing).
    s = _rows([{
        "symbol": "BTCUSDT", "direction": -1, "side": "Buy",
        "quantity": "1", "price": "90", "gross_pnl": "10.0",
        "order_id": "SHORT", "exit_timestamp": _TS,
    }])
    rec = s.canonical_records[0]
    assert rec.direction == -1        # held short, NOT +1 from the closing 'Buy'


# ── 13 & 14. input order independence ───────────────────────────────────────
def _three_events():
    return [
        {"symbol": "BTCUSDT", "direction": 1, "quantity": "1", "entry_price": "100",
         "exit_price": "110", "order_id": "A", "exit_timestamp": "2026-01-01T00:00:00+00:00"},
        {"symbol": "ETHUSDT", "direction": -1, "quantity": "2", "entry_price": "50",
         "exit_price": "45", "order_id": "B", "exit_timestamp": "2026-01-02T00:00:00+00:00"},
        {"symbol": "SOLUSDT", "direction": 1, "quantity": "3", "entry_price": "10",
         "exit_price": "12", "order_id": "C", "exit_timestamp": "2026-01-03T00:00:00+00:00"},
    ]


def test_input_order_does_not_change_canonical_records():
    e = _three_events()
    fwd = _events(e)
    rev = _events(list(reversed(e)))
    assert [r.order_id for r in fwd.canonical_records] == \
           [r.order_id for r in rev.canonical_records]


def test_input_order_does_not_change_fingerprints():
    e = _three_events()
    fwd = _events(e)
    shuffled = _events([e[2], e[0], e[1]])
    assert fwd.kelly_input_fingerprint == shuffled.kelly_input_fingerprint
    assert fwd.history_data_fingerprint == shuffled.history_data_fingerprint
    assert fwd.canonical_json() == shuffled.canonical_json()


# ── 15 & 16. duplicates follow contract rules ───────────────────────────────
def test_identical_duplicate_rows_deduplicate():
    row = {"symbol": "BTCUSDT", "direction": 1, "quantity": "1", "gross_pnl": "10.0",
           "fee": "0.5", "order_id": "DUP", "exit_timestamp": _TS}
    s = _rows([dict(row), dict(row)])
    assert s.record_count == 1


def test_conflicting_duplicate_rows_fail_closed():
    a = {"symbol": "BTCUSDT", "direction": 1, "quantity": "1", "gross_pnl": "10.0",
         "order_id": "DUP", "exit_timestamp": _TS}
    b = {"symbol": "BTCUSDT", "direction": 1, "quantity": "1", "gross_pnl": "3.0",
         "order_id": "DUP", "exit_timestamp": _TS}
    with pytest.raises(ConflictingDuplicateError):
        _rows([a, b])


# ── 17. cutoff excludes future records ──────────────────────────────────────
def test_cutoff_excludes_future_records():
    s = _rows([
        {"symbol": "BTCUSDT", "direction": 1, "quantity": "1", "gross_pnl": "4.0",
         "order_id": "PAST", "exit_timestamp": "2026-01-01T00:00:00+00:00"},
        {"symbol": "BTCUSDT", "direction": 1, "quantity": "1", "gross_pnl": "9.0",
         "order_id": "FUT", "exit_timestamp": "2026-06-01T00:00:00+00:00"},
    ], snapshot_cutoff_timestamp="2026-03-01T00:00:00+00:00")
    ids = [r.order_id for r in s.canonical_records]
    assert ids == ["PAST"]
    assert any("post-cutoff" in w for w in s.warnings)


# ── 18 & 19. snapshot identity ──────────────────────────────────────────────
def test_snapshot_source_type_is_live_and_basis_is_gross():
    s = _rows([{"symbol": "BTCUSDT", "direction": 1, "quantity": "1",
                "gross_pnl": "10.0", "order_id": "X", "exit_timestamp": _TS}])
    assert s.source_type is SourceType.LIVE
    assert s.pnl_basis is PnlBasis.GROSS
    assert s.to_dict()["source_type"] == "LIVE"
    assert s.to_dict()["pnl_basis"] == "GROSS"


# ── 20. round-trip preserves adapter output ─────────────────────────────────
def test_snapshot_roundtrip_preserves_adapter_output():
    s = _events(_three_events(),
                snapshot_cutoff_timestamp="2026-12-01T00:00:00+00:00")
    restored = TradeHistorySnapshot.from_dict(s.to_dict())
    assert restored.kelly_input_fingerprint == s.kelly_input_fingerprint
    assert restored.history_data_fingerprint == s.history_data_fingerprint
    assert restored.provenance_fingerprint == s.provenance_fingerprint
    assert restored.selected_kelly_pnls == s.selected_kelly_pnls
    assert restored.completeness_status is s.completeness_status


# ── 21. no I/O API in the adapter module ────────────────────────────────────
def test_adapter_module_has_no_io_api():
    src_path = _ROOT / "src" / "strategy_core" / "live_trade_history_adapter.py"
    text = src_path.read_text(encoding="utf-8")
    forbidden = ("import os", "import socket", "import sqlite3", "import urllib",
                 "import requests", "import http", "from pathlib", "import pathlib",
                 "open(", "socket.", "requests.", "sqlite3.", "os.environ",
                 "getenv")
    offenders = [tok for tok in forbidden if tok in text]
    assert offenders == [], f"adapter references forbidden I/O API: {offenders}"

    import src.strategy_core.live_trade_history_adapter as mod
    for banned in ("os", "socket", "sqlite3", "requests", "urllib", "open", "Path"):
        assert not hasattr(mod, banned), f"module exposes {banned}"


# ── adapter misuse fails loudly ─────────────────────────────────────────────
def test_non_sequence_input_raises_adapter_error():
    with pytest.raises(LiveTradeHistoryAdapterError):
        adapt_live_history_rows(
            {"symbol": "BTCUSDT"},           # a mapping, not a sequence of rows
            strategy_family="trend", strategy_spec_version="v1",
            source_reference="x", source_completeness=LiveSourceCompleteness.UNKNOWN)


def test_row_missing_symbol_raises_adapter_error():
    with pytest.raises(LiveTradeHistoryAdapterError):
        _rows([{"direction": 1, "gross_pnl": "10.0", "exit_timestamp": _TS}])


# ── 11/13 reinforcement: hash-seed independence of adapter output ───────────
_SUBPROCESS = r"""
import sys
sys.path.insert(0, r"{root}")
from src.strategy_core.live_trade_history_adapter import (
    adapt_same_process_close_events, LiveSourceCompleteness)
events = [
    {{"symbol":"BTCUSDT","direction":1,"quantity":"1","entry_price":"100",
      "exit_price":"110","order_id":"A","exit_timestamp":"2026-01-01T00:00:00+00:00"}},
    {{"symbol":"ETHUSDT","direction":-1,"quantity":"2","entry_price":"50",
      "exit_price":"45","order_id":"B","exit_timestamp":"2026-01-02T00:00:00+00:00"}},
]
s = adapt_same_process_close_events(
    events, strategy_family="trend", strategy_spec_version="v1",
    source_reference="live://x", source_completeness=LiveSourceCompleteness.ATTESTED_COMPLETE,
    generated_at="2026-02-01T00:00:00+00:00")
print(s.kelly_input_fingerprint)
print(s.history_data_fingerprint)
"""


def _fps(seed):
    import os
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    out = subprocess.run([sys.executable, "-c", _SUBPROCESS.format(root=str(_ROOT))],
                         env=env, capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()


def test_adapter_fingerprints_independent_of_hash_seed():
    assert _fps("0") == _fps("1") == _fps("random")


# ══ SR-101D1-R1 hardening regressions ═══════════════════════════════════════

# ── A. EXIT-action enforcement ──────────────────────────────────────────────
def test_exit_action_with_explicit_gross_is_eligible():
    s = _rows([{"symbol": "BTCUSDT", "action": "EXIT", "direction": 1,
                "quantity": "1", "gross_pnl": "10.0", "order_id": "E",
                "exit_timestamp": _TS}])
    assert s.kelly_eligible_count == 1
    assert s.completeness_status is CompletenessStatus.COMPLETE


def test_entry_action_with_explicit_gross_is_not_eligible():
    s = _rows([{"symbol": "BTCUSDT", "action": "ENTRY", "direction": 1,
                "quantity": "1", "gross_pnl": "10.0", "order_id": "N",
                "exit_timestamp": _TS}])
    assert s.record_count == 0                # ENTRY is not a closed trade
    assert s.kelly_eligible_count == 0
    assert s.completeness_status is CompletenessStatus.COMPLETE   # clean exclusion
    assert any("ENTRY" in w for w in s.warnings)


def test_non_exit_rows_absent_from_canonical_records():
    s = _rows([
        {"symbol": "BTCUSDT", "action": "EXIT", "direction": 1, "quantity": "1",
         "gross_pnl": "10.0", "order_id": "OK", "exit_timestamp": _TS},
        {"symbol": "ETHUSDT", "action": "ENTRY", "direction": 1, "quantity": "1",
         "gross_pnl": "5.0", "order_id": "IN", "exit_timestamp": _TS},
        {"symbol": "SOLUSDT", "action": "HOLD", "direction": 1, "quantity": "1",
         "gross_pnl": "3.0", "order_id": "HD", "exit_timestamp": _TS},
    ])
    syms = {r.symbol for r in s.canonical_records}
    assert syms == {"BYBIT:BTCUSDT.P"}


def test_missing_action_is_not_eligible_and_downgrades_complete():
    s = adapt_live_history_rows(
        [{"symbol": "BTCUSDT", "direction": 1, "quantity": "1",
          "gross_pnl": "10.0", "order_id": "MISS", "exit_timestamp": _TS}],
        strategy_family="trend", strategy_spec_version="v1",
        source_reference="ledger://live",
        source_completeness=LiveSourceCompleteness.ATTESTED_COMPLETE,
        generated_at=_GEN)
    assert s.record_count == 0
    assert s.kelly_eligible_count == 0
    assert s.completeness_status is CompletenessStatus.PARTIAL
    assert any("missing/unrecognized action" in w for w in s.warnings)


def test_action_filtering_is_order_and_warning_independent():
    rows = [
        {"symbol": "BTCUSDT", "action": "EXIT", "direction": 1, "quantity": "1",
         "gross_pnl": "10.0", "order_id": "A", "exit_timestamp": "2026-01-01T00:00:00+00:00"},
        {"symbol": "ETHUSDT", "action": "ENTRY", "direction": 1, "quantity": "1",
         "gross_pnl": "5.0", "order_id": "B", "exit_timestamp": "2026-01-02T00:00:00+00:00"},
    ]
    a = _rows(rows)
    b = _rows(list(reversed(rows)))
    assert a.warnings == b.warnings
    assert a.history_data_fingerprint == b.history_data_fingerprint
    assert a.kelly_input_fingerprint == b.kelly_input_fingerprint


# ── B. strategy-family binding ──────────────────────────────────────────────
def test_missing_row_family_inherits_snapshot_family():
    s = _rows([{"symbol": "BTCUSDT", "action": "EXIT", "direction": 1,
                "quantity": "1", "gross_pnl": "10.0", "order_id": "X",
                "exit_timestamp": _TS}], strategy_family="trend")
    assert s.canonical_records[0].strategy_family == "trend"


def test_matching_row_family_succeeds():
    s = _rows([{"symbol": "BTCUSDT", "action": "EXIT", "direction": 1,
                "quantity": "1", "gross_pnl": "10.0", "strategy": "trend",
                "order_id": "X", "exit_timestamp": _TS}], strategy_family="trend")
    assert s.canonical_records[0].strategy_family == "trend"


def test_mismatched_ledger_family_raises():
    with pytest.raises(LiveTradeHistoryAdapterError):
        _rows([{"symbol": "BTCUSDT", "action": "EXIT", "direction": 1,
                "quantity": "1", "gross_pnl": "10.0", "strategy_family": "vp",
                "order_id": "X", "exit_timestamp": _TS}], strategy_family="trend")


def test_mismatched_close_event_family_raises():
    with pytest.raises(LiveTradeHistoryAdapterError):
        _events([{"symbol": "BTCUSDT", "direction": 1, "quantity": "1",
                  "entry_price": "100", "exit_price": "110", "strategy": "bb",
                  "order_id": "X", "exit_timestamp": _TS}], strategy_family="trend")


def test_every_canonical_record_family_equals_snapshot_family():
    s = _events([
        {"symbol": "BTCUSDT", "direction": 1, "quantity": "1", "entry_price": "100",
         "exit_price": "110", "order_id": "A", "exit_timestamp": "2026-01-01T00:00:00+00:00"},
        {"symbol": "ETHUSDT", "direction": -1, "quantity": "1", "entry_price": "50",
         "exit_price": "45", "strategy_family": "trend", "order_id": "B",
         "exit_timestamp": "2026-01-02T00:00:00+00:00"},
    ], strategy_family="trend")
    assert all(r.strategy_family == "trend" for r in s.canonical_records)
    assert s.strategy_family == "trend"


def test_blank_family_argument_raises():
    with pytest.raises(LiveTradeHistoryAdapterError):
        _rows([{"symbol": "BTCUSDT", "action": "EXIT", "gross_pnl": "1.0",
                "exit_timestamp": _TS}], strategy_family="   ")


# ── C. invalid explicit gross declarations ──────────────────────────────────
@pytest.mark.parametrize("bad", ["invalid", None, "", float("nan"), float("inf")])
def test_invalid_explicit_gross_downgrades_and_not_eligible(bad):
    s = _rows([{"symbol": "BTCUSDT", "action": "EXIT", "direction": 1,
                "quantity": "1", "gross_pnl": bad, "order_id": "BAD",
                "exit_timestamp": _TS}],
              completeness=LiveSourceCompleteness.ATTESTED_COMPLETE)
    assert s.kelly_eligible_count == 0
    assert s.completeness_status is CompletenessStatus.PARTIAL
    assert any("gross_pnl" in w for w in s.warnings)


def test_valid_decimal_gross_remains_eligible():
    s = _rows([{"symbol": "BTCUSDT", "action": "EXIT", "direction": 1,
                "quantity": "1", "gross_pnl": Decimal("12.50"), "order_id": "OK",
                "exit_timestamp": _TS}])
    assert s.kelly_eligible_count == 1
    assert s.selected_kelly_pnls == (Decimal("12.50"),)
    assert s.completeness_status is CompletenessStatus.COMPLETE


def test_declared_gross_basis_with_invalid_pnl_is_partial_problem():
    s = _rows([{"symbol": "BTCUSDT", "action": "EXIT", "direction": 1,
                "quantity": "1", "pnl_basis": "GROSS", "pnl": "oops",
                "order_id": "G", "exit_timestamp": _TS}],
              completeness=LiveSourceCompleteness.ATTESTED_COMPLETE)
    assert s.kelly_eligible_count == 0
    assert s.completeness_status is CompletenessStatus.PARTIAL


# ── D. epoch sub-second precision ───────────────────────────────────────────
def test_epoch_ms_preserves_millisecond_fraction():
    s = _events([{"symbol": "BTCUSDT", "direction": 1, "quantity": "1",
                  "entry_price": "100", "exit_price": "110", "order_id": "E",
                  "exit_timestamp": {"epoch_ms": 1767225600123}}])
    assert s.canonical_records[0].exit_timestamp == "2026-01-01T00:00:00.123000+00:00"


def test_epoch_s_preserves_fraction():
    s = _events([{"symbol": "BTCUSDT", "direction": 1, "quantity": "1",
                  "entry_price": "100", "exit_price": "110", "order_id": "E",
                  "exit_timestamp": {"epoch_s": "1767225600.5"}}])
    assert s.canonical_records[0].exit_timestamp == "2026-01-01T00:00:00.500000+00:00"


def test_millisecond_difference_changes_identity_and_fingerprint():
    def mk(ms):
        return _events([{"symbol": "BTCUSDT", "direction": 1, "quantity": "1",
                         "entry_price": "100", "exit_price": "110", "order_id": "",
                         "exit_timestamp": {"epoch_ms": ms}}])
    a = mk(1767225600000)
    b = mk(1767225600001)
    assert a.canonical_records[0].exit_timestamp != b.canonical_records[0].exit_timestamp
    # no order_id -> natural identity includes exit_timestamp
    assert a.kelly_input_fingerprint != b.kelly_input_fingerprint
    assert a.history_data_fingerprint != b.history_data_fingerprint


def test_bare_numeric_timestamp_still_refused():
    s = _events([{"symbol": "BTCUSDT", "direction": 1, "quantity": "1",
                  "entry_price": "100", "exit_price": "110", "order_id": "B",
                  "exit_timestamp": 1767225600123}])
    assert s.kelly_eligible_count == 0
    assert any("exit timestamp" in w for w in s.warnings)


# ── E. same-process close arithmetic validation ─────────────────────────────
@pytest.mark.parametrize("bad_field,value", [
    ("quantity", "0"), ("quantity", "-1"), ("quantity", float("inf")),
    ("entry_price", "0"), ("entry_price", "-5"),
    ("exit_price", "0"), ("exit_price", "-5"), ("exit_price", float("nan")),
])
def test_invalid_close_arithmetic_not_eligible_and_partial(bad_field, value):
    ev = {"symbol": "BTCUSDT", "direction": 1, "quantity": "1",
          "entry_price": "100", "exit_price": "110", "order_id": "BAD",
          "exit_timestamp": _TS}
    ev[bad_field] = value
    s = _events([ev], completeness=LiveSourceCompleteness.ATTESTED_COMPLETE)
    assert s.kelly_eligible_count == 0
    assert s.completeness_status is CompletenessStatus.PARTIAL
    assert any("invalid close arithmetic" in w for w in s.warnings)


def test_valid_decimal_close_computes_exact_gross():
    s = _events([{"symbol": "BTCUSDT", "direction": -1, "quantity": Decimal("2.5"),
                  "entry_price": Decimal("100.25"), "exit_price": Decimal("90.05"),
                  "order_id": "OK", "exit_timestamp": _TS}])
    # (90.05 - 100.25) * 2.5 * -1 = 25.50
    assert s.selected_kelly_pnls == (Decimal("25.500"),)
