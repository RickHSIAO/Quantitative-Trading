"""TASK-014BS -- read-only adapter from the primary Forward Record output to the
TASK-014BR Pilot daily runner.

Strictly OFFLINE and read-only. It loads the COMPLETED 30-day Forward Record
*primary* artifacts (run key ``prev3y_crypto``, strategy
``prev3y_crypto_combined_paper_safe_variant``) and converts the authoritative
signal rows into the runner's normalized strategy-result schema. The shadow run
(``prev3y_crypto_shadow_a_roll12``) is never selected.

It performs no Bybit/Notion/Discord network, sends no order, mutates no
position, and changes no strategy parameter. It never reads dotenv files,
credentials, webhook files, or unrelated daily logs.

Authoritative artifacts (primary run ``prev3y_crypto``):
  * ``forward_summary.json``                  -> strategy identity, latest_date
  * ``<YYYYMMDD>_forward_stats.json``         -> record date, dry_run, status, variant
  * ``<YYYYMMDD>_pnl.json``                    -> record date, n_longs/n_shorts,
                                                  data_source, reproducibility.positions_rows
  * ``<YYYYMMDD>_positions.parquet``          -> per-symbol signal rows (symbol/side/weight)
  * ``dashboard/validation_30d.csv``          -> runner_status, safety_scan, dry_run,
                                                  signal_count, n_longs, n_shorts

Date convention (documented):
  Forward Record artifacts are keyed by the market-data record date in
  ``YYYYMMDD``. The Pilot run date (``YYYY-MM-DD``) is mapped to that exact
  calendar date; the system clock is NEVER used to pick a source. If the
  requested date is not represented by the source, the adapter fails closed.
  The result separately records the Pilot run date, the Forward Record record
  date, and the underlying market-data date (validated equal here).
"""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

PRIMARY_RUN_KEY = "prev3y_crypto"
SHADOW_RUN_KEY = "prev3y_crypto_shadow_a_roll12"
EXPECTED_STRATEGY_NAME = "prev3y_crypto_combined_paper_safe_variant"

PROTECTED_SYMBOLS = frozenset({"ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"})

ACCEPTABLE_SAFETY_SCAN = "PASS"
FAILED_RUNNER_STATUSES = frozenset({"FAILED", "ERROR", "STOPPED", "ABORTED"})


class ForwardSourceError(Exception):
    """Fail-closed error loading the primary Forward Record source."""


@dataclass(frozen=True)
class SourceArtifact:
    role: str
    path: str          # repository-relative, sanitized
    sha256: str
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "path": self.path, "sha256": self.sha256, "size": self.size}


