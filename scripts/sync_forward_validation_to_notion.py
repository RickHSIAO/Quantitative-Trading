"""
sync_forward_validation_to_notion.py
TASK-009: Notion Sync for 30-Day Forward Validation Dashboard

Reads the latest row from
    outputs/forward_record/dashboard/validation_30d.csv
and upserts it into a Notion database. Pages are matched by Date.

Usage:
  python3 scripts/sync_forward_validation_to_notion.py            # live sync
  python3 scripts/sync_forward_validation_to_notion.py --dry-run  # preview only

Environment:
  NOTION_TOKEN                          Notion integration token (required)
  NOTION_FORWARD_VALIDATION_DATABASE_ID Target database id        (required)

Exit / stdout tokens (parsed by run_forward_record_daily.sh):
  NOTION_SYNC=SKIP     env not set, CSV missing/empty, or no data row
  NOTION_SYNC=DRY_RUN  --dry-run: payload printed, no API call
  NOTION_SYNC=PASS     upsert succeeded
  NOTION_SYNC=FAIL     schema mismatch or API error

SAFETY INVARIANTS (must never be relaxed):
  - NO trading / order / bybit / private_post / submit / place / create_order imports
  - NO modification of main.py live logic or strategy core
  - paper_execution_status = FORBIDDEN, live_trading_status = FORBIDDEN
  - --dry-run never reaches the network
  - Secrets are never printed; the token is only used as an Authorization header
  - Notion failure must not affect forward record / dashboard / Discord
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Project root on sys.path
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CSV_PATH = ROOT / "outputs" / "forward_record" / "dashboard" / "validation_30d.csv"
SUMMARY_MD_PATH = ROOT / "outputs" / "forward_record" / "dashboard" / "latest_summary.md"

NOTION_TOKEN_ENV = "NOTION_TOKEN"
NOTION_DB_ID_ENV = "NOTION_FORWARD_VALIDATION_DATABASE_ID"
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_API_VERSION = "2022-06-28"

CLOCK_START = "20260518"  # Day 1, authorised by Rick 2026-05-18
TOTAL_DAYS = 30
_D_START = datetime.strptime(CLOCK_START, "%Y%m%d")
VALIDATION_DAY30 = (_D_START + timedelta(days=TOTAL_DAYS - 1)).strftime("%Y%m%d")
REVIEW_DATE = (_D_START + timedelta(days=TOTAL_DAYS)).strftime("%Y%m%d")

SAFETY = {
    "paper_execution_status": "FORBIDDEN",
    "live_trading_status": "FORBIDDEN",
    "order_endpoint_called": False,
    "bybit_write_called": False,
    "external_post_attempted": False,
}

# ---------------------------------------------------------------------------
# Expected Notion property names (must match the database schema exactly)
# Property "Date" is special: it can be Notion type "title" or "date".
# All other properties below must exist with compatible types.
# ---------------------------------------------------------------------------
EXPECTED_PROPERTIES: list[str] = [
    "Date",
    "Validation Day",
    "Days Remaining",
    "Runner Status",
    "Data Source",
    "Safety Scan",
    "Dry Run",
    "Paper Execution Status",
    "Live Trading Status",
    "Signal Count",
    "Daily PnL %",
    "Cumulative PnL %",
    "Max DD %",
    "Alerts Triggered",
    "Review Ready",
    "Notes",
]

# ---------------------------------------------------------------------------
# Property aliases -- maps each canonical (English) name to all accepted forms.
# aliases[0] = English canonical, aliases[1] = Traditional Chinese.
# When the Notion database uses Chinese property names the script resolves the
# canonical name to the Chinese form before building API payloads or query
# filters.  If both forms exist in the schema, Chinese is preferred.
# ---------------------------------------------------------------------------
PROPERTY_ALIASES: dict[str, list[str]] = {
    "Date":                   ["Date",                   "日期"],
    "Validation Day":         ["Validation Day",         "驗證日"],
    "Days Remaining":         ["Days Remaining",         "剩餘天數"],
    "Runner Status":          ["Runner Status",          "執行狀態"],
    "Data Source":            ["Data Source",            "資料來源"],
    "Safety Scan":            ["Safety Scan",            "安全掃描"],
    "Dry Run":                ["Dry Run",                "模擬執行"],
    "Paper Execution Status": ["Paper Execution Status", "紙上執行狀態"],
    "Live Trading Status":    ["Live Trading Status",    "真實交易狀態"],
    "Signal Count":           ["Signal Count",           "訊號數"],
    "Daily PnL %":            ["Daily PnL %",            "當日 PnL %"],
    "Cumulative PnL %":       ["Cumulative PnL %",       "累計 PnL %"],
    "Max DD %":               ["Max DD %",               "最大回撤 %"],
    "Alerts Triggered":       ["Alerts Triggered",       "觸發警報數"],
    "Review Ready":           ["Review Ready",           "可檢視"],
    "Notes":                  ["Notes",                  "備註"],
}

# ---------------------------------------------------------------------------
# Safety self-check -- exit 99 if any forbidden token appears in an import
# ---------------------------------------------------------------------------
_FORBIDDEN_TOKENS = [
    "bybit",
    "ccxt",
    "place_order",
    "create_order",
    "submit_order",
    "private_post",
    "private_put",
    "order_endpoint",
    "live_trading",
    "paper_trading",
    "set_leverage",
    "cancel_order",
]


def safety_self_check() -> None:
    """Abort with exit 99 if this file imports any forbidden module."""
    src = Path(__file__).read_text(encoding="utf-8")
    violations: list[str] = []
    for token in _FORBIDDEN_TOKENS:
        for m in re.finditer(
            r"^\s*(?:import|from)\s+.*" + re.escape(token),
            src,
            re.MULTILINE | re.IGNORECASE,
        ):
            violations.append(m.group().strip())
    if violations:
        print(
            f"SAFETY VIOLATION -- forbidden import: {violations}",
            file=sys.stderr,
        )
        sys.exit(99)
    print("  safety_self_check: PASS")


# ---------------------------------------------------------------------------
# Date helpers (mirror send_forward_discord_summary.py semantics)
# ---------------------------------------------------------------------------

def _iso_date(yyyymmdd: str) -> str | None:
    try:
        d = datetime.strptime(yyyymmdd, "%Y%m%d")
        return d.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def validation_day_label(date: str) -> str:
    """Return human-friendly validation-day label for a YYYYMMDD date."""
    try:
        d_run = datetime.strptime(date, "%Y%m%d")
        d_start = datetime.strptime(CLOCK_START, "%Y%m%d")
        delta = (d_run - d_start).days
    except (ValueError, TypeError):
        return "N/A"
    if delta < 0:
        return "N/A (pre-clock)"
    if delta < TOTAL_DAYS:
        return f"Day {delta + 1} / {TOTAL_DAYS}"
    if delta == TOTAL_DAYS:
        return "Review Day"
    return "Post-Validation"


def days_remaining(date: str) -> int | None:
    try:
        d_run = datetime.strptime(date, "%Y%m%d")
        d_start = datetime.strptime(CLOCK_START, "%Y%m%d")
        delta = (d_run - d_start).days
    except (ValueError, TypeError):
        return None
    if delta < 0:
        return None
    return max(0, TOTAL_DAYS - (delta + 1))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_latest_row() -> dict[str, str] | None:
    if not CSV_PATH.exists():
        return None
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            return dict(row)
    return None


def load_all_rows() -> list[dict[str, str]]:
    """Return all rows from CSV, newest-first (as written by dashboard builder)."""
    if not CSV_PATH.exists():
        return []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def load_row_by_date(date: str) -> dict[str, str] | None:
    """Return the CSV row whose 'date' column equals `date` (YYYYMMDD), or None."""
    for row in load_all_rows():
        if row.get("date", "").strip() == date.strip():
            return row
    return None


def _to_number(value: str | None) -> float | None:
    if value is None or value == "" or value == "N/A" or value == "None":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    return None


def build_record(row: dict[str, str]) -> dict[str, Any]:
    """Convert a CSV row into a normalized record dict (typed values)."""
    date_str = row.get("date", "")
    iso = _iso_date(date_str)

    return {
        "date_yyyymmdd": date_str,
        "date_iso": iso,
        "validation_day": validation_day_label(date_str),
        "days_remaining": days_remaining(date_str),
        "runner_status": row.get("runner_status", "N/A"),
        "data_source": row.get("data_source", "N/A"),
        "safety_scan": row.get("safety_scan", "N/A"),
        "dry_run": _to_bool(row.get("dry_run")),
        "paper_execution_status": row.get(
            "paper_execution_status", "FORBIDDEN"
        ),
        "live_trading_status": row.get("live_trading_status", "FORBIDDEN"),
        "signal_count": _to_number(row.get("signal_count")),
        "daily_pnl_pct": _to_number(row.get("daily_pnl_pct")),
        "cumulative_pnl_pct": _to_number(row.get("cumulative_pnl_pct")),
        "max_dd_pct": _to_number(row.get("max_dd_pct")),
        "alerts_triggered": _to_number(row.get("alerts_triggered")),
        "review_ready": _to_bool(row.get("review_006b_ready")),
        "notes": _build_notes(row),
    }


def _build_notes(row: dict[str, str]) -> str:
    parts = [
        f"strategy=prev3y_crypto/combined_paper_safe_variant",
        f"FORBIDDEN_order_endpoint={row.get('FORBIDDEN_order_endpoint', 'NOT_ATTEMPTED')}",
        f"FORBIDDEN_bybit_write={row.get('FORBIDDEN_bybit_write', 'NOT_ATTEMPTED')}",
    ]
    n_longs = row.get("n_longs")
    n_shorts = row.get("n_shorts")
    if n_longs or n_shorts:
        parts.append(f"n_longs={n_longs or 0}, n_shorts={n_shorts or 0}")
    overlay = row.get("overlay_pass")
    if overlay and overlay != "N/A":
        parts.append(f"overlay_pass={overlay}")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Notion HTTP client (urllib, no external deps)
# ---------------------------------------------------------------------------

class NotionAPIError(Exception):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body


def _notion_request(
    method: str,
    path: str,
    token: str,
    body: dict | None = None,
    timeout: int = 15,
) -> dict:
    url = NOTION_API_BASE + path
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", NOTION_API_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = str(exc)
        raise NotionAPIError(exc.code, err_body) from None
    except urllib.error.URLError as exc:
        raise NotionAPIError(0, f"URLError: {exc.reason}") from None


# ---------------------------------------------------------------------------
# Notion payload building
# ---------------------------------------------------------------------------

def _rt(text: str) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": text}}]}


def _title(text: str) -> dict:
    return {"title": [{"type": "text", "text": {"content": text}}]}


def _select(name: str) -> dict:
    return {"select": {"name": name}}


def _number(value: float | None) -> dict:
    return {"number": value}


def _checkbox(value: bool | None) -> dict:
    return {"checkbox": bool(value) if value is not None else False}


def _date(iso: str | None) -> dict:
    return {"date": {"start": iso} if iso else None}


def build_property_payload(
    record: dict[str, Any],
    schema: dict[str, dict],
) -> dict[str, dict]:
    """Build a Notion 'properties' dict matching the database schema types.

    Property names in the returned dict use the actual names from the schema
    (English or Chinese), resolved via PROPERTY_ALIASES.  Unknown Notion types
    fall back to rich_text (string repr).
    """
    resolved = resolve_schema_names(schema)
    props: dict[str, dict] = {}

    def encode(canonical: str, value: Any) -> dict | None:
        actual = resolved.get(canonical, canonical)
        prop = schema.get(actual)
        if prop is None:
            return None
        ptype = prop.get("type")
        if ptype == "title":
            text = "" if value is None else str(value)
            return _title(text)
        if ptype == "rich_text":
            text = "" if value is None else str(value)
            return _rt(text)
        if ptype == "number":
            if value is None:
                return _number(None)
            try:
                return _number(float(value))
            except (TypeError, ValueError):
                return _number(None)
        if ptype == "checkbox":
            if isinstance(value, bool):
                return _checkbox(value)
            return _checkbox(_to_bool(value if value is None else str(value)))
        if ptype == "select":
            if value is None or value == "":
                return {"select": None}
            return _select(str(value))
        if ptype == "date":
            if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", value):
                return _date(value)
            iso = _iso_date(str(value)) if value is not None else None
            return _date(iso)
        # Fallback
        return _rt("" if value is None else str(value))

    # Mapping from canonical property name -> record value
    value_map: dict[str, Any] = {
        "Date": record["date_iso"] or record["date_yyyymmdd"],
        "Validation Day": record["validation_day"],
        "Days Remaining": record["days_remaining"],
        "Runner Status": record["runner_status"],
        "Data Source": record["data_source"],
        "Safety Scan": record["safety_scan"],
        "Dry Run": record["dry_run"],
        "Paper Execution Status": record["paper_execution_status"],
        "Live Trading Status": record["live_trading_status"],
        "Signal Count": record["signal_count"],
        "Daily PnL %": record["daily_pnl_pct"],
        "Cumulative PnL %": record["cumulative_pnl_pct"],
        "Max DD %": record["max_dd_pct"],
        "Alerts Triggered": record["alerts_triggered"],
        "Review Ready": record["review_ready"],
        "Notes": record["notes"],
    }

    # If the resolved "Date" property is title type, use YYYYMMDD as text
    # (Notion title properties cannot hold date values).
    date_actual = resolved.get("Date", "Date")
    if date_actual in schema and schema[date_actual].get("type") == "title":
        value_map["Date"] = record["date_yyyymmdd"]

    for canonical in EXPECTED_PROPERTIES:
        encoded = encode(canonical, value_map.get(canonical))
        if encoded is not None:
            actual = resolved.get(canonical, canonical)
            props[actual] = encoded

    return props


# ---------------------------------------------------------------------------
# Notion upsert
# ---------------------------------------------------------------------------

def fetch_database_schema(token: str, db_id: str) -> dict[str, dict]:
    db = _notion_request("GET", f"/databases/{db_id}", token)
    props = db.get("properties", {})
    # Each value already has 'type' so we can return as-is.
    return props


def check_required_properties(schema: dict[str, dict]) -> list[str]:
    """Return diagnostics for each canonical property absent from schema.

    Checks both English and Chinese aliases.  Each returned entry is formatted:
      'canonical' (accepted: English | Chinese)
    so operators know exactly which name to add to the Notion database.
    """
    missing: list[str] = []
    for canonical, aliases in PROPERTY_ALIASES.items():
        if not any(a in schema for a in aliases):
            accepted = " | ".join(aliases)
            missing.append(f"{canonical!r} (accepted: {accepted})")
    return missing


def resolve_schema_names(schema: dict[str, dict]) -> dict[str, str]:
    """Return {canonical: actual_name_in_schema} for every PROPERTY_ALIASES entry.

    For each canonical name all accepted aliases are checked; Chinese aliases are
    preferred over English when both exist.  If neither alias is present in the
    schema the canonical name maps to itself (will surface as missing later).
    """
    resolved: dict[str, str] = {}
    for canonical, aliases in PROPERTY_ALIASES.items():
        found: str | None = None
        # Prefer Chinese (last alias) over English (first alias).
        for alias in reversed(aliases):
            if alias in schema:
                found = alias
                break
        resolved[canonical] = found if found is not None else canonical
    return resolved


def find_existing_page(
    token: str,
    db_id: str,
    record: dict[str, Any],
    schema: dict[str, dict],
) -> str | None:
    """Return page_id of an existing row matching Date (or 日期), or None.

    Resolves the date property name via PROPERTY_ALIASES so Chinese-named
    databases are queried with the correct property name.
    """
    resolved  = resolve_schema_names(schema)
    date_actual = resolved.get("Date", "Date")
    date_prop   = schema.get(date_actual, {})
    ptype       = date_prop.get("type")
    body: dict
    if ptype == "title":
        body = {
            "filter": {
                "property": date_actual,
                "title": {"equals": record["date_yyyymmdd"]},
            },
            "page_size": 1,
        }
    elif ptype == "date":
        iso = record["date_iso"]
        if not iso:
            return None
        body = {
            "filter": {
                "property": date_actual,
                "date": {"equals": iso},
            },
            "page_size": 1,
        }
    elif ptype == "rich_text":
        body = {
            "filter": {
                "property": date_actual,
                "rich_text": {"equals": record["date_yyyymmdd"]},
            },
            "page_size": 1,
        }
    else:
        return None

    result = _notion_request("POST", f"/databases/{db_id}/query", token, body)
    pages = result.get("results", [])
    if pages:
        return pages[0].get("id")
    return None


def upsert_page(
    token: str,
    db_id: str,
    record: dict[str, Any],
    schema: dict[str, dict],
) -> tuple[str, str]:
    """Create or update a page. Returns (action, page_id)."""
    props = build_property_payload(record, schema)
    existing_id = find_existing_page(token, db_id, record, schema)
    if existing_id:
        SAFETY["external_post_attempted"] = True
        _notion_request(
            "PATCH",
            f"/pages/{existing_id}",
            token,
            {"properties": props},
        )
        return "UPDATED", existing_id
    SAFETY["external_post_attempted"] = True
    created = _notion_request(
        "POST",
        "/pages",
        token,
        {"parent": {"database_id": db_id}, "properties": props},
    )
    return "CREATED", created.get("id", "")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _redact_token(s: str, token: str) -> str:
    if token and token in s:
        return s.replace(token, "<redacted>")
    return s


# ---------------------------------------------------------------------------
# Row selection helpers (TASK-013)
# ---------------------------------------------------------------------------

_SYNTHETIC_SCHEMA: dict[str, dict] = {
    "Date": {"type": "date"},
    "Validation Day": {"type": "rich_text"},
    "Days Remaining": {"type": "number"},
    "Runner Status": {"type": "select"},
    "Data Source": {"type": "rich_text"},
    "Safety Scan": {"type": "select"},
    "Dry Run": {"type": "checkbox"},
    "Paper Execution Status": {"type": "select"},
    "Live Trading Status": {"type": "select"},
    "Signal Count": {"type": "number"},
    "Daily PnL %": {"type": "number"},
    "Cumulative PnL %": {"type": "number"},
    "Max DD %": {"type": "number"},
    "Alerts Triggered": {"type": "number"},
    "Review Ready": {"type": "checkbox"},
    "Notes": {"type": "rich_text"},
}


def _parse_cli() -> tuple[bool, bool, str | None]:
    """
    Parse CLI args. Returns (dry_run, sync_all, date_arg).
    Priority: --date > --all > default (latest row).
    """
    args = sys.argv[1:]
    dry_run  = "--dry-run" in args
    sync_all = "--all"     in args
    date_arg: str | None = None
    for i, a in enumerate(args):
        if a == "--date" and i + 1 < len(args):
            date_arg = args[i + 1]
            break
        if a.startswith("--date="):
            date_arg = a.split("=", 1)[1]
            break
    return dry_run, sync_all, date_arg


def _select_rows(sync_all: bool, date_arg: str | None) -> tuple[list[dict[str, str]], str]:
    """Return (rows, mode_description). mode: latest | date:<YYYYMMDD> | all."""
    if date_arg:
        row = load_row_by_date(date_arg)
        return ([row], f"date:{date_arg}") if row is not None else ([], f"date:{date_arg}")
    if sync_all:
        return load_all_rows(), "all"
    row = load_latest_row()
    return ([row], "latest") if row is not None else ([], "latest")


def _preview_dry_run(rows: list[dict[str, str]]) -> None:
    for i, row in enumerate(rows):
        record = build_record(row)
        props  = build_property_payload(record, _SYNTHETIC_SCHEMA)
        print(f"  === ROW {i+1}/{len(rows)}: date={record['date_yyyymmdd']} ===")
        for k, v in props.items():
            try:
                preview = json.dumps(v, ensure_ascii=False)
            except (TypeError, ValueError):
                preview = str(v)
            print(f"    {k}: {preview}")
    print()
    print("  alias_support: ENABLED (Chinese property names accepted)")
    print("  example_aliases: Date/\u65e5\u671f, \u9a57\u8b49\u65e5, \u5269\u9918\u5929\u6578 ...")


def main() -> int:
    dry_run, sync_all, date_arg = _parse_cli()

    print("sync_forward_validation_to_notion.py")
    print(f"  dry_run={dry_run}")
    if date_arg:
        print(f"  mode=date:{date_arg}")
    elif sync_all:
        print("  mode=all")
    else:
        print("  mode=latest")
    print()

    safety_self_check()

    # ── Row selection ────────────────────────────────────────────────────
    rows, mode = _select_rows(sync_all, date_arg)
    selected_rows = len(rows)

    if selected_rows == 0:
        if date_arg:
            print(f"  WARNING: date {date_arg} not found in {CSV_PATH}")
            print("  NOTION_SYNC=SKIP (date not in CSV)")
        else:
            print(f"  WARNING: {CSV_PATH} not found or empty")
            print("  NOTION_SYNC=SKIP (no data)")
        return 0

    print(f"  selected_rows={selected_rows}  mode={mode}")
    if selected_rows <= 3:
        for r in rows:
            print(f"    date={r.get('date','?')}  runner_status={r.get('runner_status','?')}"
                  f"  daily_pnl_pct={r.get('daily_pnl_pct','?')}%")
    print()

    # ── Dry-run path ─────────────────────────────────────────────────────
    if dry_run:
        _preview_dry_run(rows)
        print()
        print("  NOTION_SYNC=DRY_RUN (no API call attempted)")
        print(f"  selected_rows={selected_rows}  processed_rows=0")
        print("  created_count=0  updated_count=0")
        print()
        print("  safety gates:")
        for k, v in SAFETY.items():
            print(f"    {k} = {v}")
        return 0

    # ── Live path ────────────────────────────────────────────────────────
    token = os.environ.get(NOTION_TOKEN_ENV, "").strip()
    db_id = os.environ.get(NOTION_DB_ID_ENV, "").strip()
    if not token or not db_id:
        if not token:
            print(f"  {NOTION_TOKEN_ENV} not set in environment")
        if not db_id:
            print(f"  {NOTION_DB_ID_ENV} not set in environment")
        print("  NOTION_SYNC=SKIP")
        return 0

    # Discover schema (once; reused across all rows)
    try:
        schema = fetch_database_schema(token, db_id)
    except NotionAPIError as exc:
        msg = _redact_token(str(exc), token)
        print(f"  ERROR fetching database schema: {msg}", file=sys.stderr)
        print("  NOTION_SYNC=FAIL", file=sys.stderr)
        print("  NOTION_SYNC=FAIL")
        return 1

    missing = check_required_properties(schema)
    if missing:
        print(f"  ERROR: Notion database missing required properties: {missing}",
              file=sys.stderr)
        print("  NOTION_SYNC=FAIL", file=sys.stderr)
        print("  NOTION_SYNC=FAIL")
        return 1

    # ── Multi-row upsert loop ─────────────────────────────────────────────
    created_count  = 0
    updated_count  = 0
    failed_count   = 0
    processed_rows = 0

    for i, row in enumerate(rows):
        record     = build_record(row)
        date_label = record["date_yyyymmdd"]
        print(f"  [{i+1}/{selected_rows}] upserting date={date_label} ...")
        try:
            action, _ = upsert_page(token, db_id, record, schema)
            if action == "created":
                created_count += 1
            else:
                updated_count += 1
            processed_rows += 1
            print(f"    {action}: {date_label}")
        except NotionAPIError as exc:
            msg = _redact_token(str(exc), token)
            print(f"    ERROR: {msg}", file=sys.stderr)
            print(f"    NOTION_SYNC_ROW=FAIL date={date_label}")
            failed_count += 1
        except Exception as exc:
            msg = _redact_token(f"{exc.__class__.__name__}: {exc}", token)
            print(f"    ERROR: {msg}", file=sys.stderr)
            print(f"    NOTION_SYNC_ROW=FAIL date={date_label}")
            failed_count += 1

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print(f"  selected_rows={selected_rows}")
    print(f"  processed_rows={processed_rows}")
    print(f"  created_count={created_count}")
    print(f"  updated_count={updated_count}")
    print(f"  failed_count={failed_count}")

    if failed_count > 0 and processed_rows == 0:
        print("  NOTION_SYNC=FAIL")
        return 1
    elif failed_count > 0:
        print(f"  NOTION_SYNC=PASS (partial: {failed_count} rows failed)")
    else:
        print(f"  NOTION_SYNC=PASS ({processed_rows} rows upserted)")

    print()
    print("  safety gates:")
    for k, v in SAFETY.items():
        print(f"    {k} = {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())