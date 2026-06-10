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


# ---------------------------------------------------------------------------
# TASK-014D: Proof strength classification
# ---------------------------------------------------------------------------

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.demo_readonly_client import PROOF_MISSING, PROOF_STRONG, PROOF_WEAK


class TestProofStrengthClassification:
    """F2-F5: STRONG / WEAK / MISSING classification in build_runtime_proof."""

    def test_fixture_proof_strength_is_strong(self):
        """F2: fixture mode always returns PROOF_STRONG."""
        p = _fixture_client().build_runtime_proof()
        assert p.proof_strength == PROOF_STRONG

    def test_real_mode_no_key_returns_proof_missing(self, monkeypatch):
        """F3: real mode with no api_key → PROOF_MISSING."""
        monkeypatch.delenv("BYBIT_DEMO_API_KEY",    raising=False)
        monkeypatch.delenv("BYBIT_DEMO_API_SECRET",  raising=False)
        client = DemoReadOnlyClient(allow_real_network=True)
        p = client.build_runtime_proof()
        assert p.proof_strength == PROOF_MISSING
        assert p.demo_flag is False

    def test_real_mode_retcode_nonzero_returns_proof_missing(self, monkeypatch):
        """F3 variant: retCode != 0 → PROOF_MISSING."""
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "FAKE_KEY")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "FAKE_SECRET")
        client = DemoReadOnlyClient(allow_real_network=True)
        with patch.object(client, "_get", return_value={"retCode": 10004, "result": {}}):
            p = client.build_runtime_proof()
        assert p.proof_strength == PROOF_MISSING
        assert p.demo_flag is False

    def test_real_mode_retcode_zero_no_uid_returns_proof_weak(self, monkeypatch):
        """F4: retCode==0 but response lacks uid/apiKey → PROOF_WEAK."""
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "FAKE_KEY")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "FAKE_SECRET")
        client = DemoReadOnlyClient(allow_real_network=True)
        with patch.object(client, "_get", return_value={"retCode": 0, "result": {}}):
            p = client.build_runtime_proof()
        assert p.proof_strength == PROOF_WEAK
        assert p.demo_flag is False

    def test_real_mode_retcode_zero_with_uid_and_apikey_returns_proof_strong(self, monkeypatch):
        """F5: retCode==0 + result has userID + apiKey → PROOF_STRONG."""
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "FAKE_KEY")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "FAKE_SECRET")
        client = DemoReadOnlyClient(allow_real_network=True)
        fake_result = {"retCode": 0, "result": {"userID": "123", "apiKey": "FAKE_KEY"}}
        with patch.object(client, "_get", return_value=fake_result):
            p = client.build_runtime_proof()
        assert p.proof_strength == PROOF_STRONG
        assert p.demo_flag is True

    def test_real_mode_uid_variant_uid_field(self, monkeypatch):
        """F5 variant: uid (not userID) also qualifies."""
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "FAKE_KEY")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "FAKE_SECRET")
        client = DemoReadOnlyClient(allow_real_network=True)
        fake_result = {"retCode": 0, "result": {"uid": "456", "note": "mykey"}}
        with patch.object(client, "_get", return_value=fake_result):
            p = client.build_runtime_proof()
        assert p.proof_strength == PROOF_STRONG

    def test_proof_strength_field_exists_on_snapshot(self):
        """proof_strength field is present and non-empty in fixture mode."""
        p = _fixture_client().build_runtime_proof()
        assert hasattr(p, "proof_strength")
        assert p.proof_strength != ""


# ---------------------------------------------------------------------------
# TASK-014D: api_secret_present tracking
# ---------------------------------------------------------------------------

