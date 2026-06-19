"""TASK-014BM_FIX -- regression tests for the signing + status-mapping fix.

These tests reproduce the exact observed Bybit Demo failure
(retCode=10004 "Error sign"), and verify the fix:

1. ``final_status`` is NEVER ``EXECUTED_DEMO_ONLY`` unless all five
   conditions hold:
       * network_attempted == True
       * order_endpoint_called == True
       * order_sent == True
       * bybit_ret_code == 0
       * bybit_order_id non-empty
2. retCode=10004 maps to ``STATUS_BYBIT_REJECTED_NO_ORDER_SENT`` and
   ``order_sent`` remains False; no order id surfaces.
3. The exact serialized JSON body bytes used for the HTTP POST is
   byte-for-byte identical to the JSON body string used for the
   HMAC prehash, with stable compact serialization and lowercase
   JSON booleans.
4. The request includes ``X-BAPI-SIGN-TYPE: 2`` and a lowercase-hex
   HMAC-SHA256 digest in ``X-BAPI-SIGN``.

These tests use only fake sender callables -- no live endpoint, no
real credentials, no network access.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re

import pytest

from src import demo_only_tiny_execution_adapter_tiny_order_execution as bm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _no_env(monkeypatch) -> None:
    for name in (
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)


def _ok_sender_capture(captured: dict):
    def sender(url, headers, body):
        captured["url"] = url
        captured["headers"] = dict(headers)
        captured["body"] = body
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": '{"retCode":0,"retMsg":"OK","result":{"orderId":"demo-oid-fix"}}',
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": "demo-oid-fix"},
            },
        }

    return sender


# ---------------------------------------------------------------------------
# 1. retCode=10004 regression -- exact observed failure
# ---------------------------------------------------------------------------


def test_bybit_retcode_10004_maps_to_rejected_no_order_sent(monkeypatch):
    """The exact observed failure: retCode=10004, retMsg contains
    'Error sign', orderId empty -- must NOT report EXECUTED_DEMO_ONLY."""

    _no_env(monkeypatch)

    def fake_sender(url, headers, body):
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": (
                '{"retCode":10004,"retMsg":"Error sign, please check your '
                'signature generation algorithm","result":{}}'
            ),
            "json": {
                "retCode": 10004,
                "retMsg": (
                    "Error sign, please check your signature generation "
                    "algorithm"
                ),
                "result": {},
            },
        }

    creds = bm.DemoCredentials(api_key="demo_k", api_secret="demo_s")
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=creds,
        sender=fake_sender,
    )
    assert report.network_attempted is True
    assert report.order_endpoint_called is True
    assert report.order_sent is False
    assert report.bybit_order_id == ""
    assert report.bybit_ret_code == 10004
    assert "Error sign" in report.bybit_ret_msg
    # The critical assertion: status must NOT be EXECUTED_DEMO_ONLY.
    assert report.final_status != bm.STATUS_EXECUTED_DEMO_ONLY
    assert report.final_status == bm.STATUS_BYBIT_REJECTED_NO_ORDER_SENT


@pytest.mark.parametrize("retcode", [10003, 10004, 10005, 10010, 110007])
def test_any_nonzero_retcode_never_executed_demo_only(monkeypatch, retcode):
    _no_env(monkeypatch)

    def fake_sender(url, headers, body):
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": "",
            "json": {"retCode": retcode, "retMsg": "x", "result": {}},
        }

    creds = bm.DemoCredentials(api_key="k", api_secret="s")
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=creds,
        sender=fake_sender,
    )
    assert report.final_status != bm.STATUS_EXECUTED_DEMO_ONLY
    assert report.final_status == bm.STATUS_BYBIT_REJECTED_NO_ORDER_SENT
    assert report.order_sent is False
    assert report.bybit_order_id == ""


def test_retcode_zero_but_empty_order_id_never_executed_demo_only(monkeypatch):
    """retCode=0 but no orderId in result must NOT be EXECUTED_DEMO_ONLY."""

    _no_env(monkeypatch)

    def fake_sender(url, headers, body):
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": "",
            "json": {"retCode": 0, "retMsg": "OK", "result": {"orderId": ""}},
        }

    creds = bm.DemoCredentials(api_key="k", api_secret="s")
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=creds,
        sender=fake_sender,
    )
    assert report.final_status != bm.STATUS_EXECUTED_DEMO_ONLY
    assert report.final_status == bm.STATUS_BYBIT_REJECTED_NO_ORDER_SENT
    assert report.order_sent is False


def test_executed_demo_only_requires_all_five_conditions(monkeypatch):
    """Positive control: retCode=0 + non-empty orderId is the only path
    that produces EXECUTED_DEMO_ONLY, and all five reporting fields
    line up."""

    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        sender=_ok_sender_capture({}),
    )
    assert report.final_status == bm.STATUS_EXECUTED_DEMO_ONLY
    assert report.network_attempted is True
    assert report.order_endpoint_called is True
    assert report.order_sent is True
    assert report.bybit_ret_code == 0
    assert report.bybit_order_id == "demo-oid-fix"


# ---------------------------------------------------------------------------
# 2. Signing invariants -- body bytes equal signed body string
# ---------------------------------------------------------------------------


def test_signed_body_string_equals_posted_body_bytes(monkeypatch):
    """The body bytes posted over HTTP must be the exact UTF-8 encoding
    of the body string used in the HMAC prehash."""

    _no_env(monkeypatch)
    captured: dict = {}
    creds = bm.DemoCredentials(
        api_key="demo_k", api_secret="demo_s", recv_window="5000"
    )
    bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=creds,
        sender=_ok_sender_capture(captured),
    )

    posted_body_bytes = captured["body"]
    # Re-serialize the same body_preview that BM uses internally.
    # The same serializer must produce the same exact bytes.
    posted_string = posted_body_bytes.decode("utf-8")
    # Round-trip: bytes -> string -> bytes is byte-equal.
    assert posted_string.encode("utf-8") == posted_body_bytes

    # Verify the HMAC signature in the headers matches HMAC over the
    # exact prehash with the exact posted body string.
    headers = captured["headers"]
    timestamp_ms = headers["X-BAPI-TIMESTAMP"]
    api_key = headers["X-BAPI-API-KEY"]
    recv_window = headers["X-BAPI-RECV-WINDOW"]
    sig = headers["X-BAPI-SIGN"]
    expected = hmac.new(
        creds.api_secret.encode("utf-8"),
        f"{timestamp_ms}{api_key}{recv_window}{posted_string}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert sig == expected, (
        "X-BAPI-SIGN must equal HMAC over the EXACT posted body string -- "
        "otherwise Bybit returns 10004"
    )


def test_serialize_signed_body_is_compact_and_stable():
    sample = {
        "category": "linear",
        "symbol": "SOLUSDT",
        "side": "Buy",
        "orderType": "Market",
        "qty": "0.01",
        "timeInForce": "IOC",
        "reduceOnly": False,
        "closeOnTrigger": False,
        "orderLinkId": "DEMO_ONLY_TINY_BH_xyz",
    }
    s1, b1 = bm._serialize_signed_body(sample)
    s2, b2 = bm._serialize_signed_body(dict(sample))  # dict copy
    assert s1 == s2  # stable
    assert b1 == b2  # stable
    assert b1 == s1.encode("utf-8")  # byte-equal contract
    # Compact: no spaces between separators.
    assert ": " not in s1
    assert ", " not in s1
    # Lowercase JSON booleans, not Python True/False.
    assert ":false" in s1
    assert ":true" not in s1  # no True booleans in this sample
    assert "True" not in s1
    assert "False" not in s1
    # Strings round-trip through json.loads.
    assert json.loads(s1) == sample


def test_serialize_signed_body_preserves_bool_lowercase():
    s, _ = bm._serialize_signed_body({"x": True, "y": False})
    assert '"x":true' in s
    assert '"y":false' in s


def test_x_bapi_sign_type_header_is_two(monkeypatch):
    _no_env(monkeypatch)
    captured: dict = {}
    bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        sender=_ok_sender_capture(captured),
    )
    headers = captured["headers"]
    assert bm.BAPI_SIGN_TYPE_HEADER == "X-BAPI-SIGN-TYPE"
    assert bm.BAPI_SIGN_TYPE_VALUE == "2"
    assert headers.get("X-BAPI-SIGN-TYPE") == "2"


def test_x_bapi_sign_is_lowercase_hex_sha256(monkeypatch):
    _no_env(monkeypatch)
    captured: dict = {}
    bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        sender=_ok_sender_capture(captured),
    )
    sig = captured["headers"]["X-BAPI-SIGN"]
    assert len(sig) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", sig), (
        f"X-BAPI-SIGN must be lowercase hex; got {sig!r}"
    )


def test_sign_bybit_v5_matches_manual_hmac():
    sig = bm._sign_bybit_v5(
        timestamp_ms="1700000000000",
        api_key="kk",
        api_secret="ss",
        recv_window="5000",
        json_body_string='{"a":1}',
    )
    expected = hmac.new(
        b"ss",
        b"1700000000000kk5000{\"a\":1}",
        hashlib.sha256,
    ).hexdigest()
    assert sig == expected
    assert sig == sig.lower()


# ---------------------------------------------------------------------------
# 3. Required V5 envelope headers
# ---------------------------------------------------------------------------


def test_v5_envelope_headers_complete(monkeypatch):
    _no_env(monkeypatch)
    captured: dict = {}
    bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
        sender=_ok_sender_capture(captured),
    )
    headers = captured["headers"]
    for required in (
        "X-BAPI-API-KEY",
        "X-BAPI-TIMESTAMP",
        "X-BAPI-SIGN",
        "X-BAPI-SIGN-TYPE",
        "X-BAPI-RECV-WINDOW",
        "Content-Type",
    ):
        assert required in headers, (
            f"missing required Bybit V5 header: {required}"
        )
    assert headers["Content-Type"] == "application/json"
    # Timestamp is a positive ms-precision integer string.
    assert headers["X-BAPI-TIMESTAMP"].isdigit()
    assert int(headers["X-BAPI-TIMESTAMP"]) > 1_700_000_000_000


# ---------------------------------------------------------------------------
# 4. Safety: FIX task did NOT introduce new network / live surface
# ---------------------------------------------------------------------------


def test_status_constant_exposed():
    assert bm.STATUS_BYBIT_REJECTED_NO_ORDER_SENT == "BYBIT_REJECTED_NO_ORDER_SENT"
    assert "STATUS_BYBIT_REJECTED_NO_ORDER_SENT" in bm.__all__
    assert "BAPI_SIGN_TYPE_HEADER" in bm.__all__
    assert "BAPI_SIGN_TYPE_VALUE" in bm.__all__


def test_fix_did_not_change_max_order_count():
    assert bm.MAX_ORDER_COUNT == 1


def test_fix_did_not_change_allowed_endpoint():
    assert (
        bm.ALLOWED_DEMO_ENDPOINT_URL
        == "https://api-demo.bybit.com/v5/order/create"
    )
    assert bm.ALLOWED_DEMO_ENDPOINT_HOST == "api-demo.bybit.com"


def test_fix_did_not_change_demo_scoped_env_names():
    assert bm.DEMO_API_KEY_ENV == "BYBIT_DEMO_API_KEY"
    assert bm.DEMO_API_SECRET_ENV == "BYBIT_DEMO_API_SECRET"
    assert bm.DEMO_RECV_WINDOW_ENV == "BYBIT_DEMO_RECV_WINDOW"
