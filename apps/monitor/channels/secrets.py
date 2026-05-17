from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.monitor.config import ChannelConfig


@dataclass(frozen=True)
class ChannelSecrets:
    telegram_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""


def load_channel_secrets(
    channel: ChannelConfig,
    environ: Mapping[str, str] | None = None,
) -> ChannelSecrets:
    env = environ if environ is not None else os.environ
    local = _load_local_secrets(channel.secrets_path)
    telegram = local.get("telegram", {})
    discord = local.get("discord", {})
    token_env = channel.secrets_env_token or "MONITOR_TELEGRAM_TOKEN"
    chat_env = channel.secrets_env_chat_id or "MONITOR_TELEGRAM_CHAT_ID"
    webhook_env = channel.secrets_env_webhook_url or "MONITOR_DISCORD_WEBHOOK_URL"
    return ChannelSecrets(
        telegram_token=env.get(token_env, "") or str(telegram.get("token", "") or ""),
        telegram_chat_id=env.get(chat_env, "") or str(telegram.get("chat_id", "") or ""),
        discord_webhook_url=env.get(webhook_env, "") or str(discord.get("webhook_url", "") or ""),
    )


def _load_local_secrets(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_simple_nested_yaml(text)
    data = yaml.safe_load(text) or {}
    return data if isinstance(data, dict) else {}


def _parse_simple_nested_yaml(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    current_key = ""
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0 and stripped.endswith(":"):
            current_key = stripped[:-1]
            out[current_key] = {}
        elif indent == 2 and current_key and ":" in stripped:
            key, value = stripped.split(":", 1)
            out[current_key][key.strip()] = value.strip().strip('"').strip("'")
    return out
