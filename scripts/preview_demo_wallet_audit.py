"""
scripts/preview_demo_wallet_audit.py
TASK-014I: Bybit Demo wallet / margin availability field audit.

Default mode (fixture): zero network calls, zero secrets loaded.
  python scripts/preview_demo_wallet_audit.py [--write-report]

Real read-only mode:
  python scripts/preview_demo_wallet_audit.py --real-readonly --write-report

Purpose:
  Determine whether available_balance_usd = 0.00 is a genuine account state
  or a field-mapping error.  Reads the raw Bybit wallet-balance response,
  evaluates all candidate available-balance fields, and reports which field
  the system currently uses vs. what alternatives are present.

SAFETY GUARANTEES:
  no_orders_sent = True (always)
  order_endpoint_called = False (always)
  secret_value_observed = False (always)
  new_entry_allowed = False (always)

Exit codes:
  0  Audit completed; fail_closed=False.
  1  Fail-closed: proof weak/missing, endpoint wrong, or all fields missing.
"""
from __future__ import annotations

import argparse
import json
import os
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

from src.demo_readonly_client import PROOF_STRONG, DemoReadOnlyClient
from src.demo_wallet_audit import (
    CURRENT_MAPPING_FIELD,
    FIXTURE_WALLET_RAW,
    WalletAuditResult,
    audit_wallet,
)

_SEP        = "-" * 72
_OUTPUT_DIR = ROOT / "outputs" / "demo_trading" / "wallet_audit"


# ---------------------------------------------------------------------------
# Raw wallet fetcher
# ---------------------------------------------------------------------------

