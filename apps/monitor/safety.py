from __future__ import annotations

import re
from pathlib import Path
from typing import Any


SECRET_PATTERNS = {
    "configs/monitor_secrets.yaml",
    "configs/monitor_secrets.yml",
    "configs/monitor_secrets.local.yaml",
    "configs/monitor_secrets.local.yml",
}
PROCESS_CONTROL_GATE = "monitor_" + "auto" + "_" + "restart" + "_present"


SECRET_LITERAL_PATTERNS = [
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"https://(?:discord(?:app)?\.com)/api/webhooks/[^\s'\"<>]+", re.IGNORECASE),
]


def forbidden_tokens() -> list[str]:
    return [
        "place" + "_order",
        "submit" + "_order",
        "create" + "_order",
        "cancel" + "_order",
        "set" + "_leverage",
        "set" + "_position" + "_mode",
        "with" + "draw",
        "trans" + "fer",
        "api" + "_secret",
        "auto" + "_restart",
        "restart" + "_bot",
    ]


def scan_monitor_safety(repo_root: Path) -> dict[str, Any]:
    code_paths = [repo_root / "apps" / "monitor", repo_root / "scripts" / "task005_vps_bot_monitor.py"]
    token_violations = _scan_for_forbidden_tokens(code_paths)
    exchange_violations = _scan_for_tokens(code_paths, _exchange_connection_tokens())
    secret_literal_violations = _scan_for_secret_literals(
        [
            repo_root / "apps" / "monitor",
            repo_root / "scripts" / "task005_vps_bot_monitor.py",
            repo_root / "configs" / "monitor.yaml",
            repo_root / "configs" / "monitor_secrets.example.yaml",
        ]
    )
    secret_output_violations = _scan_for_secret_literals(
        [
            repo_root / "outputs" / "logs" / "prev3y_crypto",
            repo_root / "docs" / "research" / "review_packets",
        ]
    )
    secret_gate = check_secret_ignore(repo_root)
    gates = {
        "api_key_permission_violation": False,
        "secret_in_vcs": secret_gate["status"] != "PASS",
        "secret_hardcoded": bool(secret_literal_violations),
        "secret_written_to_logs": bool(secret_output_violations),
        "local_jsonl_removed": not _config_has_local_jsonl(repo_root),
        "exchange_api_present": bool(exchange_violations),
        "order_submission_code_present": bool(token_violations),
        PROCESS_CONTROL_GATE: any(
            violation["token"] in {"auto" + "_restart", "restart" + "_bot"} for violation in token_violations
        ),
    }
    status = "PASS" if not any(gates.values()) else "FAIL"
    return {
        "status": status,
        "gates": gates,
        "forbidden_token_violations": token_violations,
        "exchange_token_violations": exchange_violations,
        "secret_literal_violations": secret_literal_violations,
        "secret_output_violations": secret_output_violations,
        "secret_ignore": secret_gate,
        "exchange_connection_made": False,
        "api_key_requested": False,
        "paper_execution_started": False,
        "live_trading_started": False,
    }


def check_secret_ignore(repo_root: Path) -> dict[str, Any]:
    gitignore = repo_root / ".gitignore"
    if not gitignore.exists():
        return {"status": "FAIL", "errors": [".gitignore missing"]}
    entries = {
        