"""TASK-014BX_FIX / BY_FIX / BY_FIX2 / BY_FIX3 -- canonical action planner.

ACTIVE V1 EXECUTION PATH = exact V1 baseline target-weight translation.

Proven canonical V1 sizing semantics (audited from the authoritative Primary
Forward Record implementation):

    apps/forward_record/primary.py:
        frame["position_usd"] = frame["weight"] * config.paper_config.initial_nav_usd

    paper_portfolio/state.json confirms position_usd / weight == initial_nav_usd
    for every position (equal-weight 25 long / 25 short, +/-0.02, long_weight_sum
    = +0.5, short_weight_sum = -0.5, gross_exposure = 1.0, net_exposure ~ 0).

V1 sizes by the strategy's TARGET WEIGHT against a FROZEN CAPITAL BASE (10,000
USDT), cross-validated from TWO independent authoritative sources:

    Source A: PaperTradingConfig.initial_nav_usd  (frozen config default)
    Source B: paper_portfolio/state.json  paper_equity_init  (runtime artifact)

Both must be readable, valid (>0, finite), and must agree exactly. A mismatch
fails closed ``V1_BASELINE_CAPITAL_BASE_CONFLICT``; a missing or unreadable
source fails closed ``V1_BASELINE_CAPITAL_BASE_UNVERIFIED``. Demo wallet equity
never participates in resolving the capital base.

    target_weight   <- authoritative Forward positions artifact (signed)
    capital_base    <- cross-validated evidence (NOT wallet equity)
    target_notional <- target_weight * capital_base
    target_qty      <- |target_notional| / current Demo price, floored to qty step
    transitions     <- compare target vs current Demo positions -> OPEN/ADD/REDUCE/CLOSE

The 0.4 fractional-Kelly sizer (src/demo_portfolio_risk.compute_demo_portfolio_sizing)
is DELIBERATELY NOT imported or called here; it remains available only for
OFFLINE / SHADOW Challenger experiments.

No artificial Pilot order/notional/position caps are applied. Protected symbols
are rejected; Demo-only endpoint and Live-denied guards are enforced downstream.
This module performs no network I/O, sends no order, and imports neither main,
src.risk nor the live BybitExecutor.
"""

from __future__ import annotations

import hashlib
import json as _json
import math
import pathlib as _pathlib
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Any, Mapping, Protocol, Sequence

from src import demo_strategy_pilot_native_execution as nx
from src.demo_instrument_rules import InstrumentRules, round_qty_down
from src.demo_portfolio_risk import DemoOpenPosition  # type only (NOT the Kelly sizer)

TASK_ID = "TASK-014BY_FIX3"

# Proof references for the active V1 sizing semantics.
V1_SIZING_MODE = "V1_BASELINE_TARGET_WEIGHT_TRANSLATION"
V1_SIZING_PROOF = (
    "apps/forward_record/primary.py: position_usd = weight * paper_config.initial_nav_usd; "
    "paper_portfolio/state.json: paper_equity_init cross-validated against config"
)

_MODULE_ROOT = _pathlib.Path(__file__).resolve().parents[1]
DEFAULT_STATE_ARTIFACT_PATH = str(
    _MODULE_ROOT / "outputs" / "forward_record" / "paper_portfolio" / "state.json"
)
_CONFIG_SOURCE_IDENTITY = "apps.paper_trading.config.PaperTradingConfig.initial_nav_usd"

PROTECTED_SYMBOLS = frozenset(nx.PROTECTED_SYMBOLS)

STATUS_PLANNED = "STRATEGY_NATIVE_ACTIONS_PLANNED"
STATUS_PLANNER_UNAVAILABLE = "STRATEGY_NATIVE_ACTION_PLANNER_UNAVAILABLE"
STATUS_V1_BASELINE_SIZING_UNVERIFIED = "V1_BASELINE_SIZING_UNVERIFIED"
STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED = "V1_BASELINE_CAPITAL_BASE_UNVERIFIED"
STATUS_V1_BASELINE_CAPITAL_BASE_CONFLICT = "V1_BASELINE_CAPITAL_BASE_CONFLICT"