def _fetch_raw_wallet(client: DemoReadOnlyClient) -> dict:
    """
    Fetch raw wallet-balance API response.
    In fixture mode returns FIXTURE_WALLET_RAW.
    In real mode calls the signed endpoint.
    """
    if not client._allow_real:
        return FIXTURE_WALLET_RAW
    # Real mode: call the wallet endpoint directly for raw response
    return client._get(
        "/v5/account/wallet-balance",
        {"accountType": "UNIFIED"},
        signed=True,
    )


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(result: WalletAuditResult, output_dir: Path) -> None:
    """Write timestamped + latest JSON and Markdown audit reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ts_safe     = result.timestamp_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")
    json_path   = output_dir / f"{ts_safe}_wallet_audit.json"
    json_latest = output_dir / "latest_wallet_audit.json"
    md_path     = output_dir / f"{ts_safe}_wallet_audit.md"
    md_latest   = output_dir / "latest_wallet_audit.md"

    data      = result.to_dict()
    json_text = json.dumps(data, indent=2, default=str)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    fs   = result.raw_wallet_field_summary
    cands = result.candidate_available_fields

    status_str = "FAIL_CLOSED" if result.fail_closed else (
        "MAPPING_SUSPECT" if result.available_balance_mapping_suspect else "OK"
    )

    md_lines = [
        "# Demo Wallet Availability Audit Report",
        "",
        f"timestamp: `{result.timestamp_utc}`  ",
        f"demo_runtime_verified: `{result.demo_runtime_verified}`  ",
        f"proof_strength: **{result.proof_strength}**  ",
        f"endpoint_family: `{result.endpoint_family}`  ",
        f"status: **{status_str}**  ",
        "",
        "## Wallet Summary",
        "",
        "| field | value |",
        "|---|---|",
        f"| equity_usd | {result.equity_usd:.2f} |",
        f"| current_available_balance_usd | {result.current_available_balance_usd:.2f} |",
        f"| current_available_balance_usd_source | {result.current_available_balance_usd_source} |",
        "",
        "## Raw Wallet Fields",
        "",
        "| field | value | missing |",
        "|---|---|---|",
        f"| account.accountType | {fs.account_type} | — |",
        f"| account.totalEquity | {fs.total_equity} | — |",
        f"| account.totalWalletBalance | {fs.total_wallet_balance} | — |",
        f"| account.totalMarginBalance | {fs.total_margin_balance} | — |",
        f"| account.totalAvailableBalance | {fs.total_available_balance} | {fs.field_missing_total_available_balance} |",
        f"| account.availableToWithdraw | {fs.account_available_to_withdraw} | {fs.field_missing_account_available_to_withdraw} |",
        f"| account.accountIMRate | {fs.account_im_rate} | — |",
        f"| account.accountMMRate | {fs.account_mm_rate} | — |",
        f"| coin.USDT.equity | {fs.coin_usdt_equity} | — |",
        f"| coin.USDT.walletBalance | {fs.coin_usdt_wallet_balance} | {fs.field_missing_coin_usdt_wallet_balance} |",
        f"| coin.USDT.free | {fs.coin_usdt_free} | {fs.field_missing_coin_usdt_free} |",
        f"| coin.USDT.locked | {fs.coin_usdt_locked} | — |",
        f"| coin.USDT.availableToWithdraw | {fs.coin_usdt_available_to_withdraw} | {fs.field_missing_coin_usdt_available_to_withdraw} |",
        f"| coin.USDT.usdValue | {fs.coin_usdt_usd_value} | — |",
        f"| coin.USDT.borrowAmount | {fs.coin_usdt_borrow_amount} | — |",
        f"| coin.USDT.accruedInterest | {fs.coin_usdt_accrued_interest} | — |",
        "",
        "## Candidate Available-Balance Fields",
        "",
        "| field | value | present |",
        "|---|---|---|",
    ]
    for c in cands:
        md_lines.append(f"| {c.field_name} | {c.value} | {c.present} |")

    md_lines += [
        "",
        "## Audit Conclusions",
        "",
        f"- chosen_available_balance_field: `{result.chosen_available_balance_field}`",
        f"- chosen_available_balance_value: `{result.chosen_available_balance_value}`",
        f"- chosen_reason: {result.chosen_reason}",
        f"- available_balance_mapping_suspect: **{result.available_balance_mapping_suspect}**",
    ]
    if result.mismatch_warning:
        md_lines.append(f"- mismatch_warning: {result.mismatch_warning}")

    md_lines += [
        "",
        f"## Recommended Next Action",
        "",
        f"> {result.recommended_next_action}",
        "",
        "## Safety Invariants",
        "",
        f"- no_orders_sent: `{result.no_orders_sent}`",
        f"- order_endpoint_called: `{result.order_endpoint_called}`",
        f"- secret_value_observed: `{result.secret_value_observed}`",
        f"- new_entry_allowed: `{result.new_entry_allowed}`",
        "",
        "> secret_value_observed is always False.",
        "> no_orders_sent is always True.",
        "> new_entry_allowed is always False in this module.",
        "",
    ]
    if result.fail_closed:
        md_lines += [
            "## Fail-Closed Details",
            "",
            f"- fail_reason: {result.fail_reason}",
            "",
        ]

    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _hdr(title: str) -> None:
    pad = max(0, 60 - len(title))
    print(f"\n{'=' * 5} {title} {'=' * pad}")


def _print_result(result: WalletAuditResult) -> None:
    fs = result.raw_wallet_field_summary

    _hdr("Runtime Verification")
    print(f"  demo_runtime_verified   : {result.demo_runtime_verified}")
    print(f"  proof_strength          : {result.proof_strength}")
    print(f"  endpoint_family         : {result.endpoint_family}")
    print(f"  account_mode            : {result.account_mode}")

    _hdr("Raw Wallet Fields")
    print(f"  accountType             : {fs.account_type}")
    print(f"  totalEquity             : {fs.total_equity}")
    print(f"  totalWalletBalance      : {fs.total_wallet_balance}")
    print(f"  totalMarginBalance      : {fs.total_margin_balance}")
    print(f"  totalAvailableBalance   : {fs.total_available_balance}"
          + (" [MISSING]" if fs.field_missing_total_available_balance else ""))
    print(f"  account.availToWithdraw : {fs.account_available_to_withdraw}"
          + (" [MISSING]" if fs.field_missing_account_available_to_withdraw else ""))
    print(f"  accountIMRate           : {fs.account_im_rate}")
    print(f"  accountMMRate           : {fs.account_mm_rate}")
    print(f"  coin.USDT.equity        : {fs.coin_usdt_equity}")
    print(f"  coin.USDT.walletBalance : {fs.coin_usdt_wallet_balance}"
          + (" [MISSING]" if fs.field_missing_coin_usdt_wallet_balance else ""))
    print(f"  coin.USDT.free          : {fs.coin_usdt_free}"
          + (" [MISSING]" if fs.field_missing_coin_usdt_free else ""))
    print(f"  coin.USDT.locked        : {fs.coin_usdt_locked}")
    print(f"  coin.USDT.availToWithdraw: {fs.coin_usdt_available_to_withdraw}"
          + (" [MISSING]" if fs.field_missing_coin_usdt_available_to_withdraw else ""))
    print(f"  coin.USDT.usdValue      : {fs.coin_usdt_usd_value}")
    print(f"  coin.USDT.borrowAmount  : {fs.coin_usdt_borrow_amount}")
    print(f"  coin.USDT.accruedInterest: {fs.coin_usdt_accrued_interest}")

    _hdr("Candidate Available-Balance Fields")
    print(f"  current_mapping_field   : {CURRENT_MAPPING_FIELD}")
    print(f"  current_value           : {result.current_available_balance_usd:.2f}")
    print()
    print(f"  {'Field':<42} {'Value':>12} Present")
    for c in result.candidate_available_fields:
        val_str = f"{c.value:.2f}" if c.value is not None else "None"
        marker = " <-- current" if c.field_name == CURRENT_MAPPING_FIELD else ""
        print(f"  {c.field_name:<42} {val_str:>12} {c.present}{marker}")

    _hdr("Audit Conclusions")
    print(f"  chosen_field            : {result.chosen_available_balance_field}")
    print(f"  chosen_value            : {result.chosen_available_balance_value:.2f}")
    print(f"  chosen_reason           : {result.chosen_reason}")
    print(f"  mapping_suspect         : {result.available_balance_mapping_suspect}")
    if result.mismatch_warning:
        print(f"  mismatch_warning        : {result.mismatch_warning}")
    print(f"  fail_closed             : {result.fail_closed}")
    if result.fail_reason:
        print(f"  fail_reason             : {result.fail_reason}")

    _hdr("Recommended Next Action")
    print(f"  {result.recommended_next_action}")

    _hdr("Safety Invariants")
    print("  DRY RUN / NO ORDERS SENT  : TRUE")
    print(f"  no_orders_sent            : {result.no_orders_sent}")
    print(f"  order_endpoint_called     : {result.order_endpoint_called}")
    print(f"  secret_value_observed     : {result.secret_value_observed}")
    print(f"  new_entry_allowed         : {result.new_entry_allowed}")


# ---------------------------------------------------------------------------
# Preview runner
# ---------------------------------------------------------------------------

def run_preview(
    use_real_network: bool = False,
    write_report:     bool = False,
    output_dir:       Path | None = None,
) -> int:
    """
    Run the wallet audit dry-run preview.

    Returns 0 if audit completed and fail_closed=False.
    Returns 1 if fail_closed=True.
    """
    _output_dir = output_dir or _OUTPUT_DIR

    print(_SEP)
    print("DRY RUN / NO ORDERS SENT / NO POSITIONS MODIFIED")
    print("TASK-014I: Demo Wallet Availability Field Audit")
    print(_SEP)

    if use_real_network:
        api_key    = os.environ.get("BYBIT_DEMO_API_KEY",    "")
        api_secret = os.environ.get("BYBIT_DEMO_API_SECRET", "")
        if not api_key or not api_secret:
            missing = []
            if not api_key:
                missing.append("BYBIT_DEMO_API_KEY")
            if not api_secret:
                missing.append("BYBIT_DEMO_API_SECRET")
            print(f"\n[ERROR] --real-readonly requires: {', '.join(missing)}")
            print("  Set env vars (e.g. source .env.demo) and retry.")
            print(_SEP)
            return 1

    client      = DemoReadOnlyClient(allow_real_network=use_real_network)
    wallet      = client.get_wallet_balance()
    proof_snap  = client.build_runtime_proof()
    raw_wallet  = _fetch_raw_wallet(client)

    ts_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    result = audit_wallet(
        raw_response=raw_wallet,
        current_available_usd=wallet.available_balance_usd,
        proof_strength=proof_snap.proof_strength,
        endpoint_family=proof_snap.endpoint_family,
        account_mode=proof_snap.account_mode,
        demo_runtime_verified=(proof_snap.proof_strength == PROOF_STRONG
                               and proof_snap.endpoint_family == "bybit_demo"),
        equity_usd=wallet.equity_usd,
        timestamp_utc=ts_utc,
    )

    _print_result(result)
    print(_SEP)

    if write_report:
        _write_report(result, _output_dir)

    return 1 if result.fail_closed else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo wallet availability field audit — read-only, no orders"
    )
    parser.add_argument(
        "--real-readonly",
        action="store_true",
        help="Use real Bybit Demo API (requires BYBIT_DEMO_API_KEY + BYBIT_DEMO_API_SECRET).",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write JSON + Markdown audit report to outputs/demo_trading/wallet_audit/.",
    )
    args = parser.parse_args()
    sys.exit(run_preview(
        use_real_network=args.real_readonly,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
