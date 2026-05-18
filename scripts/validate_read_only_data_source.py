from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.forward_record.config import ForwardRecordConfig
from apps.forward_record.market_data import CacheMarketDataProvider
from apps.forward_record.primary import build_primary_record
from apps.forward_record.report_writer import write_track_outputs
from apps.forward_record.safety import scan_no_order_endpoints
from apps.forward_record.pnl_calculator import build_pnl_payload
from apps.forward_record.stats_updater import build_forward_stats, build_forward_summary


PUBLIC_BYBIT_BASE_URL = "https://api.bybit.com"
PUBLIC_BYBIT_PROBES = (
    ("kline", {"category": "linear", "symbol": "BTCUSDT", "interval": "D", "limit": "1"}),
    ("funding/history", {"category": "linear", "symbol": "BTCUSDT", "limit": "1"}),
)
SECRET_MARKERS = (
    "BYBIT_API_KEY",
    "BYBIT_API_SECRET",
    "MONITOR_DISCORD_WEBHOOK_URL",
    "api_key",
    "api_secret",
    "webhook",
    "Bearer ",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only data source validation for forward record")
    parser.add_argument("--date", default="20260518", help="Validation date in YYYYMMDD format")
    parser.add_argument(
        "--output-dir",
        default="outputs/forward_record/read_only_data_source",
        help="Validation artifact root",
    )
    parser.add_argument("--skip-bybit-public", action="store_true", help="Skip public Bybit market GET probes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_dir) / args.date
    primary_output_dir = output_root / "runner_primary"
    output_root.mkdir(parents=True, exist_ok=True)

    config = ForwardRecordConfig(output_dir=primary_output_dir).with_runtime(
        output_date=args.date,
        output_dir=primary_output_dir,
        dry_run=True,
        shadow_track=False,
        data_source="cache_fallback",
    )
    provider = CacheMarketDataProvider(config.prices_path, config.funding_path)

    cache_check = _validate_cache_provider(config, provider)
    runner_check = _run_forward_record_read_only(config, provider)
    bybit_check = (
        {"status": "SKIPPED", "reason": "skip-bybit-public flag"}
        if args.skip_bybit_public
        else _validate_bybit_public_read_only()
    )
    endpoint_scan = scan_no_order_endpoints(
        [
            Path("apps/forward_record"),
            Path("scripts/run_forward_record.py"),
            Path("scripts/validate_read_only_data_source.py"),
        ]
    )
    safety = {
        "no_order_private_write_endpoint": endpoint_scan,
        "paper_execution_status": "FORBIDDEN",
        "live_trading_status": "FORBIDDEN",
        "clock_started": False,
        "external_post_attempted": False,
        "alerting_invoked": False,
        "secrets_read": False,
        "secrets_modified": False,
    }
    result = {
        "artifact": "read_only_data_source_validation",
        "run_ts": _utc_now(),
        "date": args.date,
        "status": _overall_status(cache_check, runner_check, bybit_check, endpoint_scan),
        "configured_data_sources": {
            "forward_runner_data_source": "cache_fallback",
            "prices_path": config.prices_path.as_posix(),
            "funding_path": config.funding_path.as_posix(),
            "bybit_public_market_get": "https://api.bybit.com/v5/market/{resource}",
        },
        "cache_check": cache_check,
        "runner_check": runner_check,
        "bybit_public_read_only_check": bybit_check,
        "safety": safety,
    }
    result_path = output_root / "validation_result.json"
    _write_json(result_path, result)
    print(json.dumps(_redacted_console_summary(result, result_path), indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


def _validate_cache_provider(config: ForwardRecordConfig, provider: CacheMarketDataProvider) -> dict[str, Any]:
    prices = provider.load_prices(config.output_date)
    funding = provider.load_funding(config.output_date)
    prices["date"] = pd.to_datetime(prices["date"]).dt.normalize()
    funding["timestamp"] = pd.to_datetime(funding["timestamp"], utc=True)
    return {
        "status": "PASS" if len(prices) > 0 and len(funding) > 0 else "FAIL",
        "data_source": provider.data_source,
        "prices_rows": int(len(prices)),
        "prices_symbols": int(prices["symbol"].nunique()),
        "prices_max_date": prices["date"].max().strftime("%Y-%m-%d") if len(prices) else None,
        "funding_rows": int(len(funding)),
        "funding_symbols": int(funding["symbol"].nunique()),
        "funding_max_timestamp": funding["timestamp"].max().isoformat() if len(funding) else None,
        "prices_path_exists": config.prices_path.exists(),
        "funding_path_exists": config.funding_path.exists(),
    }


def _run_forward_record_read_only(
    config: ForwardRecordConfig,
    provider: CacheMarketDataProvider,
) -> dict[str, Any]:
    primary = build_primary_record(config, provider)
    pnl = build_pnl_payload(config, primary.positions, primary.variant, day_number=0)
    stats = build_forward_stats(config, pnl, primary.source_position_count, safety_pass=True)
    summary = build_forward_summary(config, stats)
    paths = write_track_outputs(
        config.output_dir,
        config.output_date,
        primary.positions,
        pnl,
        stats,
        summary,
        primary.overlay_check,
    )
    flags_ok = (
        primary.positions["paper_execution_status"].astype(str).eq("FORBIDDEN").all()
        and primary.positions["live_trading_status"].astype(str).eq("FORBIDDEN").all()
        and primary.positions["clock_started"].astype(bool).eq(False).all()
        and pnl["paper_execution_status"] == "FORBIDDEN"
        and pnl["live_trading_status"] == "FORBIDDEN"
        and stats["paper_execution_status"] == "FORBIDDEN"
        and stats["live_trading_status"] == "FORBIDDEN"
        and stats["clock_started"] is False
    )
    return {
        "status": "PASS" if flags_ok and len(primary.positions) > 0 else "FAIL",
        "output_dir": config.output_dir.as_posix(),
        "positions_rows": int(len(primary.positions)),
        "source_position_count": int(primary.source_position_count),
        "data_source_values": sorted(primary.positions["data_source"].astype(str).unique().tolist()),
        "dry_run_values": sorted(primary.positions["dry_run"].astype(bool).unique().tolist()),
        "paper_execution_status": "FORBIDDEN",
        "live_trading_status": "FORBIDDEN",
        "clock_started": False,
        "external_post_attempted": False,
        "paths": {key: Path(path).as_posix() for key, path in paths.items()},
    }


def _validate_bybit_public_read_only() -> dict[str, Any]:
    probes = []
    for resource, params in PUBLIC_BYBIT_PROBES:
        payload = _bybit_public_get(resource, params)
        result = payload.get("result", {})
        rows = result.get("list", [])
        probes.append(
            {
                "resource": resource,
                "method": "GET",
                "path": f"/v5/market/{resource}",
                "symbol": params.get("symbol"),
                "ret_code": payload.get("retCode"),
                "ret_msg": payload.get("retMsg"),
                "row_count": len(rows) if isinstance(rows, list) else 0,
            }
        )
    status = "PASS" if all(item["ret_code"] == 0 and item["row_count"] > 0 for item in probes) else "FAIL"
    return {"status": status, "base_url": PUBLIC_BYBIT_BASE_URL, "probes": probes}


def _bybit_public_get(resource: str, params: dict[str, str]) -> dict[str, Any]:
    if resource not in {"kline", "funding/history"}:
        raise ValueError(f"unsupported read-only resource: {resource}")
    query = urllib.parse.urlencode(params)
    url = f"{PUBLIC_BYBIT_BASE_URL}/v5/market/{resource}?{query}"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "QuantForwardRecord/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _overall_status(
    cache_check: dict[str, Any],
    runner_check: dict[str, Any],
    bybit_check: dict[str, Any],
    endpoint_scan: dict[str, Any],
) -> str:
    bybit_ok = bybit_check["status"] in {"PASS", "SKIPPED"}
    return (
        "PASS"
        if cache_check["status"] == "PASS"
        and runner_check["status"] == "PASS"
        and bybit_ok
        and endpoint_scan["status"] == "PASS"
        else "FAIL"
    )


def _redacted_console_summary(result: dict[str, Any], result_path: Path) -> dict[str, Any]:
    text = json.dumps(result, sort_keys=True)
    leaked = [marker for marker in SECRET_MARKERS if marker in text]
    return {
        "status": result["status"],
        "artifact_path": result_path.as_posix(),
        "cache_status": result["cache_check"]["status"],
        "runner_status": result["runner_check"]["status"],
        "bybit_public_read_only_status": result["bybit_public_read_only_check"]["status"],
        "endpoint_scan_status": result["safety"]["no_order_private_write_endpoint"]["status"],
        "paper_execution_status": result["safety"]["paper_execution_status"],
        "live_trading_status": result["safety"]["live_trading_status"],
        "external_post_attempted": result["safety"]["external_post_attempted"],
        "secret_marker_leak_check": "PASS" if not leaked else "FAIL",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
