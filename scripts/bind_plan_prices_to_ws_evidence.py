"""scripts/bind_plan_prices_to_ws_evidence.py
TASK-014CG: Plan-only same-message WebSocket price binding (local-artifact-only).

This is the THIN CLI around the pure logic in
``src/demo_strategy_native_ws_price_binding.py``. It:

  * reads a local Plan-only run artifact (the Strategy-native V1 planner output);
  * reads a local canonical public WebSocket ticker evidence artifact;
  * binds each of the 50 Strategy planner actions to the EXACT same WebSocket
    source message that supplied its selected ``lastPrice``; and
  * writes a canonical, fingerprinted ``strategy_native_ws_price_binding``
    artifact.

It performs ZERO network I/O (no private, public, WebSocket or order request),
imports no order/transport sender, creates no execution authorization marker, and
NEVER authorizes execution. The opt-in is explicit: the binding only runs when
``--bind-plan-prices-to-ws-evidence`` is supplied together with an explicit
``--ws-ticker-evidence-json`` path. There is no auto-discovery of the newest
artifact, and no path can transition from binding into send.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_strategy_native_ws_price_binding as wb  # noqa: E402

# Stable documented exit codes (mirror the WS collector's vocabulary).
EXIT_COMPLETE = 0
EXIT_INVALID_CONFIG = 2
EXIT_SOURCE_FAILURE = 3
EXIT_PARTIAL = 5
EXIT_CONFLICT = 6
EXIT_SAFETY = 7

# Env var that, if set to a non-empty value, signals an execution authorization
# marker is present. The binding path MUST refuse to run when it is set.
_EXECUTION_AUTH_MARKER_ENV = "DEMO_EXECUTION_AUTHORIZATION_MARKER"
_SENDER_REACHABLE_ENV = "DEMO_SENDER_REACHABLE"

# Env var names that MIGHT hold credentials. The binder never uses them; the
# optional leak check reads them ONLY to prove they never reach the artifact.
_CREDENTIAL_ENV_NAMES = (
    "BYBIT_API_KEY", "BYBIT_API_SECRET", "BYBIT_DEMO_API_KEY",
    "BYBIT_DEMO_API_SECRET", "API_KEY", "API_SECRET",
)


def _in_test_or_temp_context(out_path: str | None) -> bool:
    """True only inside an explicit pytest run or when writing under a temp dir.
    Unsafe test-only overrides (a forced binding epoch) are rejected outside it."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    tmp = os.path.realpath(tempfile.gettempdir())
    if out_path:
        try:
            if os.path.realpath(os.path.dirname(out_path) or ".").startswith(tmp):
                return True
        except OSError:
            return False
    return False


