"""
tests/demo_trading/test_demo_runtime_probe.py
TASK-014B: Tests for src/demo_runtime_probe.py

Covers all required test cases for the demo runtime probe:
  1. config_true + no proof -> fail_closed
  2. config_false -> fail_closed
  3. valid fixture proof -> demo_runtime_verified=True
  4. missing proof (None) -> fail_closed
  5. no order endpoint called
  6. no secrets loaded/printed
  7. demo_flag=True alone (without account_mode) insufficient
  Plus: demo_flag=False, bad account_mode, unrecognised endpoint,
        module source safety scan.

SAFETY: no exchange imports, no order calls, no secrets.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.demo_runtime_probe as dr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _good_proof(**kwargs) -> dr.DemoRuntimeProof:
    """Build a valid fixture proof, optionally overriding fields."""
    defaults = dict(
        account_mode="demo",
        demo_flag=True,
        endpoint_family="bybit_demo",
        source="test_fixture",
    )
    defaults.update(kwargs)
    return dr.DemoRuntimeProof(**defaults)


# ---------------------------------------------------------------------------
# 1 / 4. Fail-closed when proof is absent
# ---------------------------------------------------------------------------

class TestNoProofFailClosed:
    def test_config_true_no_proof_returns_fail_closed(self):
        """Test case 1: config=True but runtime_proof=None -> fail_closed."""
        r = dr.probe_demo_runtime(demo_config_expected=True, runtime_proof=None)
        assert r.demo_runtime_verified is False
        assert r.fail_closed is True
        assert r.failure_reason == dr.FAIL_NO_PROOF

    def test_no_proof_no_orders_sent(self):
        r = dr.probe_demo_runtime(True, None)
        assert r.no_orders_sent is True

    def test_no_proof_secrets_not_loaded(self):
        r = dr.probe_demo_runtime(True, None)
        assert r.secrets_loaded is False

    def test_no_proof_no_private_order_endpoint(self):
        r = dr.probe_demo_runtime(True, None)
        assert r.private_order_endpoint_called is False


# ---------------------------------------------------------------------------
# 2. Config=False -> fail_closed
# ---------------------------------------------------------------------------

class TestConfigFalseFailClosed:
    def test_config_false_fails(self):
        """Test case 2: demo_config_expected=False -> fail_closed."""
        proof = _good_proof()
        r = dr.probe_demo_runtime(demo_config_expected=False, runtime_proof=proof)
        assert r.demo_runtime_verified is False
        assert r.fail_closed is True
        assert r.failure_reason == dr.FAIL_CONFIG_FALSE

    def test_config_false_no_proof_also_fails(self):
        r = dr.probe_demo_runtime(demo_config_expected=False, runtime_proof=None)
        assert r.fail_closed is True
        assert r.failure_reason == dr.FAIL_CONFIG_FALSE

    def test_config_false_always_no_orders(self):
        r = dr.probe_demo_runtime(False)
        assert r.no_orders_sent is True
        assert r.secrets_loaded is False


# ---------------------------------------------------------------------------
# 3. Valid fixture proof -> verified
# ---------------------------------------------------------------------------

class TestFixtureProofVerified:
    def test_valid_fixture_proof_verified(self):
        """Test case 3: valid fixture proof -> demo_runtime_verified=True."""
        proof = dr.make_fixture_proof()
        r = dr.probe_demo_runtime(demo_config_expected=True, runtime_proof=proof)
        assert r.demo_runtime_verified is True
        assert r.fail_closed is False
        assert r.failure_reason == ""

    def test_verified_result_no_orders(self):
        proof = dr.make_fixture_proof()
        r = dr.probe_demo_runtime(True, proof)
        assert r.no_orders_sent is True
        assert r.secrets_loaded is False
        assert r.private_order_endpoint_called is False

    def test_verified_carries_endpoint_and_mode(self):
        proof = dr.make_fixture_proof(endpoint_family="bybit_demo", account_mode="demo")
        r = dr.probe_demo_runtime(True, proof)
        assert r.endpoint_family == "bybit_demo"
        assert r.account_mode    == "demo"

    @pytest.mark.parametrize("ef", list(dr.DEMO_ENDPOINT_FAMILIES))
    def test_all_recognised_endpoint_families_pass(self, ef):
        proof = _good_proof(endpoint_family=ef)
        r = dr.probe_demo_runtime(True, proof)
        assert r.demo_runtime_verified is True


# ---------------------------------------------------------------------------
# 5 / 6. Safety outputs always correct
# ---------------------------------------------------------------------------

class TestSafetyOutputsAlwaysTrue:
    @pytest.mark.parametrize("config,proof", [
        (True,  None),
        (False, None),
        (True,  _good_proof()),
        (False, _good_proof()),
    ])
    def test_no_orders_sent_in_all_cases(self, config, proof):
        """Test case 5: no order endpoint called (flag always True)."""
        r = dr.probe_demo_runtime(config, proof)
        assert r.no_orders_sent is True

    @pytest.mark.parametrize("config,proof", [
        (True,  None),
        (False, None),
        (True,  _good_proof()),
    ])
    def test_secrets_never_loaded(self, config, proof):
        """Test case 6: no secrets loaded or printed."""
        r = dr.probe_demo_runtime(config, proof)
        assert r.secrets_loaded is False

    def test_private_order_endpoint_never_called(self):
        r = dr.probe_demo_runtime(True, None)
        assert r.private_order_endpoint_called is False


# ---------------------------------------------------------------------------
# 7. demo_flag alone (or account_mode alone) is insufficient
# ---------------------------------------------------------------------------

class TestConfigAloneInsufficient:
    def test_demo_flag_true_but_account_mode_not_demo(self):
        """Test case 7: demo_flag=True alone without correct account_mode fails."""
        proof = _good_proof(account_mode="live", demo_flag=True)
        r = dr.probe_demo_runtime(True, proof)
        assert r.demo_runtime_verified is False
        assert r.failure_reason == dr.FAIL_ACCOUNT_MODE_INVALID

    def test_demo_flag_true_but_unrecognised_endpoint(self):
        proof = _good_proof(endpoint_family="production")
        r = dr.probe_demo_runtime(True, proof)
        assert r.demo_runtime_verified is False
        assert r.failure_reason == dr.FAIL_ENDPOINT_UNRECOGNISED

    def test_demo_flag_false_rejected(self):
        proof = _good_proof(demo_flag=False)
        r = dr.probe_demo_runtime(True, proof)
        assert r.demo_runtime_verified is False
        assert r.failure_reason == dr.FAIL_DEMO_FLAG_FALSE

    def test_account_mode_DEMO_uppercase_passes(self):
        """account_mode check is case-insensitive."""
        proof = _good_proof(account_mode="DEMO")
        r = dr.probe_demo_runtime(True, proof)
        assert r.demo_runtime_verified is True

    def test_account_mode_mixed_case_containing_demo_passes(self):
        proof = _good_proof(account_mode="Demo_Account")
        r = dr.probe_demo_runtime(True, proof)
        assert r.demo_runtime_verified is True

    def test_empty_account_mode_fails(self):
        proof = _good_proof(account_mode="")
        r = dr.probe_demo_runtime(True, proof)
        assert r.fail_closed is True

    def test_empty_endpoint_family_fails(self):
        proof = _good_proof(endpoint_family="")
        r = dr.probe_demo_runtime(True, proof)
        assert r.fail_closed is True


# ---------------------------------------------------------------------------
# Invalid proof fields
# ---------------------------------------------------------------------------

class TestInvalidProofFields:
    def test_proof_with_none_account_mode_fails(self):
        proof = _good_proof(account_mode="")
        r = dr.probe_demo_runtime(True, proof)
        assert r.fail_closed is True

    def test_proof_with_none_endpoint_family_fails(self):
        proof = _good_proof(endpoint_family="")
        r = dr.probe_demo_runtime(True, proof)
        assert r.fail_closed is True


# ---------------------------------------------------------------------------
# make_fixture_proof helper
# ---------------------------------------------------------------------------

class TestFixtureProofFactory:
    def test_default_fixture_produces_verified(self):
        proof = dr.make_fixture_proof()
        r = dr.probe_demo_runtime(True, proof)
        assert r.demo_runtime_verified is True

    def test_fixture_with_wrong_flag_fails(self):
        proof = dr.make_fixture_proof(demo_flag=False)
        r = dr.probe_demo_runtime(True, proof)
        assert r.demo_runtime_verified is False

    def test_fixture_with_wrong_mode_fails(self):
        proof = dr.make_fixture_proof(account_mode="live")
        r = dr.probe_demo_runtime(True, proof)
        assert r.demo_runtime_verified is False


# ---------------------------------------------------------------------------
# Module source safety scan
# ---------------------------------------------------------------------------

class TestModuleSourceSafety:
    MODULE = ROOT / "src" / "demo_runtime_probe.py"

    def test_module_exists(self):
        assert self.MODULE.exists()

    def test_no_forbidden_order_tokens(self):
        src = self.MODULE.read_text(encoding="utf-8")
        for token in ("place_order", "create_order", "submit_order",
                      "cancel_order", "private_post"):
            assert token not in src, f"Forbidden token '{token}' found in module"

    def test_no_pybit_import(self):
        src = self.MODULE.read_text(encoding="utf-8")
        assert "pybit" not in src

    def test_no_bybit_executor_import(self):
        src = self.MODULE.read_text(encoding="utf-8")
        assert "BybitExecutor" not in src

    def test_no_secret_handling(self):
        src = self.MODULE.read_text(encoding="utf-8")
        for token in ("dotenv", "os.environ", "getenv", "API_KEY", "API_SECRET"):
            assert token not in src, f"Secret-related token '{token}' found in module"

    def test_no_network_calls(self):
        src = self.MODULE.read_text(encoding="utf-8")
        for token in ("requests.", "httpx.", "urllib.request", "socket."):
            assert token not in src, f"Network token '{token}' found in module"

    def test_no_main_import(self):
        src = self.MODULE.read_text(encoding="utf-8")
        assert "import main" not in src
        assert "from main" not in src

    def test_no_risk_import(self):
        src = self.MODULE.read_text(encoding="utf-8")
        assert "src.risk" not in src
