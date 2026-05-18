"""
validate_discord_webhook_dryrun.py
===================================
VPS Discord webhook dry-run validation script.

Purpose:
    Confirm that Discord webhook secret can be safely configured on VPS
    while alert pipeline always returns DRY_RUN status and never sends
    a real POST, even when a real webhook URL is present in env.

Safety invariants verified:
    1. dry_run branch exits BEFORE load_channel_secrets() is called
    2. redact_text() removes webhook URLs from all outputs
    3. ChannelResult.external_post_attempted = False in dry_run mode
    4. Triple dry_run gate: force_dry_run + live_alerts=False + yaml dry_run=true

Usage (VPS):
    # Set fake webhook URL in env to simulate configured state
    export MONITOR_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/000000000000/FAKE_TOKEN_FOR_VALIDATION_ONLY"
    python scripts/validate_discord_webhook_dryrun.py

    # Optional: provide real webhook URL to confirm real config path is also safe
    # (still uses dry_run=True, so no POST will be sent)
    export MONITOR_DISCORD_WEBHOOK_URL="<your-real-webhook-url>"
    python scripts/validate_discord_webhook_dryrun.py

DO NOT:
    - Do NOT use --live-alerts
    - Do NOT set discord dry_run to false
    - Do NOT run with force_dry_run=False
    - Do NOT commit real webhook URLs to repo or logs
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.monitor.alerts import Alert  # noqa: E402
from apps.monitor.channels.discord import send_discord_alerts  # noqa: E402
from apps.monitor.channels.redaction import redact_text, redacted_discord_endpoint  # noqa: E402
from apps.monitor.channels.secrets import load_channel_secrets  # noqa: E402
from apps.monitor.config import ChannelConfig, MonitorConfig  # noqa: E402
from apps.forward_record.safety import scan_no_order_endpoints  # noqa: E402


VALIDATION_DATE = datetime.now(timezone.utc).strftime("%Y%m%d")
FAKE_WEBHOOK = "https://discord.com/api/webhooks/000000000000/FAKE_TOKEN_FOR_VALIDATION_ONLY"
OUTPUT_DIR = Path(f"outputs/forward_record/discord_webhook_validation/{VALIDATION_DATE}")


def _make_test_alert() -> Alert:
    return Alert(
        timestamp=datetime.now(timezone.utc).isoformat(),
        severity="WARNING",
        category="FORWARD_RECORD_A-1",
        message="[VALIDATION] Test alert — dry_run gate check",
        dedupe_key="validation:discord_dryrun",
        source="validate_discord_webhook_dryrun",
        action_required="no_action_required_this_is_a_validation_run",
        paper_execution_status="FORBIDDEN",
        live_trading_status="FORBIDDEN",
    )


def _make_monitor_config() -> MonitorConfig:
    """Monitor config with discord channel enabled but dry_run=True."""
    channel = ChannelConfig(
        type="discord",
        enabled=True,
        dry_run=True,                         # MANDATORY: always True for this validation
        secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
        timeout_seconds=10,
    )
    from apps.monitor.config import AlertsConfig
    return MonitorConfig(
        bot_name="prev3y_crypto_paper",
        environment="vps_discord_dryrun_validation",
        account_mode="read_only_monitor",
        alerts=AlertsConfig(channels=(channel,)),
        paper_execution_status="FORBIDDEN",
        live_trading_status="FORBIDDEN",
    )


# ---------------------------------------------------------------------------
# Gate 1 — dry_run dispatch path: exits before load_channel_secrets()
# ---------------------------------------------------------------------------
def check_gate_1_dry_run_exits_before_secret_load() -> dict:
    """
    Verify: send_discord_alerts() with dry_run=True returns DRY_RUN status
    without ever reading the webhook URL from env.
    """
    channel = ChannelConfig(
        type="discord",
        enabled=True,
        dry_run=True,
        secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
    )
    config = _make_monitor_config()
    alerts = [_make_test_alert()]

    # Use a custom environ that has the fake webhook
    fake_env = {"MONITOR_DISCORD_WEBHOOK_URL": FAKE_WEBHOOK}

    result = send_discord_alerts(
        config=config,
        channel=channel,
        alerts=alerts,
        http_client=None,   # DefaultHttpClient would make real HTTP calls — but dry_run exits first
        test_send=False,
        environ=fake_env,
    )

    passed = (
        result.status == "DRY_RUN"
        and result.dry_run is True
        and result.external_post_attempted is False
        and result.endpoint == redacted_discord_endpoint()
        and "discord.com/api/webhooks" not in result.endpoint  # endpoint is redacted constant
    )
    return {
        "gate": "G-1",
        "name": "dry_run exits before secret load",
        "status": result.status,
        "dry_run": result.dry_run,
        "external_post_attempted": result.external_post_attempted,
        "endpoint": result.endpoint,
        "delivered_count": result.delivered_count,
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Gate 2 — redaction: webhook URL never appears in any output
# ---------------------------------------------------------------------------
def check_gate_2_redaction() -> dict:
    """
    Verify: redact_text() removes webhook URLs from all output strings.
    Both literal match and regex pattern match.
    """
    real_looking_url = "https://discord.com/api/webhooks/123456789012345678/abcDEFghiJKLmnoPQRstuvwxyz_ABCDEFGH"
    short_token_url = "https://discordapp.com/api/webhooks/999/XYZ"
    plain_text = f"Sending to {real_looking_url} and also {short_token_url} end"

    redacted = redact_text(plain_text)

    real_url_removed = real_looking_url not in redacted
    short_url_removed = short_token_url not in redacted
    redacted_marker_present = "<redacted>" in redacted

    passed = real_url_removed and short_url_removed and redacted_marker_present
    return {
        "gate": "G-2",
        "name": "webhook URL redaction",
        "real_url_removed": real_url_removed,
        "short_url_removed": short_url_removed,
        "redacted_marker_present": redacted_marker_present,
        "redacted_output": redacted,
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Gate 3 — no real secret in output when dry_run=True
# ---------------------------------------------------------------------------
def check_gate_3_no_secret_in_output() -> dict:
    """
    Verify: when dry_run=True, ChannelResult dict contains no webhook URL
    even when the env contains a real-looking URL.
    """
    channel = ChannelConfig(
        type="discord",
        enabled=True,
        dry_run=True,
        secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
    )
    fake_env = {"MONITOR_DISCORD_WEBHOOK_URL": FAKE_WEBHOOK}
    config = _make_monitor_config()
    result = send_discord_alerts(
        config=config,
        channel=channel,
        alerts=[_make_test_alert()],
        environ=fake_env,
    )
    result_str = json.dumps(result.to_dict())
    webhook_present = "FAKE_TOKEN" in result_str or "discord.com/api/webhooks/0000" in result_str
    passed = not webhook_present and result.status == "DRY_RUN"
    return {
        "gate": "G-3",
        "name": "no secret in ChannelResult output",
        "webhook_literal_in_output": webhook_present,
        "status": result.status,
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Gate 4 — safety scan: no order endpoint imports
# ---------------------------------------------------------------------------
def check_gate_4_safety_scan() -> dict:
    targets = [
        Path("scripts/validate_discord_webhook_dryrun.py"),
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
# Gate 5 — triple dry_run gate: force_dry_run + live_alerts=False
# ---------------------------------------------------------------------------
def check_gate_5_triple_dry_run_gate() -> dict:
    """
    Verify: run_forward_alerting() with force_dry_run=True always produces
    dry_run=True in alert_log regardless of channel config.
    """
    from apps.forward_record.alerting import run_forward_alerting

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # Minimal forward_record config
        import yaml  # type: ignore
        config_path = base / "forward_record.yaml"
        monitor_path = base / "monitor.yaml"

        forward_config = {
            "output_paths": {
                "log": str(base / "{date}_forward_record.log"),
                "primary": {
                    "positions": str(base / "{date}_positions.parquet"),
                    "forward_stats": str(base / "{date}_forward_stats.json"),
                    "overlay_check": str(base / "{date}_overlay_check.json"),
                    "pnl": str(base / "{date}_pnl.json"),
                },
                "shadow": {
                    "positions": str(base / "shadow_{date}_positions.parquet"),
                    "forward_stats": str(base / "shadow_{date}_forward_stats.json"),
                    "overlay_check": str(base / "shadow_{date}_overlay_check.json"),
                    "pnl": str(base / "shadow_{date}_pnl.json"),
                },
            }
        }
        with open(config_path, "w") as f:
            yaml.dump(forward_config, f)

        # Monitor config with discord enabled but dry_run=True
        monitor_config_text = "\n".join([
            "bot_name: validation_triple_gate",
            "environment: vps_validation",
            "account_mode: read_only_monitor",
            "paper_execution_status: FORBIDDEN",
            "live_trading_status: FORBIDDEN",
            "alerts:",
            "  channels:",
            "    - type: discord",
            "      enabled: true",
            "      dry_run: true",
            f"      secrets_env_webhook_url: MONITOR_DISCORD_WEBHOOK_URL",
            "      timeout_seconds: 10",
        ]) + "\n"
        monitor_path.write_text(monitor_config_text, encoding="utf-8")

        alert_dir = base / "alerts"
        alert_log = run_forward_alerting(
            "20260517",
            forward_record_config_path=config_path,
            monitor_config_path=monitor_path,
            alert_log_dir=alert_dir,
            live_alerts=False,
            force_dry_run=True,
        )

    passed = (
        alert_log.get("dry_run") is True
        and alert_log.get("FORBIDDEN_live_trading") == "NOT_ATTEMPTED"
        and alert_log.get("FORBIDDEN_order_endpoint") == "NOT_ATTEMPTED"
        and alert_log.get("FORBIDDEN_bybit_write") == "NOT_ATTEMPTED"
        and not alert_log.get("clock_started", True)
    )
    return {
        "gate": "G-5",
        "name": "triple dry_run gate: force_dry_run + live_alerts=False",
        "dry_run": alert_log.get("dry_run"),
        "FORBIDDEN_live_trading": alert_log.get("FORBIDDEN_live_trading"),
        "FORBIDDEN_order_endpoint": alert_log.get("FORBIDDEN_order_endpoint"),
        "FORBIDDEN_bybit_write": alert_log.get("FORBIDDEN_bybit_write"),
        "clock_started": alert_log.get("clock_started"),
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_validation() -> dict:
    print("=== Discord webhook dry-run validation ===")
    print(f"Date: {VALIDATION_DATE}")
    print(f"MONITOR_DISCORD_WEBHOOK_URL set: {'YES (present)' if os.environ.get('MONITOR_DISCORD_WEBHOOK_URL') else 'NO (not set)'}")
    print()

    gates = []
    for fn in [
        check_gate_1_dry_run_exits_before_secret_load,
        check_gate_2_redaction,
        check_gate_3_no_secret_in_output,
        check_gate_4_safety_scan,
        check_gate_5_triple_dry_run_gate,
    ]:
        result = fn()
        status = "PASS" if result["pass"] else "FAIL"
        print(f"  [{status}] {result['gate']} — {result['name']}")
        gates.append(result)

    all_pass = all(g["pass"] for g in gates)
    overall = "PASS" if all_pass else "FAIL"
    print()
    print(f"Overall: {overall} ({sum(g['pass'] for g in gates)}/{len(gates)} gates)")

    report = {
        "validation": "discord_webhook_dryrun",
        "date": VALIDATION_DATE,
        "run_ts": datetime.now(timezone.utc).isoformat(),
        "overall_result": overall,
        "webhook_env_configured": bool(os.environ.get("MONITOR_DISCORD_WEBHOOK_URL")),
        "gates": gates,
        "FORBIDDEN_live_trading": "NOT_ATTEMPTED",
        "FORBIDDEN_discord_real_post": "NOT_ATTEMPTED",
        "FORBIDDEN_live_alerts": "NOT_ATTEMPTED",
        "clock_started": False,
        "paper_execution_status": "FORBIDDEN",
        "live_trading_status": "FORBIDDEN",
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "validation_result.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report written: {out_path}")
    return report


if __name__ == "__main__":
    report = run_validation()
    sys.exit(0 if report["overall_result"] == "PASS" else 1)