def _read_json(path: str) -> dict[str, Any]:
    with open(path, "rb") as fh:
        return json.loads(fh.read())


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="TASK-014CG Plan-only same-message WebSocket price binding "
                    "(local-artifact-only; performs no network or order I/O).")
    ap.add_argument("--plan-json", required=True,
                    help="Path to the local Plan-only run artifact (planner block).")
    ap.add_argument("--ws-ticker-evidence-json", required=True,
                    help="Explicit path to the local public WebSocket evidence artifact.")
    ap.add_argument("--bind-plan-prices-to-ws-evidence", action="store_true",
                    help="Explicit Plan-only opt-in. Required to perform binding.")
    ap.add_argument("--binding-freshness-threshold-ms", type=int,
                    default=wb.DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS,
                    help="Strict binding-time freshness threshold (never loosened).")
    ap.add_argument("--require-complete", action="store_true",
                    help="Exit non-zero unless 50/50 bindings COMPLETE + parity PASS.")
    ap.add_argument("--out", default=None, help="Artifact output path (JSON).")
    ap.add_argument("--verify-no-credential-leak", action="store_true",
                    help="Prove credential env values never reach the artifact.")
    ap.add_argument("--json-only", action="store_true")
    # Test-only override (gated to a pytest / temp context).
    ap.add_argument("--unsafe-test-binding-epoch-ns", default=None,
                    help="TEST ONLY: force the binding epoch (ns).")
    ap.add_argument("--unsafe-allow-test-overrides", action="store_true",
                    help="TEST ONLY: enable unsafe overrides (pytest/temp only).")
    args = ap.parse_args(argv)

    # The opt-in is mandatory; default behavior is to do nothing.
    if not args.bind_plan_prices_to_ws_evidence:
        print(json.dumps({
            "status": "REFUSED_OPT_IN_REQUIRED",
            "detail": "pass --bind-plan-prices-to-ws-evidence with an explicit "
                      "--ws-ticker-evidence-json path to perform Plan-only binding.",
            "execution_batch_authorized": False, "order_post_count": 0,
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_INVALID_CONFIG

    # Fail closed if an execution authorization marker is present or the sender is
    # reachable: binding is a Plan-only path and must never run in a send context.
    if os.environ.get(_EXECUTION_AUTH_MARKER_ENV, "").strip():
        print(json.dumps({"status": "REFUSED_EXECUTION_AUTHORIZATION_MARKER_PRESENT",
                          "execution_batch_authorized": False, "order_post_count": 0},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_SAFETY
    if os.environ.get(_SENDER_REACHABLE_ENV, "").strip():
        print(json.dumps({"status": "REFUSED_SENDER_REACHABLE_ENABLED",
                          "execution_batch_authorized": False, "order_post_count": 0},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_SAFETY

    # Resolve the binding epoch (real wall clock; test override gated).
    binding_epoch_ns = time.time_ns()
    if args.unsafe_test_binding_epoch_ns is not None:
        if not (args.unsafe_allow_test_overrides and _in_test_or_temp_context(args.out)):
            print(json.dumps({"status": "REFUSED_TEST_ONLY_OPTION",
                              "detail": "--unsafe-test-binding-epoch-ns is pytest/temp only"},
                             ensure_ascii=False, indent=2, sort_keys=True))
            return EXIT_INVALID_CONFIG
        try:
            binding_epoch_ns = int(args.unsafe_test_binding_epoch_ns)
        except (TypeError, ValueError):
            print(json.dumps({"status": "REFUSED_INVALID_BINDING_EPOCH"},
                             ensure_ascii=False, indent=2, sort_keys=True))
            return EXIT_INVALID_CONFIG

    # Read local artifacts (no network).
    try:
        plan_artifact = _read_json(args.plan_json)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "INPUT_FAILURE",
                          "detail": f"plan artifact unreadable: {exc}"},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_SOURCE_FAILURE
    try:
        ws_bytes = _read_bytes(args.ws_ticker_evidence_json)
        ws_artifact = json.loads(ws_bytes)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "INPUT_FAILURE",
                          "detail": f"ws artifact unreadable: {exc}"},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_SOURCE_FAILURE

    ws_sha256 = wb.compute_file_sha256(ws_bytes)

    try:
        # CG_FIX1: emit the canonical revised Plan-only artifact (wrapper whose
        # canonical_bound_plan field is the 50 WS-priced target positions), not
        # only the sidecar audit overlay.
        artifact = wb.build_ws_bound_plan_artifact(
            plan_artifact=plan_artifact, ws_artifact=ws_artifact,
            ws_artifact_path=args.ws_ticker_evidence_json, ws_artifact_sha256=ws_sha256,
            binding_epoch_ns=binding_epoch_ns,
            binding_freshness_threshold_ms=args.binding_freshness_threshold_ms)
    except wb.WsPriceBindingError as exc:
        print(json.dumps({"status": "INPUT_FAILURE",
                          "detail": f"binding input invalid: {exc}"},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_SOURCE_FAILURE

    # Optional credential-leak verification.
    if args.verify_no_credential_leak:
        secret_values = [os.environ[name] for name in _CREDENTIAL_ENV_NAMES
                         if os.environ.get(name)]
        try:
            wb.ws.assert_no_credentials(artifact, secret_values=secret_values)
            artifact["credential_leak_check"] = "NO_CREDENTIAL_VALUE_OR_KEY_PRESENT"
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"status": "CREDENTIAL_LEAK_DETECTED", "detail": str(exc)},
                             ensure_ascii=False, indent=2, sort_keys=True))
            return EXIT_SAFETY

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(artifact, fh, ensure_ascii=False, indent=2, sort_keys=True)

    overall = artifact["overall_binding_status"]
    parity = artifact["wrapper_parity_status"]
    canonical_complete = (artifact["canonical_bound_plan"] is not None
                          and artifact["execution_grade_freshness_complete"] is True
                          and parity == wb.WS_PLANNER_BINDING_PARITY_PASS)
    if canonical_complete:
        exit_code = EXIT_COMPLETE
    elif overall == wb.WS_PLANNER_PRICE_BINDING_CONFLICT:
        exit_code = EXIT_CONFLICT
    elif overall == wb.WS_PLANNER_PRICE_BINDING_UNAVAILABLE:
        exit_code = EXIT_SOURCE_FAILURE
    else:
        exit_code = EXIT_PARTIAL
    artifact["cli_exit_status"] = exit_code

    if args.json_only or args.out is None:
        print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "overall_binding_status": overall,
            "wrapper_parity_status": parity,
            "canonical_revised_action_count": artifact["canonical_revised_action_count"],
            "bound_action_count": artifact["bound_action_count"],
            "failed_action_count": artifact["failed_action_count"],
            "canonical_bound_plan_present": artifact["canonical_bound_plan"] is not None,
            "execution_grade_freshness_complete": artifact["execution_grade_freshness_complete"],
            "execution_batch_authorized": artifact["execution_batch_authorized"],
            "order_post_count": artifact["order_post_count"],
            "cli_exit_status": exit_code,
            "out": args.out,
        }, ensure_ascii=False, indent=2, sort_keys=True))

    if args.require_complete and exit_code != EXIT_COMPLETE:
        return exit_code
    return EXIT_COMPLETE if not args.require_complete else exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
