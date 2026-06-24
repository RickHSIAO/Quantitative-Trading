"""TASK-014CH2 -- explicit opt-in, terminal Plan-only WebSocket-bound orchestration.

This module is the narrow seam that connects the existing native REST seed Plan to
the existing WS binder (``demo_strategy_native_ws_price_binding``) and the completed
CH1 consumer (``demo_strategy_native_ws_bound_plan_consumer``), producing exactly one
canonical WS-bound Plan wrapper artifact.

Hard scope (CH2):

  * It is a Plan-only path: it NEVER reaches readiness, the execution gate, native
    execution, or any Pilot-state mutation, and it never authorizes execution.
  * It performs NO WebSocket collection and opens NO socket. The source WS evidence
    artifact is supplied by the caller (read from a local JSON file by the CLI).
  * It imports neither a sender, a runner, readiness, the execution gate, native
    execution, the live ``BybitExecutor``, ``main`` nor ``src.risk``. It contains no
    order-endpoint string and cannot place / amend / cancel an order.
  * There is NO REST fallback: the REST seed Plan is only an upstream binding seed.
    Any WS-stage failure is terminal; the seed Plan is never used as a result Plan.

Separation of concerns: :func:`build_and_validate_ws_bound_plan_only` is a PURE
build+validation core (no file/network/clock). File reads and the single atomic
artifact write are thin helpers used by the CLI.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_bound_plan_consumer as consumer
from src import demo_strategy_native_ws_price_binding as wb

TASK_ID = "TASK-014CH2"

# Fixed Strategy-native V1 expectations (caller ground truth; never inferred from
# the produced wrapper).
EXPECTED_POLICY_ID = wb.ACTIVE_STRATEGY_NATIVE_V1_POLICY
EXPECTED_STRATEGY_ID = wb.EXPECTED_STRATEGY_NAME
EXPECTED_STRATEGY_SYMBOL_COUNT = wb.EXPECTED_STRATEGY_SYMBOL_COUNT  # 50
DEFAULT_FRESHNESS_THRESHOLD_MS = wb.DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS  # 10_000
STRICT_MAX_FRESHNESS_THRESHOLD_MS = wb.DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS  # 10_000

# --- Status vocabulary ------------------------------------------------------
WS_BOUND_PLAN_ONLY_PASS = "WS_BOUND_PLAN_ONLY_PASS"
WS_BOUND_PLAN_ONLY_INPUT_INVALID = "WS_BOUND_PLAN_ONLY_INPUT_INVALID"
WS_BOUND_PLAN_ONLY_SOURCE_READ_FAILED = "WS_BOUND_PLAN_ONLY_SOURCE_READ_FAILED"
WS_BOUND_PLAN_ONLY_SOURCE_JSON_INVALID = "WS_BOUND_PLAN_ONLY_SOURCE_JSON_INVALID"
WS_BOUND_PLAN_ONLY_BINDING_FAILED = "WS_BOUND_PLAN_ONLY_BINDING_FAILED"
WS_BOUND_PLAN_ONLY_CONSUMER_FAILED = "WS_BOUND_PLAN_ONLY_CONSUMER_FAILED"
WS_BOUND_PLAN_ONLY_OUTPUT_FAILED = "WS_BOUND_PLAN_ONLY_OUTPUT_FAILED"
WS_BOUND_PLAN_ONLY_OUTPUT_EXISTS = "WS_BOUND_PLAN_ONLY_OUTPUT_EXISTS"


class WsBoundPlanOnlyError(ValueError):
    """Raised by the thin file helpers (read/write); the pure core never raises."""


@dataclass(frozen=True)
class WsBoundPlanOnlyResult:
    status: str
    blockers: tuple[str, ...]
    wrapper_artifact: Mapping[str, Any] | None
    canonical_bound_plan_fingerprint: str | None
    source_ws_artifact_fingerprint: str | None
    source_ws_artifact_sha256: str | None
    original_plan_fingerprint: str | None
    binding_epoch_ns: int | None
    freshness_threshold_ms: int | None
    execution_authorized: bool
    pilot_advanced: bool

    @property
    def passed(self) -> bool:
        return self.status == WS_BOUND_PLAN_ONLY_PASS


def _is_pos_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


# ---------------------------------------------------------------------------
# Pure build + validation core (no file / network / clock)
# ---------------------------------------------------------------------------

def build_and_validate_ws_bound_plan_only(
    *,
    seed_plan: Mapping[str, Any],
    source_ws_artifact: Mapping[str, Any],
    source_ws_artifact_bytes: bytes,
    binding_epoch_ns: int,
    freshness_threshold_ms: int,
    expected_policy_id: str,
    expected_strategy_id: str,
    expected_run_date: str,
    expected_symbols: Sequence[str],
    source_ws_artifact_path: str = "WS_TICKER_EVIDENCE",
) -> WsBoundPlanOnlyResult:
    """Bind the REST seed Plan to the source WS evidence and validate the result
    through the CH1 consumer. Pure, deterministic, and fail-closed (returns a result
    rather than raising for malformed JSON-compatible input). The wrapper is exposed
    ONLY when the consumer returns PASS.

    The EXACT ``source_ws_artifact_bytes`` are the single source of truth: they are
    parsed inside this core and that parsed object drives the logical fingerprint, the
    binder input AND the CH1 consumer source artifact. The byte SHA256 is computed from
    those same exact bytes; the original seed-Plan fingerprint is computed BEFORE
    binding. ``source_ws_artifact`` is retained for compatibility and MUST deep-equal
    the exact-bytes parse (else fail closed); it is never used as a fallback parse."""

    def _fail(status: str, *blockers: str) -> WsBoundPlanOnlyResult:
        return WsBoundPlanOnlyResult(
            status=status, blockers=tuple(blockers), wrapper_artifact=None,
            canonical_bound_plan_fingerprint=None,
            source_ws_artifact_fingerprint=None, source_ws_artifact_sha256=None,
            original_plan_fingerprint=None, binding_epoch_ns=None,
            freshness_threshold_ms=None, execution_authorized=False, pilot_advanced=False)

    # --- Input validation (fail closed) ---------------------------------------
    if not _is_pos_int(binding_epoch_ns):
        return _fail(WS_BOUND_PLAN_ONLY_INPUT_INVALID, "binding_epoch_ns_not_positive_int")
    if not _is_pos_int(freshness_threshold_ms):
        return _fail(WS_BOUND_PLAN_ONLY_INPUT_INVALID, "freshness_threshold_ms_not_positive_int")
    if freshness_threshold_ms > STRICT_MAX_FRESHNESS_THRESHOLD_MS:
        return _fail(WS_BOUND_PLAN_ONLY_INPUT_INVALID, "freshness_threshold_exceeds_strict_max")
    if not isinstance(source_ws_artifact_bytes, (bytes, bytearray)):
        return _fail(WS_BOUND_PLAN_ONLY_INPUT_INVALID, "source_ws_artifact_bytes_not_bytes")
    if not isinstance(seed_plan, Mapping):
        return _fail(WS_BOUND_PLAN_ONLY_INPUT_INVALID, "seed_plan_not_mapping")
    sym_list = [str(s).strip().upper() for s in (expected_symbols or [])]
    if len(set(sym_list)) != EXPECTED_STRATEGY_SYMBOL_COUNT or len(sym_list) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        return _fail(WS_BOUND_PLAN_ONLY_INPUT_INVALID, "expected_symbols_not_exactly_fifty_unique")

    # --- EXACT bytes are authoritative: parse them HERE (no caller fallback) ---
    try:
        parsed_source = json.loads(bytes(source_ws_artifact_bytes))
    except (json.JSONDecodeError, ValueError, TypeError):
        return _fail(WS_BOUND_PLAN_ONLY_SOURCE_JSON_INVALID, "source_ws_bytes_invalid_json")
    if not isinstance(parsed_source, Mapping):
        return _fail(WS_BOUND_PLAN_ONLY_SOURCE_JSON_INVALID, "source_ws_bytes_not_object")
    # Compatibility guard: the supplied Mapping must MATCH the exact-bytes parse.
    if not isinstance(source_ws_artifact, Mapping):
        return _fail(WS_BOUND_PLAN_ONLY_INPUT_INVALID, "source_ws_artifact_not_mapping")
    if dict(source_ws_artifact) != dict(parsed_source):
        return _fail(WS_BOUND_PLAN_ONLY_INPUT_INVALID, "source_ws_mapping_does_not_match_exact_bytes")

    # --- Independent anchors derived from the EXACT bytes / their parse --------
    byte_sha256 = wb.compute_file_sha256(bytes(source_ws_artifact_bytes))
    try:
        recomputed_source_fp = ws._fingerprint(
            {k: v for k, v in parsed_source.items() if k != "artifact_fingerprint"})
    except (TypeError, ValueError):
        return _fail(WS_BOUND_PLAN_ONLY_INPUT_INVALID, "source_ws_artifact_fingerprint_unrecomputable")
    try:
        original_plan_fingerprint = wb._fingerprint(dict(seed_plan))
    except (TypeError, ValueError):
        return _fail(WS_BOUND_PLAN_ONLY_INPUT_INVALID, "seed_plan_fingerprint_unrecomputable")

    # --- Bind (existing WS binder) -- uses the exact-bytes parse as input ------
    try:
        wrapper = wb.build_ws_bound_plan_artifact(
            plan_artifact=seed_plan, ws_artifact=parsed_source,
            ws_artifact_path=str(source_ws_artifact_path), ws_artifact_sha256=byte_sha256,
            binding_epoch_ns=binding_epoch_ns,
            binding_freshness_threshold_ms=freshness_threshold_ms)
    except wb.WsPriceBindingError as exc:
        return _fail(WS_BOUND_PLAN_ONLY_BINDING_FAILED, f"binder_error:{exc}")
    except (KeyError, TypeError, ValueError) as exc:  # noqa: BLE001
        return _fail(WS_BOUND_PLAN_ONLY_BINDING_FAILED, f"binder_error:{type(exc).__name__}")

    if not isinstance(wrapper, Mapping) or wrapper.get("canonical_bound_plan") is None:
        overall = str(_as_str(wrapper, "overall_binding_status"))
        return _fail(WS_BOUND_PLAN_ONLY_BINDING_FAILED,
                     f"no_canonical_bound_plan:{overall}")

    # --- Validate through the CH1 consumer (same exact-bytes parse) -----------
    result = consumer.validate_ws_bound_plan_artifact(
        wrapper,
        source_ws_artifact=parsed_source,
        expected_policy_id=expected_policy_id,
        expected_strategy_id=expected_strategy_id,
        expected_run_date=expected_run_date,
        expected_original_plan_fingerprint=original_plan_fingerprint,
        expected_ws_artifact_sha256=byte_sha256,
        expected_ws_artifact_fingerprint=recomputed_source_fp,
        expected_binding_epoch_ns=binding_epoch_ns,
        expected_freshness_threshold_ms=freshness_threshold_ms,
        expected_symbols=sym_list)

    if not result.passed:
        return WsBoundPlanOnlyResult(
            status=WS_BOUND_PLAN_ONLY_CONSUMER_FAILED,
            blockers=tuple([result.status, *result.failure_codes, *result.blockers]),
            wrapper_artifact=None,
            canonical_bound_plan_fingerprint=None,
            source_ws_artifact_fingerprint=None,
            source_ws_artifact_sha256=byte_sha256,
            original_plan_fingerprint=original_plan_fingerprint,
            binding_epoch_ns=binding_epoch_ns,
            freshness_threshold_ms=freshness_threshold_ms,
            execution_authorized=False, pilot_advanced=False)

    return WsBoundPlanOnlyResult(
        status=WS_BOUND_PLAN_ONLY_PASS,
        blockers=(),
        wrapper_artifact=wrapper,
        canonical_bound_plan_fingerprint=result.canonical_bound_plan_fingerprint,
        source_ws_artifact_fingerprint=recomputed_source_fp,
        source_ws_artifact_sha256=byte_sha256,
        original_plan_fingerprint=original_plan_fingerprint,
        binding_epoch_ns=binding_epoch_ns,
        freshness_threshold_ms=freshness_threshold_ms,
        execution_authorized=False, pilot_advanced=False)


def _as_str(m: Any, key: str) -> Any:
    return m.get(key) if isinstance(m, Mapping) else None


# ---------------------------------------------------------------------------
# Thin file helpers (the only impure surface)
# ---------------------------------------------------------------------------

def read_source_ws_bytes(path: str | Path) -> bytes:
    """Read the exact bytes of the source WS evidence file. Raises
    :class:`WsBoundPlanOnlyError` on any read failure (no network)."""
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise WsBoundPlanOnlyError(f"source ws evidence unreadable: {exc}") from exc


def parse_source_ws_artifact(raw: bytes) -> Mapping[str, Any]:
    """Parse the source WS evidence bytes into a JSON object Mapping. Raises
    :class:`WsBoundPlanOnlyError` on invalid JSON or a non-object root."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WsBoundPlanOnlyError(f"source ws evidence is not valid JSON: {exc}") from exc
    if not isinstance(data, Mapping):
        raise WsBoundPlanOnlyError("source ws evidence JSON root is not an object")
    return data


