"""TASK: GET /v5/position/list complete cursor pagination + network-audit counters.

Root cause covered: the original single-page read returned only the first ~20 rows for an account
with >20 positions. These offline tests drive the real client through a faked transport (no real
network) and prove: all pages merge in order; cursor semantics (not len<limit) drive termination;
repeated/cyclic cursors, malformed responses, a failing later page, and the max-page cap all FAIL
CLOSED (never returning partial data); the read-only request counter equals the page count; and
the mutating counter stays 0.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.demo_readonly_client import DemoReadOnlyClient, DemoPaginationError, _EP_POSITIONS


class _FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _page(rows, next_cursor=""):
    return {"retCode": 0, "retMsg": "OK",
            "result": {"list": list(rows), "nextPageCursor": next_cursor}}


def _rows(prefix, n, side="Buy"):
    return [{"symbol": f"{prefix}{i}USDT", "side": side, "size": "1", "avgPrice": "1"}
            for i in range(n)]


def _urlopen_from_pages(pages_by_cursor):
    """Build a fake urlopen that dispatches by the request's ?cursor= query param."""
    def fake(req, timeout=10):
        import urllib.parse as up
        q = up.parse_qs(up.urlparse(req.full_url).query)
        cursor = q.get("cursor", [""])[0]
        return _FakeResp(pages_by_cursor[cursor])
    return fake


def _client():
    return DemoReadOnlyClient(allow_real_network=True)


# 1. single page, empty cursor
def test_single_page_empty_cursor():
    pages = {"": _page(_rows("S", 7), "")}
    c = _client()
    with patch("urllib.request.urlopen", side_effect=_urlopen_from_pages(pages)):
        pos, prov = c.get_open_positions_paginated()
    assert len(pos) == 7 and prov["page_count"] == 1
    assert prov["termination_reason"] == "empty_cursor"


# 2. two pages merged
def test_two_pages_merged():
    pages = {"": _page(_rows("S", 20), "c1"), "c1": _page(_rows("T", 5, "Sell"), "")}
    c = _client()
    with patch("urllib.request.urlopen", side_effect=_urlopen_from_pages(pages)):
        pos, prov = c.get_open_positions_paginated()
    assert len(pos) == 25 and prov["page_count"] == 2


# 3. three+ pages merged in order
def test_three_pages_merged_in_order():
    pages = {"": _page(_rows("S", 20), "c1"), "c1": _page(_rows("T", 20, "Sell"), "c2"),
             "c2": _page(_rows("U", 11), "")}
    c = _client()
    with patch("urllib.request.urlopen", side_effect=_urlopen_from_pages(pages)):
        pos, prov = c.get_open_positions_paginated()
    assert len(pos) == 51 and prov["page_count"] == 3
    assert pos[0].symbol == "S0USDT" and pos[-1].symbol == "U10USDT"   # page order preserved


# 4. blank cursor terminates (None treated as empty)
def test_none_cursor_terminates():
    pages = {"": {"retCode": 0, "result": {"list": _rows("S", 3), "nextPageCursor": None}}}
    c = _client()
    with patch("urllib.request.urlopen", side_effect=_urlopen_from_pages(pages)):
        pos, prov = c.get_open_positions_paginated()
    assert len(pos) == 3 and prov["termination_reason"] == "empty_cursor"


# 5. repeated cursor -> fail closed
def test_repeated_cursor_fails_closed():
    pages = {"": _page(_rows("S", 2), "c1"), "c1": _page(_rows("T", 2), "c1")}
    c = _client()
    with patch("urllib.request.urlopen", side_effect=_urlopen_from_pages(pages)):
        with pytest.raises(DemoPaginationError):
            c.get_open_positions_paginated()


# 6. A -> B -> A cursor cycle -> fail closed
def test_cursor_cycle_fails_closed():
    pages = {"": _page(_rows("S", 2), "A"), "A": _page(_rows("T", 2), "B"),
             "B": _page(_rows("U", 2), "A")}
    c = _client()
    with patch("urllib.request.urlopen", side_effect=_urlopen_from_pages(pages)):
        with pytest.raises(DemoPaginationError):
            c.get_open_positions_paginated()


# 7. malformed result (not an object) -> fail closed
def test_malformed_result_object_fails_closed():
    c = _client()
    with patch.object(c, "_get", return_value={"retCode": 0, "result": "not-a-dict"}):
        with pytest.raises(DemoPaginationError):
            c._paginate_get(_EP_POSITIONS, {"category": "linear"})


# 8. list is not a list -> fail closed
def test_non_list_payload_fails_closed():
    c = _client()
    with patch.object(c, "_get", return_value={"retCode": 0, "result": {"list": "nope"}}):
        with pytest.raises(DemoPaginationError):
            c._paginate_get(_EP_POSITIONS, {"category": "linear"})


# 9. second page fails -> NO partial first page returned
def test_second_page_failure_returns_no_partial():
    pages = {
        "": _page(_rows("S", 20), "c1"),
        "c1": {"retCode": 10002, "retMsg": "boom", "result": {}},
    }
    c = _client()
    with patch("urllib.request.urlopen", side_effect=_urlopen_from_pages(pages)):
        with pytest.raises(DemoPaginationError):
            c.get_open_positions_paginated()


# 10. max page cap -> fail closed (never-ending fresh cursors)
def test_max_page_cap_fails_closed():
    c = _client()
    calls = {"n": 0}

    def endless(path, params, signed=True):
        calls["n"] += 1
        return {"retCode": 0, "result": {"list": [], "nextPageCursor": f"cur{calls['n']}"}}

    with patch.object(c, "_get", side_effect=endless):
        with pytest.raises(DemoPaginationError):
            c._paginate_get(_EP_POSITIONS, {"category": "linear"}, max_pages=5)
    assert calls["n"] == 5   # stopped exactly at the cap, did not run away


# 11. read-only request counter == actual page count
def test_read_only_counter_equals_page_count():
    pages = {"": _page(_rows("S", 20), "c1"), "c1": _page(_rows("T", 20, "Sell"), "c2"),
             "c2": _page(_rows("U", 11), "")}
    c = _client()
    with patch("urllib.request.urlopen", side_effect=_urlopen_from_pages(pages)):
        _pos, prov = c.get_open_positions_paginated()
    counters = c.network_audit_counters()
    assert counters["private_read_only_request_count"] == prov["page_count"] == 3


# 12. mutating counter stays 0 across pagination
def test_mutating_counter_stays_zero():
    pages = {"": _page(_rows("S", 20), "c1"), "c1": _page(_rows("T", 3, "Sell"), "")}
    c = _client()
    with patch("urllib.request.urlopen", side_effect=_urlopen_from_pages(pages)):
        c.get_open_positions_paginated()
    assert c.network_audit_counters()["private_mutating_request_count"] == 0