@dataclass(frozen=True)
class ForwardStrategySourceResult:
    run_key: str
    strategy_name: str
    requested_run_date: str        # Pilot run date YYYY-MM-DD
    forward_record_date: str       # YYYY-MM-DD (artifact record date)
    market_data_date: str          # YYYY-MM-DD (date inside pnl/stats)
    source_data_date: str          # YYYY-MM-DD (== market_data_date here)
    source_data_status: str        # data_source, e.g. "cache_fallback"
    runner_status: str
    safety_scan_status: str
    dry_run: bool
    signal_count: int
    normalized_signals: tuple
    current_position_snapshot: Mapping[str, Any]
    source_artifacts: tuple
    source_fingerprint: str
    warnings: tuple

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_key": self.run_key,
            "strategy_name": self.strategy_name,
            "requested_run_date": self.requested_run_date,
            "forward_record_date": self.forward_record_date,
            "market_data_date": self.market_data_date,
            "source_data_date": self.source_data_date,
            "source_data_status": self.source_data_status,
            "runner_status": self.runner_status,
            "safety_scan_status": self.safety_scan_status,
            "dry_run": self.dry_run,
            "signal_count": self.signal_count,
            "normalized_signals": [dict(s) for s in self.normalized_signals],
            "current_position_snapshot": dict(self.current_position_snapshot),
            "source_artifacts": [a.to_dict() for a in self.source_artifacts],
            "source_fingerprint": self.source_fingerprint,
            "warnings": list(self.warnings),
        }

    def to_strategy_result(self) -> dict[str, Any]:
        """Return the runner-compatible strategy-result dict (no secrets)."""
        return {
            "data_date": self.source_data_date,
            "data_status": self.source_data_status,
            "signals": [dict(s) for s in self.normalized_signals],
            "forward_summary": {"strategy": self.strategy_name},
            "run_key": self.run_key,
            "market_data_date": self.market_data_date,
            "source_metadata": {
                "run_key": self.run_key,
                "strategy_name": self.strategy_name,
                "forward_record_date": self.forward_record_date,
                "market_data_date": self.market_data_date,
                "source_data_status": self.source_data_status,
                "runner_status": self.runner_status,
                "safety_scan_status": self.safety_scan_status,
                "dry_run": self.dry_run,
                "signal_count": self.signal_count,
                "source_fingerprint": self.source_fingerprint,
                "source_artifacts": [a.to_dict() for a in self.source_artifacts],
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compact(date_iso: str) -> str:
    try:
        return datetime.strptime(date_iso, "%Y-%m-%d").strftime("%Y%m%d")
    except (ValueError, TypeError) as exc:
        raise ForwardSourceError(f"invalid requested run date {date_iso!r} (expected YYYY-MM-DD)") from exc


def _iso(compact: str) -> str:
    return datetime.strptime(compact, "%Y%m%d").strftime("%Y-%m-%d")


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise ForwardSourceError(f"missing source artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ForwardSourceError(f"malformed JSON in {path}: {exc}") from exc


def _hash_artifact(path: pathlib.Path, role: str, repo_root: pathlib.Path) -> SourceArtifact:
    if not path.exists():
        raise ForwardSourceError(f"missing source artifact ({role}): {path}")
    data = path.read_bytes()
    rel = path.resolve().relative_to(repo_root.resolve())
    return SourceArtifact(role=role, path=str(rel).replace("\\", "/"),
                          sha256="sha256:" + hashlib.sha256(data).hexdigest(), size=len(data))


def _default_positions_reader(path: pathlib.Path) -> list[dict[str, Any]]:
    import pandas as pd  # local import; only needed for the real parquet path
    try:
        df = pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001
        raise ForwardSourceError(f"unable to read positions parquet {path}: {exc}") from exc
    return [dict(r) for r in df.to_dict(orient="records")]


def _core_symbol(raw: str) -> str:
    s = str(raw or "").strip().upper()
    if ":" in s:
        s = s.split(":", 1)[1]
    if s.endswith(".P"):
        s = s[:-2]
    return s


def _read_validation_row(csv_path: pathlib.Path, compact_date: str) -> dict[str, str]:
    if not csv_path.exists():
        raise ForwardSourceError(f"missing validation_30d.csv: {csv_path}")
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as exc:
        raise ForwardSourceError(f"malformed validation_30d.csv {csv_path}: {exc}") from exc
    matches = [r for r in rows if str(r.get("date", "")).strip() == compact_date]
    if not matches:
        raise ForwardSourceError(
            f"requested date {compact_date} not represented in validation_30d.csv")
    if len(matches) > 1:
        raise ForwardSourceError(f"duplicate conflicting validation rows for {compact_date}")
    return matches[0]


def load_primary_forward_strategy_result(
    *,
    run_date: str,
    repo_root: pathlib.Path | str,
    forward_source_root: pathlib.Path | str | None = None,
    positions_reader: Callable[[pathlib.Path], Sequence[Mapping[str, Any]]] | None = None,
) -> ForwardStrategySourceResult:
    """Load and validate the primary Forward Record source for ``run_date``.

    Fails closed on any missing/malformed/ambiguous/mismatched/shadow/stale
    evidence. Returns a frozen result; never selects the shadow run; never reads
    credentials; never uses the system clock to choose a source.
    """
    repo_root = pathlib.Path(repo_root)
    root = pathlib.Path(forward_source_root) if forward_source_root is not None \
        else repo_root / "outputs" / "forward_record"
    primary_dir = root / PRIMARY_RUN_KEY
    if not primary_dir.exists():
        raise ForwardSourceError(f"missing primary Forward Record directory: {primary_dir}")

    compact = _compact(run_date)
    warnings: list[str] = []

    # --- forward_summary.json (strategy identity) ---
    summary_path = primary_dir / "forward_summary.json"
    summary = _read_json(summary_path)
    strategy = str(summary.get("strategy", "")).strip()
    if not strategy:
        raise ForwardSourceError("forward_summary.json missing 'strategy'")
    if "shadow" in strategy.lower():
        raise ForwardSourceError(f"refusing shadow strategy {strategy!r}")
    if strategy != EXPECTED_STRATEGY_NAME:
        raise ForwardSourceError(
            f"strategy mismatch: summary={strategy!r} expected={EXPECTED_STRATEGY_NAME!r}")
    latest_date = str(summary.get("latest_date", "")).strip()
    if not latest_date:
        raise ForwardSourceError("forward_summary.json missing 'latest_date'")
    if compact > latest_date:
        raise ForwardSourceError(
            f"requested date {compact} is newer than the Forward Record latest_date "
            f"{latest_date} (not represented / stale summary)")

    # --- per-date stats + pnl ---
    stats_path = primary_dir / f"{compact}_forward_stats.json"
    pnl_path = primary_dir / f"{compact}_pnl.json"
    positions_path = primary_dir / f"{compact}_positions.parquet"
    if not stats_path.exists() or not pnl_path.exists():
        raise ForwardSourceError(f"requested date {compact} not represented by primary source artifacts")
    stats = _read_json(stats_path)
    pnl = _read_json(pnl_path)

    stats_date = str(stats.get("date", "")).strip()
    pnl_date = str(pnl.get("date", "")).strip()
    if stats_date != compact or pnl_date != compact:
        raise ForwardSourceError(
            f"source record-date mismatch: requested={compact} stats={stats_date} pnl={pnl_date}")
    market_data_date = compact  # validated equal to the record date

    if str(stats.get("variant", "")).strip() != "combined_paper_safe_variant":
        raise ForwardSourceError(f"unexpected forward_stats variant {stats.get('variant')!r}")

    dry_run = bool(stats.get("dry_run", False)) and bool(pnl.get("dry_run", False))
    if not dry_run:
        raise ForwardSourceError("non-dry-run Forward Record source unexpectedly observed")

    data_source = str(pnl.get("data_source", "")).strip() or "unknown"

    # --- validation_30d.csv (authoritative runner/safety/signal counts) ---
    csv_path = root / "dashboard" / "validation_30d.csv"
    vrow = _read_validation_row(csv_path, compact)
    runner_status = str(vrow.get("runner_status", "")).strip()
    if not runner_status or runner_status.upper() in FAILED_RUNNER_STATUSES:
        raise ForwardSourceError(f"Forward Record runner failed/invalid: status={runner_status!r}")
    safety_scan = str(vrow.get("safety_scan", "")).strip()
    if safety_scan != ACCEPTABLE_SAFETY_SCAN:
        raise ForwardSourceError(f"Forward Record safety scan not PASS: {safety_scan!r}")
    if str(vrow.get("dry_run", "")).strip().lower() not in ("true", "1"):
        raise ForwardSourceError("validation_30d.csv dry_run is not true")

    try:
        v_signal_count = int(vrow.get("signal_count", "0") or "0")
        v_longs = int(vrow.get("n_longs", "0") or "0")
        v_shorts = int(vrow.get("n_shorts", "0") or "0")
    except (TypeError, ValueError) as exc:
        raise ForwardSourceError(f"malformed signal counts in validation_30d.csv: {exc}") from exc

    try:
        p_longs = int(pnl.get("n_longs", 0) or 0)
        p_shorts = int(pnl.get("n_shorts", 0) or 0)
        positions_rows = int((pnl.get("reproducibility", {}) or {}).get("positions_rows", -1))
    except (TypeError, ValueError) as exc:
        raise ForwardSourceError(f"malformed pnl counts: {exc}") from exc

    if v_signal_count != v_longs + v_shorts:
        raise ForwardSourceError(
            f"signal_count {v_signal_count} != n_longs+n_shorts {v_longs + v_shorts} (validation_30d.csv)")
    if (p_longs, p_shorts) != (v_longs, v_shorts):
        raise ForwardSourceError(
            f"pnl counts ({p_longs},{p_shorts}) != validation counts ({v_longs},{v_shorts})")
    if positions_rows != v_signal_count:
        raise ForwardSourceError(
            f"positions_rows {positions_rows} != signal_count {v_signal_count}")

    # --- positions parquet (authoritative per-symbol signal rows) ---
    signal_count = v_signal_count
    normalized: list[dict[str, Any]] = []
    if signal_count > 0:
        reader = positions_reader or _default_positions_reader
        rows = list(reader(positions_path))
        if len(rows) != signal_count:
            raise ForwardSourceError(
                f"positions rows {len(rows)} != signal_count {signal_count}")
        seen: dict[str, str] = {}
        n_long = n_short = 0
        for row in rows:
            raw_symbol = str(row.get("symbol", "")).strip()
            side = str(row.get("side", "")).strip().lower()
            if not raw_symbol:
                raise ForwardSourceError("positions row missing symbol")
            if side not in ("long", "short"):
                raise ForwardSourceError(f"unsupported direction {side!r} for {raw_symbol!r}")
            core = _core_symbol(raw_symbol)
            if not core:
                raise ForwardSourceError(f"unable to normalize symbol {raw_symbol!r}")
            if core in seen and seen[core] != side:
                raise ForwardSourceError(f"duplicate conflicting signal for {core}: {seen[core]} vs {side}")
            if core in seen:
                raise ForwardSourceError(f"duplicate signal row for {core}")
            seen[core] = side
            n_long += 1 if side == "long" else 0
            n_short += 1 if side == "short" else 0
            score = ""
            if "weight" in row:
                try:
                    score = format(abs(float(row.get("weight") or 0)), "f")
                except (TypeError, ValueError):
                    score = ""
            entry = {"symbol": core, "side": side, "score": score, "source_reference": raw_symbol}
            if core in PROTECTED_SYMBOLS:
                entry["eligibility_hint"] = "PROTECTED_SYMBOL_BLOCKED"
            normalized.append(entry)
        if (n_long, n_short) != (v_longs, v_shorts):
            raise ForwardSourceError(
                f"parsed direction counts ({n_long},{n_short}) != authoritative ({v_longs},{v_shorts})")
        normalized.sort(key=lambda e: (e["symbol"], e["side"]))
    else:
        # A legitimate zero-signal day: the positions artifact must still be a
        # structurally valid (empty) file, but no rows are required.
        if not positions_path.exists():
            warnings.append("zero_signal_day_no_positions_artifact")

    # --- artifact hashing (exact bytes; deterministic order) ---
    artifacts = [
        _hash_artifact(summary_path, "forward_summary", repo_root),
        _hash_artifact(stats_path, "forward_stats", repo_root),
        _hash_artifact(pnl_path, "pnl", repo_root),
        _hash_artifact(csv_path, "validation_30d_csv", repo_root),
    ]
    if positions_path.exists():
        artifacts.append(_hash_artifact(positions_path, "positions", repo_root))
    artifacts.sort(key=lambda a: a.role)
    source_fingerprint = hashlib.sha256(
        json.dumps([[a.role, a.sha256, a.size] for a in artifacts], sort_keys=True).encode("utf-8")
    ).hexdigest()

    return ForwardStrategySourceResult(
        run_key=PRIMARY_RUN_KEY,
        strategy_name=strategy,
        requested_run_date=run_date,
        forward_record_date=_iso(compact),
        market_data_date=_iso(market_data_date),
        source_data_date=_iso(market_data_date),
        source_data_status=data_source,
        runner_status=runner_status,
        safety_scan_status=safety_scan,
        dry_run=dry_run,
        signal_count=signal_count,
        normalized_signals=tuple(normalized),
        current_position_snapshot={"symbol": "", "side": "", "qty": "0"},
        source_artifacts=tuple(artifacts),
        source_fingerprint=source_fingerprint,
        warnings=tuple(warnings),
    )


__all__ = [
    "EXPECTED_STRATEGY_NAME",
    "ForwardSourceError",
    "ForwardStrategySourceResult",
    "PRIMARY_RUN_KEY",
    "PROTECTED_SYMBOLS",
    "SHADOW_RUN_KEY",
    "SourceArtifact",
    "TASK_ID",
    "load_primary_forward_strategy_result",
]

TASK_ID = "TASK-014BS"
