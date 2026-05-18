from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from apps.forward_record import RUNNER_VERSION
from apps.forward_record.config import ForwardRecordConfig


def write_track_outputs(
    output_dir: Path,
    date: str,
    positions: pd.DataFrame,
    pnl: dict[str, Any],
    stats: dict[str, Any],
    summary: dict[str, Any],
    overlay_check: dict[str, Any] | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "positions": output_dir / f"{date}_positions.parquet",
        "pnl": output_dir / f"{date}_pnl.json",
        "forward_stats": output_dir / f"{date}_forward_stats.json",
        "forward_summary": output_dir / "forward_summary.json",
    }
    positions.to_parquet(paths["positions"], index=False)
    pnl = dict(pnl)
    pnl["reproducibility"] = reproducibility_payload(paths["positions"], positions, date)
    _write_json(paths["pnl"], pnl)
    _write_json(paths["forward_stats"], stats)
    _write_json(paths["forward_summary"], summary)
    if overlay_check is not None:
        paths["overlay_check"] = output_dir / f"{date}_overlay_check.json"
        _write_json(paths["overlay_check"], overlay_check)
    return {key: str(value) for key, value in paths.items()}


def write_review_artifacts(
    config: ForwardRecordConfig,
    *,
    primary_paths: dict[str, str],
    shadow_paths: dict[str, str] | None,
    primary_stats: dict[str, Any],
    shadow_stats: dict[str, Any] | None,
    safety_scan: dict[str, Any],
) -> dict[str, Any]:
    status = "REVIEW_READY" if safety_scan["status"] == "PASS" and not primary_stats["active_stop_gates"] else "FAIL"
    numbers = {
        "task": "TASK-009",
        "status": status,
        "runner_version": RUNNER_VERSION,
        "output_date": config.output_date,
        "primary_variant": config.primary_variant,
        "shadow_variant": config.shadow_variant if shadow_paths else None,
        "primary_generated": bool(primary_paths),
        "shadow_generated": bool(shadow_paths),
        "review_006b_trigger_ready": bool(primary_stats["review_006b_trigger_ready"]),
        "active_warning_gates": primary_stats["active_warning_gates"],
        "active_stop_gates": primary_stats["active_stop_gates"],
        "safety_scan": safety_scan,
        "outputs": {
            "primary": primary_paths,
            "shadow": shadow_paths or {},
            "log": str(config.log_dir / f"{config.output_date}_forward_record.log"),
        },
        "paper_execution_status": config.paper_execution_status,
        "live_trading_status": config.live_trading_status,
        "clock_started": bool(config.clock_started),
        "dry_run": bool(config.dry_run),
    }
    config.review_numbers_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(config.review_numbers_path, numbers)
    packet_lines = [
        "# REVIEW-009 Packet - TASK-009 Forward Record Runner",
        "",
        f"- Status: {status}",
        f"- Runner version: {RUNNER_VERSION}",
        f"- Output date: {config.output_date}",
        f"- Primary generated: {bool(primary_paths)}",
        f"- Shadow generated: {bool(shadow_paths)}",
        f"- review_006b_trigger_ready: {bool(primary_stats['review_006b_trigger_ready'])}",
        f"- Warning gates: {primary_stats['active_warning_gates']}",
        f"- Stop gates: {primary_stats['active_stop_gates']}",
        f"- Safety scan: {safety_scan['status']}",
        "- Paper execution: FORBIDDEN",
        "- Live trading: FORBIDDEN",
        "- Bybit connection: NOT_ATTEMPTED",
        "- API key request: NOT_ATTEMPTED",
        "- 30-day forward clock: NOT_STARTED",
        "",
        "## Outputs",
        f"- primary: `{config.output_dir}`",
        f"- shadow: `{config.shadow_output_dir if shadow_paths else 'disabled'}`",
        f"- numbers: `{config.review_numbers_path}`",
    ]
    config.review_packet_path.write_text("\n".join(packet_lines) + "\n", encoding="utf-8")
    return numbers


def write_log(config: ForwardRecordConfig, lines: list[str]) -> Path:
    config.log_dir.mkdir(parents=True, exist_ok=True)
    path = config.log_dir / f"{config.output_date}_forward_record.log"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def reproducibility_payload(path: Path, positions: pd.DataFrame, date: str) -> dict[str, Any]:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    digest.update(positions.to_json(orient="records", date_format="iso").encode("utf-8"))
    digest.update(date.encode("utf-8"))
    return {
        "runner_version": RUNNER_VERSION,
        "date": date,
        "positions_hash": f"sha256:{digest.hexdigest()}",
        "positions_rows": int(len(positions)),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value

