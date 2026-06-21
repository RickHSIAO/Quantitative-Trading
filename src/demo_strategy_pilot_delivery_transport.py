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

NOTION_DUPLICATE_IDENTITY_CONFLICT = "NOTION_DUPLICATE_IDENTITY_CONFLICT"

# Minimal presence set used only when a caller queries without supplying the
# finalized payload. The authoritative check validates EVERY property the actual
# Pilot payload will send (derived dynamically in _validate_payload_schema).
REQUIRED_PILOT_SCHEMA_PROPS = (
    "Date", "Pilot ID", "Excel Export Status", "Notion Sync Status", "Discord Notify Status",
)

# Optional identity property; when a database provides it, it is preferred for
# lookup and written on create/update. It is never required for compatibility.
IDEMPOTENCY_KEY_PROPERTY = "Idempotency Key"

# Approved property-name aliases (canonical -> acceptable database names).
PROPERTY_ALIASES: dict[str, tuple[str, ...]] = {}

_TITLE_TEXT = ("title", "rich_text")
_NUMBERY = ("number", "rich_text", "title")
_TEXTY = ("rich_text", "title", "select")


def _acceptable_types(name: str) -> tuple[str, ...]:
    """Return the Notion property types compatible with a payload field."""
    if name == "Date":
        return ("date", "title", "rich_text")
    if name == "Pilot Day" or name.endswith("Count"):
        return _NUMBERY
    if (name.endswith("USDT") or name.endswith("%") or "PnL" in name
            or "Return" in name or "Drawdown" in name):
        return _NUMBERY
    return _TEXTY


def resolve_schema_name(name: str, schema: Mapping[str, Any]) -> str | None:
    """Resolve a canonical property name to the actual database property name."""
    if name in schema:
        return name
    for alt in PROPERTY_ALIASES.get(name, ()):
        if alt in schema:
            return alt
    return None


def validate_payload_schema(schema: Mapping[str, Any], names) -> tuple[list[str], list[str]]:
    """Validate that ``names`` (the finalized payload property names) all exist in
    ``schema`` with a compatible Notion type. Returns ``(missing, incompatible)``;
    the incompatible entries are sanitized ``name:type->expected[...]`` strings.
    This is the single shared validator used by both the delivery transport and
    the one-shot schema provisioner."""
    missing: list[str] = []
    incompatible: list[str] = []
    for name in names:
        actual = resolve_schema_name(name, schema)
        if actual is None:
            missing.append(name)
            continue
        ptype = (schema.get(actual, {}) or {}).get("type")
        if ptype not in _acceptable_types(name):
            incompatible.append(f"{name}:{ptype}->expected{list(_acceptable_types(name))}")
    return missing, incompatible


class NotionSchemaIncompatible(Exception):
    """The selected Notion database schema cannot host the full Pilot payload."""


