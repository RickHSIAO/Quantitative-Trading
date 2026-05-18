from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


MANDATORY_CAVEATS = {
    "caveat_1_sample_size": (
        "Strategy backtest covers 760 active days (2024-04-01 to 2026-04-30) "
        "only. Forward performance may differ materially."
    ),
    "caveat_2_btc_ir": (
        "IR vs BTC = -0.0017 for the high_funding_cost_filter reference. "
        "Paper planning does not imply BTC outperformance."
    ),
    "caveat_3_concentration": (
        "Top 5 symbols remain a structural concentration risk. "
        "TASK-008 strategy-layer cap is the permanent fix."
    ),
    "caveat_4_long_side": (
        "Long-side net alpha is structurally negative at baseline. "
        "combined_paper_safe_variant turns long net positive historically, "
        "but this has not been forward validated."
    ),
    "caveat_5_forward_only": (
        "All numbers are historical planning outputs. This does not approve "
        "paper or live trading."
    ),
    "live_trading_status": "FORBIDDEN",
}


@dataclass(frozen=True)
class PaperTradingConfig:
    output_date: str = "20260516"
    baseline_run_id: str = "20260513_run008"
    variant_run_id: str = "20260515_task007"
    initial_nav_usd: float = 10_000.0
    currency: str = "USDT"
    venue: str = "bybit_perp"
    account_type: str = "offline_simulation_only"
    primary_variant: str = "combined_paper_safe_variant"
    secondary_variant: str = "high_funding_cost_filter"
    funding_threshold_8h: float = 0.0003
    funding_window_days: int = 30
    long_cap_gross_share: float = 0.50
    symbol_cap_abs_weight: float = 0.05
    taker_fee_bps: float = 5.5
    slippage_bps: float = 5.0
    annualization_factor: float = 365.25
    forward_validation_days: int = 30
    baseline_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv")
    positions_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet")
    prices_path: Path = Path("data/crypto/prices_daily.parquet")
    funding_path: Path = Path("data/crypto/funding_rates.parquet")
    task007_daily_path: Path = Path("outputs/variants/prev3y_crypto/20260515_task007_variant_daily.csv")
    task007_summary_path: Path = Path("outputs/variants/prev3y_crypto/20260515_task007_variant_summary.csv")
    review007_numbers_path: Path = Path("docs/research/review_packets/REVIEW-007_NUMBERS.json")
    output_dir: Path = Path("outputs/paper_trading/prev3y_crypto")
    log_dir: Path = Path("outputs/logs/prev3y_crypto")
    review_packet_path: Path = Path("docs/research/review_packets/REVIEW-006_PACKET.md")
    review_numbers_path: Path = Path("docs/research/review_packets/REVIEW-006_NUMBERS.json")
    mandatory_caveats: dict[str, str] = field(default_factory=lambda: dict(MANDATORY_CAVEATS))

    def input_paths(self) -> dict[str, Path]:
        return {
            "run008_baseline_csv": self.baseline_path,
            "run008_positions_parquet": self.positions_path,
            "prices_daily_parquet": self.prices_path,
            "funding_rates_parquet": self.funding_path,
            "task007_daily_csv": self.task007_daily_path,
            "task007_summary_csv": self.task007_summary_path,
            "review007_numbers_json": self.review007_numbers_path,
        }

