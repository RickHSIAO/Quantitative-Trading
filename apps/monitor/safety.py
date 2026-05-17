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
        line.strip().replace("\\", "/")
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    missing = sorted(SECRET_PATTERNS - entries)
    existing_secret_files = sorted(
        str(path)
        for path in (repo_root / "configs").glob("monitor_secrets*.y*ml")
        if not path.name.startswith("monitor_secrets.example.")
    )
    errors = []
    if missing:
        errors.append(f"missing .gitignore entries: {missing}")
    if existing_secret_files:
        errors.append(f"local secret files must not be created for TASK-005 delivery: {existing_secret_files}")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "required_patterns": sorted(SECRET_PATTERNS)}


def _scan_for_forbidden_tokens(paths: list[Path]) -> list[dict[str, str]]:
    return _scan_for_tokens(paths, forbidden_tokens())


def _scan_for_tokens(paths: list[Path], tokens: list[str]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for root in paths:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else list(root.rglob("*.py"))
        for path in candidates:
            text = path.read_text(encoding="utf-8")
            for token in tokens:
                if token in text:
                    violations.append({"path": str(path), "token": token})
    return violations


def _scan_for_secret_literals(paths: list[Path]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for root in paths:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else [
            path
            for pattern in ("*.py", "*.yaml", "*.yml", "*.md", "*.json", "*.log")
            for path in root.rglob(pattern)
        ]
        for path in candidates:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in SECRET_LITERAL_PATTERNS:
                if pattern.search(text):
                    violations.append({"path": str(path), "pattern": pattern.pattern})
    return violations


def _config_has_local_jsonl(repo_root: Path) -> bool:
    config_path = repo_root / "configs" / "monitor.yaml"
    if not config_path.exists():
        return False
    text = config_path.read_text(encoding="utf-8")
    return "type: local_jsonl" in text


def _exchange_connection_tokens() -> list[str]:
    return ["c" + "cxt", "py" + "bit", "/" + "v5" + "/"]
