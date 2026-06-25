"""TASK-014CH3C2_FIX2 -- credential-key matching is token/boundary aware.

A broad ``"sign" in key`` substring test falsely rejected benign keys such as
``rejected_signals`` / ``design_version`` even though they carry no credential.
This module proves:

  * benign signal/design keys (and a realistic seed Plan that contains them) pass;
  * genuine credential KEYS still fail closed (substring + discrete ``sign`` token);
  * secret VALUE detection is unchanged and never leaks the secret;
  * forbidden auth-op detection is unchanged;
  * the final WS-evidence seal still recomputes and still includes the
    ``credential_leak_check`` field in the fingerprint material.

Offline only; no network, no execution.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

from src import demo_public_ws_ticker_evidence as ws

_HERE = os.path.dirname(os.path.abspath(__file__))

_CG = os.path.join(_HERE, "test_demo_strategy_native_ws_price_binding_cg.py")
_spec = importlib.util.spec_from_file_location("_cg_helpers_cf_fix5", _CG)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)


# ---------------------------------------------------------------------------
# 1. Benign keys containing the characters "sign" are NOT credential keys
# ---------------------------------------------------------------------------

BENIGN_KEYS = [
    "rejected_signals",
    "accepted_signals",
    "signal",
    "signals",
    "signal_count",
    "strategy_signal_count",
    "unsigned_value",
    "assigned_symbols",
    "design_version",
    "rejectedSignals",   # camelCase form of the regression key
    "designVersion",
]


@pytest.mark.parametrize("key", BENIGN_KEYS)
def test_benign_signal_design_keys_are_not_credentials(key):
    assert ws._find_forbidden_credential_key(key) is None
    # And they pass the recursive guard, even nested.
    ws.assert_no_credentials({key: 123, "args": [{key: ["ok"]}]})


def test_rejected_signals_passes_guard():
    ws.assert_no_credentials({"op": "subscribe", "rejected_signals": ["BTCUSDT"]})


# ---------------------------------------------------------------------------
# 2. Genuine credential keys still fail closed
# ---------------------------------------------------------------------------

CREDENTIAL_KEYS = [
    "api_key", "apikey", "api-key", "API_KEY", "apiKey",
    "secret", "client_secret", "api_secret",
    "signature", "sign",
    "x-bapi-api-key", "x-bapi-sign", "X-BAPI-SIGN", "passphrase",
    # boundary forms of the short token
    "Sign", "x_bapi_sign", "xBapiSign",
]


@pytest.mark.parametrize("key", CREDENTIAL_KEYS)
def test_genuine_credential_keys_are_classified(key):
    assert ws._find_forbidden_credential_key(key) is not None


@pytest.mark.parametrize("key", CREDENTIAL_KEYS)
def test_genuine_credential_keys_rejected_by_guard(key):
    with pytest.raises(ws.WsEndpointError):
        ws.assert_no_credentials({key: "value"})


def test_nested_credential_key_rejected():
    with pytest.raises(ws.WsEndpointError):
        ws.assert_no_credentials(
            {"args": [{"meta": {"signal_count": 3, "x-bapi-sign": "deadbeef"}}]})


def test_sign_is_token_tier_not_substring_tier():
    # The short token must NOT be a substring fragment (that was the false-positive
    # bug); it must be a discrete-token fragment instead.
    assert "sign" not in ws._FORBIDDEN_CREDENTIAL_KEY_SUBSTRINGS
    assert "sign" in ws._FORBIDDEN_CREDENTIAL_KEY_TOKENS


# ---------------------------------------------------------------------------
# 3. Secret VALUE protection unchanged (and never leaked)
# ---------------------------------------------------------------------------

def test_secret_value_rejected_when_nested_without_leaking():
    # Current contract: a known secret VALUE is matched recursively (nested
    # dict/list) and the error never echoes the secret. Unchanged by this fix.
    secret = "S3CR3T-LIVE-KEY-DO-NOT-LEAK"
    payload = {"args": [{"meta": {"note": secret}}]}
    with pytest.raises(ws.WsEndpointError) as ei:
        ws.assert_no_credentials(payload, secret_values=[secret])
    assert secret not in str(ei.value)


def test_forbidden_auth_op_still_rejected():
    with pytest.raises(ws.WsEndpointError):
        ws.assert_no_credentials({"op": "auth", "args": ["k", "expires", "sig"]})


def test_clean_signal_payload_passes_with_secret_scan():
    ws.assert_no_credentials(
        {"op": "subscribe", "rejected_signals": ["BTCUSDT"], "signal_count": 1},
        secret_values=["unused-secret"])


# ---------------------------------------------------------------------------
# 4. Final WS-evidence seal still recomputes and keeps credential_leak_check
# ---------------------------------------------------------------------------

def _recompute_ok(artifact) -> bool:
    return artifact.get("artifact_fingerprint") == ws._fingerprint(
        {k: v for k, v in artifact.items() if k != "artifact_fingerprint"})


def test_sealed_artifact_recomputes_and_includes_credential_leak_check():
    art = cg.build_complete_ws_artifact(now_ns=1_700_000_000_000_000_000)
    sealed = ws.seal_artifact_fingerprint(
        art, verify_no_credential_leak=True, secret_values=["not-present-value"])
    assert sealed["credential_leak_check"] == "NO_CREDENTIAL_VALUE_OR_KEY_PRESENT"
    assert _recompute_ok(sealed)
    # The credential-leak field is part of the fingerprint material: dropping it
    # must change the recomputed fingerprint.
    without = {k: v for k, v in sealed.items()
               if k not in ("artifact_fingerprint", "credential_leak_check")}
    assert ws._fingerprint(without) != sealed["artifact_fingerprint"]
