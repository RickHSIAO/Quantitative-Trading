from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from apps.paper_trading.config import PaperTradingConfig


@dataclass(frozen=True)
class ForwardRecordConfig:
    output_date: str = "20260517"
    strategy_config: Path = Path("configs/prev3y_crypto.yaml")
    output_dir: Path = Path("outputs/forward_record/prev3y_crypto")
    shadow_output_dir: Path = Path("outputs/forward_record/prev3y_crypto_shadow_a_roll12")
    log_dir: Path = Path("outputs/logs/prev3y_crypto")
    review_packet_path: Path = Path("docs/research/review_packets/REVIEW-009_PACKET.md")
    review_numbers_path: Path = Path("docs/research/review_packets/REVIEW-009_NUMBERS.json")
    primary_variant: str = "combined_paper_safe_variant"
    shadow_variant: str = "A_roll12_share20_exclude"
    dry_run: bool = True
    shadow_track: bool = False
    data_source: str = "cache_fallback"
    clock_started: bool = False
    paper_execution_status: str = "FORBIDDEN"
    live_trading_status: str = "FORBIDDEN"
    task008_detail_path: Path = Path("outputs/variants/prev3y_crypto/20260517_task008_variant_detail.csv")
    task008_comparison_path: Path = Path("outputs/variants/prev3y_crypto/20260517_task008_comparison.json")
    paper_config: PaperTradingConfig = field(default_factory=PaperTradingConfig)

    @property
    def positions_path(self) -> Path:
        return self.paper_config.positions_path

    @property
    def prices_path(self) -> Path:
        return self.paper_config.prices_path

    @property
    def funding_path(self) -> Path:
        return self.paper_config.funding_path

    @property
    def baseline_path(self) -> Path:
        return self.paper_config.baseline_path

    def with_runtime(
        self,
        *,
        output_date: str | None = None,
        output_dir: Path | None = None,
        dry_run: bool | None = None,
        shadow_track: bool | None = None,
        data_source: str | None = None,
    ) -> "ForwardRecordConfig":
        return ForwardRecordConfig(
            output_date=output_date or self.output_date,
            strategy_config=self.strategy_config,
            output_dir=output_dir or self.output_dir,
            shadow_output_dir=self.shadow_output_dir,
            log_dir=self.log_dir,
            review_packet_path=self.review_packet_path,
            review_numbers_path=self.review_numbers_path,
            primary_variant=self.primary_variant,
            shadow_variant=self.shadow_variant,
            dry_run=self.dry_run if dry_run is None else dry_run,
            shadow_track=self.shadow_track if shadow_track is None else shadow_track,
            data_source=data_source or self.data_source,
            clock_started=self.clock_started,
            paper_execution_status=self.paper_execution_status,
            live_trading_status=self.live_trading_status,
            task008_detail_path=self.task008_detail_path,
            task008_comparison_path=self.task008_comparison_path,
            paper_config=self.paper_config,
        )

