"""TASK-014BU -- explicitly gated real delivery transports for the Pilot.

Provides narrow, dependency-injected production transports for the Pilot Notion
upsert and Discord notify adapters. A transport is constructed ONLY when the
corresponding explicit ``--allow-*-network`` flag is supplied AND the credential
is present; merely having credentials present never constructs a transport.

Secrets (token / database id / webhook URL) are never printed or serialized;
HTTP errors are sanitized. No Bybit sender / trading executor is imported.

Reuses the approved networking primitives:
  * Discord: ``apps.monitor.channels.base.DefaultHttpClient`` + ``redaction``
  * Notion : a urllib request mirror of ``scripts/sync_forward_validation_to_notion``

Tests inject fake ``http`` objects; no test performs real HTTP.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping

# Sanitized status / detail tokens.
NETWORK_NOT_ALLOWED = "NETWORK_NOT_ALLOWED"
CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
TRANSPORT_CONSTRUCTION_FAILED = "TRANSPORT_CONSTRUCTION_FAILED"
NOTION_DATABASE_SCHEMA_INCOMPATIBLE = "NOTION_DATABASE_SCHEMA_INCOMPATIBLE"
HTTP_DELIVERY_FAILED = "HTTP_DELIVERY_FAILED"
DELIVERY_PASS = "PASS"

NOTION_TOKEN_ENV = "NOTION_TOKEN"
NOTION_PILOT_DATABASE_ID_ENV = "NOTION_PILOT_DATABASE_ID"
NOTION_FORWARD_DATABASE_ID_ENV = "NOTION_FORWARD_VALIDATION_DATABASE_ID"
DISCORD_WEBHOOK_ENV = "MONITOR_DISCORD_WEBHOOK_URL"

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_API_VERSION = "2022-06-28"

# Pilot properties that MUST exist in a Notion database for it to be compatible.
REQUIRED_PILOT_SCHEMA_PROPS = (
    "Date", "Pilot ID", "Excel Export Status", "Notion Sync Status", "Discord Notify Status",
)


class NotionSchemaIncompatible(Exception):
    """The selected Notion database schema cannot host the Pilot row."""


def _redact(text: str, secrets: list[str]) -> str:
    try:
        from apps.monitor.channels.redaction import redact_text
        return redact_text(text, [s for s in secrets if s])
    except Exception:  # noqa: BLE001  (redaction is best-effort; still scrub manually)
        out = text
        for s in secrets:
            if s:
                out = out.replace(s, "***")
        return out


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------


class _RealNotionHttp:
    """Minimal Notion REST client (urllib). Token used only as a header."""

    def request(self, method: str, path: str, token: str, body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(NOTION_API_BASE + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Notion-Version", NOTION_API_VERSION)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))


class RealNotionTransport:
    """Thin transport matching ``NotionDailySync``'s injected interface.

    Self-contained auth via the stored token + database id and an injected
    ``http`` client. Validates schema compatibility before any write and fails
    closed (``NotionSchemaIncompatible``) otherwise. Never logs secrets.
    """

    def __init__(self, *, token: str, database_id: str, http: Any, prefer_source: str = "pilot") -> None:
        self._token = token
        self._db = database_id
        self._http = http
        self.prefer_source = prefer_source
        self._schema: dict[str, Any] | None = None

    def _secrets(self) -> list[str]:
        return [self._token, self._db]

    def _ensure_schema(self) -> dict[str, Any]:
        if self._schema is None:
            db = self._http.request("GET", f"/databases/{self._db}", self._token)
            self._schema = dict(db.get("properties", {}) or {})
        return self._schema

    def _assert_compatible(self) -> None:
        schema = self._ensure_schema()
        missing = [p for p in REQUIRED_PILOT_SCHEMA_PROPS if p not in schema]
        if missing:
            raise NotionSchemaIncompatible(NOTION_DATABASE_SCHEMA_INCOMPATIBLE)

    def _build_props(self, properties: Mapping[str, Any]) -> dict[str, Any]:
        schema = self._ensure_schema()
        out: dict[str, Any] = {}
        for name, value in properties.items():
            spec = schema.get(name)
            if not isinstance(spec, Mapping):
                continue  # never write a property absent from the schema
            ptype = spec.get("type")
            if ptype == "title":
                out[name] = {"title": [{"text": {"content": str(value)}}]}
            elif ptype == "rich_text":
                out[name] = {"rich_text": [{"text": {"content": str(value)}}]}
            elif ptype == "number":
                try:
                    out[name] = {"number": float(value)}
                except (TypeError, ValueError):
                    pass
            elif ptype == "date":
                out[name] = {"date": {"start": str(value)}}
            elif ptype == "select":
                out[name] = {"select": {"name": str(value)}}
            elif ptype == "checkbox":
                out[name] = {"checkbox": bool(value)}
            # other property types are intentionally skipped (no partial write risk)
        return out

    def query(self, *, database_id: str, idempotency_key: str, headers: Mapping[str, str] | None = None) -> dict[str, Any]:
        self._assert_compatible()
        date = idempotency_key.split(":", 1)[1] if ":" in idempotency_key else idempotency_key
        schema = self._ensure_schema()
        date_type = (schema.get("Date", {}) or {}).get("type", "date")
        if date_type == "title":
            flt = {"property": "Date", "title": {"equals": date}}
        else:
            flt = {"property": "Date", "date": {"equals": date}}
        try:
            res = self._http.request("POST", f"/databases/{self._db}/query", self._token, {"filter": flt})
        except urllib.error.URLError as exc:
            raise RuntimeError(_redact(f"notion query failed: {exc}", self._secrets())) from exc
        items = res.get("results", []) if isinstance(res, Mapping) else []
        if items:
            return {"page_id": items[0].get("id")}
        return {}

    def upsert(self, *, database_id: str, page_id: str | None, properties: Mapping[str, Any],
               headers: Mapping[str, str] | None = None) -> dict[str, Any]:
        self._assert_compatible()
        props = self._build_props(properties)
        try:
            if page_id:
                return self._http.request("PATCH", f"/pages/{page_id}", self._token, {"properties": props})
            return self._http.request("POST", "/pages", self._token,
                                      {"parent": {"database_id": self._db}, "properties": props})
        except urllib.error.URLError as exc:
            raise RuntimeError(_redact(f"notion upsert failed: {exc}", self._secrets())) from exc


def select_notion_database(env: Mapping[str, str]) -> tuple[str, str]:
    """Return (database_id, source) preferring the dedicated Pilot database."""
    pilot = (env.get(NOTION_PILOT_DATABASE_ID_ENV, "") or "").strip()
    if pilot:
        return pilot, "pilot"
    fwd = (env.get(NOTION_FORWARD_DATABASE_ID_ENV, "") or "").strip()
    if fwd:
        return fwd, "forward_validation_fallback"
    return "", "none"


def build_notion_transport(*, allow_network: bool, env: Mapping[str, str] | None = None,
                           http: Any = None) -> tuple[RealNotionTransport | None, str]:
    """Construct a Notion transport ONLY when allowed and credentials exist."""
    if not allow_network:
        return None, NETWORK_NOT_ALLOWED
    src = env if env is not None else os.environ
    token = (src.get(NOTION_TOKEN_ENV, "") or "").strip()
    db_id, source = select_notion_database(src)
    if not token or not db_id:
        return None, CREDENTIAL_MISSING
    try:
        transport = RealNotionTransport(token=token, database_id=db_id,
                                        http=http or _RealNotionHttp(), prefer_source=source)
    except Exception:  # noqa: BLE001
        return None, TRANSPORT_CONSTRUCTION_FAILED
    return transport, DELIVERY_PASS


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------


class _RealDiscordHttp:
    """Reuse the approved monitor Discord HTTP client (post_json)."""

    def __init__(self) -> None:
        from apps.monitor.channels.base import DefaultHttpClient
        self._client = DefaultHttpClient()

    def post_json(self, url: str, payload: Mapping[str, Any], timeout_seconds: int) -> Any:
        return self._client.post_json(url, dict(payload), timeout_seconds)


class RealDiscordTransport:
    """Thin transport matching ``DiscordDailyNotify``'s injected interface."""

    def __init__(self, *, http: Any) -> None:
        self._http = http

    def post(self, *, webhook_url: str, content: str) -> dict[str, Any]:
        result = self._http.post_json(webhook_url, {"content": content}, 15)
        status = int(getattr(result, "status_code", 0))
        if 200 <= status < 300:
            return {"status_code": status}
        text = _redact(str(getattr(result, "text", "")), [webhook_url])
        raise RuntimeError(f"{HTTP_DELIVERY_FAILED}: status={status} {text}"[:300])