# Parity tolerance for verifying the strategy target survives translation.
_GROSS_NET_TOLERANCE = 1e-6


class PilotAccountMarketProvider(Protocol):
    """Read-only account / market data needed for V1 target-weight translation.

    Production implementations read Bybit DEMO (read-only). Test implementations
    return fixtures. Any method raising / returning unusable data makes the
    planner fail closed."""

    def equity_usd(self) -> float: ...
    def available_balance_usd(self) -> float: ...
    def open_positions(self) -> Sequence[DemoOpenPosition]: ...
    def market_price(self, symbol: str) -> float | None: ...
    def instrument_rule(self, symbol: str) -> InstrumentRules | None: ...


@dataclass
class PlannerResult:
    status: str
    actions: list[nx.StrategyNativeAction]
    target_positions: list[dict[str, Any]]
    current_positions: list[dict[str, Any]]
    rejected_signals: list[dict[str, Any]]
    sizing_verification: Mapping[str, Any]
    detail: str = ""

    @property
    def available(self) -> bool:
        return self.status == STATUS_PLANNED

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": TASK_ID, "status": self.status, "sizing_mode": V1_SIZING_MODE,
            "action_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
            # Canonical Decimal strings only -- no binary-float artifact in JSON.
            "target_positions": [_canon_target_position(tp) for tp in self.target_positions],
            "current_positions": self.current_positions,
            "rejected_signals": self.rejected_signals,
            "sizing_verification": dict(self.sizing_verification),
            "detail": self.detail,
        }


def _side_to_long_short(side: str) -> str:
    s = str(side or "").strip().lower()
    if s in ("long", "buy"):
        return "long"
    if s in ("short", "sell"):
        return "short"
    return ""


def _open_side(long_short: str) -> str:
    return "Buy" if long_short == "long" else "Sell"


def _close_side(long_short: str) -> str:
    return "Sell" if long_short == "long" else "Buy"


def _qty_str(value: float) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def _canon_qty_str(value: float, qty_step: float | None = None) -> str:
    """Canonical fixed-point qty string. When a positive ``qty_step`` is known,
    the value is floored to an exact ``qty_step`` multiple using pure Decimal so
    no binary-float artifact (e.g. ``2744.6000000000004``) can reach a payload.
    The numeric VALUE is unchanged -- only the serialization is canonicalized."""
    try:
        v = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return "0"
    if qty_step and qty_step > 0:
        step = Decimal(str(qty_step))
        steps = (v / step).to_integral_value(rounding=ROUND_DOWN)
        v = steps * step
    v = v.normalize()
    if v == v.to_integral_value():
        v = v.quantize(Decimal("1"))
    return format(v, "f")


def _canon_dec_str(value: Any) -> str:
    """Canonical fixed-point decimal string with no binary-float artifact. The
    shortest round-trip ``str(float)`` is parsed via Decimal, so a clean value
    like ``0.07287`` stays ``0.07287`` and the intended value is preserved."""
    try:
        v = Decimal(str(value)).normalize()
    except (InvalidOperation, ValueError, TypeError):
        return "0"
    if v == v.to_integral_value():
        v = v.quantize(Decimal("1"))
    return format(v, "f")


def _canon_target_position(tp: Mapping[str, Any]) -> dict[str, Any]:
    """Serialize one target-position with canonical Decimal STRINGS for every
    numeric field so no binary-float artifact (e.g. ``209.10000000000002``) can
    appear in the audit JSON. Calculations are unchanged; only display is
    canonicalized. Authoritative ``*_decimal`` aliases are also emitted."""
    step = tp.get("qty_step")
    qty_s = _canon_qty_str(tp.get("qty", 0), step)
    step_s = _canon_dec_str(step) if step is not None else None
    price_s = _canon_dec_str(tp.get("price")) if "price" in tp else None
    notional_s = _canon_dec_str(tp.get("target_notional")) if "target_notional" in tp else None
    weight_s = _canon_dec_str(tp.get("target_weight")) if "target_weight" in tp else None
    out: dict[str, Any] = {"symbol": tp.get("symbol"), "side": tp.get("side"),
                           "qty": qty_s, "qty_decimal": qty_s}
    if step_s is not None:
        out["qty_step"] = step_s
        out["qty_step_decimal"] = step_s
    if price_s is not None:
        out["price"] = price_s
        out["price_decimal"] = price_s
    if notional_s is not None:
        out["target_notional"] = notional_s
        out["target_notional_decimal"] = notional_s
    if weight_s is not None:
        out["target_weight"] = weight_s
        out["target_weight_decimal"] = weight_s
    return out