class NotionDuplicateIdentityConflict(Exception):
    """More than one Notion page matched the Pilot/date identity."""


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

    def _resolve(self, name: str, schema: Mapping[str, Any]) -> str | None:
        if name in schema:
            return name
        for alt in PROPERTY_ALIASES.get(name, ()):  # approved name mapping
            if alt in schema:
                return alt
        return None

    def _validate_payload_schema(self, properties: Mapping[str, Any] | None) -> None:
        """Validate EVERY property the finalized payload will send (or the
        minimal presence set when no payload is supplied). Fails closed BEFORE
        any query/create/update; the detail lists missing/incompatible names and
        types but never exposes the token or database id."""
        schema = self._ensure_schema()
        names = list(properties.keys()) if properties else list(REQUIRED_PILOT_SCHEMA_PROPS)
        missing, incompatible = validate_payload_schema(schema, names)
        if missing or incompatible:
            raise NotionSchemaIncompatible(
                f"{NOTION_DATABASE_SCHEMA_INCOMPATIBLE} missing={sorted(missing)} "
                f"incompatible={sorted(incompatible)}")

    def _filter_for(self, name: str, value: str, schema: Mapping[str, Any]) -> dict[str, Any]:
        actual = self._resolve(name, schema)
        ptype = (schema.get(actual, {}) or {}).get("type")
        if ptype == "date":
            return {"property": actual, "date": {"equals": value}}
        if ptype == "title":
            return {"property": actual, "title": {"equals": value}}
        return {"property": actual, "rich_text": {"equals": value}}

    def _build_props(self, properties: Mapping[str, Any], *, pilot_id: str, date: str) -> dict[str, Any]:
        schema = self._ensure_schema()
        out: dict[str, Any] = {}
        for name, value in properties.items():
            actual = self._resolve(name, schema)
            if actual is None:
                continue  # validated earlier; defensive
            ptype = (schema.get(actual, {}) or {}).get("type")
            if ptype == "title":
                out[actual] = {"title": [{"text": {"content": str(value)}}]}
            elif ptype == "rich_text":
                out[actual] = {"rich_text": [{"text": {"content": str(value)}}]}
            elif ptype == "number":
                try:
                    out[actual] = {"number": float(value)}
                except (TypeError, ValueError):
                    out[actual] = {"number": None}
            elif ptype == "date":
                out[actual] = {"date": {"start": str(value)}}
            elif ptype == "select":
                out[actual] = {"select": {"name": str(value)}}
            elif ptype == "checkbox":
                out[actual] = {"checkbox": bool(value)}
        # Write the explicit idempotency key only when the database provides it.
        key_actual = self._resolve(IDEMPOTENCY_KEY_PROPERTY, schema)
        if key_actual:
            ktype = (schema.get(key_actual, {}) or {}).get("type")
            keyval = f"{pilot_id}:{date}"
            if ktype == "title":
                out[key_actual] = {"title": [{"text": {"content": keyval}}]}
            else:
                out[key_actual] = {"rich_text": [{"text": {"content": keyval}}]}
        return out

    @staticmethod
    def _split_key(idempotency_key: str) -> tuple[str, str]:
        if ":" in idempotency_key:
            pilot_id, date = idempotency_key.split(":", 1)
            return pilot_id, date
        return "", idempotency_key

    def query(self, *, database_id: str, idempotency_key: str,
              headers: Mapping[str, str] | None = None,
              properties: Mapping[str, Any] | None = None) -> dict[str, Any]:
        # Full schema validation BEFORE any lookup.
        self._validate_payload_schema(properties)
        schema = self._ensure_schema()
        pilot_id, date = self._split_key(idempotency_key)
        # Prefer an explicit Idempotency Key property; otherwise AND(Pilot ID, Date).
        key_actual = self._resolve(IDEMPOTENCY_KEY_PROPERTY, schema)
        if key_actual:
            flt = self._filter_for(IDEMPOTENCY_KEY_PROPERTY, f"{pilot_id}:{date}", schema)
        else:
            flt = {"and": [self._filter_for("Pilot ID", pilot_id, schema),
                           self._filter_for("Date", date, schema)]}
        try:
            res = self._http.request("POST", f"/databases/{self._db}/query", self._token, {"filter": flt})
        except urllib.error.URLError as exc:
            raise RuntimeError(_redact(f"notion query failed: {exc}", self._secrets())) from exc
        items = res.get("results", []) if isinstance(res, Mapping) else []
        if len(items) > 1:
            raise NotionDuplicateIdentityConflict(
                f"{NOTION_DUPLICATE_IDENTITY_CONFLICT}: {len(items)} pages for {pilot_id}:{date}")
        if items:
            return {"page_id": items[0].get("id")}
        return {}

    def upsert(self, *, database_id: str, page_id: str | None, properties: Mapping[str, Any],
               headers: Mapping[str, str] | None = None) -> dict[str, Any]:
        # Re-validate the full payload schema BEFORE any create/update.
        self._validate_payload_schema(properties)
        pilot_id = str(properties.get("Pilot ID", ""))
        date = str(properties.get("Date", ""))
        props = self._build_props(properties, pilot_id=pilot_id, date=date)
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
    "IDEMPOTENCY_KEY_PROPERTY",
    "NETWORK_NOT_ALLOWED",
    "NOTION_DATABASE_SCHEMA_INCOMPATIBLE",
    "NOTION_DUPLICATE_IDENTITY_CONFLICT",
    "NotionDuplicateIdentityConflict",
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
    "resolve_schema_name",
    "select_notion_database",
    "validate_payload_schema",
]
