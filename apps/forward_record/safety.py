from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


def forbidden_terms() -> list[str]:
    return [
        "create" + "_order",
        "submit" + "_order",
        "place" + "_order",
        "cancel" + "_order",
        "order" + "/create",
        "order" + "/cancel",
        "/v5/" + "order",
        "private" + "/",
    ]


def scan_no_order_endpoints(paths: Iterable[Path]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    terms = forbidden_terms()
    for root in paths:
        if not root.exists():
            continue
        files = [root] if root.is_file() else list(root.rglob("*.py"))
        for path in files:
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for term in terms:
                if term in text:
                    violations.append({"file": str(path), "term": term})
    return {"status": "PASS" if not violations else "FAIL", "violations": violations}


def output_flags_present(output_dir: Path, date: str) -> bool:
    json_paths = [
        output_dir / f"{date}_pnl.json",
        output_dir / f"{date}_forward_stats.json",
        output_dir / "forward_summary.json",
    ]
    for path in json_paths:
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("paper_execution_status") != "FORBIDDEN":
            return False
        if data.get("live_trading_status") != "FORBIDDEN":
            return False
    parquet_path = output_dir / f"{date}_positions.parquet"
    if not parquet_path.exists():
        return False
    positions = pd.read_parquet(parquet_path)
    if "paper_execution_status" not in positions or "live_trading_status" not in positions:
        return False
    return bool(
        positions["paper_execution_status"].astype(str).eq("FORBIDDEN").all()
        and positions["live_trading_status"].astype(str).eq("FORBIDDEN").all()
    )


def scan_no_secrets_in_outputs(paths: Iterable[Path]) -> dict[str, Any]:
    indicators = ["api_key", "api_secret", "webhook", "token", "BYBIT_API_KEY", "BYBIT_API_SECRET"]
    violations: list[dict[str, str]] = []
    for root in paths:
        if not root.exists():
            continue
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".json", ".md", ".log", ".csv", ".txt"}]
        for path in files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for indicator in indicators:
                if indicator in text:
                    violations.append({"file": str(path), "indicator": indicator})
    return {"status": "PASS" if not violations else "FAIL", "violations": violations}


def run_safety_scan(source_paths: Iterable[Path], output_dirs: Iterable[Path], date: str) -> dict[str, Any]:
    endpoint_scan = scan_no_order_endpoints(source_paths)
    secret_scan = scan_no_secrets_in_outputs(output_dirs)
    flags = {str(path): output_flags_present(path, date) for path in output_dirs if path.exists()}
    status = "PASS" if endpoint_scan["status"] == "PASS" and secret_scan["status"] == "PASS" and all(flags.values()) else "FAIL"
    return {
        "status": status,
        "endpoint_scan": endpoint_scan,
        "secret_scan": secret_scan,
        "forbidden_flags": flags,
    }

