from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AttributionConfig:
    baseline_run_id: str = "20260513_run008"
    cost_stress_run_id: str = "20260515"
    primary_scenario: str = "realistic_combo"
    output_date: str = "20260515"
    tolerance: float = 1e-6
    annualization_factor: float = 365.25
    std_ddof: int = 1
    baseline_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv")
    positions_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet")
    stats_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_stats.json")
    cost_stress_path: Path = Path("outputs/backtests/prev3y_crypto/20260515_cost_stress.csv")
    positions_cost_path: Path = Path("outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet")
    cost_summary_path: Path = Path("outputs/backtests/prev3y_crypto/20260515_cost_stress_summary.json")
    prices_path: Path = Path("data/crypto/prices_daily.parquet")
    universe_path: Path = Path("data/crypto/universe_membership.parquet")
    funding_path: Path = Path("data/crypto/funding_rates.parquet")
    prev3y_config_path: Path = Path("configs/prev3y_crypto.yaml")
    output_dir: Path = Path("outputs/attribution/prev3y_crypto")
    log_dir: Path = Path("outputs/logs/prev3y_crypto")
    known_funding_gap_symbols: tuple[str, ...] = (
        "BYBIT:XTZUSDT.P",
        "BYBIT:FLOWUSDT.P",
        "BYBIT:LPTUSDT.P",
        "BYBIT:AXSUSDT.P",
        "BYBIT:RVNUSDT.P",
        "BYBIT:INJUSDT.P",
        "BYBIT:CTCUSDT.P",
    )
    warning_thresholds: dict[str, float] = field(default_factory=lambda: {
        "top5_symbol_concentration": 0.60,
        "single_symbol_concentration": 0.25,
        "funding_gap_concentration": 0.20,
        "single_year_concentration": 0.70,
        "short_side_drag_pct_gross": 0.50,
        "gross_net_rank_divergence": 10.0,
    })

    def input_paths(self) -> dict[str, Path]:
        return {
            "run008_baseline_csv": self.baseline_path,
            "run008_positions_parquet": self.positions_path,
            "run008_stats_json": self.stats_path,
            "cost_stress_csv": self.cost_stress_path,
            "cost_stress_positions_cost_parquet": self.positions_cost_path,
            "cost_stress_summary_json": self.cost_summary_path,
            "prices_daily_parquet": self.prices_path,
            "universe_membership_parquet": self.universe_path,
            "funding_rates_parquet": self.funding_path,
            "prev3y_crypto_yaml": self.prev3y_config_path,
        }

