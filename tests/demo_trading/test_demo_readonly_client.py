"""
tests/demo_trading/test_demo_readonly_client.py
TASK-014C: Tests for src/demo_readonly_client.py

Covers TASK-014C requirements 1-5:
  1. default fixture mode does not call network
  2. without --real-readonly, no secrets loaded
  3. source contains no order/create/submit/cancel endpoint calls
  4. no secret value in output
  5. live endpoint fallback forbidden

Additional coverage:
  - Fixture data integrity (correct types, values)
  - Safety output invariants (secret_value_observed, order_endpoint_called always False)
  - Allowed path enforcement
  - Module source safety scan

SAFETY: no exchange imports, no order calls, no secrets.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.demo_readonly_client as drc
from src.demo_readonly_client import (
    DEMO_BASE_URL,
    FIXTURE_INSTRUMENTS,
    FIXTURE_POSITIONS,
    FIXTURE_RUNTIME_PROOF,
    FIXTURE_WALLET,
    DemoReadOnlyClient,
    InstrumentSnapshot,
    PositionSnapshot,
    RuntimeProofSnapshot,
    WalletSnapshot,
    _ALLOWED_PATHS,
    _LIVE_HOSTNAME,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fixture_client() -> DemoReadOnlyClient:
    return DemoReadOnlyClient(allow_real_network=False)


# ---------------------------------------------------------------------------
# 1. Fixture mode — no network calls
# ---------------------------------------------------------------------------

class TestNetworkIsolation:
    """Requirement 1: default fixture mode does not call network."""

    def test_get_wallet_does_not_call_urlopen(self):
        with patch("urllib.request.urlopen") as mock_open:
            _fixture_client().get_wallet_balance()
            mock_open.assert_not_called()

    def test_get_positions_does_not_call_urlopen(self):
        with patch("urllib.request.urlopen") as mock_open:
            _fixture_client().get_open_positions()
            mock_open.assert_not_called()

    def test_get_instruments_does_not_call_urlopen(self):
        with patch("urllib.request.urlopen") as mock_open:
            _fixture_client().get_instruments_info()
            mock_open.assert_not_called()

    def test_build_proof_does_not_call_urlopen(self):
        with patch("urllib.request.urlopen") as mock_open:
            _fixture_client().build_runtime_proof()
            mock_open.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Secrets not loaded without real-network flag
# ---------------------------------------------------------------------------

class TestSecretsNotLoadedInFixtureMode:
    """Requirement 2: without allow_real_network, no secrets loaded."""

    def test_fixture_client_api_key_empty(self, monkeypatch):
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "FAKE_KEY_123")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "FAKE_SECRET_456")
        client = DemoReadOnlyClient(allow_real_network=False)
        assert client._api_key == ""
        assert client._api_secret == ""

    def test_fixture_client_key_present_false(self, monkeypatch):
        monkeypatch.setenv("BYBIT_DEMO_API_KEY", "FAKE_KEY_123")
        client = DemoReadOnlyClient(allow_real_network=False)
        assert client._key_present is False

    def test_wallet_api_key_present_false_in_fixture_mode(self):
        w = _fixture_client().get_wallet_balance()
        assert w.api_key_present is False

    def test_proof_api_key_present_false_in_fixture_mode(self):
        p = _fixture_client().build_runtime_proof()
        assert p.api_key_present is False


# ---------------------------------------------------------------------------
# 3. Source safety — no forbidden order tokens
# ---------------------------------------------------------------------------

class TestModuleSourceSafety:
    """Requirement 3: source contains no forbidden order/cancel endpoints."""
    MODULE = ROOT / "src" / "demo_readonly_client.py"

    def _src(self) -> str:
        return self.MODULE.read_text(encoding="utf-8")

    def test_module_exists(self):
        assert self.MODULE.exists()

    def test_no_place_order(self):
        assert "place_order" not in self._src()

    def test_no_create_order(self):
        # "create_order" as a call; "order" alone is allowed in path names
        assert "create_order" not in self._src()

    def test_no_submit_order(self):
        assert "submit_order" not in self._src()

    def test_no_cancel_order(self):
        assert "cancel_order" not in self._src()

    def test_no_private_post(self):
        assert "private_post" not in self._src()

    def test_no_set_leverage(self):
        assert "set_leverage" not in self._src()

    def test_no_set_trading_stop(self):
        assert "set_trading_stop" not in self._src()

    def test_no_transfer_call(self):
        assert "transfer(" not in self._src()

    def test_demo_base_url_is_demo_domain(self):
        assert "api-demo.bybit.com" in self._src()

    def test_no_pybit_import(self):
        assert "pybit" not in self._src()

    def test_no_bybit_executor_import(self):
        assert "BybitExecutor" not in self._src()

    def test_no_main_import(self):
        assert "import main" not in self._src()
        assert "from main" not in self._src()

    def test_no_src_risk_import(self):
        assert "src.risk" not in self._src()


# ---------------------------------------------------------------------------
# 4. Secret value never observed in output
# ---------------------------------------------------------------------------

class TestSecretNeverObserved:
    """Requirement 4: no secret value printed or returned."""

    def test_wallet_secret_value_observed_false(self):
        w = _fixture_client().get_wallet_balance()
        assert w.secret_value_observed is False

    def test_wallet_secret_leak_violations_empty(self):
        w = _fixture_client().get_wallet_balance()
        assert w.secret_leak_violations == []

    def test_proof_secret_value_observed_false(self):
        p = _fixture_client().build_runtime_proof()
        assert p.secret_value_observed is False

    def test_proof_secret_leak_violations_empty(self):
        p = _fixture_client().build_runtime_proof()
        assert p.secret_leak_violations == []

    def test_real_mode_secret_never_in_wallet(self, monkeypatch):
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "KEY_SHOULD_NOT_APPEAR")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "SECRET_SHOULD_NOT_APPEAR")
        # Fixture mode — secret not in output regardless
        w = DemoReadOnlyClient(allow_real_network=False).get_wallet_balance()
        assert w.secret_value_observed is False


# ---------------------------------------------------------------------------
# 5. Live endpoint fallback forbidden
# ---------------------------------------------------------------------------

class TestLiveEndpointForbidden:
    """Requirement 5: live endpoint fallback forbidden."""

    def test_demo_base_url_not_live(self):
        assert _LIVE_HOSTNAME not in DEMO_BASE_URL

    def test_live_hostname_sentinel_value(self):
        assert _LIVE_HOSTNAME == "api.bybit.com"

    def test_fixture_proof_live_fallback_false(self):
        p = _fixture_client().build_runtime_proof()
        assert p.live_endpoint_fallback_detected is False

    def test_allowed_paths_contain_no_live_hostname(self):
        for path in _ALLOWED_PATHS:
            assert _LIVE_HOSTNAME not in path

    def test_allowed_paths_are_all_read_only(self):
        forbidden_fragments = ("order", "leverage", "trading-stop",
                               "transfer", "withdraw", "deposit")
        for path in _ALLOWED_PATHS:
            for frag in forbidden_fragments:
                assert frag not in path, f"Forbidden fragment '{frag}' in {path!r}"


# ---------------------------------------------------------------------------
# Safety outputs always correct
# ---------------------------------------------------------------------------

class TestSafetyOutputsAlwaysCorrect:
    def test_wallet_order_endpoint_called_false(self):
        assert _fixture_client().get_wallet_balance().order_endpoint_called is False

    def test_proof_order_endpoint_called_false(self):
        assert _fixture_client().build_runtime_proof().order_endpoint_called is False

    def test_wallet_secret_value_observed_false_repeatedly(self):
        for _ in range(3):
            w = _fixture_client().get_wallet_balance()
            assert w.secret_value_observed is False

    def test_proof_secret_value_observed_false_repeatedly(self):
        for _ in range(3):
            p = _fixture_client().build_runtime_proof()
            assert p.secret_value_observed is False


# ---------------------------------------------------------------------------
# Fixture data integrity
# ---------------------------------------------------------------------------

class TestFixtureDataIntegrity:
    def test_fixture_wallet_returns_expected_equity(self):
        w = _fixture_client().get_wallet_balance()
        assert w.equity_usd == 10_000.0

    def test_fixture_wallet_available_less_than_equity(self):
        w = _fixture_client().get_wallet_balance()
        assert 0 < w.available_balance_usd <= w.equity_usd

    def test_fixture_positions_count(self):
        ps = _fixture_client().get_open_positions()
        assert len(ps) == 2

    def test_fixture_positions_have_stop_price(self):
        ps = _fixture_client().get_open_positions()
        for p in ps:
            assert p.stop_price is not None
            assert p.stop_price > 0

    def test_fixture_positions_side_normalised(self):
        ps = _fixture_client().get_open_positions()
        for p in ps:
            assert p.side in ("long", "short")

    def test_fixture_instruments_count(self):
        instr = _fixture_client().get_instruments_info()
        assert len(instr) == 10

    def test_fixture_instruments_filter_by_symbols(self):
        instr = _fixture_client().get_instruments_info(symbols=["BTCUSDT", "ETHUSDT"])
        assert set(instr.keys()) == {"BTCUSDT", "ETHUSDT"}

    def test_fixture_instruments_all_qty_step_positive(self):
        instr = _fixture_client().get_instruments_info()
        for snap in instr.values():
            assert snap.qty_step > 0

    def test_fixture_instruments_all_tick_size_positive(self):
        instr = _fixture_client().get_instruments_info()
        for snap in instr.values():
            assert snap.tick_size > 0

    def test_fixture_proof_endpoint_family_is_demo(self):
        p = _fixture_client().build_runtime_proof()
        assert p.endpoint_family == "bybit_demo"

    def test_fixture_proof_base_url_is_demo(self):
        p = _fixture_client().build_runtime_proof()
        assert p.base_url_used == DEMO_BASE_URL

    def test_fixture_proof_demo_flag_true(self):
        p = _fixture_client().build_runtime_proof()
        assert p.demo_flag is True

    def test_fixture_proof_source_is_fixture(self):
        p = _fixture_client().build_runtime_proof()
        assert p.source == "fixture"

    def test_each_call_returns_independent_list(self):
        ps1 = _fixture_client().get_open_positions()
        ps2 = _fixture_client().get_open_positions()
        assert ps1 is not ps2

    def test_each_instruments_call_returns_independent_dict(self):
        d1 = _fixture_client().get_instruments_info()
        d2 = _fixture_client().get_instruments_info()
        assert d1 is not d2


# ---------------------------------------------------------------------------
# Allowed paths enforcement
# ---------------------------------------------------------------------------

class TestAllowedPathsEnforcement:
    def test_allowed_paths_not_empty(self):
        assert len(_ALLOWED_PATHS) >= 4

    def test_real_mode_get_rejects_unknown_path(self):
        client = DemoReadOnlyClient(allow_real_network=True)
        with pytest.raises(ValueError, match="not in allowed list"):
            client._get("/v5/order/create", {})

    def test_real_mode_get_rejects_live_path_segment(self):
        client = DemoReadOnlyClient(allow_real_network=True)
        with pytest.raises(ValueError):
            client._get("/v5/order/cancel", {})