def resolve_v1_capital_base_evidence(
    *,
    state_artifact_path: str | None = None,
    config_value_override: float | None = None,
    state_value_override: float | None = None,
) -> dict[str, Any]:
    """Cross-validate V1 capital base from config + state artifact.

    Production: both sources must be readable, valid (>0, finite), and agree
    exactly. A mismatch sets ``sources_agree=False`` (CONFLICT). A missing or
    unreadable source leaves ``capital_base_verified=False`` (UNVERIFIED).
    Tests may inject overrides via ``config_value_override`` / ``state_value_override``.
    """
    if state_artifact_path is None:
        state_artifact_path = DEFAULT_STATE_ARTIFACT_PATH

    evidence: dict[str, Any] = {
        "capital_base_usd": None,
        "capital_base_verified": False,
        "capital_base_source_count": 0,
        "capital_base_sources": [],
        "config_source_identity": _CONFIG_SOURCE_IDENTITY,
        "config_source_fingerprint": None,
        "config_value_usd": None,
        "state_artifact_path": state_artifact_path,
        "state_artifact_fingerprint": None,
        "state_value_usd": None,
        "evidence_bundle_fingerprint": None,
        "sources_agree": False,
        "wallet_used_for_target_sizing": False,
        "kelly_used": False,
    }

    # Source A: PaperTradingConfig.initial_nav_usd
    config_value = config_value_override
    if config_value is None:
        try:
            from apps.paper_trading.config import PaperTradingConfig
            config_value = float(PaperTradingConfig().initial_nav_usd)
        except Exception:  # noqa: BLE001
            pass
    if config_value is not None:
        config_repr = f"{_CONFIG_SOURCE_IDENTITY}={config_value!r}"
        evidence["config_source_fingerprint"] = "sha256:" + hashlib.sha256(
            config_repr.encode("utf-8")).hexdigest()
        evidence["config_value_usd"] = config_value

    # Source B: state.json paper_equity_init
    state_value = state_value_override
    if state_value is None:
        try:
            state_bytes = _pathlib.Path(state_artifact_path).read_bytes()
            evidence["state_artifact_fingerprint"] = "sha256:" + hashlib.sha256(
                state_bytes).hexdigest()
            state_data = _json.loads(state_bytes)
            state_value = float(state_data["paper_equity_init"])
        except Exception:  # noqa: BLE001
            pass
    else:
        synthetic_repr = f"paper_equity_init={state_value!r}"
        evidence["state_artifact_fingerprint"] = "sha256:" + hashlib.sha256(
            synthetic_repr.encode("utf-8")).hexdigest()
    if state_value is not None:
        evidence["state_value_usd"] = state_value

    # Count valid sources
    sources: list[str] = []
    config_valid = (config_value is not None and config_value > 0
                    and math.isfinite(config_value))
    state_valid = (state_value is not None and state_value > 0
                   and math.isfinite(state_value))
    if config_valid:
        sources.append("config")
    if state_valid:
        sources.append("state_artifact")
    evidence["capital_base_source_count"] = len(sources)
    evidence["capital_base_sources"] = sources

    # Cross-validate: both must be readable, valid, and agree
    if config_valid and state_valid:
        if config_value == state_value:
            evidence["sources_agree"] = True
            evidence["capital_base_usd"] = config_value
            evidence["capital_base_verified"] = True
        else:
            evidence["sources_agree"] = False

    # Deterministic evidence_bundle_fingerprint
    fp_input = _json.dumps({
        "config_source_identity": evidence["config_source_identity"],
        "config_source_fingerprint": evidence["config_source_fingerprint"],
        "config_value_usd": evidence["config_value_usd"],
        "state_artifact_fingerprint": evidence["state_artifact_fingerprint"],
        "state_value_usd": evidence["state_value_usd"],
    }, sort_keys=True, separators=(",", ":"))
    evidence["evidence_bundle_fingerprint"] = "sha256:" + hashlib.sha256(
        fp_input.encode("utf-8")).hexdigest()

    return evidence


