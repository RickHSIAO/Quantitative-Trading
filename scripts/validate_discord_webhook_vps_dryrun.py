"""
validate_discord_webhook_vps_dryrun.py
========================================
VPS-side Discord webhook dry-run validation with strict guards.

Purpose:
    Confirm that on the VPS:
      1. Discord webhook config / env var is present and non-empty
      2. Alert pipeline still uses dry_run=True only (no real POST)
      3. load_channel_secrets() is NOT called during dry_run dispatch
      4. No secret value appears anywhere in output or artifacts
      5. All existing safety gates (G-1 ~ G-5) still pass

Strict guards (monkeypatching):
    - If load_channel_secrets() is reached during dry_run dispatch -> FAIL immediately
    - If DefaultHttpClient.post_json() is called -> FAIL immediately
    - If any Discord webhook URL pattern appears in stdout/artifacts -> FAIL immediately

Safety invariants (all must hold):
    dry_run=true, external_post_attempted=false, clock_started=false,
    paper_execution_status=FORBIDDEN, live_trading_status=FORBIDDEN,
    secret_value_observed=false

Usage (VPS):
    # Configure webhook URL via env var (do NOT commit value to repo)
    export MONITOR_DISCORD_WEBHOOK_URL="<real-webhook-url>"

    # Run validation
    python scripts/validate_discord_webhook_vps_dryrun.py

    # Or with explicit output dir
    python scripts/validate_discord_webhook_vps_dryrun.py --output-dir outputs/forward_record/discord_webhook_vps_dry_run/20260518

DO NOT:
    - Do NOT use --live-alerts anywhere
    - Do NOT set configs/monitor.yaml discord dry_run to false
    - Do NOT set force_dry_run=False
    - Do NOT commit real webhook URLs to repo, logs, or output files
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import socket
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Secret leak detector -- regex patterns that must NEVER appear in artifacts
# ---------------------------------------------------------------------------
_LEAK_PATTERNS = [
    re.compile(r"https://(?:discord(?:app)?\.com)/api/webhooks/[^\s'\"<>{}\]]+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_-]{50,}\b"),   # long token-like strings
]

VALIDATION_DATE = datetime.now(timezone.utc).strftime("%Y%m%d")
_FAIL_MESSAGES: list[str] = []


def _check_no_secret_leak(text: str, context: str) -> bool:
    """Return True if no secret pattern found; record failure otherwise."""
    for pattern in _LEAK_PATTERNS:
        m = pattern.search(text)
        if m:
            _FAIL_MESSAGES.append(
                f"SECRET LEAK DETECTED in {context}: pattern '{pattern.pattern[:40]}' matched"
            )
            return False
    return True


# ---------------------------------------------------------------------------
# Strict monkeypatches
# ---------------------------------------------------------------------------
def _forbidden_http_post(*args: Any, **kwargs: Any) -> Any:
    """Replacement for DefaultHttpClient.post_json -- must never be called."""
    raise AssertionError(
        "STRICT GUARD VIOLATED: DefaultHttpClient.post_json() was called. "
        "A real HTTP POST was attempted during dry_run validation. FAIL."
    )


_secrets_call_log: list[str] = []


def _guarded_load_channel_secrets(channel: Any, environ: Any = None) -> Any:
    """Wrapper around load_channel_secrets that records the call site."""
    stack = traceback.format_stack()
    _secrets_call_log.append("".join(stack[-5:]))
    # Allow the real function to run (we check whether it was reached later)
    from apps.monitor.channels.secrets import load_channel_secrets as _real
    return _real(channel, environ=environ)


# ---------------------------------------------------------------------------
# Environment / platform gate
# ---------------------------------------------------------------------------
def check_vps_environment() -> dict:
    """Record hostname and platform -- never prints secrets or env vars."""
    hostname = socket.gethostname()
    plat = platform.system()
    release = platform.release()
    py_ver = platform.python_version()
    on_linux = plat == "Linux"
    return {
        "gate": "ENV",
        "name": "VPS environment detection",
        "hostname": hostname,
        "platform": plat,
        "release": release,
        "python_version": py_ver,
        "running_on_linux": on_linux,
        "pass": True,            # informational -- not a hard gate
    }


# ---------------------------------------------------------------------------
# Gate W-0 -- webhook config presence (boolean only, no value)
# ---------------------------------------------------------------------------
def check_gate_w0_webhook_config_presence() -> dict:
    """
    Check that webhook config is present and non-empty.
    Records ONLY boolean results -- never the value, length, hash, or prefix.
    """
    env_var = "MONITOR_DISCORD_WEBHOOK_URL"
    env_value = os.environ.get(env_var)
    env_present = env_value is not None
    env_non_empty = bool(env_value) if env_present else False

    # Also check secrets file (presence check only)
    secrets_path = Path("configs/monitor_secrets.local.yaml")
    file_present = secrets_path.exists()
    file_webhook_non_empty = False
    if file_present:
        try:
            text = secrets_path.read_text(encoding="utf-8")
            import re as _re
            m = _re.search(r"webhook_url\s*:\s*(\S+)", text)
            if m:
                val = m.group(1).strip("\"'")
                file_webhook_non_empty = bool(val) and val not in ("", "null", "~", "PLACEHOLDER")
        except Exception:
            pass

    webhook_available = (env_present and env_non_empty) or file_webhook_non_empty
    passed = webhook_available

    return {
        "gate": "W-0",
        "name": "webhook config presence (VPS)",
        "env_var": env_var,
        "webhook_config_present": webhook_available,
        "webhook_config_non_empty": webhook_available,
        "source_env_var": env_present and env_non_empty,
        "source_secrets_file": file_webhook_non_empty,
        "secret_value_observed": False,     # hardcoded; value never read into this report
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Gate G-1 -- dry_run exits before load_channel_secrets() is called
# ---------------------------------------------------------------------------
def check_gate_g1_dry_run_no_secret_load() -> dict:
    """dry_run exits before load_channel_secrets() -- strict guard"""
    from apps.monitor.alerts import Alert
    from apps.monitor.channels.discord import send_discord_alerts
    from apps.monitor.channels.redaction import redacted_discord_endpoint
    from apps.monitor.config import AlertsConfig, ChannelConfig, MonitorConfig

    _secrets_call_log.clear()

    channel = ChannelConfig(
        type="discord",
        enabled=True,
        dry_run=True,
        secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
        timeout_seconds=10,
    )
    config = MonitorConfig(
        bot_name="vps_dryrun_validation",
        environment="vps_discord_dryrun_validation",
        account_mode="read_only_monitor",
        alerts=AlertsConfig(channels=(channel,)),
        paper_execution_status="FORBIDDEN",
        live_trading_status="FORBIDDEN",
    )
    alert = Alert(
        timestamp=datetime.now(timezone.utc).isoformat(),
        severity="WARNING",
        category="FORWARD_RECORD_VALIDATION",
        message="[VPS VALIDATION] dry_run gate check -- no real POST",
        dedupe_key="validation:vps_dryrun",
        source="validate_discord_webhook_vps_dryrun",
        action_required="no_action_required",
        paper_execution_status="FORBIDDEN",
        live_trading_status="FORBIDDEN",
    )

    with patch("apps.monitor.channels.discord.load_channel_secrets", side_effect=_guarded_load_channel_secrets), \
         patch("apps.monitor.channels.base.DefaultHttpClient.post_json", side_effect=_forbidden_http_post):
        result = send_discord_alerts(
            config=config,
            channel=channel,
            alerts=[alert],
            test_send=False,
        )

    secrets_called = len(_secrets_call_log) > 0
    result_dict = result.to_dict()
    result_json = json.dumps(result_dict)

    no_leak = _check_no_secret_leak(result_json, "G-1 ChannelResult")
    passed = (
        result.status == "DRY_RUN"
        and result.dry_run is True
        and result.external_post_attempted is False
        and result.endpoint == redacted_discord_endpoint()
        and not secrets_called
        and no_leak
    )

    return {
        "gate": "G-1",
        "name": "dry_run exits before load_channel_secrets() -- strict guard",
        "status": result.status,
        "dry_run": result.dry_run,
        "external_post_attempted": result.external_post_attempted,
        "endpoint": result.endpoint,
        "load_channel_secrets_called": secrets_called,
        "secret_value_observed": False,
        "no_secret_leak_in_output": no_leak,
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Gate G-2 -- redaction
# ---------------------------------------------------------------------------
def check_gate_g2_redaction() -> dict:
    """webhook URL redaction"""
    from apps.monitor.channels.redaction import redact_text

    FAKE = "https://discord.com/api/webhooks/000000000000/FAKE_TOKEN_FOR_VALIDATION"
    FAKE2 = "https://discordapp.com/api/webhooks/999/XYZ_token_abcDEF"
    plain = f"Sending to {FAKE} and also {FAKE2} end"
    redacted = redact_text(plain)

    r1 = FAKE not in redacted
    r2 = FAKE2 not in redacted
    r3 = "<redacted>" in redacted
    no_leak = _check_no_secret_leak(redacted, "G-2 redacted output")
    passed = r1 and r2 and r3 and no_leak
    return {
        "gate": "G-2",
        "name": "webhook URL redaction",
        "real_url_removed": r1,
        "discordapp_url_removed": r2,
        "redacted_marker_present": r3,
        "no_leak_in_redacted_output": no_leak,
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Gate G-3 -- no secret in ChannelResult
# ---------------------------------------------------------------------------
def check_gate_g3_no_secret_in_output() -> dict:
    """no secret in ChannelResult output -- real env"""
    from apps.monitor.channels.discord import send_discord_alerts
    from apps.monitor.config import AlertsConfig, ChannelConfig, MonitorConfig
    from apps.monitor.alerts import Alert

    channel = ChannelConfig(
        type="discord", enabled=True, dry_run=True,
        secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
    )
    config = MonitorConfig(
        alerts=AlertsConfig(channels=(channel,)),
        paper_execution_status="FORBIDDEN",
        live_trading_status="FORBIDDEN",
    )
    with patch("apps.monitor.channels.base.DefaultHttpClient.post_json", side_effect=_forbidden_http_post):
        result = send_discord_alerts(
            config=config,
            channel=channel,
            alerts=[Alert(
                timestamp=datetime.now(timezone.utc).isoformat(),
                severity="INFO", category="VALIDATION", message="G-3 check",
                dedupe_key="g3", source="validation",
                action_required="none",
                paper_execution_status="FORBIDDEN", live_trading_status="FORBIDDEN",
            )],
        )

    result_json = json.dumps(result.to_dict())
    no_leak = _check_no_secret_leak(result_json, "G-3 ChannelResult JSON")
    passed = result.status == "DRY_RUN" and no_leak
    return {
        "gate": "G-3",
        "name": "no secret in ChannelResult output -- real env",
        "status": result.status,
        "external_post_attempted": result.external_post_attempted,
        "no_secret_leak_in_output": no_leak,
        "secret_value_observed": False,
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Gate G-4 -- safety scan
# ---------------------------------------------------------------------------
def check_gate_g4_safety_scan() -> dict:
    """safety scan: no order endpoint imports"""
    from apps.forward_record.safety import scan_no_order_endpoints
    targets = [
        Path("scripts/validate_discord_webhook_vps_dryrun.py"),
        Path("apps/forward_record/alerting.py"),
        Path("apps/monitor/channels/discord.py"),
    ]
    scan = scan_no_order_endpoints(targets)
    passed = scan["status"] == "PASS" and scan["violations"] == []
    return {
        "gate": "G-4",
        "name": "safety scan: no order endpoint imports",
        "scan_status": scan["status"],
        "violations": scan["violations"],
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Gate G-5 -- triple dry_run gate
# ---------------------------------------------------------------------------
def check_gate_g5_triple_dry_run_gate() -> dict:
    """triple dry_run gate: force_dry_run + live_alerts=False"""
    from apps.forward_record.alerting import run_forward_alerting
    import yaml
    import pandas as pd

    DRILL_DATE = "20260517"
    PREV_DATE  = "20260516"

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        config_path  = base / "forward_record.yaml"
        monitor_path = base / "monitor.yaml"

        yaml.dump({
            "output_paths": {
                "log": str(base / "{date}_forward_record.log"),
                "primary": {
                    "positions":     str(base / "{date}_positions.parquet"),
                    "forward_stats": str(base / "{date}_forward_stats.json"),
                    "overlay_check": str(base / "{date}_overlay_check.json"),
                    "pnl":           str(base / "{date}_pnl.json"),
                },
                "shadow": {
                    "positions":     str(base / "shadow_{date}_positions.parquet"),
                    "forward_stats": str(base / "shadow_{date}_forward_stats.json"),
                    "overlay_check": str(base / "shadow_{date}_overlay_check.json"),
                    "pnl":           str(base / "shadow_{date}_pnl.json"),
                },
            }
        }, open(config_path, "w"))

        base_stats = {
            "active_stop_gates": [],
            "active_warning_gates": [],
            "review_006b_trigger_ready": False,
            "data_source": "MOCK",
            "paper_execution_status": "FORBIDDEN",
            "live_trading_status": "FORBIDDEN",
        }
        for date in (DRILL_DATE, PREV_DATE):
            rows = [{"symbol": "BTCUSDT", "weight": 0.02, "weight_raw": 0.02,
                     "paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN"}]
            pd.DataFrame(rows).to_parquet(base / f"{date}_positions.parquet", index=False)
            pd.DataFrame(rows).to_parquet(base / f"shadow_{date}_positions.parquet", index=False)
            stats = {**base_stats, "date": date}
            (base / f"{date}_forward_stats.json").write_text(json.dumps(stats), encoding="utf-8")
            (base / f"shadow_{date}_forward_stats.json").write_text(json.dumps(stats), encoding="utf-8")
            (base / f"{date}_overlay_check.json").write_text(json.dumps({"overlay_pass": True}), encoding="utf-8")
            (base / f"shadow_{date}_overlay_check.json").write_text(json.dumps({"overlay_pass": True}), encoding="utf-8")
            (base / f"{date}_pnl.json").write_text(
                json.dumps({"paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN"}),
                encoding="utf-8")
            (base / f"shadow_{date}_pnl.json").write_text(
                json.dumps({"paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN"}),
                encoding="utf-8")
            (base / f"{date}_forward_record.log").write_text("status=REVIEW_READY\n", encoding="utf-8")

        monitor_path.write_text(
            "bot_name: vps_triple_gate\nenvironment: vps_validation\n"
            "account_mode: read_only_monitor\npaper_execution_status: FORBIDDEN\n"
            "live_trading_status: FORBIDDEN\nalerts:\n  channels:\n"
            "    - type: discord\n      enabled: true\n      dry_run: true\n"
            "      secrets_env_webhook_url: MONITOR_DISCORD_WEBHOOK_URL\n"
            "      timeout_seconds: 10\n",
            encoding="utf-8",
        )

        alert_dir = base / "alerts"
        with patch("apps.monitor.channels.base.DefaultHttpClient.post_json",
                   side_effect=_forbidden_http_post):
            alert_log = run_forward_alerting(
                DRILL_DATE,
                forward_record_config_path=config_path,
                monitor_config_path=monitor_path,
                alert_log_dir=alert_dir,
                live_alerts=False,
                force_dry_run=True,
            )

    alert_log_json = json.dumps(alert_log)
    no_leak = _check_no_secret_leak(alert_log_json, "G-5 alert_log")

    passed = (
        alert_log.get("dry_run") is True
        and alert_log.get("FORBIDDEN_live_trading") == "NOT_ATTEMPTED"
        and alert_log.get("FORBIDDEN_order_endpoint") == "NOT_ATTEMPTED"
        and alert_log.get("FORBIDDEN_bybit_write") == "NOT_ATTEMPTED"
        and alert_log.get("clock_started") is not True   # absent/False/None = not started
        and no_leak
    )
    return {
        "gate": "G-5",
        "name": "triple dry_run gate: force_dry_run + live_alerts=False",
        "dry_run": alert_log.get("dry_run"),
        "FORBIDDEN_live_trading": alert_log.get("FORBIDDEN_live_trading"),
        "FORBIDDEN_order_endpoint": alert_log.get("FORBIDDEN_order_endpoint"),
        "FORBIDDEN_bybit_write": alert_log.get("FORBIDDEN_bybit_write"),
        "clock_started": alert_log.get("clock_started"),
        "no_secret_leak_in_alert_log": no_leak,
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_validation(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    env_info = check_vps_environment()

    print("=== Discord webhook VPS dry-run validation (strict guards) ===", flush=True)
    print(f"Host:     {env_info['hostname']}", flush=True)
    print(f"Platform: {env_info['platform']} {env_info['release']}", flush=True)
    print(f"Python:   {env_info['python_version']}", flush=True)
    print(flush=True)

    gates = []

    # W-0: webhook presence
    w0 = check_gate_w0_webhook_config_presence()
    gates.append(w0)
    print(f"  [{'PASS' if w0['pass'] else 'FAIL'}] W-0 -- {w0['name']}", flush=True)
    print(f"         webhook_config_present={w0['webhook_config_present']}  "
          f"webhook_config_non_empty={w0['webhook_config_non_empty']}  "
          f"secret_value_observed={w0['secret_value_observed']}", flush=True)

    # G-1 through G-5
    for fn in [
        check_gate_g1_dry_run_no_secret_load,
        check_gate_g2_redaction,
        check_gate_g3_no_secret_in_output,
        check_gate_g4_safety_scan,
        check_gate_g5_triple_dry_run_gate,
    ]:
        try:
            result = fn()
        except AssertionError as e:
            result = {
                "gate": fn.__name__,
                "name": fn.__doc__ or fn.__name__,
                "pass": False,
                "error": f"STRICT GUARD VIOLATED: {e}",
            }
        except Exception as e:
            result = {
                "gate": fn.__name__,
                "name": str(fn.__name__),
                "pass": False,
                "error": f"{type(e).__name__}: {e}",
            }
        gates.append(result)
        status = "PASS" if result["pass"] else "FAIL"
        print(f"  [{status}] {result['gate']} -- {result['name']}", flush=True)
        if not result["pass"] and "error" in result:
            print(f"         ERROR: {result['error']}", flush=True)

    # Global leak check
    if _FAIL_MESSAGES:
        for msg in _FAIL_MESSAGES:
            print(f"  [FAIL] SECRET LEAK: {msg}", flush=True)

    all_pass = all(g["pass"] for g in gates) and not _FAIL_MESSAGES
    overall = "PASS" if all_pass else "FAIL"
    passed_count = sum(g["pass"] for g in gates)
    total_count = len(gates)

    print(flush=True)
    print(f"Overall: {overall} ({passed_count}/{total_count} gates)", flush=True)
    if _FAIL_MESSAGES:
        print(f"Secret leak violations: {len(_FAIL_MESSAGES)}", flush=True)

    report = {
        "validation": "discord_webhook_vps_dryrun",
        "date": VALIDATION_DATE,
        "run_ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z",
        "overall_result": overall,
        "environment": {
            "hostname": env_info["hostname"],
            "platform": env_info["platform"],
            "release": env_info["release"],
            "python_version": env_info["python_version"],
        },
        "gates": gates,
        "secret_leak_violations": _FAIL_MESSAGES,
        "FORBIDDEN_live_trading": "NOT_ATTEMPTED",
        "FORBIDDEN_discord_real_post": "NOT_ATTEMPTED",
        "FORBIDDEN_live_alerts": "NOT_ATTEMPTED",
        "clock_started": False,
        "paper_execution_status": "FORBIDDEN",
        "live_trading_status": "FORBIDDEN",
        "external_post_attempted": False,
        "secret_value_observed": False,
    }

    # Scan report JSON itself for leaks before writing
    report_json = json.dumps(report, indent=2)
    if not _check_no_secret_leak(report_json, "final report JSON"):
        print("  [FAIL] Secret leak detected in final report -- aborting write", flush=True)
        sys.exit(2)

    out_path = output_dir / "validation_result.json"
    out_path.write_text(report_json + "\n", encoding="utf-8")
    print(f"Report:  {out_path}", flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_dir = (Path(args.output_dir) if args.output_dir
               else Path(f"outputs/forward_record/discord_webhook_vps_dry_run/{date_str}"))
    report = run_validation(out_dir)
    sys.exit(0 if report["overall_result"] == "PASS" else 1)
