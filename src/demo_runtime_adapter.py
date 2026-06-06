"""
src/demo_runtime_adapter.py
TASK-014C: Adapter converting Bybit Demo read-only snapshots to Phase 2 planner inputs.

Converts:
  WalletSnapshot          → (equity_usd, available_balance_usd)
  list[PositionSnapshot]  → list[DemoOpenPosition]  (src.demo_portfolio_risk)
  dict[str, InstrumentSnapshot] → dict[str, InstrumentRules]  (src.demo_instrument_rules)
  RuntimeProofSnapshot    → DemoRuntimeProof | None  (src.demo_runtime_probe)

FAIL-CLOSED RULES:
  - Any position with stop_price=None → stop_price=0.0 in DemoOpenPosition AND
    fail_closed=True (Phase 2 also treats stop_price<=0 as fail-closed).
  - live_endpoint_fallback_detected=True → fail_closed=True.
  - RuntimeProofSnapshot with unknown/invalid endpoint_family → proof=None →
    fail_closed=True.

No network calls, no order calls, no secrets.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import DemoOpenPosition
from src.demo_readonly_client import (
    PROOF_MISSING,
    PROOF_WEAK,
    InstrumentSnapshot,
    PositionSnapshot,
    RuntimeProofSnapshot,
    WalletSnapshot,
)
from src.demo_runtime_probe import DEMO_ENDPOINT_FAMILIES, DemoRuntimeProof


# ---------------------------------------------------------------------------
# Adapter output
# ---------------------------------------------------------------------------

@dataclass
class AdaptedPlannerInput:
    """
    All data needed to run the Phase 2 portfolio sizer, derived from read-only snapshots.
    If fail_closed is True no sizing proposals should be generated.
    """
    equity_usd:                   float
    available_balance_usd:        float
    open_positions:               list[DemoOpenPosition]
    positions_with_missing_stop:  list[str]       # symbols whose stop_price was None
    instrument_rules:             dict[str, InstrumentRules]
    missing_instrument_symbols:   list[str]
    runtime_proof:                DemoRuntimeProof | None
    fail_closed:                  bool
    fail_reasons:                 list[str]


# ---------------------------------------------------------------------------
# Individual adapters
# ---------------------------------------------------------------------------

def adapt_wallet(wallet: WalletSnapshot) -> tuple[float, float]:
    """Return (equity_usd, available_balance_usd)."""
    return wallet.equity_usd, wallet.available_balance_usd


def adapt_positions(
    snapshots: list[PositionSnapshot],
) -> tuple[list[DemoOpenPosition], list[str]]:
    """
    Convert PositionSnapshot list to DemoOpenPosition list.

    Positions with stop_price=None are included with stop_price=0.0 so that
    Phase 2's compute_existing_stop_risk treats their full notional as risk
    (fail-closed). They are also recorded in missing_stop_symbols.

    Returns (positions, missing_stop_symbols).
    """
    positions: list[DemoOpenPosition] = []
    missing:   list[str]              = []

    for snap in snapshots:
        if snap.stop_price is None:
            missing.append(snap.symbol)
            stop = 0.0   # Phase 2 treats stop_price <= 0 as fail-closed
        else:
            stop = snap.stop_price

        positions.append(DemoOpenPosition(
            symbol=snap.symbol,
            side=snap.side,
            quantity=snap.quantity,
            entry_price=snap.entry_price,
            stop_price=stop,
        ))

    return positions, missing


def adapt_instruments(
    snapshots: dict[str, InstrumentSnapshot],
) -> dict[str, InstrumentRules]:
    """Convert InstrumentSnapshot dict to InstrumentRules dict."""
    return {
        sym: InstrumentRules(
            symbol=snap.symbol,
            qty_step=snap.qty_step,
            min_qty=snap.min_qty,
            max_qty=snap.max_qty,
            tick_size=snap.tick_size,
            min_notional=snap.min_notional,
            price_precision=snap.price_precision,
            qty_precision=snap.qty_precision,
        )
        for sym, snap in snapshots.items()
    }


def adapt_runtime_proof(
    snap: RuntimeProofSnapshot,
) -> DemoRuntimeProof | None:
    """
    Convert RuntimeProofSnapshot to DemoRuntimeProof.

    Returns None (fail-closed signal) when:
      - live_endpoint_fallback_detected is True
      - account_mode or endpoint_family is empty
      - endpoint_family is not in DEMO_ENDPOINT_FAMILIES (e.g. "unknown")
    """
    if snap.live_endpoint_fallback_detected:
        return None
    if snap.proof_strength in (PROOF_WEAK, PROOF_MISSING):
        return None
    if not snap.account_mode or not snap.endpoint_family:
        return None
    if snap.endpoint_family not in DEMO_ENDPOINT_FAMILIES:
        return None
    return DemoRuntimeProof(
        account_mode=snap.account_mode,
        demo_flag=snap.demo_flag,
        endpoint_family=snap.endpoint_family,
        source=snap.source,
    )


# ---------------------------------------------------------------------------
# Integrated adapter
# ---------------------------------------------------------------------------

def adapt_all(
    wallet:         WalletSnapshot,
    positions:      list[PositionSnapshot],
    instruments:    dict[str, InstrumentSnapshot],
    proof_snapshot: RuntimeProofSnapshot,
    symbols:        list[str] | None = None,
) -> AdaptedPlannerInput:
    """
    Convert all read-only snapshots into a single AdaptedPlannerInput struct.

    fail_closed is True when any of the following hold:
      - Any position has stop_price=None (stop risk unknown).
      - live_endpoint_fallback_detected=True in the proof snapshot.
      - DemoRuntimeProof cannot be constructed (unknown/invalid endpoint_family).
    """
    fail_closed  = False
    fail_reasons: list[str] = []

    # Wallet
    equity, available = adapt_wallet(wallet)

    # Positions — missing stop triggers fail-closed
    open_positions, missing_stops = adapt_positions(positions)
    if missing_stops:
        fail_closed = True
        for sym in missing_stops:
            fail_reasons.append(f"missing_stop_price: {sym}")

    # Live endpoint fallback — fail-closed
    if proof_snapshot.live_endpoint_fallback_detected:
        fail_closed = True
        fail_reasons.append("live_endpoint_fallback_detected")

    # Runtime proof
    runtime_proof = adapt_runtime_proof(proof_snapshot)
    if runtime_proof is None and not proof_snapshot.live_endpoint_fallback_detected:
        fail_closed = True
        fail_reasons.append("cannot_construct_runtime_proof")

    # Instruments
    instrument_rules = adapt_instruments(instruments)
    target_syms      = symbols or list(instruments.keys())
    missing_instr    = [s for s in target_syms if s not in instrument_rules]

    return AdaptedPlannerInput(
        equity_usd=equity,
        available_balance_usd=available,
        open_positions=open_positions,
        positions_with_missing_stop=missing_stops,
        instrument_rules=instrument_rules,
        missing_instrument_symbols=missing_instr,
        runtime_proof=runtime_proof,
        fail_closed=fail_closed,
        fail_reasons=fail_reasons,
    )