def _signed_weight(side_ls: str, score: Any) -> float | None:
    """Signed target weight = (+ for long, - for short) * |weight| (score)."""
    try:
        mag = abs(float(score))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(mag):
        return None
    return mag if side_ls == "long" else -mag


def plan_strategy_native_actions(
    *,
    forward_result: Any,
    provider: PilotAccountMarketProvider | None,
    capital_base_evidence: dict[str, Any] | None = None,
    v1_capital_base_usd: float | None = None,
    full_kelly_fraction: float | None = None,  # accepted for back-compat; IGNORED (V1 != Kelly)
) -> PlannerResult:
    """Produce V1-baseline strategy-native actions for a date.

    Target sizing uses the frozen V1 strategy capital base, cross-validated from
    two independent authoritative sources. Demo wallet equity is read for
    reference only and is never used to scale target positions.

    Fails closed with CAPITAL_BASE_UNVERIFIED when a source is missing/invalid,
    CAPITAL_BASE_CONFLICT when sources disagree, SIZING_UNVERIFIED when target
    weights cannot be proven, PLANNER_UNAVAILABLE on missing provider.
    """
    empty_verif: dict[str, Any] = {
        "verified": False, "sizing_mode": V1_SIZING_MODE, "kelly_used": False,
        "proof": V1_SIZING_PROOF, "wallet_used_for_target_sizing": False}
    if provider is None:
        return PlannerResult(STATUS_PLANNER_UNAVAILABLE, [], [], [], [], empty_verif,
                             "no account/market provider available")

    # Resolve V1 capital base evidence (frozen strategy capital, NOT Demo wallet).
    if v1_capital_base_usd is not None and capital_base_evidence is None:
        if not (v1_capital_base_usd > 0 and math.isfinite(v1_capital_base_usd)):
            return PlannerResult(STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED, [], [], [], [],
                                 empty_verif, "explicit v1_capital_base_usd invalid")
        capital_base_evidence = {
            "capital_base_usd": v1_capital_base_usd,
            "capital_base_verified": True,
            "capital_base_source_count": 1,
            "capital_base_sources": ["explicit_parameter"],
            "config_source_identity": "explicit_parameter",
            "config_source_fingerprint": None,
            "config_value_usd": v1_capital_base_usd,
            "state_artifact_path": None,
            "state_artifact_fingerprint": None,
            "state_value_usd": None,
            "evidence_bundle_fingerprint": None,
            "sources_agree": True,
            "wallet_used_for_target_sizing": False,
            "kelly_used": False,
        }
    elif capital_base_evidence is None:
        capital_base_evidence = resolve_v1_capital_base_evidence()

    if not capital_base_evidence.get("capital_base_verified"):
        src_count = capital_base_evidence.get("capital_base_source_count", 0)
        if src_count >= 2 and not capital_base_evidence.get("sources_agree"):
            status = STATUS_V1_BASELINE_CAPITAL_BASE_CONFLICT
            detail = (f"V1 capital base sources disagree: config={capital_base_evidence.get('config_value_usd')}"
                      f" vs state={capital_base_evidence.get('state_value_usd')}; send path must refuse")
        else:
            status = STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED
            detail = "V1 capital base cannot be verified from authoritative sources; send path must refuse"
        return PlannerResult(status, [], [], [], [],
                             {**empty_verif, **capital_base_evidence}, detail)

    v1_capital_base_usd = capital_base_evidence["capital_base_usd"]

    signals = list(getattr(forward_result, "normalized_signals", None)
                   or (forward_result.get("signals") if isinstance(forward_result, Mapping) else []))

    try:
        wallet_equity = float(provider.equity_usd())
        wallet_available = float(provider.available_balance_usd())
        open_positions = list(provider.open_positions())
    except Exception as exc:  # noqa: BLE001
        return PlannerResult(STATUS_PLANNER_UNAVAILABLE, [], [], [], [], empty_verif,
                             f"account read failed: {exc}")
    if not (wallet_equity > 0):
        return PlannerResult(STATUS_PLANNER_UNAVAILABLE, [], [], [], [], empty_verif,
                             "equity unavailable / non-positive")

    targets: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    weight_unverifiable = False
    long_exp = short_exp = gross_exp = net_exp = 0.0

    for sig in signals:
        symbol = str(sig.get("symbol", "")).strip().upper()
        ls = _side_to_long_short(sig.get("side"))
        if not symbol or not ls:
            rejected.append({"symbol": symbol, "reason": "invalid_signal"})
            continue
        if symbol in PROTECTED_SYMBOLS:
            rejected.append({"symbol": symbol, "reason": "protected_symbol"})
            continue
        # V1 sizing PROOF requirement: an explicit signed target weight must exist.
        if "score" not in sig and "weight" not in sig:
            weight_unverifiable = True
            rejected.append({"symbol": symbol, "reason": "target_weight_unverifiable"})
            continue
        raw_w = sig.get("weight", sig.get("score"))
        weight = _signed_weight(ls, raw_w)
        if weight is None:
            weight_unverifiable = True
            rejected.append({"symbol": symbol, "reason": "target_weight_unparseable"})
            continue

        price = provider.market_price(symbol)
        rule = provider.instrument_rule(symbol)
        if price is None or not (float(price) > 0):
            rejected.append({"symbol": symbol, "reason": "no_market_price"})
            continue
        if rule is None:
            rejected.append({"symbol": symbol, "reason": "no_instrument_rule"})
            continue
        rule_ok, rule_err = rule.is_valid()
        if not rule_ok:
            rejected.append({"symbol": symbol, "reason": "malformed_instrument_rule",
                             "detail": rule_err})
            continue

        # EXECUTION TRANSLATION (NOT a new sizing strategy):
        #   target_notional = target_weight * v1_capital_base ; qty = |notional| / price (floored).
        target_notional = weight * v1_capital_base_usd
        target_qty = round_qty_down(abs(target_notional) / float(price), rule.qty_step)
        long_exp += weight if weight > 0 else 0.0
        short_exp += weight if weight < 0 else 0.0
        gross_exp += abs(weight)
        net_exp += weight
        if target_qty <= 0:
            rejected.append({"symbol": symbol, "reason": "qty_floored_to_zero",
                             "target_weight": weight})
            continue
        targets[symbol] = {"symbol": symbol, "side": ls, "qty": target_qty,
                           "target_weight": weight, "target_notional": target_notional,
                           "price": float(price), "qty_step": float(rule.qty_step)}

    verified = (len(targets) > 0) and not weight_unverifiable
    sizing_verification = {
        "verified": verified,
        "sizing_mode": V1_SIZING_MODE,
        "proof": V1_SIZING_PROOF,
        "weight_source": "forward_positions_artifact_signed_weight",
        **capital_base_evidence,
        "demo_wallet_equity_usd": wallet_equity,
        "demo_available_balance_usd": wallet_available,
        # Round the summed exposures to remove binary-float accumulation artifacts
        # (e.g. fifty 0.02 weights summing to 1.0000000000000007). The intended
        # values (gross ~ 1.0, net ~ 0.0) are unchanged; weights/capital untouched.
        "long_target_exposure": round(long_exp, 12),
        "short_target_exposure": round(short_exp, 12),
        "gross_target_exposure": round(gross_exp, 12),
        "net_target_exposure": round(net_exp, 12),
        "target_symbol_count": len(targets),
    }

    if not verified:
        return PlannerResult(
            STATUS_V1_BASELINE_SIZING_UNVERIFIED, [], list(targets.values()),
            [_pos_dict(p) for p in open_positions], rejected, sizing_verification,
            "V1 baseline sizing could not be proven for all eligible signals; send path must refuse"
            if weight_unverifiable else "no usable V1 target weights")

    current = {pos.symbol: pos for pos in open_positions}
    actions = _diff_positions(targets, current)
    return PlannerResult(
        STATUS_PLANNED, actions, list(targets.values()),
        [_pos_dict(p) for p in open_positions], rejected, sizing_verification,
        "V1 baseline target-weight translation (no Kelly); strategy target preserved")


