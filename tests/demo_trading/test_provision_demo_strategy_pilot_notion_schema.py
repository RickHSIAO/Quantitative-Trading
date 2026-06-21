"""Tests for TASK-014BV one-shot Notion Pilot schema provisioner.

Fully offline: fake Notion HTTP, no real network, no page writes, no Bybit.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

prov = importlib.import_module("scripts.provision_demo_strategy_pilot_notion_schema")

ENV = {"NOTION_TOKEN": "SECRET_TOKEN", "NOTION_PILOT_DATABASE_ID": "SECRET_DB"}


def correct_schema(*, extra=None):
    s = {prov.TITLE_PROPERTY: {"type": "title"}}
    for n in prov.NUMBER_PROPS:
        s[n] = {"type": "number"}
    for n in prov.DATE_PROPS:
        s[n] = {"type": "date"}
    for n in prov.RICH_TEXT_PROPS:
        s[n] = {"type": "rich_text"}
    if extra:
        s.update(extra)
    return s


class FakeHttp:
    def __init__(self, *, sources, schema, fail=None):
        self.sources = sources
        self.schema = {k: dict(v) for k, v in schema.items()}
        self.fail = fail
        self.calls = []
        self.bodies = []

    def request(self, method, path, token, body=None):
        self.calls.append((method, path))
        self.bodies.append((method, path, body))
        if self.fail and self.fail in path:
            raise RuntimeError("boom")
        if path.startswith("/pages"):
            raise AssertionError("provisioner must never touch pages")
        if method == "GET" and path.startswith("/databases/"):
            return {"data_sources": self.sources}
        if method == "GET" and path.startswith("/data_sources/"):
            return {"properties": {k: dict(v) for k, v in self.schema.items()}}
        if method == "PATCH" and path.startswith("/data_sources/"):
            for name, spec in (body or {}).get("properties", {}).items():
                if "name" in spec:  # rename
                    self.schema[spec["name"]] = self.schema.pop(name)
                else:  # addition
                    t = next(k for k in spec if k in ("date", "number", "rich_text"))
                    self.schema[name] = {"type": t}
            return {}
        return {}

    def patches(self):
        return [b for (m, p, b) in self.bodies if m == "PATCH"]

    def title_count(self):
        return sum(1 for v in self.schema.values() if v.get("type") == "title")


def run(http, *, apply=False, ack=False, env=None, selector=None):
    return prov.provision(http=http, env=ENV if env is None else env,
                          apply=apply, acknowledged=ack, selector=selector)


# ---------------------------------------------------------------------------
# Plan / apply gating
# ---------------------------------------------------------------------------


def test_plan_performs_no_patch():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    r = run(http, apply=False)
    assert r["status"] == "PLAN_CHANGES_REQUIRED"
    assert http.patches() == []


def test_apply_requires_both_flags():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    r = run(http, apply=True, ack=False)
    assert r["status"] == "REFUSED_NOT_AUTHORIZED"
    assert http.patches() == []
    http2 = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    r2 = run(http2, apply=True, ack=True)
    assert r2["status"] == "APPLIED" and len(http2.patches()) == 1


# ---------------------------------------------------------------------------
# Title rename
# ---------------------------------------------------------------------------


def test_title_rename_from_chinese():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    r = run(http, apply=True, ack=True)
    assert r["title_rename"]["from"] == "名稱" and r["title_rename"]["to"] == "Pilot ID"
    assert http.title_count() == 1 and "Pilot ID" in http.schema
    assert http.schema["Pilot ID"]["type"] == "title"


def test_title_rename_from_name():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"Name": {"type": "title"}})
    r = run(http, apply=True, ack=True)
    assert r["title_rename"]["from"] == "Name"
    assert http.title_count() == 1 and http.schema["Pilot ID"]["type"] == "title"


def test_already_named_pilot_id_no_rename():
    http = FakeHttp(sources=[{"id": "ds1"}], schema=correct_schema())
    r = run(http, apply=True, ack=True)
    assert r["status"] == "NO_CHANGES_REQUIRED"
    assert r["title_rename"]["needed"] is False
    assert http.patches() == []


def test_exactly_one_title_retained():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    run(http, apply=True, ack=True)
    assert http.title_count() == 1


# ---------------------------------------------------------------------------
# Additions / types / unrelated retention
# ---------------------------------------------------------------------------


def test_all_required_fields_added():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    run(http, apply=True, ack=True)
    for name in list(prov.NUMBER_PROPS) + list(prov.DATE_PROPS) + list(prov.RICH_TEXT_PROPS):
        assert name in http.schema


def test_canonical_types_correct():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    run(http, apply=True, ack=True)
    assert http.schema["Date"]["type"] == "date"
    assert http.schema["Signal Count"]["type"] == "number"
    assert http.schema["Realized PnL USDT"]["type"] == "number"
    assert http.schema["Idempotency Key"]["type"] == "rich_text"
    assert http.schema["Notes"]["type"] == "rich_text"


def test_unrelated_fields_retained():
    schema = {"名稱": {"type": "title"}, "Misc Field": {"type": "rich_text"},
              "Owner": {"type": "people"}}
    http = FakeHttp(sources=[{"id": "ds1"}], schema=schema)
    run(http, apply=True, ack=True)
    assert "Misc Field" in http.schema and "Owner" in http.schema


# ---------------------------------------------------------------------------
# Incompatible / data source failures
# ---------------------------------------------------------------------------


def test_incompatible_field_refuses():
    schema = correct_schema()
    schema["Date"] = {"type": "number"}  # canonical Date must be date
    http = FakeHttp(sources=[{"id": "ds1"}], schema=schema)
    r = run(http, apply=True, ack=True)
    assert r["status"] == "NOTION_DATABASE_SCHEMA_INCOMPATIBLE"
    assert http.patches() == []
    assert any("Date" in c for c in r["incompatible"])


def test_multiple_data_sources_refuse():
    http = FakeHttp(sources=[{"id": "a"}, {"id": "b"}], schema={"名稱": {"type": "title"}})
    r = run(http, apply=False)
    assert r["status"] == "MULTIPLE_DATA_SOURCES" and http.patches() == []


def test_no_data_source_refuse():
    http = FakeHttp(sources=[], schema={"名稱": {"type": "title"}})
    r = run(http, apply=False)
    assert r["status"] == "NO_DATA_SOURCE"


def test_data_source_selector_used_when_multiple():
    http = FakeHttp(sources=[{"id": "a"}, {"id": "b"}], schema={"名稱": {"type": "title"}})
    r = run(http, apply=False, selector="a")
    assert r["status"] == "PLAN_CHANGES_REQUIRED"


def test_database_inaccessible_fails_closed():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}}, fail="/databases/")
    r = run(http, apply=False)
    assert r["status"] == "DATABASE_INACCESSIBLE"


def test_credential_missing_fails_closed():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    assert run(http, apply=False, env={})["status"] == "CREDENTIAL_MISSING"
    assert run(http, apply=False, env={"NOTION_TOKEN": "t"})["status"] == "CREDENTIAL_MISSING"


# ---------------------------------------------------------------------------
# Idempotency / post-apply validation
# ---------------------------------------------------------------------------


def test_idempotent_rerun():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    run(http, apply=True, ack=True)
    before = dict(http.schema)
    r2 = run(http, apply=True, ack=True)
    assert r2["status"] == "NO_CHANGES_REQUIRED"
    assert len(http.patches()) == 1  # no second PATCH
    assert http.schema == before  # no duplicate / no change


def test_post_apply_validation_runs_and_passes():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    r = run(http, apply=True, ack=True)
    assert r["post_apply_validation"]["ok"] is True
    assert r["post_apply_validation"]["missing"] == []


# ---------------------------------------------------------------------------
# No page ops / no secrets / safety scans
# ---------------------------------------------------------------------------


def test_no_page_create_or_update():
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    run(http, apply=True, ack=True)
    assert not any(p.startswith("/pages") for (m, p) in http.calls)


def test_no_secrets_in_output_or_errors():
    # success path
    http = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}})
    r = run(http, apply=True, ack=True)
    assert "SECRET_TOKEN" not in json.dumps(r) and "SECRET_DB" not in json.dumps(r)
    # failure path (patch fails)
    http2 = FakeHttp(sources=[{"id": "ds1"}], schema={"名稱": {"type": "title"}}, fail="/data_sources/")
    r2 = run(http2, apply=True, ack=True)
    assert "SECRET_TOKEN" not in json.dumps(r2) and "SECRET_DB" not in json.dumps(r2)


def test_uses_notion_api_version_2025_09_03():
    assert prov.NOTION_API_VERSION == "2025-09-03"


def test_no_bybit_or_order_imports():
    src = (ROOT / "scripts/provision_demo_strategy_pilot_notion_schema.py").read_text(encoding="utf-8")
    assert "/v5/order" not in src and "order/create" not in src and "api-demo.bybit.com" not in src
    assert "BybitExecutor" not in src
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith(("import ", "from ")):
            assert "executors.bybit" not in s and "src.risk" not in s and not s.startswith("import main")


def test_no_retry_loop():
    src = (ROOT / "scripts/provision_demo_strategy_pilot_notion_schema.py").read_text(encoding="utf-8")
    assert "while True" not in src
    for token in ("import tenacity", "import backoff", "@retry"):
        assert token not in src


def test_json_only_main_valid(monkeypatch, capsys):
    monkeypatch.setenv("NOTION_TOKEN", "tok")
    monkeypatch.setenv("NOTION_PILOT_DATABASE_ID", "db")
    http = FakeHttp(sources=[{"id": "ds1"}], schema=correct_schema())
    rc = prov.main(["--plan", "--json-only"], http=http)
    payload = json.loads(capsys.readouterr().out)
    assert payload["task_id"] == "TASK-014BV" and payload["status"] == "NO_CHANGES_REQUIRED"
    assert rc == 0


def test_documentation_updated():
    for rel in ("README.md", "docs/research/commands/NEXT_ACTION.md",
                "docs/research/commands/COMMAND_LOG.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "TASK-014BV" in text
