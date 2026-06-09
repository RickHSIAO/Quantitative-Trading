"""
scripts/preview_demo_new_entry_review.py
TASK-014K: Dry-run preview of Demo new-entry candidate review.

Default mode (fixture): zero network calls, zero secrets loaded.
  python scripts/preview_demo_new_entry_review.py

Read from latest reconciliation report (uses real_readonly snapshot when
present):
  python scripts/preview_demo_new_entry_review.py --from-latest-reconciliation

Write review report:
  python scripts/preview_demo_new_entry_review.py --from-latest-reconciliation \\
      --write-report

SAFETY GUARANTEES (all modes):
  DRY RUN / NO ORDERS SENT  — no order endpoint is ever called.
  NO POSITIONS MODIFIED     — purely observational.
  secret_value_observed     — always False.
  action_type               — always PREVIEW_REVIEW_ONLY.
  No sender exists for new-entry payloads in TASK-014K.

Exit codes:
  0  At least one candidate accepted (payload_preview generated).
  1  Top-level fail_closed, OR every candidate rejected, OR reconciliation
     file missing / unverified.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.demo_instrument_rules import InstrumentRules
from src.demo_market_price_guard import (
    DEFAULT_PRICE_GUARD_THRESHOLD_PCT,
    DemoMarketPriceGuard,
    PriceGuardEvaluation,
    RealtimeMarketPrice,
    evaluate_price_guard,
)
from src.demo_new_entry_review import (
    NewEntryCandidate,
    NewEntryReviewResult,
    review_new_entry_candidates,
)
from src.demo_portfolio_risk import DemoOpenPosition
from src.demo_position_reconcile import (
    PositionDetail,
    ReconciliationResult,
    reconcile,
)

_SEP = "-" * 72
_DEFAULT_RECONCILE_DIR = ROOT / "outputs" / "demo_trading" / "reconciliation"
_DEFAULT_REVIEW_DIR    = ROOT / "outputs" / "demo_trading" / "new_entry_review"


# ---------------------------------------------------------------------------
# Fixture instrument rules — pragmatic defaults for known symbols
# ---------------------------------------------------------------------------

_FIXTURE_INSTRUMENT_RULES: dict[str, InstrumentRules] = {
    "BTCUSDT":  InstrumentRules("BTCUSDT",  0.001, 0.001, 0,  0.1,    1.0, 1, 3),
    "ETHUSDT":  InstrumentRules("ETHUSDT",  0.01,  0.01,  0,  0.05,   1.0, 2, 2),
    "BNBUSDT":  InstrumentRules("BNBUSDT",  0.01,  0.01,  0,  0.01,   1.0, 2, 2),
    "SOLUSDT":  InstrumentRules("SOLUSDT",  0.1,   0.1,   0,  0.01,   1.0, 2, 1),
    "XRPUSDT":  InstrumentRules("XRPUSDT",  1.0,   1.0,   0,  0.0001, 1.0, 4, 0),
    "ADAUSDT":  InstrumentRules("ADAUSDT",  1.0,   1.0,   0,  0.0001, 1.0, 4, 0),
    "DOTUSDT":  InstrumentRules("DOTUSDT",  0.1,   0.1,   0,  0.001,  1.0, 3, 1),
    "LINKUSDT": InstrumentRules("LINKUSDT", 0.1,   0.1,   0,  0.001,  1.0, 3, 1),
    "AAVEUSDT": InstrumentRules("AAVEUSDT", 0.01,  0.01,  0,  0.01,   1.0, 2, 2),
    "AVAXUSDT": InstrumentRules("AVAXUSDT", 0.1,   0.1,   0,  0.01,   1.0, 2, 1),
}

_PERMISSIVE_RULES = InstrumentRules(
    "PERMISSIVE", 0.0001, 0.0001, 0, 0.0001, 1.0, 4, 4,
)


def _build_rules_for(symbols: list[str]) -> dict[str, InstrumentRules]:
    """Return an InstrumentRules dict covering each requested symbol."""
    out: dict[str, InstrumentRules] = {}
    for sym in symbols:
        out[sym] = _FIXTURE_INSTRUMENT_RULES.get(sym, InstrumentRules(
            symbol=sym,
            qty_step=_PERMISSIVE_RULES.qty_step,
            min_qty=_PERMISSIVE_RULES.min_qty,
            max_qty=_PERMISSIVE_RULES.max_qty,
            tick_size=_PERMISSIVE_RULES.tick_size,
            min_notional=_PERMISSIVE_RULES.min_notional,
            price_precision=_PERMISSIVE_RULES.price_precision,
            qty_precision=_PERMISSIVE_RULES.qty_precision,
        ))
    return out


# ---------------------------------------------------------------------------
# Fixture clean-state reconciliation snapshot
# ---------------------------------------------------------------------------

def _fixture_clean_reconciliation() -> ReconciliationResult:
    """Clean fixture reconciliation: PASS state with capacity for new entries."""
    positions = [
        DemoOpenPosition("BTCUSDT", "long",  0.05, 67_000.0, 65_000.0),
        DemoOpenPosition("ETHUSDT", "short", 0.30,  3_500.0,  3_700.0),
    ]
    rules = _build_rules_for([p.symbol for p in positions])
    result = reconcile(
        equity_usd=10_000.0,
        available_balance_usd=8_500.0,
        positions=positions,
        instrument_rules=rules,
        full_kelly_fraction=0.60,
        demo_runtime_verified=True,
        proof_strength="STRONG",
        mode="fixture",
        position_details_source="real_readonly",
    )
    return result


# ---------------------------------------------------------------------------
# Fixture candidate lists
# ---------------------------------------------------------------------------

def _fixture_candidates_clean() -> list[NewEntryCandidate]:
    """Two long + one short candidate (capacity exists in clean fixture)."""
    return [
        NewEntryCandidate(
            symbol="SOLUSDT",  side="long",
            entry_reference_price=160.0,  stop_price=150.0,
            requested_risk_usd=40.0,  score=1.0,
        ),
        NewEntryCandidate(
            symbol="AAVEUSDT", side="long",
            entry_reference_price=120.0, stop_price=110.0,
            requested_risk_usd=30.0,   score=0.9,
        ),
        NewEntryCandidate(
            symbol="LINKUSDT", side="short",
            entry_reference_price=15.0,  stop_price=16.5,
            requested_risk_usd=25.0,   score=0.8,
        ),
    ]


def _fixture_candidates_full_short() -> list[NewEntryCandidate]:
    """Mix of longs + shorts — used when the reconciliation has short_count=5/5."""
    return [
        NewEntryCandidate(
            symbol="SOLUSDT",  side="long",
            entry_reference_price=160.0,  stop_price=150.0,
            requested_risk_usd=40.0,  score=1.0,
        ),
        NewEntryCandidate(
            symbol="AAVEUSDT", side="long",
            entry_reference_price=120.0, stop_price=110.0,
            requested_risk_usd=30.0,   score=0.9,
        ),
        NewEntryCandidate(
            symbol="AVAXUSDT", side="short",
            entry_reference_price=30.0,  stop_price=33.0,
            requested_risk_usd=25.0,   score=0.8,
        ),
        NewEntryCandidate(
            symbol="LINKUSDT", side="short",
            entry_reference_price=15.0,  stop_price=16.5,
            requested_risk_usd=20.0,   score=0.7,
        ),
    ]


# ---------------------------------------------------------------------------
# Reconciliation JSON loader (real mode)
# ---------------------------------------------------------------------------

def load_latest_reconciliation(reconcile_dir: Path) -> dict | None:
    """Load latest_reconciliation.json. Returns None when absent or unreadable."""
    path = reconcile_dir / "latest_reconciliation.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _positions_from_rec(rec: dict) -> list[DemoOpenPosition]:
    raw = rec.get("positions", []) or []
    out: list[DemoOpenPosition] = []
    for p in raw:
        out.append(DemoOpenPosition(
            symbol=str(p.get("symbol", "")),
            side=str(p.get("side", "")),
            quantity=float(p.get("quantity", 0.0) or 0.0),
            entry_price=float(p.get("entry_price", 0.0) or 0.0),
            stop_price=float(p.get("stop_price", 0.0) or 0.0),
        ))
    return out


def _reconciliation_from_json(rec: dict) -> ReconciliationResult:
    """
    Rebuild a ReconciliationResult by replaying reconcile() on the snapshot data.
    Falls back to permissive instrument rules for unknown symbols.
    """
    positions = _positions_from_rec(rec)
    rules     = _build_rules_for([p.symbol for p in positions])
    result = reconcile(
        equity_usd=float(rec.get("equity_usd", 0.0) or 0.0),
        available_balance_usd=float(rec.get("available_balance_usd", 0.0) or 0.0),
        positions=positions,
        instrument_rules=rules,
        full_kelly_fraction=float(rec.get("full_kelly_fraction", 0.60) or 0.60),
        demo_runtime_verified=bool(rec.get("demo_runtime_verified", False)),
        proof_strength=str(rec.get("proof_strength", "")),
        mode="real_readonly_snapshot",
        position_details_source=str(rec.get("position_details_source", "fixture")),
    )
    return result


def _candidates_for_real(rec: ReconciliationResult) -> list[NewEntryCandidate]:
    """
    Pick demo candidates that avoid existing symbols so the duplicate gate is
    not the one that rejects.  Caller still applies all per-candidate gates.
    """
    existing = {p.symbol for p in rec.positions}
    pool = [
        NewEntryCandidate("SOLUSDT",  "long",  160.0, 150.0, 40.0, score=1.0),
        NewEntryCandidate("AAVEUSDT", "long",  120.0, 110.0, 30.0, score=0.9),
        NewEntryCandidate("AVAXUSDT", "short",  30.0,  33.0, 25.0, score=0.8),
        NewEntryCandidate("LINKUSDT", "short",  15.0,  16.5, 20.0, score=0.7),
    ]
    return [c for c in pool if c.symbol not in existing][:4] or pool


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(result: NewEntryReviewResult, output_dir: Path, ts_utc: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_safe = ts_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")

    json_path   = output_dir / f"{ts_safe}_new_entry_review.json"
    json_latest = output_dir / "latest_new_entry_review.json"
    md_path     = output_dir / f"{ts_safe}_new_entry_review.md"
    md_latest   = output_dir / "latest_new_entry_review.md"

    data = result.to_dict(timestamp_utc=ts_utc)
    json_text = json.dumps(data, indent=2, default=str)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    status = (
        "FAIL_CLOSED" if result.fail_closed
        else ("ACCEPTED" if result.accepted_candidates else "ALL_REJECTED")
    )

    md_lines = [
        "# Demo New-entry Review Report",
        "",
        f"timestamp: `{ts_utc}`  ",
        f"mode: `{result.mode}`  ",
        f"position_details_source: `{result.position_details_source}`  ",
        f"demo_runtime_verified: `{result.demo_runtime_verified}`  ",
        f"proof_strength: **{result.proof_strength}**  ",
        f"endpoint_family: `{result.endpoint_family}`  ",
        f"account_mode: `{result.account_mode}`  ",
        "",
        f"## Status: {status}",
        "",
        "## Account Snapshot",
        "",
        "| metric | value |",
        "|---|---|",
        f"| equity_usd | {result.equity_usd:.2f} |",
        f"| available_balance_usd | {result.available_balance_usd:.2f} |",
        f"| available_balance_usd_source | `{result.available_balance_usd_source}` |",
        f"| portfolio_risk_budget_usd | {result.portfolio_risk_budget_usd:.2f} |",
        f"| remaining_risk_budget_usd | {result.remaining_risk_budget_usd:.2f} |",
        f"| open_positions_count | {result.open_positions_count} |",
        f"| long_count | {result.long_count} / 5 |",
        f"| short_count | {result.short_count} / 5 |",
        f"| max_long_allowed_remaining | {result.max_long_allowed_remaining} |",
        f"| max_short_allowed_remaining | {result.max_short_allowed_remaining} |",
        f"| gross_exposure_ratio | {result.gross_exposure_ratio:.4f} |",
        f"| net_exposure_ratio | {result.net_exposure_ratio:.4f} |",
        f"| new_entry_allowed_from_reconciliation | {result.new_entry_allowed_from_reconciliation} |",
        "",
    ]
    if result.fail_closed:
        md_lines += ["## Top-level Fail-closed Reasons", ""]
        for r in result.fail_closed_reasons:
            md_lines.append(f"- `{r}`")
        md_lines.append("")

    if result.evaluations:
        md_lines += ["## Candidate Evaluations", ""]
        md_lines.append("| Symbol | Side | Accepted | Reason |")
        md_lines.append("|---|---|---|---|")
        for ev in result.evaluations:
            reason = ev.reject_reason if not ev.accepted else "—"
            md_lines.append(
                f"| {ev.symbol} | {ev.side} | {ev.accepted} | `{reason}` |"
            )
        md_lines.append("")

    md_lines += [
        "## Realtime Price Guard (TASK-014O)",
        "",
        f"- realtime_price_guard_verified: `{result.realtime_price_guard_verified}`",
        f"- price_guard_threshold_pct: `{result.price_guard_threshold_pct}`",
        f"- price_guard_evaluations: `{len(result.price_guard_evaluations)}`",
        "",
    ]
    if result.price_guard_evaluations:
        md_lines.append("| Symbol | Candidate Ref | Realtime | Source | Dev % | Verified |")
        md_lines.append("|---|---|---|---|---|---|")
        for ev in result.price_guard_evaluations:
            md_lines.append(
                f"| {ev.get('symbol', '')} "
                f"| {ev.get('candidate_entry_reference_price', '')} "
                f"| {ev.get('realtime_market_price', '')} "
                f"| `{ev.get('price_source', '')}` "
                f"| {ev.get('price_deviation_pct', '')} "
                f"| {ev.get('realtime_price_guard_verified', '')} |"
            )
        md_lines.append("")

    if result.payload_previews:
        md_lines += ["## Payload Previews (PLANNING ONLY — never sent)", ""]
        for p in result.payload_previews:
            md_lines += [
                f"### {p.symbol}",
                f"- side: `{p.side}`",
                f"- order_type: `{p.order_type}`",
                f"- qty: `{p.qty}`",
                f"- reduce_only: `{p.reduce_only}` (new entry — must be False)",
                f"- entry_reference_price: `{p.entry_reference_price}`",
                f"- rounded_entry_price: `{p.rounded_entry_price}`",
                f"- realtime_market_price: `{p.realtime_market_price}`",
                f"- price_source: `{p.price_source}`",
                f"- price_deviation_pct: `{p.price_deviation_pct:.4f}`",
                f"- realtime_price_guard_verified: `{p.realtime_price_guard_verified}`",
                f"- stop_price: `{p.stop_price}`",
                f"- rounded_stop_price: `{p.rounded_stop_price}`",
                f"- estimated_notional_usd: `{p.estimated_notional_usd:.2f}`",
                f"- estimated_stop_risk_usd: `{p.estimated_stop_risk_usd:.2f}`",
                f"- projected_gross_exposure_ratio: `{p.projected_gross_exposure_ratio:.4f}`",
                f"- projected_net_exposure_ratio: `{p.projected_net_exposure_ratio:.4f}`",
                f"- preview_only: `{p.preview_only}`",
                f"- order_sent: `{p.order_sent}`",
                f"- order_endpoint_called: `{p.order_endpoint_called}`",
                f"- confirmation_required: `{p.confirmation_required}`",
                "",
            ]

    md_lines += [
        "## Safety Invariants",
        "",
        f"- action_type: `{result.action_type}`",
        f"- no_orders_sent: `{result.no_orders_sent}`",
        f"- no_position_modified: `{result.no_position_modified}`",
        f"- order_endpoint_called: `{result.order_endpoint_called}`",
        f"- secret_value_observed: `{result.secret_value_observed}`",
        "",
        f"## Next Required Task: `{result.next_required_task}`",
        "",
        "> **NOTE**: payload_preview is PLANNING ONLY.  No sender exists for",
        "> new-entry payloads in TASK-014K.  TASK-014L is required before any",
        "> new-entry payload could be sent, and that task adds another manual",
        "> confirmation gate.",
        "",
    ]

    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report written: {json_path.name}")
    print(f"  report written: {md_path.name}")
    print(f"  latest  : {json_latest}")
    print(f"  latest  : {md_latest}")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _hdr(title: str) -> None:
    pad = max(0, 60 - len(title))
    print(f"\n{'=' * 5} {title} {'=' * pad}")


def _fmt_usd(v: float) -> str:
    return f"${v:,.2f}"


def _print_result(result: NewEntryReviewResult) -> None:
    _hdr("Source")
    print(f"  mode                    : {result.mode}")
    print(f"  position_details_source : {result.position_details_source}")
    print(f"  endpoint_family         : {result.endpoint_family}")
    print(f"  account_mode            : {result.account_mode}")
    print(f"  proof_strength          : {result.proof_strength}")
    print(f"  demo_runtime_verified   : {result.demo_runtime_verified}")
    print(f"  available_balance_source: {result.available_balance_usd_source}")

    _hdr("Account Snapshot")
    print(f"  equity_usd               : {_fmt_usd(result.equity_usd)}")
    print(f"  available_balance_usd    : {_fmt_usd(result.available_balance_usd)}")
    print(f"  portfolio_risk_budget    : {_fmt_usd(result.portfolio_risk_budget_usd)}")
    print(f"  remaining_risk_budget    : {_fmt_usd(result.remaining_risk_budget_usd)}")
    print(f"  open_positions_count     : {result.open_positions_count}")
    print(f"  long_count               : {result.long_count} / 5")
    print(f"  short_count              : {result.short_count} / 5")
    print(f"  gross_exposure_ratio     : {result.gross_exposure_ratio:.4f}")
    print(f"  net_exposure_ratio       : {result.net_exposure_ratio:.4f}")

    if result.fail_closed:
        _hdr("Top-level Fail-closed")
        for r in result.fail_closed_reasons:
            print(f"  - {r}")

    _hdr("Realtime Price Guard (TASK-014O)")
    print(f"  realtime_price_guard_verified : {result.realtime_price_guard_verified}")
    print(f"  price_guard_threshold_pct     : {result.price_guard_threshold_pct}")
    if result.price_guard_evaluations:
        for ev in result.price_guard_evaluations:
            print(
                f"  {ev.get('symbol', ''):<10} "
                f"cand={ev.get('candidate_entry_reference_price', 0):<10} "
                f"real={ev.get('realtime_market_price', 0):<10} "
                f"src={ev.get('price_source', ''):<35} "
                f"dev%={ev.get('price_deviation_pct', 0):<8} "
                f"verified={ev.get('realtime_price_guard_verified', False)}"
            )

    _hdr("Candidate Evaluations")
    if not result.evaluations:
        print("  (no candidates supplied)")
    else:
        print(f"  {'Symbol':<10} {'Side':<6} {'Accepted':<10} Reason")
        for ev in result.evaluations:
            reason = ev.reject_reason if not ev.accepted else ""
            print(f"  {ev.symbol:<10} {ev.side:<6} {str(ev.accepted):<10} {reason}")

    if result.payload_previews:
        _hdr("Payload Previews (PLANNING ONLY — no orders sent)")
        for p in result.payload_previews:
            print(f"  {p.symbol}:")
            print(f"    side                       : {p.side}")
            print(f"    qty                        : {p.qty}")
            print(f"    reduce_only                : {p.reduce_only}  (new entry)")
            print(f"    preview_only               : {p.preview_only}")
            print(f"    rounded_entry/stop         : "
                  f"{p.rounded_entry_price} / {p.rounded_stop_price}")
            print(f"    notional / stop_risk USD   : "
                  f"{p.estimated_notional_usd:.2f} / {p.estimated_stop_risk_usd:.2f}")
            print(f"    projected gross / net      : "
                  f"{p.projected_gross_exposure_ratio:.4f} / "
                  f"{p.projected_net_exposure_ratio:.4f}")
            print(f"    order_sent                 : {p.order_sent}")
            print(f"    order_endpoint_called      : {p.order_endpoint_called}")

    _hdr("Safety Invariants")
    print(f"  action_type            : {result.action_type}")
    print(f"  no_orders_sent         : {result.no_orders_sent}")
    print(f"  no_position_modified   : {result.no_position_modified}")
    print(f"  order_endpoint_called  : {result.order_endpoint_called}")
    print(f"  secret_value_observed  : {result.secret_value_observed}")

    _hdr("Next Required Task")
    print(f"  {result.next_required_task}")


# ---------------------------------------------------------------------------
# Preview runner
# ---------------------------------------------------------------------------

def _build_price_guard_evaluations(
    candidates:                  list[NewEntryCandidate],
    allow_real_network:          bool,
    price_guard_threshold_pct:   float,
) -> dict[str, PriceGuardEvaluation]:
    """
    Fetch a realtime market price for every candidate symbol and evaluate the
    guard.  In fixture mode the client returns a deterministic fixture price.

    Pure helper — never calls any order endpoint.
    """
    client = DemoMarketPriceGuard(allow_real_network=allow_real_network)
    symbols = sorted({c.symbol for c in candidates})
    market_prices = client.fetch_market_prices(symbols)
    evals: dict[str, PriceGuardEvaluation] = {}
    for cand in candidates:
        evals[cand.symbol] = evaluate_price_guard(
            symbol=cand.symbol,
            candidate_entry_reference_price=cand.entry_reference_price,
            market_price=market_prices.get(cand.symbol),
            threshold_pct=price_guard_threshold_pct,
        )
    return evals


def run_preview(
    mode:           str  = "fixture",
    write_report:   bool = False,
    reconcile_dir:  Path | None = None,
    review_dir:     Path | None = None,
    with_realtime_price_guard: bool = True,
    allow_real_market_network: bool = False,
    price_guard_threshold_pct: float = DEFAULT_PRICE_GUARD_THRESHOLD_PCT,
) -> int:
    """
    Run the new-entry candidate review preview.

    Returns 0 if any candidate accepted; 1 otherwise (incl. fail_closed).
    """
    _reconcile_dir = reconcile_dir or _DEFAULT_RECONCILE_DIR
    _review_dir    = review_dir    or _DEFAULT_REVIEW_DIR

    print(_SEP)
    print("DRY RUN / NO ORDERS SENT / NO POSITIONS MODIFIED")
    print("TASK-014K / TASK-014O: Demo New-entry Review Preview")
    print(_SEP)

    if mode == "from_latest_reconciliation":
        rec_json = load_latest_reconciliation(_reconcile_dir)
        if rec_json is None:
            print("\n[FAIL CLOSED] latest_reconciliation.json not found or unreadable.")
            print(f"  Expected: {_reconcile_dir / 'latest_reconciliation.json'}")
            print("  Run:  python scripts/preview_demo_position_reconcile.py "
                  "--from-latest-readonly-smoke --write-report")
            print(_SEP)
            return 1
        if not bool(rec_json.get("demo_runtime_verified", False)):
            print("\n[FAIL CLOSED] reconciliation: demo_runtime_verified=False.")
            print(f"  proof_strength={rec_json.get('proof_strength', 'MISSING')}")
            print("  Re-run readonly smoke + reconciliation with valid credentials.")
            print(_SEP)
            return 1
        if str(rec_json.get("position_details_source", "")) != "real_readonly":
            print("\n[FAIL CLOSED] reconciliation: position_details_source != real_readonly.")
            print(f"  source={rec_json.get('position_details_source', 'MISSING')}")
            print("  New-entry review requires a real_readonly reconciliation snapshot.")
            print(_SEP)
            return 1
        if str(rec_json.get("proof_strength", "")) != "STRONG":
            print("\n[FAIL CLOSED] reconciliation: proof_strength != STRONG.")
            print(f"  proof_strength={rec_json.get('proof_strength', 'MISSING')}")
            print(_SEP)
            return 1

        recon      = _reconciliation_from_json(rec_json)
        candidates = _candidates_for_real(recon)
        avail_src  = "account.totalAvailableBalance"
        print(f"  [recon] equity_usd={recon.equity_usd:.2f}")
        print(f"  [recon] available_balance_usd={recon.available_balance_usd:.2f}")
        print(f"  [recon] short_count={recon.short_count} / 5")
        print(f"  [recon] long_count={recon.long_count} / 5")
        print(f"  [recon] positions_loaded={len(recon.positions)}")
    else:
        recon      = _fixture_clean_reconciliation()
        candidates = _fixture_candidates_clean()
        avail_src  = "fixture_clean"

    instrument_rules = _build_rules_for(
        sorted({c.symbol for c in candidates}
               | {p.symbol for p in recon.positions})
    )

    price_guard_evals: dict[str, PriceGuardEvaluation] | None = None
    if with_realtime_price_guard:
        # In real-reconciliation mode, fetch live ticker prices from the demo
        # public market endpoint; in fixture mode, use the deterministic
        # FIXTURE_MARKET_PRICES dict (no I/O).
        real_market_net = allow_real_market_network and (mode == "from_latest_reconciliation")
        price_guard_evals = _build_price_guard_evaluations(
            candidates=candidates,
            allow_real_network=real_market_net,
            price_guard_threshold_pct=price_guard_threshold_pct,
        )

    result = review_new_entry_candidates(
        reconciliation=recon,
        candidates=candidates,
        instrument_rules=instrument_rules,
        endpoint_family="bybit_demo",
        account_mode="demo",
        available_balance_usd_source=avail_src,
        price_guard_evaluations=price_guard_evals,
        price_guard_threshold_pct=price_guard_threshold_pct,
    )

    _print_result(result)
    print(_SEP)

    if write_report:
        ts_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_report(result, _review_dir, ts_utc)

    if result.fail_closed:
        return 1
    return 0 if result.accepted_candidates else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run preview of Demo new-entry candidate review"
    )
    parser.add_argument(
        "--from-latest-reconciliation",
        action="store_true",
        help=(
            "Read reconciliation snapshot from "
            "outputs/demo_trading/reconciliation/latest_reconciliation.json. "
            "Fails closed on missing/unverified/non-real_readonly/non-STRONG."
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write JSON + Markdown report to outputs/demo_trading/new_entry_review/.",
    )
    parser.add_argument(
        "--no-realtime-price-guard",
        action="store_true",
        help=(
            "Disable the TASK-014O realtime market price guard. Without this "
            "flag the guard is engaged in fixture mode (FIXTURE_MARKET_PRICES) "
            "and in real-reconciliation mode (with --allow-real-market-network)."
        ),
    )
    parser.add_argument(
        "--allow-real-market-network",
        action="store_true",
        help=(
            "Allow read-only GETs to api-demo.bybit.com/v5/market/tickers for "
            "the realtime price guard.  Only takes effect with "
            "--from-latest-reconciliation."
        ),
    )
    parser.add_argument(
        "--price-guard-threshold-pct",
        type=float,
        default=DEFAULT_PRICE_GUARD_THRESHOLD_PCT,
        help="Maximum allowed deviation (percent) between candidate entry_reference_price "
             "and the realtime market price.  Default: 5.0.",
    )
    args = parser.parse_args()
    mode = (
        "from_latest_reconciliation" if args.from_latest_reconciliation
        else "fixture"
    )
    sys.exit(run_preview(
        mode=mode,
        write_report=args.write_report,
        with_realtime_price_guard=not args.no_realtime_price_guard,
        allow_real_market_network=args.allow_real_market_network,
        price_guard_threshold_pct=args.price_guard_threshold_pct,
    ))


if __name__ == "__main__":
    main()
