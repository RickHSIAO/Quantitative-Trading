from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from apps.forward_record.alert_conditions import (
    _extract_yyyymmdd,
    check_alpha_gap,
    check_data_source_failure,
    check_forbidden_field_violation,
    check_review_006b_trigger,
    check_runner_missing_rows,
    check_stop_gate,
    check_warning_gate_streak,
    dated_path_from_template,
)
from apps.forward_record.alerting import resolve_forward_output_paths_from_config, run_forward_alerting
from apps.forward_record.safety import scan_no_order_endpoints


class ForwardAlertingTest(unittest.TestCase):
    def test_a1_missing_rows_no_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _positions(base / "20260101_positions.parquet", [0.1])
            _positions(base / "20260102_positions.parquet", [0.1])

            result = check_runner_missing_rows("20260102", base / "20260102_positions.parquet")

            self.assertFalse(result.triggered)

    def test_a1_missing_rows_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            result = check_runner_missing_rows("20260102", base / "20260102_positions.parquet")

            self.assertTrue(result.triggered)
            self.assertEqual(result.condition_id, "A-1")

    def test_a2_stop_gate_trigger(self) -> None:
        result = check_stop_gate({"date": "20260102", "active_stop_gates": ["S-2"]})

        self.assertTrue(result.triggered)

    def test_a2_stop_gate_no_trigger(self) -> None:
        result = check_stop_gate({"date": "20260102", "active_stop_gates": []})

        self.assertFalse(result.triggered)

    def test_a3_warning_streak_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for date in ["20260101", "20260102", "20260103"]:
                _json(base / f"{date}_forward_stats.json", {"active_warning_gates": ["W-1"]})

            result = check_warning_gate_streak("20260103", base / "20260103_forward_stats.json")

            self.assertTrue(result.triggered)
            self.assertEqual(result.data["streak_gates"], ["W-1"])

    def test_a3_warning_streak_no_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _json(base / "20260101_forward_stats.json", {"active_warning_gates": []})
            _json(base / "20260102_forward_stats.json", {"active_warning_gates": ["W-1"]})
            _json(base / "20260103_forward_stats.json", {"active_warning_gates": ["W-1"]})

            result = check_warning_gate_streak("20260103", base / "20260103_forward_stats.json")

            self.assertFalse(result.triggered)

    def test_a4_alpha_gap_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _positions(base / "primary.parquet", [0.10, -0.10])
            _positions(base / "shadow.parquet", [0.00, -0.20])

            result = check_alpha_gap("20260102", base / "primary.parquet", base / "shadow.parquet", threshold=0.05)

            self.assertTrue(result.triggered)
            self.assertGreater(result.data["mean_abs_diff"], 0.05)

    def test_a4_alpha_gap_no_shadow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _positions(base / "primary.parquet", [0.10])

            result = check_alpha_gap("20260102", base / "primary.parquet", base / "missing.parquet")

            self.assertFalse(result.triggered)
            self.assertTrue(result.data["skipped"])

    def test_a5_data_source_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            result = check_data_source_failure("20260102", base / "missing_stats.json", base / "missing.log")

            self.assertTrue(result.triggered)

    def test_a5_cache_provider_log_is_not_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stats = base / "forward_stats.json"
            log = base / "forward.log"
            _json(stats, {"date": "20260102", "data_source": "LIVE", "rows": 50})
            log.write_text("CacheMarketDataProvider initialized successfully\n", encoding="utf-8")

            result = check_data_source_failure("20260102", stats, log)

            self.assertFalse(result.triggered)
            self.assertEqual(result.detail, "data source readable")

    def test_a5_data_source_failed_log_marker_triggers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stats = base / "forward_stats.json"
            log = base / "forward.log"
            _json(stats, {"date": "20260102", "data_source": "LIVE"})
            log.write_text("data_source=FAILED\n", encoding="utf-8")

            result = check_data_source_failure("20260102", stats, log)

            self.assertTrue(result.triggered)
            self.assertIn("data_source=FAILED", result.detail)

    def test_a5_runtime_error_log_marker_triggers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stats = base / "forward_stats.json"
            log = base / "forward.log"
            _json(stats, {"date": "20260102", "data_source": "LIVE"})
            log.write_text("RuntimeError: cache read failed\n", encoding="utf-8")

            result = check_data_source_failure("20260102", stats, log)

            self.assertTrue(result.triggered)
            self.assertIn("RuntimeError", result.detail)

    def test_extract_yyyymmdd_prefers_path_stem(self) -> None:
        self.assertEqual(_extract_yyyymmdd("outputs/20260102_positions.parquet"), "20260102")
        self.assertEqual(_extract_yyyymmdd("outputs/20260101/20260102_positions.parquet"), "20260102")
        self.assertIsNone(_extract_yyyymmdd("outputs/positions.parquet"))
        self.assertEqual(_extract_yyyymmdd("outputs/20260101/positions.parquet"), "20260101")
        self.assertIsNone(_extract_yyyymmdd("outputs/202601010_positions.parquet"))

    def test_dated_path_from_template_with_placeholder(self) -> None:
        path = dated_path_from_template(Path("outputs/{date}_positions.parquet"), "20260102")

        self.assertEqual(path, Path("outputs/20260102_positions.parquet"))

    def test_resolve_output_paths_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "forward_record.yaml"
            config_path.write_text(
                "\n".join([
                    "output_paths:",
                    "  log: \"outputs/logs/prev3y_crypto/{date}_forward_record.log\"",
                    "  primary:",
                    "    positions: \"outputs/forward_record/primary/{date}_positions.parquet\"",
                    "    forward_stats: \"outputs/forward_record/primary/{date}_forward_stats.json\"",
                    "    overlay_check: \"outputs/forward_record/primary/{date}_overlay_check.json\"",
                    "    pnl: \"outputs/forward_record/primary/{date}_pnl.json\"",
                    "  shadow:",
                    "    positions: \"outputs/forward_record/shadow/{date}_positions.parquet\"",
                    "    forward_stats: \"outputs/forward_record/shadow/{date}_forward_stats.json\"",
                    "    overlay_check: \"outputs/forward_record/shadow/{date}_overlay_check.json\"",
                    "    pnl: \"outputs/forward_record/shadow/{date}_pnl.json\"",
                ])
                + "\n",
                encoding="utf-8",
            )

            paths = resolve_forward_output_paths_from_config(config_path, "20260102")

            self.assertEqual(paths["primary"]["positions"], Path("outputs/forward_record/primary/20260102_positions.parquet"))
            self.assertEqual(paths["shadow"]["positions"], Path("outputs/forward_record/shadow/20260102_positions.parquet"))

    def test_a6_review006b_trigger(self) -> None:
        result = check_review_006b_trigger({"date": "20260102", "review_006b_trigger_ready": True})

        self.assertTrue(result.triggered)

    def test_a6_review006b_no_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "20260101_alert_log.json"
            _json(log, {"alerts_sent": [{"condition_id": "A-6"}]})

            result = check_review_006b_trigger(
                {"date": "20260102", "review_006b_trigger_ready": True},
                previous_alert_log=log,
            )

            self.assertFalse(result.triggered)

    def test_a7_forbidden_field_violation(self) -> None:
        result = check_forbidden_field_violation({
            "FORBIDDEN_live_trading": "POST_ATTEMPTED",
            "FORBIDDEN_order_endpoint": "NOT_ATTEMPTED",
            "FORBIDDEN_bybit_write": "NOT_ATTEMPTED",
        })

        self.assertTrue(result.triggered)

    def test_dry_run_no_actual_post(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _alert_fixture(Path(tmp), stop_gates=["S-2"])

            payload = run_forward_alerting(
                "20260102",
                review_numbers_path=paths["review_numbers"],
                monitor_config_path=paths["monitor_config"],
                alert_log_dir=paths["alert_dir"],
                force_dry_run=True,
            )

            self.assertTrue(payload["dry_run"])
            self.assertTrue(payload["discord_results"])
            self.assertEqual(payload["discord_results"][0]["status"], "DRY_RUN")
            self.assertFalse(payload["discord_results"][0]["external_post_attempted"])

    def test_alert_log_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _alert_fixture(Path(tmp))

            payload = run_forward_alerting(
                "20260102",
                review_numbers_path=paths["review_numbers"],
                monitor_config_path=paths["monitor_config"],
                alert_log_dir=paths["alert_dir"],
                force_dry_run=True,
            )

            alert_log = Path(payload["alert_log_path"])
            written = json.loads(alert_log.read_text(encoding="utf-8"))
            self.assertEqual(written["FORBIDDEN_live_trading"], "NOT_ATTEMPTED")
            self.assertIn("health_check", written)

    def test_run_forward_alerting_with_forward_record_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _alert_fixture(Path(tmp))

            payload = run_forward_alerting(
                "20260102",
                forward_record_config_path=paths["forward_record_config"],
                monitor_config_path=paths["monitor_config"],
                alert_log_dir=paths["alert_dir"],
                force_dry_run=True,
            )

            self.assertTrue(payload["dry_run"])
            self.assertTrue(Path(payload["alert_log_path"]).exists())


def _positions(path: Path, weights: list[float]) -> None:
    import pandas as pd
    rows = [
        {
            "symbol": f"S{i}",
            "weight": w,
            "weight_raw": w,
            "paper_execution_status": "FORBIDDEN",
            "live_trading_status": "FORBIDDEN",
        }
        for i, w in enumerate(weights)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _alert_fixture(base: Path, stop_gates: list[str] | None = None) -> dict:
    primary_dir = base / "primary"
    shadow_dir = base / "shadow"
    log_dir = base / "logs"
    alert_dir = base / "alerts"
    forward_record_config_dir = base / "configs"
    date = "20260102"
    previous = "20260101"
    _positions(primary_dir / f"{previous}_positions.parquet", [0.1, -0.1])
    _positions(primary_dir / f"{date}_positions.parquet", [0.1, -0.1])
    _positions(shadow_dir / f"{date}_positions.parquet", [0.1, -0.1])
    stats = {
        "date": date,
        "active_warning_gates": [],
        "active_stop_gates": stop_gates or [],
        "review_006b_trigger_ready": False,
        "paper_execution_status": "FORBIDDEN",
        "live_trading_status": "FORBIDDEN",
        "data_source": "MOCK",
    }
    _json(primary_dir / f"{previous}_forward_stats.json", {**stats, "date": previous, "active_stop_gates": []})
    _json(primary_dir / f"{date}_forward_stats.json", stats)
    _json(primary_dir / f"{date}_overlay_check.json", {"overlay_pass": True})
    _json(primary_dir / f"{date}_pnl.json", {"paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN"})
    _json(shadow_dir / f"{date}_forward_stats.json", stats)
    _json(shadow_dir / f"{date}_overlay_check.json", {"overlay_pass": True})
    _json(shadow_dir / f"{date}_pnl.json", {"paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN"})
    log_path = log_dir / f"{date}_forward_record.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("status=REVIEW_READY\n", encoding="utf-8")
    review_numbers = base / "REVIEW-009_NUMBERS.json"
    _json(review_numbers, {
        "outputs": {
            "log": str(log_path),
            "primary": {
                "positions": str(primary_dir / f"{date}_positions.parquet"),
                "forward_stats": str(primary_dir / f"{date}_forward_stats.json"),
                "overlay_check": str(primary_dir / f"{date}_overlay_check.json"),
                "pnl": str(primary_dir / f"{date}_pnl.json"),
            },
            "shadow": {
                "positions": str(shadow_dir / f"{date}_positions.parquet"),
                "forward_stats": str(shadow_dir / f"{date}_forward_stats.json"),
                "overlay_check": str(shadow_dir / f"{date}_overlay_check.json"),
                "pnl": str(shadow_dir / f"{date}_pnl.json"),
            },
        }
    })
    forward_record_config_dir.mkdir(parents=True, exist_ok=True)
    forward_record_config = forward_record_config_dir / "forward_record.yaml"
    forward_record_config.write_text(
        "\n".join([
            "output_paths:",
            f"  log: \"{log_path}\"",
            "  primary:",
            f"    positions: \"{primary_dir / date}_positions.parquet\"",
            f"    forward_stats: \"{primary_dir / date}_forward_stats.json\"",
            f"    overlay_check: \"{primary_dir / date}_overlay_check.json\"",
            f"    pnl: \"{primary_dir / date}_pnl.json\"",
            "  shadow:",
            f"    positions: \"{shadow_dir / date}_positions.parquet\"",
            f"    forward_stats: \"{shadow_dir / date}_forward_stats.json\"",
            f"    overlay_check: \"{shadow_dir / date}_overlay_check.json\"",
            f"    pnl: \"{shadow_dir / date}_pnl.json\"",
        ]) + "\n",
        encoding="utf-8",
    )
    monitor_config = base / "monitor.yaml"
    monitor_config.write_text(
        "\n".join([
            "bot_name: test_alerting",
            "environment: mock_test",
            "account_mode: read_only_monitor",
            "secrets_config_path: configs/monitor_secrets.local.yaml",
            "paper_execution_status: FORBIDDEN",
            "live_trading_status: FORBIDDEN",
            "alerts:",
            "  channels:",
            "    - type: discord",
            "      enabled: true",
            "      dry_run: true",
            "      secrets_env_webhook_url: TEST_UNUSED_CREDENTIAL",
            "      timeout_seconds: 10",
        ]) + "\n",
        encoding="utf-8",
    )
    return {
        "review_numbers": review_numbers,
        "monitor_config": monitor_config,
        "alert_dir": alert_dir,
        "forward_record_config": forward_record_config,
    }


if __name__ == "__main__":
    unittest.main()