def build_discord_transport(*, allow_network: bool, env: Mapping[str, str] | None = None,
                            http: Any = None) -> tuple[RealDiscordTransport | None, str]:
    """Construct a Discord transport ONLY when allowed and a webhook exists."""
    if not allow_network:
        return None, NETWORK_NOT_ALLOWED
    src = env if env is not None else os.environ
    webhook = (src.get(DISCORD_WEBHOOK_ENV, "") or "").strip()
    if not webhook:
        return None, CREDENTIAL_MISSING
    try:
        transport = RealDiscordTransport(http=http or _RealDiscordHttp())
    except Exception:  # noqa: BLE001
        return None, TRANSPORT_CONSTRUCTION_FAILED
    return transport, DELIVERY_PASS


__all__ = [
    "CREDENTIAL_MISSING",
    "DELIVERY_PASS",
    "DISCORD_WEBHOOK_ENV",
    "HTTP_DELIVERY_FAILED",
    "NETWORK_NOT_ALLOWED",
    "NOTION_DATABASE_SCHEMA_INCOMPATIBLE",
    "NOTION_FORWARD_DATABASE_ID_ENV",
    "NOTION_PILOT_DATABASE_ID_ENV",
    "NOTION_TOKEN_ENV",
    "NotionSchemaIncompatible",
    "REQUIRED_PILOT_SCHEMA_PROPS",
    "RealDiscordTransport",
    "RealNotionTransport",
    "TRANSPORT_CONSTRUCTION_FAILED",
    "build_discord_transport",
    "build_notion_transport",
    "select_notion_database",
]
