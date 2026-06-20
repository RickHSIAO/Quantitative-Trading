"""Importable fake BM senders used by orchestrator CLI tests.

These are *not* test functions. They are stable importable callables
used by the
``--fake-sender-import-path`` CLI argument of
``preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py``
so the CLI can be exercised end-to-end in Stage 1 without any real
network call.
"""

from __future__ import annotations


def ok_sender(url, headers, body):
    """Return a Bybit-shaped happy-path response."""

    return {
        "http_status": 200,
        "json": {
            "retCode": 0,
            "retMsg": "OK",
            "result": {"orderId": "fake-cli-1", "orderLinkId": "l-cli-1"},
        },
        "raw_text": "{}",
    }


def bybit_reject_sender(url, headers, body):
    """Return a Bybit-shaped rejected response."""

    return {
        "http_status": 200,
        "json": {
            "retCode": 10004,
            "retMsg": "auth failed (fake)",
            "result": {},
        },
        "raw_text": "{}",
    }


def network_error_sender(url, headers, body):
    """Simulate a network error."""

    raise OSError("fake network down")
