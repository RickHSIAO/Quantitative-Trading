from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HeartbeatConfig:
    interval_seconds: int = 60
    failure_threshold: int = 3
    stale_fill_minutes: int = 15


@dataclass(frozen=True)
class PnlConfig:
    daily_delta_warn_pct: float = 5.0
    equity_floor_usd: float = 8_000.0


@dataclass(frozen=True)
class ChannelConfig:
    type: str = "local_jsonl"
    enabled: bool = True
    dry_run: bool = True
    secrets_path: Path = Path("configs/monitor_secrets.local.yaml")
    secrets_env_token: str = ""
    secrets_env_chat_id: str = ""
    secrets_env_webhook_url: str = ""
    timeout_seconds: int = 10


@dataclass(frozen=True)
class AlertsConfig:
    dedup_window_minutes: int = 30
    channels: tuple[ChannelConfig, ...] = (ChannelConfig(),)


@dataclass(frozen=True)
class LoggingConfig:
    bot_log_paths: tuple[str, ...] = ("logs/quantbot/*.log",)
    output_heartbeat: Path = Path("outputs/monitor/prev3y_crypto")
    output_alerts_dir: Path = Path("outputs/monitor/prev3y_crypto/alerts")
    output_log_dir: Path = Path("outputs/logs/prev3y_crypto")


@dataclass(frozen=True)
class MonitorConfig:
    bot_name: str = "prev3y_crypto_paper"
    environment: str = "offline_sample"
    account_mode: str = "read_only_monitor"
    secrets_config_path: Path = Path("configs/monitor_secrets.local.yaml")
    heartbeat: HeartbeatConfig = HeartbeatConfig()
    pnl: PnlConfig = PnlConfig()
    alerts: AlertsConfig = AlertsConfig()
    logging: LoggingConfig = LoggingConfig()
    paper_execution_status: str = "FORBIDDEN"
    live_trading_status: str = "FORBIDDEN"


def load_monitor_config(path: Path) -> MonitorConfig:
    raw = _load_yaml_like(path)
    return monitor_config_from_dict(raw)


def monitor_config_from_dict(raw: dict[str, Any]) -> MonitorConfig:
    heartbeat = raw.get("heartbeat", {})
    pnl = raw.get("pnl", {})
    alerts = raw.get("alerts", {})
    logging = raw.get("logging", {})
    channels = tuple(
        ChannelConfig(
            type=str(channel.get("type", "local_jsonl")),
            enabled=_to_bool(channel.get("enabled", True)),
            dry_run=_to_bool(channel.get("dry_run", True)),
            secrets_path=Path(str(channel.get("secrets_path", "configs/monitor_secrets.local.yaml"))),
            secrets_env_token=str(channel.get("secrets_env_token", "")),
            secrets_env_chat_id=str(channel.get("secrets_env_chat_id", "")),
            secrets_env_webhook_url=str(channel.get("secrets_env_webhook_url", "")),
            timeout_seconds=int(channel.get("timeout_seconds", 10)),
        )
        for channel in alerts.get("channels", [{"type": "local_jsonl", "enabled": True, "dry_run": True}])
    )
    config = MonitorConfig(
        bot_name=str(raw.get("bot_name", "prev3y_crypto_paper")),
        environment=str(raw.get("environment", "offline_sample")),
        account_mode=str(raw.get("account_mode", "read_only_monitor")),
        secrets_config_path=Path(str(raw.get("secrets_config_path", "configs/monitor_secrets.local.yaml"))),
        heartbeat=HeartbeatConfig(
            interval_seconds=int(heartbeat.get("interval_seconds", 60)),
            failure_threshold=int(heartbeat.get("failure_threshold", 3)),
            stale_fill_minutes=int(heartbeat.get("stale_fill_minutes", 15)),
        ),
        pnl=PnlConfig(
            daily_delta_warn_pct=float(pnl.get("daily_delta_warn_pct", 5.0)),
            equity_floor_usd=float(pnl.get("equity_floor_usd", 8000.0)),
        ),
        alerts=AlertsConfig(
            dedup_window_minutes=int(alerts.get("dedup_window_minutes", 30)),
            channels=channels,
        ),
        logging=LoggingConfig(
            bot_log_paths=tuple(str(item) for item in logging.get("bot_log_paths", ["logs/quantbot/*.log"])),
            output_heartbeat=Path(str(logging.get("output_heartbeat", "outputs/monitor/prev3y_crypto"))),
            output_alerts_dir=Path(str(logging.get("output_alerts_dir", "outputs/monitor/prev3y_crypto/alerts"))),
            output_log_dir=Path(str(logging.get("output_log_dir", "outputs/logs/prev3y_crypto"))),
        ),
        paper_execution_status=str(raw.get("paper_execution_status", "FORBIDDEN")),
        live_trading_status=str(raw.get("live_trading_status", "FORBIDDEN")),
    )
    validate_monitor_config(config)
    return config


def validate_monitor_config(config: MonitorConfig) -> None:
    if config.heartbeat.interval_seconds <= 0:
        raise ValueError("heartbeat.interval_seconds must be positive")
    if config.heartbeat.interval_seconds > 120:
        raise ValueError("heartbeat.interval_seconds must be <= 120")
    if config.heartbeat.failure_threshold <= 0:
        raise ValueError("heartbeat.failure_threshold must be positive")
    if config.alerts.dedup_window_minutes <= 0:
        raise ValueError("alerts.dedup_window_minutes must be positive")
    if not config.alerts.channels:
        raise ValueError("at least one alert channel must be configured")
    for channel in config.alerts.channels:
        if channel.timeout_seconds <= 0:
            raise ValueError("channel.timeout_seconds must be positive")
    if config.secrets_config_path.name not in {
        "monitor_secrets.yaml",
        "monitor_secrets.yml",
        "monitor_secrets.local.yaml",
        "monitor_secrets.local.yml",
    }:
        raise ValueError("secrets_config_path must point to a local monitor secrets file")


def _load_yaml_like(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_simple_yaml(text)
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"monitor config must be a mapping: {path}")
    return data


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    current_key: str | None = None
    list_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0 and ":" in stripped:
            key, value = stripped.split(":", 1)
            if value.strip():
                out[key] = _parse_scalar(value.strip())
                current = None
                current_key = None
            else:
                out[key] = {}
                current = out[key]
                current_key = key
            list_key = None
        elif indent == 2 and current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            if value.strip():
                current[key] = _parse_scalar(value.strip())
                list_key = None
            else:
                current[key] = []
                list_key = key
        elif indent == 4 and stripped.startswith("- ") and current is not None and list_key:
            item_text = stripped[2:]
            item: dict[str, Any] = {}
            if ":" in item_text:
                key, value = item_text.split(":", 1)
                item[key] = _parse_scalar(value.strip())
            current[list_key].append(item)
        elif indent == 6 and current_key and list_key and ":" in stripped:
            items = out[current_key][list_key]
            if not items:
                items.append({})
            key, value = stripped.split(":", 1)
            items[-1][key] = _parse_scalar(value.strip())
    return out


def _parse_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