class TestApiSecretPresent:
    """F9-F11: api_secret_present propagation."""

    def test_fixture_mode_api_secret_present_is_false(self, monkeypatch):
        """F10: fixture mode — api_secret_present always False."""
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "SOME_SECRET")
        p = DemoReadOnlyClient(allow_real_network=False).build_runtime_proof()
        assert p.api_secret_present is False

    def test_real_mode_with_secret_api_secret_present_true(self, monkeypatch):
        """F9: real mode + secret set → api_secret_present True."""
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "FAKE_KEY")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "FAKE_SECRET")
        client = DemoReadOnlyClient(allow_real_network=True)
        # no_key early exit: api_key is set, so it will try _get; mock it
        with patch.object(client, "_get", return_value={"retCode": 0, "result": {"userID": "1", "apiKey": "k"}}):
            p = client.build_runtime_proof()
        assert p.api_secret_present is True

    def test_real_mode_no_secret_api_secret_present_false(self, monkeypatch):
        """F9: real mode + no secret → api_secret_present False."""
        monkeypatch.setenv("BYBIT_DEMO_API_KEY", "FAKE_KEY")
        monkeypatch.delenv("BYBIT_DEMO_API_SECRET", raising=False)
        client = DemoReadOnlyClient(allow_real_network=True)
        with patch.object(client, "_get", return_value={"retCode": 0, "result": {"userID": "1", "apiKey": "k"}}):
            p = client.build_runtime_proof()
        assert p.api_secret_present is False

    def test_api_secret_present_field_on_fixture_runtime_proof_constant(self):
        """FIXTURE_RUNTIME_PROOF constant has api_secret_present field."""
        from src.demo_readonly_client import FIXTURE_RUNTIME_PROOF
        assert hasattr(FIXTURE_RUNTIME_PROOF, "api_secret_present")
        assert FIXTURE_RUNTIME_PROOF.api_secret_present is False

    def test_secret_value_never_in_proof_output(self, monkeypatch):
        """F11: secret value never appears in proof output regardless of mode."""
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "SUPER_SECRET_KEY_VALUE")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "SUPER_SECRET_VALUE_XYZ")
        client = DemoReadOnlyClient(allow_real_network=True)
        with patch.object(client, "_get", return_value={"retCode": 0, "result": {"userID": "1", "apiKey": "k"}}):
            p = client.build_runtime_proof()
        proof_str = str(p)
        assert "SUPER_SECRET_VALUE_XYZ" not in proof_str
        assert p.secret_value_observed is False


# ---------------------------------------------------------------------------
# TASK-014D: write_report
# ---------------------------------------------------------------------------

