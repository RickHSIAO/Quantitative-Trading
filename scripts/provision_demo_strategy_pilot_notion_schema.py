"""TASK-014BV -- one-shot, explicitly authorized Notion Pilot schema provisioner.

This is a SEPARATE, manually-run provisioning tool. The normal daily runner
never auto-creates or auto-alters a Notion schema; this script performs exactly
one explicitly-authorized schema PATCH when (and only when) both
``--apply`` and ``--i-understand-this-modifies-notion-schema`` are supplied.

It uses Notion API version 2025-09-03 (databases expose child *data sources*;
properties live on the data source). It:
  * reads NOTION_TOKEN and NOTION_PILOT_DATABASE_ID;
  * retrieves the database and discovers its single child data source;
  * renames the existing title property (``名稱`` / ``Name``) to ``Pilot ID``
    (never creating a second title);
  * adds the missing canonical Pilot properties with fixed types;
  * is idempotent (an already-correct schema -> NO_CHANGES_REQUIRED);
  * fails closed on missing credentials, no/multiple data sources, an
    inaccessible database, or an incompatible existing canonical property;
  * after apply, re-reads the data source and runs the SAME full Pilot payload
    compatibility validation used by the delivery transport.

It never creates/updates a Notion page, never calls Discord, and never imports
or calls any Bybit / order / executor code. Zero automatic retries. Secrets
(token, database id, data-source id, authorization header) are never printed or
serialized.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Mapping

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_strategy_pilot_delivery_transport as dt  # noqa: E402
from src import demo_strategy_pilot_notion_sync as ns  # noqa: E402

TASK_ID = "TASK-014BV"
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_API_VERSION = "2025-09-03"
NOTION_TOKEN_ENV = "NOTION_TOKEN"
NOTION_PILOT_DATABASE_ID_ENV = "NOTION_PILOT_DATABASE_ID"

TITLE_PROPERTY = "Pilot ID"
TITLE_RENAME_FROM = ("名稱", "Name")

# Canonical non-title Pilot property types.
DATE_PROPS = ("Date",)
NUMBER_PROPS = (
    "Pilot Day", "Signal Count", "Order Count", "Filled Count", "Closed Trade Count",
    "Realized PnL USDT", "Trading Fees USDT", "Funding PnL USDT", "Daily Net PnL USDT",
    "Cumulative Net PnL USDT", "Daily Return %", "Cumulative Return %", "Max Drawdown %",
)
RICH_TEXT_PROPS = (
    "Idempotency Key", "Runner Status", "Current Position", "Excel Export Status",
    "Notion Sync Status", "Discord Notify Status", "Input Fingerprint", "Plan Fingerprint",
    "Alerts Triggered", "Notes",
)
CANONICAL_TYPE: dict[str, str] = {}
for _p in DATE_PROPS:
    CANONICAL_TYPE[_p] = "date"
for _p in NUMBER_PROPS:
    CANONICAL_TYPE[_p] = "number"
for _p in RICH_TEXT_PROPS:
    CANONICAL_TYPE[_p] = "rich_text"

_TYPE_BODY = {"date": {"date": {}}, "number": {"number": {"format": "number"}},
              "rich_text": {"rich_text": {}}}


class ProvisionError(Exception):
    """Fail-closed provisioning error (sanitized)."""


# ---------------------------------------------------------------------------
# Real HTTP client (Notion 2025-09-03). Token only as a header; never logged.
# ---------------------------------------------------------------------------


class _ProvisionNotionHttp:
    def request(self, method: str, path: str, token: str, body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(NOTION_API_BASE + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Notion-Version", NOTION_API_VERSION)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def discover_data_source(http: Any, token: str, db_id: str, selector: str | None = None) -> str:
    try:
        db = http.request("GET", f"/databases/{db_id}", token)
    except Exception as exc:  # noqa: BLE001  (sanitized; no id/token in message)
        raise ProvisionError("DATABASE_INACCESSIBLE") from exc
    sources = db.get("data_sources", []) if isinstance(db, Mapping) else []
    if selector:
        return selector
    if not sources:
        raise ProvisionError("NO_DATA_SOURCE")
    if len(sources) > 1:
        raise ProvisionError("MULTIPLE_DATA_SOURCES")
    ds_id = sources[0].get("id")
    if not ds_id:
        raise ProvisionError("NO_DATA_SOURCE")
    return str(ds_id)


def _title_name(schema: Mapping[str, Any]) -> str | None:
    for name, spec in schema.items():
        if isinstance(spec, Mapping) and spec.get("type") == "title":
            return name
    return None


def compute_schema_plan(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Compute the rename/additions/incompatibilities. Pure; no I/O."""
    title = _title_name(schema)
    rename_from = None
    if title is None:
        # No title at all is an unexpected/incompatible database.
        return {"incompatible": ["<title>:missing->expected['title']"], "rename_from": None,
                "additions": {}, "no_changes": False, "title": None}
    if title != TITLE_PROPERTY:
        rename_from = title
        # A non-title property already named "Pilot ID" would collide on rename.
        spec = schema.get(TITLE_PROPERTY)
        if isinstance(spec, Mapping) and spec.get("type") != "title":
            return {"incompatible": [f"{TITLE_PROPERTY}:{spec.get('type')}->expected['title']"],
                    "rename_from": None, "additions": {}, "no_changes": False, "title": title}

    additions: dict[str, str] = {}
    incompatible: list[str] = []
    for name, ctype in CANONICAL_TYPE.items():
        spec = schema.get(name)
        if spec is None:
            additions[name] = ctype
            continue
        actual_type = spec.get("type") if isinstance(spec, Mapping) else None
        if actual_type != ctype:
            incompatible.append(f"{name}:{actual_type}->expected['{ctype}']")
    no_changes = (rename_from is None) and (not additions) and (not incompatible)
    return {"rename_from": rename_from, "additions": additions, "incompatible": sorted(incompatible),
            "no_changes": no_changes, "title": title}


