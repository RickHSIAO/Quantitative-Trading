from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.forward_record.config import ForwardRecordConfig
from apps.forward_record.alerting import run_forward_alerting
from apps.forward_record.market_data import CacheMarketDataProvider
from apps.forward_record.pnl_calculator import build_pnl_payload
from apps.forward_record.primary import build_primary_record
from apps.forward_record.report_writer import write_log, write_review_artifacts, write_track_outputs
from apps.forward_record.safety import run_safety_scan
from apps.forward_record.shadow import build_shadow_record
from apps.forward_record.stats_updater import build_forward_stats, build_forward_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TASK-009 forward record dry-run runner")
    parser.add_argument("--date", default="20260517", help="Record date in YYYYMMDD format")
    parser.add_argument("--config", default="configs/prev3y_crypto.yaml", help="Strategy config path")
    parser.add_argument("--output-dir", default="outputs/forward_record/prev3y_crypto", help="Primary output directory")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Force alert dry-run mode")
    parser.add_argument("--shadow-track", action="store_true", help="Generate A_roll12_share20_exclude shadow track")
    parser.add_argument("--data-source", choices=["cache_fallback"], default="cache_fallback")
    parser.add_argument("--live-alerts", action="store_true", help="Allow live Discord alerts only if monitor config dry_run is false")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = ForwardRecordConfig(strategy_config=Path(args.config)).with_runtime(
        output_date=args.date,
        output_dir=Path(args.output_dir),
        dry_run=True,
        shadow_track=bool(args.shadow_track),
        data_source=args.data_source,
    )
    provider = CacheMarketDataProvider(config.prices_path, config.funding_path)

    primary = build_primary_record(config, provider)
    primary_pnl = build_pnl_payload(config, primary.positions, primary.variant, day_number=0)
    primary_stats = build_forward_stats(config, primary_pnl, primary.source_position_count, safety_pass=True)
    primary_summary = build_forward_summary(config, primary_stats)
    primary_paths = write_track_outputs(
        config.output_dir,
        config.output_date,
        primary.positions,
        primary_pnl,
        primary_stats,
        primary_summary,
        primary.overlay_check,
    )

    shadow_paths = None
    shadow_stats = None
    if config.shadow_track:
        shadow = build_shadow_record(config, provider)
        shadow_pnl = build_pnl_payload(config, shadow.positions, shadow.variant, day_number=0)
        shadow_stats = build_forward_stats(config, shadow_pnl, shadow.source_position_count, safety_pass=True)
        shadow_summary = build_forward_summary(config, shadow_stats)
        shadow_paths = write_track_outputs(
            config.shadow_output_dir,
            config.output_date,
            shadow.positions,
            shadow_pnl,
            shadow_stats,
            shadow_summary,
            shadow.overlay_check,
        )

    output_dirs = [config.output_dir] + ([config.shadow_output_dir] if shadow_paths else [])
    safety_scan = run_safety_scan(
        [Path("apps/forward_record"), Path("scripts/run_forward_record.py")],
        output_dirs,
        config.output_date,
    )
    numbers = write_review_artifacts(
        config,
        primary_paths=primary_paths,
        shadow_paths=shadow_paths,
        primary_stats=primary_stats,
        shadow_stats=shadow_stats,
        safety_scan=safety_scan,
    )
    log_path = write_log(
        config,
        [
            f"status={numbers['status']}",
            f"output_date={config.output_date}",
            f"primary_generated={numbers['primary_generated']}",
            f"shadow_generated={numbers['shadow_generated']}",
            f"review_006b_trigger_ready={numbers['review_006b_trigger_ready']}",
            f"warning_gates={numbers['active_warning_gates']}",
            f"stop_gates={numbers['active_stop_gates']}",
            f"safety_scan={safety_scan['status']}",
            "bybit_connection=NOT_ATTEMPTED",
            "api_key_request=NOT_ATTEMPTED",
            "clock_started=false",
            "paper_execution_status=FORBIDDEN",
            "live_trading_status=FORBIDDEN",
        ],
    )
    alert_log = run_forward_alerting(
        config.output_date,
        live_alerts=bool(args.live_alerts),
        force_dry_run=bool(args.dry_run) or not bool(args.live_alerts),
    )
    print(f"TASK-009 forward record status={numbers['status']}")
    