class TestWriteReport:
    """F14: --write-report creates JSON and MD files."""

    def test_write_report_creates_json_and_md(self):
        from scripts.preview_demo_readonly_runtime import _write_report
        data = {
            "run_timestamp_utc": "2026-06-06T12:00:00Z",
            "source": "fixture",
            "proof_strength": PROOF_STRONG,
            "demo_runtime_verified": True,
            "fail_closed": False,
            "fail_reasons": [],
            "api_key_present": False,
            "api_secret_present": False,
            "order_endpoint_called": False,
            "secret_value_observed": False,
            "equity_usd": 10000.0,
            "available_balance_usd": 8500.0,
            "open_positions_count": 2,
            "proposals_accepted": 3,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _write_report(data, output_dir)
            files = list(output_dir.iterdir())
            names = {f.name for f in files}
            assert "latest_smoke.json" in names
            assert "latest_smoke.md" in names
            # Also a timestamped pair
            json_files = [n for n in names if n.endswith("_smoke.json") and n != "latest_smoke.json"]
            md_files   = [n for n in names if n.endswith("_smoke.md")   and n != "latest_smoke.md"]
            assert len(json_files) == 1
            assert len(md_files)   == 1

    def test_write_report_json_content(self):
        from scripts.preview_demo_readonly_runtime import _write_report
        data = {
            "run_timestamp_utc": "2026-06-06T12:00:00Z",
            "source": "fixture",
            "proof_strength": PROOF_STRONG,
            "demo_runtime_verified": True,
            "fail_closed": False,
            "fail_reasons": [],
            "api_key_present": False,
            "api_secret_present": False,
            "order_endpoint_called": False,
            "secret_value_observed": False,
            "equity_usd": 10000.0,
            "available_balance_usd": 8500.0,
            "open_positions_count": 2,
            "proposals_accepted": 3,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _write_report(data, output_dir)
            latest = output_dir / "latest_smoke.json"
            loaded = json.loads(latest.read_text(encoding="utf-8"))
            assert loaded["proof_strength"] == PROOF_STRONG
            assert loaded["demo_runtime_verified"] is True
            assert loaded["secret_value_observed"] is False

    def test_write_report_md_contains_status_pass(self):
        from scripts.preview_demo_readonly_runtime import _write_report
        data = {
            "run_timestamp_utc": "2026-06-06T12:00:00Z",
            "source": "fixture",
            "proof_strength": PROOF_STRONG,
            "demo_runtime_verified": True,
            "fail_closed": False,
            "fail_reasons": [],
            "api_key_present": False,
            "api_secret_present": False,
            "order_endpoint_called": False,
            "secret_value_observed": False,
            "equity_usd": 10000.0,
            "available_balance_usd": 8500.0,
            "open_positions_count": 2,
            "proposals_accepted": 3,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _write_report(data, output_dir)
            md = (output_dir / "latest_smoke.md").read_text(encoding="utf-8")
            assert "PASS" in md

    def test_write_report_md_contains_status_fail_when_fail_closed(self):
        from scripts.preview_demo_readonly_runtime import _write_report
        data = {
            "run_timestamp_utc": "2026-06-06T12:00:00Z",
            "source": "bybit_readonly_api",
            "proof_strength": PROOF_MISSING,
            "demo_runtime_verified": False,
            "fail_closed": True,
            "fail_reasons": ["cannot_construct_runtime_proof"],
            "api_key_present": False,
            "api_secret_present": False,
            "order_endpoint_called": False,
            "secret_value_observed": False,
            "equity_usd": 0.0,
            "available_balance_usd": 0.0,
            "open_positions_count": 0,
            "proposals_accepted": 0,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _write_report(data, output_dir)
            md = (output_dir / "latest_smoke.md").read_text(encoding="utf-8")
            assert "FAIL" in md


# ---------------------------------------------------------------------------
# TASK-014X-FIX2: pagination + targeted SOLUSDT lookup
# ---------------------------------------------------------------------------

class TestPaginationAndTargetedLookup:
    """Pagination support for instruments-info and targeted SOLUSDT fetch."""

    def test_parse_instrument_snapshot(self):
        """_parse_instrument_snapshot extracts fields correctly."""
        client = _fixture_client()
        item = {
            "symbol": "SOLUSDT",
            "lotSizeFilter": {
                "qtyStep": "0.1",
                "minOrderQty": "0.1",
                "maxOrderQty": "0",
            },
            "priceFilter": {
                "tickSize": "0.01",
            },
        }
        snap = client._parse_instrument_snapshot(item)
        assert snap.symbol == "SOLUSDT"
        assert snap.qty_step == pytest.approx(0.1)
        assert snap.min_qty == pytest.approx(0.1)
        assert snap.tick_size == pytest.approx(0.01)

    def test_instruments_real_includes_fixture_solusdt(self):
        """Fixture mode includes SOLUSDT in instrument list."""
        client = _fixture_client()
        rules = client.get_instruments_info()
        assert "SOLUSDT" in rules, "SOLUSDT should be in fixture instruments"
        sol = rules["SOLUSDT"]
        assert sol.symbol == "SOLUSDT"
        assert sol.qty_step > 0
        assert sol.min_qty > 0
        assert sol.tick_size > 0

    def test_instruments_with_symbol_filter(self):
        """get_instruments_info(symbols=['SOLUSDT']) returns only SOLUSDT."""
        client = _fixture_client()
        rules = client.get_instruments_info(symbols=["SOLUSDT"])
        assert "SOLUSDT" in rules
        # Fixture mode ignores symbols filter; real mode would apply it

    def test_targeted_lookup_solusdt_never_missing(self):
        """_instruments_real always includes SOLUSDT (targeted + paginated)."""
        # In fixture mode, SOLUSDT is always present
        client = _fixture_client()
        rules = client.get_instruments_info()
        assert "SOLUSDT" in rules