def atomic_write_wrapper(path: str | Path, wrapper: Mapping[str, Any]) -> None:
    """Publish exactly one canonical wrapper artifact with ATOMIC create-if-absent
    semantics. The wrapper is written UNMODIFIED.

    Race-safe no-clobber: the final pathname is created with ``os.link`` (hard link
    from the fully-written temp), which atomically fails ``FileExistsError`` when the
    destination already exists -- including a destination created by another process
    between the preflight check and publication. ``os.replace`` is deliberately NOT
    used because it would overwrite such a racing destination. Unsupported link
    behavior fails closed (never falls back to an overwriting publish). Only the
    task-created temp pathname is ever removed; an existing destination is never
    deleted, unlinked, replaced or truncated."""
    p = Path(path)
    # Fast secondary defense; the atomic os.link below is the authoritative guarantee.
    if os.path.lexists(p):
        raise WsBoundPlanOnlyError(f"output destination already exists (no clobber): {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    # Temp in the destination directory => same filesystem (hard link is valid).
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(wrapper, fh, ensure_ascii=False, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
        except Exception as exc:  # noqa: BLE001  (serialization / write failure)
            raise WsBoundPlanOnlyError(f"failed to serialize wrapper artifact: {exc}") from exc
        # Atomic create-if-absent publication: succeeds ONLY when p does not exist.
        try:
            os.link(tmp, p)
        except FileExistsError as exc:
            raise WsBoundPlanOnlyError(
                f"output destination already exists (no clobber): {p}") from exc
        except (OSError, NotImplementedError, AttributeError) as exc:
            raise WsBoundPlanOnlyError(
                f"atomic no-clobber publication unsupported/failed: {exc}") from exc
    finally:
        # Remove ONLY the task-created temp pathname; a linked destination survives.
        try:
            os.unlink(tmp)
        except OSError:
            pass


__all__ = [
    "TASK_ID",
    "EXPECTED_POLICY_ID", "EXPECTED_STRATEGY_ID", "EXPECTED_STRATEGY_SYMBOL_COUNT",
    "DEFAULT_FRESHNESS_THRESHOLD_MS", "STRICT_MAX_FRESHNESS_THRESHOLD_MS",
    "WS_BOUND_PLAN_ONLY_PASS", "WS_BOUND_PLAN_ONLY_INPUT_INVALID",
    "WS_BOUND_PLAN_ONLY_SOURCE_READ_FAILED", "WS_BOUND_PLAN_ONLY_SOURCE_JSON_INVALID",
    "WS_BOUND_PLAN_ONLY_BINDING_FAILED", "WS_BOUND_PLAN_ONLY_CONSUMER_FAILED",
    "WS_BOUND_PLAN_ONLY_OUTPUT_FAILED", "WS_BOUND_PLAN_ONLY_OUTPUT_EXISTS",
    "WsBoundPlanOnlyError", "WsBoundPlanOnlyResult",
    "build_and_validate_ws_bound_plan_only",
    "read_source_ws_bytes", "parse_source_ws_artifact", "atomic_write_wrapper",
]
