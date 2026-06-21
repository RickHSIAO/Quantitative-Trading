"""TASK-014BP CLI -- demo-only single reduce-only close runner.

Two modes:

    preflight (default)
        Read-only. NEVER sends an order, NEVER arms a journal. Prints every
        gate, the permanent close orderLinkId, the sanitized body preview, the
        request-body hash, the source TASK-014BO opening-journal evidence, the
        current-position evidence, the close duplicate-check evidence, the close
        journal state, and the exact manual VPS commands. Authenticated
        position / duplicate checks run ONLY with --allow-real-network and usable
        Demo credentials; otherwise they are reported as not performed and the
        preflight is never ready.

    execute_once
        The ONLY path that can send the single authorized reduce-only close, and
        only when run manually on the VPS with every exact control flag. Sends at
        most one POST /v5/order/create (reduceOnly=true) to
        https://api-demo.bybit.com, then performs read-only verification.

Default invocation and --help never perform any network I/O and never send.

Exit codes:
    0  preflight ready / execute produced a verified or accepted close
    1  not ready / refused / post failed
    2  hard safety violation / forbidden configuration / ambiguous / critical
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_only_tiny_execution_adapter_single_real_demo_order as bo  # noqa: E402
from src import demo_only_single_reduce_only_close as bp  # noqa: E402


EXIT_READY = 0
EXIT_NOT_READY = 1
EXIT_SAFETY = 2


# ---------------------------------------------------------------------------
# Offline fixture probe (default preflight, no network)
# ---------------------------------------------------------------------------


class _OfflineFixtureProbe:
    """Non-authoritative offline probe. run_close_preflight does NOT call it
    without --allow-real-network; defined for completeness only."""

    def build_close_snapshot(self) -> bp.ClosePositionSnapshot:
        return bp.ClosePositionSnapshot(
            instrument_fresh=True, symbol_tradable=True,
            min_order_qty=Decimal("0.1"), qty_step=Decimal("0.1"),
            long_size=Decimal("0.1"), short_size=Decimal("0"), long_row_count=1,
            position_mode_one_way=True, ambiguous=False, read_source="fixture",
        )

    def lookup_order_link_realtime(self, *, order_link_id):
        return {"retCode": 0, "result": {"list": []}}

    def lookup_order_link_history(self, *, order_link_id):
        return {"retCode": 0, "result": {"list": []}}


# ---------------------------------------------------------------------------
# Real read-only probe (manual VPS path only)
# ---------------------------------------------------------------------------


class _RealReadOnlyCloseProbe:
    """Read-only api-demo.bybit.com probe for the close preflight/verification.

    Performs signed GETs to the Demo host ONLY; never posts an order. The API
    secret is held privately and never returned or printed.
    """

    def __init__(self, *, api_key: str, api_secret: str, recv_window: str) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._recv_window = recv_window

    def _signed_get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        import time
        import hmac
        import hashlib
        import urllib.parse
        import urllib.request

        query = urllib.parse.urlencode(sorted(params.items()))
        url = f"{bo.DEMO_BASE_URL}{path}" + (f"?{query}" if query else "")
        bo.assert_demo_url(url)
        timestamp = str(int(time.time() * 1000))
        sign_input = timestamp + self._api_key + self._recv_window + query
        signature = hmac.new(
            self._api_secret.encode("utf-8"), sign_input.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        headers = {
            "X-BAPI-API-KEY": self._api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self._recv_window,
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"retCode": -1, "retMsg": str(exc), "result": {}}

    def build_close_snapshot(self) -> bp.ClosePositionSnapshot:
        instr = self._signed_get(bo.EP_INSTRUMENTS, {"category": "linear", "symbol": bp.REQUIRED_SYMBOL})
        positions = self._signed_get(bo.EP_POSITION_LIST, {"category": "linear", "settleCoin": "USDT"})

        min_qty = step = None
        tradable = False
        try:
            it = (instr.get("result", {}) or {}).get("list", [])[0]
            lot = it.get("lotSizeFilter", {}) or {}
            min_qty = Decimal(str(lot.get("minOrderQty", "0")))
            step = Decimal(str(lot.get("qtyStep", "0")))
            tradable = str(it.get("status", "")) == "Trading"
        except (IndexError, KeyError, TypeError, ValueError):
            pass

        long_size = Decimal("0")
        short_size = Decimal("0")
        long_rows = 0
        one_way = True
        ambiguous = False
        try:
            for p in (positions.get("result", {}) or {}).get("list", []) or []:
                if str(p.get("symbol", "")) != bp.REQUIRED_SYMBOL:
                    continue
                try:
                    size = Decimal(str(p.get("size", "0") or "0"))
                except (InvalidOperation, TypeError):
                    ambiguous = True
                    continue
                if int(p.get("positionIdx", 0) or 0) in (1, 2):
                    one_way = False
                side = str(p.get("side", ""))
                if size == 0:
                    continue
                if side == "Buy":
                    long_size += size
                    long_rows += 1
                elif side == "Sell":
                    short_size += size
                else:
                    ambiguous = True
        except (KeyError, TypeError):
            ambiguous = True

        return bp.ClosePositionSnapshot(
            instrument_fresh=min_qty is not None,
            symbol_tradable=tradable,
            min_order_qty=min_qty, qty_step=step,
            long_size=long_size if long_rows else None,
            short_size=short_size if short_size != 0 else None,
            long_row_count=long_rows,
            position_mode_one_way=one_way, ambiguous=ambiguous,
            read_source="bybit_demo_readonly",
        )

    def lookup_order_link_realtime(self, *, order_link_id):
        return self._signed_get(bo.EP_ORDER_REALTIME, {
            "category": "linear", "symbol": bp.REQUIRED_SYMBOL, "orderLinkId": order_link_id})

    def lookup_order_link_history(self, *, order_link_id):
        return self._signed_get(bo.EP_ORDER_HISTORY, {
            "category": "linear", "symbol": bp.REQUIRED_SYMBOL, "orderLinkId": order_link_id})

    def read_order_realtime(self, *, order_id, order_link_id):
        params = {"category": "linear", "symbol": bp.REQUIRED_SYMBOL}
        if order_id:
            params["orderId"] = order_id
        elif order_link_id:
            params["orderLinkId"] = order_link_id
        return self._signed_get(bo.EP_ORDER_REALTIME, params)

    def read_order_history(self, *, order_id, order_link_id):
        params = {"category": "linear", "symbol": bp.REQUIRED_SYMBOL}
        if order_id:
            params["orderId"] = order_id
        elif order_link_id:
            params["orderLinkId"] = order_link_id
        return self._signed_get(bo.EP_ORDER_HISTORY, params)

    def read_execution_list(self, *, order_id, order_link_id):
        params = {"category": "linear", "symbol": bp.REQUIRED_SYMBOL}
        if order_id:
            params["orderId"] = order_id
        return self._signed_get(bo.EP_EXECUTION_LIST, params)

    def read_position_list(self, *, symbol):
        return self._signed_get(bo.EP_POSITION_LIST, {"category": "linear", "symbol": symbol})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _actual_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def _source_journal() -> Mapping[str, Any] | None:
    # The source TASK-014BO opening journal is read locally (no network).
    return bo.canonical_journal().read()


def _preflight_command(*, expected_commit: str) -> str:
    commit = expected_commit if bo.is_full_commit_sha(expected_commit) else "<FULL_40_CHARACTER_COMMIT_SHA>"
    return (
        "python scripts/run_demo_only_single_reduce_only_close.py \\\n"
        "  --mode preflight \\\n"
        "  --allow-real-network \\\n"
        f"  --authorization-marker {bp.CLOSE_AUTHORIZATION_MARKER} \\\n"
        f"  --expected-commit {commit}"
    )


def _manual_command(*, expected_commit: str, body_hash: str) -> str:
    commit = expected_commit if bo.is_full_commit_sha(expected_commit) else "<FULL_40_CHARACTER_COMMIT_SHA>"
    return (
        "python scripts/run_demo_only_single_reduce_only_close.py \\\n"
        "  --mode execute_once \\\n"
        "  --allow-real-network \\\n"
        "  --execute-one-reduce-only-close \\\n"
        f"  --authorization-marker {bp.CLOSE_AUTHORIZATION_MARKER} \\\n"
        f"  --expected-commit {commit} \\\n"
        f"  --request-body-hash {body_hash}"
    )


def _write_reports(output_dir: str, name: str, payload: Mapping[str, Any]) -> dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = os.path.join(output_dir, f"{name}_{stamp}.json")
    md_path = os.path.join(output_dir, f"{name}_{stamp}.md")
    latest_json = os.path.join(output_dir, f"latest_{name}.json")
    latest_md = os.path.join(output_dir, f"latest_{name}.md")
    body = json.dumps(payload, indent=2, sort_keys=True)
    md = "# " + name + "\n\n```json\n" + body + "\n```\n"
    for p, content in ((json_path, body), (latest_json, body), (md_path, md), (latest_md, md)):
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
    return {"json": json_path, "json_latest": latest_json, "md": md_path, "md_latest": latest_md}


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def _run_preflight(args: argparse.Namespace) -> int:
    actual_commit = _actual_commit()
    credentials = bo.load_demo_credentials()

    if args.allow_real_network and credentials.usable:
        probe: Any = _RealReadOnlyCloseProbe(
            api_key=os.environ.get(bo.ENV_DEMO_API_KEY, ""),
            api_secret=os.environ.get(bo.ENV_DEMO_API_SECRET, ""),
            recv_window=credentials.recv_window,
        )
    else:
        probe = _OfflineFixtureProbe()

    journal = bp.canonical_close_journal()

    report = bp.run_close_preflight(
        probe=probe,
        credentials=credentials,
        expected_commit=args.expected_commit,
        authorization_marker=args.authorization_marker or bp.CLOSE_AUTHORIZATION_MARKER,
        source_journal=_source_journal(),
        actual_commit=actual_commit,
        journal_state=journal.state(),
        expected_body_hash=(args.request_body_hash or None),
        allow_real_network=bool(args.allow_real_network),
        mode="preflight",
    )

    payload = report.to_dict()
    payload["allow_real_network"] = bool(args.allow_real_network)
    payload["canonical_close_journal_path"] = str(bp.CANONICAL_CLOSE_JOURNAL_DIR)
    payload["manual_preflight_command"] = _preflight_command(
        expected_commit=args.expected_commit or actual_commit)
    payload["manual_execute_command"] = _manual_command(
        expected_commit=args.expected_commit or actual_commit, body_hash=report.request_body_hash)
    payload["residual_authorization_note"] = bp.RESIDUAL_AUTHORIZATION_NOTE

    if args.write_report:
        _write_reports(args.output_dir, "task_014bp_close_preflight", payload)
        payload["report_written"] = True

    if args.json_only:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_READY if report.ready else EXIT_NOT_READY

    print(f"TASK-014BP reduce-only close -- PREFLIGHT (mode={report.mode})")
    print(f"  close_marker_matches         : {report.authorization_marker_matches}")
    print(f"  expected_commit              : {report.expected_commit or '(none)'}")
    print(f"  actual_commit                : {report.actual_commit or '(unknown)'}")
    print(f"  credentials_source           : {report.credentials_source}")
    print(f"  close orderLinkId (permanent): {report.order_link_id}")
    print(f"  request_body_hash            : {report.request_body_hash}")
    print(f"  canonical_close_journal_path : {payload['canonical_close_journal_path']}")
    print(f"  close_journal_state          : {report.close_journal_state}")
    print(f"  source_journal_evidence      : {report.source_journal_summary}")
    print(f"  position_evidence            : {report.position_evidence}")
    print(f"  duplicate_check              : {report.duplicate_check.get('detail') if report.duplicate_check else None}")
    print("  request body preview         :")
    print("    " + json.dumps(dict(report.request_body)))
    print("  gates:")
    for g in report.gates:
        flag = "PASS" if g.passed else "FAIL"
        print(f"    [{g.index:2d}] {flag} {g.name}" + (f"  -- {g.detail}" if not g.passed and g.detail else ""))
    print(f"  ALL GATES PASSED             : {report.all_passed}")
    print(f"  READY FOR MANUAL CLOSE       : {report.ready}")
    print("")
    print("  " + bp.RESIDUAL_AUTHORIZATION_NOTE)
    print("")
    print("  EXACT AUTHENTICATED VPS PREFLIGHT COMMAND:")
    for line in payload["manual_preflight_command"].splitlines():
        print("    " + line)
    print("")
    print("  EXACT MANUAL VPS EXECUTE COMMAND (only after a fresh passing authenticated preflight):")
    for line in payload["manual_execute_command"].splitlines():
        print("    " + line)
    return EXIT_READY if report.ready else EXIT_NOT_READY


# ---------------------------------------------------------------------------
# Execute-once (manual VPS path only)
# ---------------------------------------------------------------------------


def _run_execute_once(args: argparse.Namespace) -> int:
    if not args.allow_real_network:
        print("REFUSED: execute_once requires --allow-real-network (manual VPS path only).", file=sys.stderr)
        return EXIT_SAFETY
    if not args.execute_one_reduce_only_close:
        print("REFUSED: execute_once requires --execute-one-reduce-only-close.", file=sys.stderr)
        return EXIT_SAFETY
    if args.authorization_marker != bp.CLOSE_AUTHORIZATION_MARKER:
        print("REFUSED: close authorization marker mismatch/missing.", file=sys.stderr)
        return EXIT_SAFETY
    if not args.expected_commit:
        print("REFUSED: execute_once requires --expected-commit (full 40-char SHA).", file=sys.stderr)
        return EXIT_SAFETY
    if not args.request_body_hash:
        print("REFUSED: execute_once requires --request-body-hash from a fresh preflight.", file=sys.stderr)
        return EXIT_SAFETY

    credentials = bo.load_demo_credentials()
    if not credentials.usable:
        print("REFUSED: Demo credentials (BYBIT_DEMO_API_KEY / BYBIT_DEMO_API_SECRET) absent.", file=sys.stderr)
        return EXIT_SAFETY

    transport = bo.RealDemoHttpTransport(
        api_key=os.environ.get(bo.ENV_DEMO_API_KEY, ""),
        api_secret=os.environ.get(bo.ENV_DEMO_API_SECRET, ""),
        recv_window=credentials.recv_window,
    )
    probe = _RealReadOnlyCloseProbe(
        api_key=os.environ.get(bo.ENV_DEMO_API_KEY, ""),
        api_secret=os.environ.get(bo.ENV_DEMO_API_SECRET, ""),
        recv_window=credentials.recv_window,
    )
    sender = bo.OneShotSenderGuard(transport)
    journal = bp.canonical_close_journal()

    report = bp.execute_single_reduce_only_close(
        probe=probe, sender=sender, transport=transport, credentials=credentials,
        journal=journal, source_journal=_source_journal(),
        expected_commit=args.expected_commit, actual_commit=_actual_commit(),
        authorization_marker=args.authorization_marker,
        execution_flags={"mode": bp.REQUIRED_EXECUTE_MODE, bp.REQUIRED_EXECUTE_FLAG: True},
        expected_body_hash=args.request_body_hash, real_order_count_before=0,
    )

    payload = report.to_dict()
    if args.write_report:
        _write_reports(args.output_dir, "task_014bp_close_execution", payload)
        payload["report_written"] = True

    print(json.dumps(payload, indent=2, sort_keys=True))
    print("")
    print(bp.RESIDUAL_AUTHORIZATION_NOTE, file=sys.stderr)

    outcome = report.final_outcome
    if outcome == bp.OUTCOME_CRITICAL_SHORT or report.outcome_ambiguous:
        return EXIT_SAFETY
    if outcome in (bp.OUTCOME_FILLED_ZERO, bp.OUTCOME_PARTIAL_RESIDUAL,
                   bp.OUTCOME_CANCELLED_REMAINS, bp.OUTCOME_REJECTED, bp.OUTCOME_ACCEPTED_PENDING):
        return EXIT_READY
    return EXIT_NOT_READY


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_demo_only_single_reduce_only_close.py",
        description=("TASK-014BP demo-only single reduce-only close runner. "
                     "Default mode is preflight (read-only, never sends)."),
    )
    p.add_argument("--mode", choices=["preflight", "execute_once"], default="preflight")
    p.add_argument("--allow-real-network", action="store_true",
                   help="enable real api-demo.bybit.com read-only I/O (manual VPS path)")
    p.add_argument("--execute-one-reduce-only-close", action="store_true",
                   help="explicit one-shot close control (execute_once only)")
    p.add_argument("--authorization-marker", default="")
    p.add_argument("--expected-commit", default="",
                   help="full 40-character lowercase hex commit SHA")
    p.add_argument("--request-body-hash", default="")
    p.add_argument("--write-report", action="store_true")
    p.add_argument("--output-dir", default=bp.DEFAULT_CLOSE_JOURNAL_DIR,
                   help="optional report output dir (the one-shot close JOURNAL path is canonical "
                        "and NOT configurable)")
    p.add_argument("--json-only", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode == "execute_once":
        return _run_execute_once(args)
    return _run_preflight(args)


if __name__ == "__main__":
    raise SystemExit(main())