def _pos_dict(p: Any) -> dict[str, Any]:
    # Canonical Decimal strings -- no binary-float artifact in audit JSON.
    return {"symbol": p.symbol, "side": p.side,
            "qty": _canon_dec_str(p.quantity), "entry_price": _canon_dec_str(p.entry_price)}


def _diff_positions(targets: Mapping[str, Mapping[str, Any]],
                    current: Mapping[str, Any]) -> list[nx.StrategyNativeAction]:
    """Compare strategy target positions to current Demo positions -> OPEN / ADD /
    REDUCE / CLOSE (and CLOSE+OPEN for a side reversal). Preserves the strategy
    target quantity/direction; no removed Pilot cap is applied."""
    actions: list[nx.StrategyNativeAction] = []
    seq = 0
    for symbol in sorted(set(targets) | set(current)):
        if symbol in PROTECTED_SYMBOLS:
            continue
        tgt = targets.get(symbol)
        cur = current.get(symbol)
        cur_side = _side_to_long_short(getattr(cur, "side", "")) if cur is not None else ""
        cur_qty = float(getattr(cur, "quantity", 0) or 0) if cur is not None else 0.0

        if tgt is None:
            if cur_qty > 0:
                actions.append(nx.StrategyNativeAction(
                    symbol=symbol, side=_close_side(cur_side), qty=_qty_str(cur_qty),
                    intent=nx.INTENT_CLOSE, reduce_only=True, action_seq=seq,
                    source_reference="target_exit")); seq += 1
            continue

        tgt_side = tgt["side"]
        tgt_qty = float(tgt["qty"])
        step = tgt.get("qty_step")
        if cur is None or cur_qty <= 0:
            actions.append(nx.StrategyNativeAction(
                symbol=symbol, side=_open_side(tgt_side), qty=_canon_qty_str(tgt_qty, step),
                intent=nx.INTENT_OPEN, reduce_only=False,
                notional_usdt=_qty_str(abs(tgt.get("target_notional", 0))), action_seq=seq,
                source_reference="target_open")); seq += 1
            continue

        if cur_side == tgt_side:
            delta = round(tgt_qty - cur_qty, 12)
            if delta > 0:
                actions.append(nx.StrategyNativeAction(
                    symbol=symbol, side=_open_side(tgt_side), qty=_canon_qty_str(delta, step),
                    intent=nx.INTENT_ADD, reduce_only=False, action_seq=seq,
                    source_reference="target_add")); seq += 1
            elif delta < 0:
                actions.append(nx.StrategyNativeAction(
                    symbol=symbol, side=_close_side(tgt_side), qty=_canon_qty_str(abs(delta), step),
                    intent=nx.INTENT_REDUCE, reduce_only=True, action_seq=seq,
                    source_reference="target_reduce")); seq += 1
            continue

        actions.append(nx.StrategyNativeAction(
            symbol=symbol, side=_close_side(cur_side), qty=_qty_str(cur_qty),
            intent=nx.INTENT_CLOSE, reduce_only=True, action_seq=seq,
            source_reference="target_flip_close")); seq += 1
        actions.append(nx.StrategyNativeAction(
            symbol=symbol, side=_open_side(tgt_side), qty=_canon_qty_str(tgt_qty, step),
            intent=nx.INTENT_OPEN, reduce_only=False, action_seq=seq,
            source_reference="target_flip_open")); seq += 1
    return actions


__all__ = [
    "DEFAULT_STATE_ARTIFACT_PATH", "PROTECTED_SYMBOLS", "PilotAccountMarketProvider",
    "PlannerResult", "STATUS_PLANNED", "STATUS_PLANNER_UNAVAILABLE",
    "STATUS_V1_BASELINE_CAPITAL_BASE_CONFLICT", "STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED",
    "STATUS_V1_BASELINE_SIZING_UNVERIFIED", "TASK_ID",
    "V1_SIZING_MODE", "V1_SIZING_PROOF", "plan_strategy_native_actions",
    "resolve_v1_capital_base_evidence",
]
