"""
scripts/preview_demo_trading_stop_contract.py
TASK-014T: Demo Trading-stop Endpoint Contract Probe CLI.

Usage (PREVIEW — default, no network):
  python scripts/preview_demo_trading_stop_contract.py \\
    --from-latest-protection \\
    --symbol SOLUSDT \\
    [--write-report]

Usage (MOCK PERMISSION — still no network, synthetic envelope):
  python scripts/preview_demo_trading_stop_contract.py \\
    --from-latest-protection \\
    --symbol SOLUSDT \\
    --confirm-token CONFIRM_DEMO_TRADING_STOP_PROBE_YYYYMMDD \\
    --mock-permission \\
    [--write-report]

Usage (REAL PROBE GUARD — guarded; returns REAL_PROBE_NOT_IMPLEMENTED):
  python scripts/preview_demo_trading_stop_contract.py \\
    --from-latest-protection \\
    --symbol SOLUSDT \\
    --confirm-token CONFIRM_DEMO_TRADING_STOP_PROBE_YYYYMMDD \\
    --allow-real-stop-probe \\
    [--write-report]

Reads:
  outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json

Writes (when --write-report):
  outputs/demo_trading/trading_stop_contract/{ts}_trading_stop_contract.json
  outputs/demo_trading/trading_stop_contract/{ts}_trading_stop_contract.md
  outputs/demo_trading/trading_stop_contract/latest_trading_stop_contract.json
  outputs/demo_trading/trading_stop_contract/latest_trading_stop_contract.md

IMPORTANT:
  - There is no real trading-stop send in TASK-014T.  Even with
    --allow-real-stop-probe + a valid confirm token, the orchestrator
    returns REAL_PROBE_NOT_IMPLEMENTED.  Designing a no-op real probe
    is the subject of TASK-014U.
  - TASK-014L sender G20 (protected_entry_policy_missing) is NOT lifted.

Exit codes:
  0  result produced (preview / mock-permission / real_probe_not_implemented)
  1  protection missing / required arg missing / fail-closed contract
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

from src.demo_trading_stop_contract_probe import (
    DemoTradingStopContractProbe,
    TradingStopContractResult,
    STATUS_PREVIEW_OK,
    STATUS_MOCK_PERMISSION_OK,
    STATUS_REAL_PROBE_NOT_IMPL,
)

_SEP = "-" * 72
_DEFAULT_PROTECTION_DIR = ROOT / "outputs" / "demo_trading" / "new_entry_protection"
_DEFAULT_CONTRACT_DIR   = ROOT / "outputs" / "demo_trading" / "trading_stop_contract"


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_latest_protection(protection_dir: Path) -> dict | None:
    return _load_json(protection_dir / "latest_new_entry_protection.json")


def _print_result(r: TradingStopContractResult) -> None:
    print(f"  mode                              : {r.mode}")
    print(f"  selected_symbol                   : {r.selected_symbol}")
    print(f"  stop_loss                         : {r.stop_loss}")
    print(f"  endpoint_family                   : {r.endpoint_family}")
    print(f"  base_url                          : {r.base_url}")
    print(f"  path                              : {r.path}  (NOT invoked)")
    print(f"  method                            : {r.method}")
    print(f"  category                          : {r.category}")
    print(f"  tpsl_mode                         : {r.tpsl_mode}")
    print(f"  sl_trigger_by                     : {r.sl_trigger_by}")
    print(f"  position_idx                      : {r.position_idx}")
    print(f"  real_probe_allowed                : {r.real_probe_allowed}")
    print(f"  real_probe_implemented            : {r.real_probe_implemented}")
    print(f"  mock_permission_status            : {r.mock_permission_status}")
    print(f"  confirm_token_prefix              : {r.confirm_token_prefix or '(none)'}")
    print(f"  confirm_token_valid               : {r.confirm_token_valid}")
    print(f"  stop_endpoint_called              : {r.stop_endpoint_called}")
    print(f"  order_endpoint_called             : {r.order_endpoint_called}")
    print(f"  no_position_modified              : {r.no_position_modified}")
    print(f"  no_live_endpoint                  : {r.no_live_endpoint}")
    print(f"  no_orders_sent                    : {r.no_orders_sent}")
    print(f"  no_batch_order                    : {r.no_batch_order}")
    print(f"  no_close_only_path                : {r.no_close_only_path}")
    print(f"  emergency_close_invoked           : {r.emergency_close_invoked}")
    print(f"  secret_value_observed             : {r.secret_value_observed}")
    print(f"  status                            : {r.status}")
    if r.blocked_gates:
        print(f"  blocked_gates                     : {r.blocked_gates}")
    if r.payload_preview:
        print("  payload_preview:")
        for k, v in r.payload_preview.items():
            print(f"    {k}: {v}")
    if r.mock_response:
        print("  mock_response:")
        for k, v in r.mock_response.items():
            print(f"    {k}: {v}")


def _write_report(r: TradingStopContractResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_safe = (
        r.timestamp_utc
        .replace(":", "")
        .replace("-", "")
        .replace("T", "_")
        .replace("Z", "")
    )
    json_path   = output_dir / f"{ts_safe}_trading_stop_contract.json"
    json_latest = output_dir / "latest_trading_stop_contract.json"
    md_path     = output_dir / f"{ts_safe}_trading_stop_contract.md"
    md_latest   = output_dir / "latest_trading_stop_contract.md"

    data      = r.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    md_lines = [
        "# Demo Trading-stop Contract Probe Report (TASK-014T)",
        "",
        f"timestamp: `{r.timestamp_utc}`  ",
        f"mode: `{r.mode}`  ",
        f"status: **{r.status}**  ",
        "",
        "## Contract",
        "",
        "| field | value |",
        "|---|---|",
        f"| endpoint_family | `{r.endpoint_family}` |",
        f"| base_url | `{r.base_url}` (informational) |",
        f"| path | `{r.path}` (NOT invoked) |",
        f"| method | `{r.method}` |",
        f"| category | `{r.category}` |",
        f"| tpsl_mode | `{r.tpsl_mode}` |",
        f"| sl_trigger_by | `{r.sl_trigger_by}` |",
        f"| position_idx | `{r.position_idx}` |",
        "",
        "## Summary",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {r.selected_symbol} |",
        f"| stop_loss | {r.stop_loss} |",
        f"| real_probe_allowed | {r.real_probe_allowed} |",
        f"| real_probe_implemented | {r.real_probe_implemented} |",
        f"| mock_permission_status | {r.mock_permission_status} |",
        f"| confirm_token_valid | {r.confirm_token_valid} |",
        f"| next_required_task | {r.next_required_task} |",
        "",
    ]
    if r.blocked_gates:
        md_lines += ["## Blocked Gates", ""]
        for g in r.blocked_gates:
            md_lines.append(f"- {g}")
        md_lines.append("")
    if r.payload_preview:
        md_lines += [
            "## Payload Preview (NOT sent)",
            "",
            "```json",
            json.dumps(r.payload_preview, indent=2),
            "```",
            "",
        ]
    if r.mock_response:
        md_lines += [
            "## Mock Permission Response (synthetic, NOT from network)",
            "",
            "```json",
            json.dumps(r.mock_response, indent=2),
            "```",
            "",
        ]
    md_lines += [
        "## Safety Invariants",
        "",
        f"- stop_endpoint_called: `{r.stop_endpoint_called}`",
        f"- order_endpoint_called: `{r.order_endpoint_called}`",
        f"- no_position_modified: `{r.no_position_modified}`",
        f"- no_live_endpoint: `{r.no_live_endpoint}`",
        f"- no_orders_sent: `{r.no_orders_sent}`",
        f"- no_batch_order: `{r.no_batch_order}`",
        f"- no_close_only_path: `{r.no_close_only_path}`",
        f"- emergency_close_invoked: `{r.emergency_close_invoked}`",
        f"- secret_value_observed: `{r.secret_value_observed}`",
        "",
        "> This probe NEVER opens a socket.",
        "> The trading-stop endpoint path is documented but NOT invoked.",
        "> Real probe is deliberately not implemented in TASK-014T; the",
        "> safe no-op probe design is the subject of TASK-014U.",
        "> TASK-014L sender G20 (protected_entry_policy_missing) is NOT",
        "> lifted by this task.",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


def run_execute(
    symbol:                str  = "",
    confirm_token:         str  = "",
    mock_permission:       bool = False,
    allow_real_stop_probe: bool = False,
    write_report:          bool = False,
    protection_dir:        Path | None = None,
    contract_dir:          Path | None = None,
    _now:                  datetime | None = None,
) -> int:
    _protection_dir = protection_dir or _DEFAULT_PROTECTION_DIR
    _contract_dir   = contract_dir   or _DEFAULT_CONTRACT_DIR

    print(_SEP)
    if allow_real_stop_probe:
        print("REAL PROBE GUARD — NO NETWORK — REAL_PROBE_NOT_IMPLEMENTED")
    elif mock_permission:
        print("MOCK PERMISSION — NO NETWORK — SYNTHETIC ENVELOPE")
    else:
        print("PREVIEW — NO NETWORK — CONTRACT + PAYLOAD PREVIEW ONLY")
    print("TASK-014T: Demo Trading-stop Endpoint Contract Probe")
    print(_SEP)

    protection = load_latest_protection(_protection_dir)
    if protection is None:
        print("\n[FAIL CLOSED] latest_new_entry_protection.json not found or unreadable.")
        print(f"  Expected: {_protection_dir / 'latest_new_entry_protection.json'}")
        print(_SEP)
        return 1

    if not symbol:
        print("\n[FAIL CLOSED] --symbol is required.")
        print(_SEP)
        return 1

    if (mock_permission or allow_real_stop_probe) and not confirm_token:
        print("\n[FAIL CLOSED] --confirm-token is required for "
              "--mock-permission or --allow-real-stop-probe.")
        print("  Pattern: CONFIRM_DEMO_TRADING_STOP_PROBE_YYYYMMDD (today UTC)")
        print(_SEP)
        return 1

    print(f"\n  symbol           : {symbol}")
    if confirm_token:
        print(f"  confirm_token    : {confirm_token[:8]}***")
    print(f"  protection_src   : {_protection_dir / 'latest_new_entry_protection.json'}")

    probe = DemoTradingStopContractProbe()
    result = probe.submit_contract_probe(
        protection=protection,
        symbol=symbol,
        confirm_token=confirm_token,
        mock_permission=mock_permission,
        allow_real_stop_probe=allow_real_stop_probe,
        _now=_now,
    )

    print()
    _print_result(result)
    print(_SEP)

    if write_report:
        _write_report(result, _contract_dir)

    if result.status in (
        STATUS_PREVIEW_OK,
        STATUS_MOCK_PERMISSION_OK,
        STATUS_REAL_PROBE_NOT_IMPL,
    ):
        return 0
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Demo trading-stop endpoint contract probe — preview / "
            "mock-permission / real-probe-guard only (no network, no live "
            "endpoint, no orders / positions modified, no real "
            "trading-stop call)."
        ),
    )
    parser.add_argument("--from-latest-protection", action="store_true",
                        help="Read protection JSON from outputs/.../new_entry_protection/.")
    parser.add_argument("--symbol", default="", metavar="SYMBOL",
                        help="Symbol to probe (must match latest protection).")
    parser.add_argument("--confirm-token", default="", metavar="TOKEN",
                        help=("Manual confirmation token (required for "
                              "--mock-permission or --allow-real-stop-probe). "
                              "Pattern: CONFIRM_DEMO_TRADING_STOP_PROBE_YYYYMMDD"
                              " (today UTC)."))
    parser.add_argument("--mock-permission", action="store_true",
                        help=("Emit a synthetic retCode=0 permission "
                              "envelope.  Still does NOT open a socket."))
    parser.add_argument("--allow-real-stop-probe", action="store_true",
                        help=("Guarded flag for the future real probe.  "
                              "TASK-014T returns REAL_PROBE_NOT_IMPLEMENTED "
                              "even when this flag is set (no socket "
                              "opened)."))
    parser.add_argument("--write-report", action="store_true",
                        help="Write JSON + Markdown report to "
                             "outputs/demo_trading/trading_stop_contract/.")
    args = parser.parse_args()
    sys.exit(run_execute(
        symbol=args.symbol,
        confirm_token=args.confirm_token,
        mock_permission=args.mock_permission,
        allow_real_stop_probe=args.allow_real_stop_probe,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