def build_patch_body(plan: Mapping[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = {}
    if plan.get("rename_from"):
        props[plan["rename_from"]] = {"name": TITLE_PROPERTY}
    for name, ctype in plan.get("additions", {}).items():
        props[name] = dict(_TYPE_BODY[ctype])
    return {"properties": props}


def _full_payload_names() -> list[str]:
    return list(ns.build_notion_payload("PILOT", {"date": "1970-01-01"})["properties"].keys())


def provision(*, http: Any, env: Mapping[str, str], apply: bool, acknowledged: bool,
              selector: str | None = None) -> dict[str, Any]:
    """Plan or apply the Pilot schema provisioning. Returns a sanitized result."""
    result: dict[str, Any] = {
        "task_id": TASK_ID,
        "mode": "apply" if apply else "plan",
        "notion_api_version": NOTION_API_VERSION,
        "data_source_present": False,
        "title_rename": None,
        "planned_additions": {},
        "incompatible": [],
        "applied": False,
        "post_apply_validation": None,
        "status": "",
        "detail": "",
    }

    token = (env.get(NOTION_TOKEN_ENV, "") or "").strip()
    db_id = (env.get(NOTION_PILOT_DATABASE_ID_ENV, "") or "").strip()
    if not token or not db_id:
        result["status"] = "CREDENTIAL_MISSING"
        result["detail"] = "NOTION_TOKEN and NOTION_PILOT_DATABASE_ID are required"
        return result

    if apply and not acknowledged:
        result["status"] = "REFUSED_NOT_AUTHORIZED"
        result["detail"] = "apply requires --i-understand-this-modifies-notion-schema"
        return result

    try:
        ds_id = discover_data_source(http, token, db_id, selector)
    except ProvisionError as exc:
        result["status"] = str(exc)
        result["detail"] = str(exc)
        return result
    result["data_source_present"] = True

    try:
        ds = http.request("GET", f"/data_sources/{ds_id}", token)
    except Exception:  # noqa: BLE001
        result["status"] = "DATABASE_INACCESSIBLE"
        result["detail"] = "DATABASE_INACCESSIBLE"
        return result
    schema = dict(ds.get("properties", {}) or {})

    plan = compute_schema_plan(schema)
    result["title_rename"] = {"from": plan.get("rename_from"), "to": TITLE_PROPERTY,
                              "needed": bool(plan.get("rename_from"))}
    result["planned_additions"] = dict(plan.get("additions", {}))
    result["incompatible"] = list(plan.get("incompatible", []))

    if plan.get("incompatible"):
        result["status"] = "NOTION_DATABASE_SCHEMA_INCOMPATIBLE"
        result["detail"] = "incompatible existing canonical properties (no write performed)"
        return result

    if plan.get("no_changes"):
        result["status"] = "NO_CHANGES_REQUIRED"
        result["detail"] = "schema already correct"
        return result

    if not apply:
        result["status"] = "PLAN_CHANGES_REQUIRED"
        result["detail"] = "run with --apply --i-understand-this-modifies-notion-schema to apply"
        return result

    # APPLY: exactly one PATCH containing only the rename/additions.
    body = build_patch_body(plan)
    try:
        http.request("PATCH", f"/data_sources/{ds_id}", token, body)
    except Exception as exc:  # noqa: BLE001
        result["status"] = "PATCH_FAILED"
        result["detail"] = dt._redact(f"patch failed: {exc}", [token, db_id, ds_id])
        return result
    result["applied"] = True

    # Re-read and run the SAME full payload compatibility validation.
    try:
        ds_after = http.request("GET", f"/data_sources/{ds_id}", token)
    except Exception:  # noqa: BLE001
        result["status"] = "DATABASE_INACCESSIBLE"
        result["detail"] = "post-apply re-read failed"
        return result
    schema_after = dict(ds_after.get("properties", {}) or {})
    missing, incompatible = dt.validate_payload_schema(schema_after, _full_payload_names())
    result["post_apply_validation"] = {"missing": sorted(missing), "incompatible": sorted(incompatible),
                                       "ok": not missing and not incompatible}
    if missing or incompatible:
        result["status"] = "APPLIED_BUT_VALIDATION_FAILED"
        result["detail"] = "post-apply payload validation failed"
        return result
    result["status"] = "APPLIED"
    result["detail"] = "schema provisioned and validated"
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="provision_demo_strategy_pilot_notion_schema.py",
        description="One-shot Notion Pilot schema provisioner (plan by default; apply is explicitly gated).",
    )
    p.add_argument("--plan", action="store_true", help="read-only preview (default)")
    p.add_argument("--apply", action="store_true", help="apply exactly one schema PATCH (requires ack flag)")
    p.add_argument("--i-understand-this-modifies-notion-schema", dest="ack", action="store_true")
    p.add_argument("--data-source-id", default=None, help="explicit data source selector (when multiple exist)")
    p.add_argument("--json-only", action="store_true")
    return p


_EXIT = {
    "APPLIED": 0, "NO_CHANGES_REQUIRED": 0, "PLAN_CHANGES_REQUIRED": 0,
    "CREDENTIAL_MISSING": 2, "REFUSED_NOT_AUTHORIZED": 2,
    "NO_DATA_SOURCE": 3, "MULTIPLE_DATA_SOURCES": 3, "DATABASE_INACCESSIBLE": 3,
    "NOTION_DATABASE_SCHEMA_INCOMPATIBLE": 4, "APPLIED_BUT_VALIDATION_FAILED": 4, "PATCH_FAILED": 4,
}


def main(argv: list[str] | None = None, *, http: Any = None) -> int:
    args = build_parser().parse_args(argv)
    transport = http or _ProvisionNotionHttp()
    result = provision(http=transport, env=os.environ, apply=bool(args.apply),
                       acknowledged=bool(args.ack), selector=args.data_source_id)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return _EXIT.get(result["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
