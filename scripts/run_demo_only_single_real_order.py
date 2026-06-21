"""TASK-014BO CLI -- demo-only single real Bybit Demo order runner.

Two modes:

    preflight (default)
        Read-only. NEVER sends an order. Prints every preflight gate, the
        sanitized request preview, the request-body hash, the orderLinkId,
        the journal state, and the exact manual VPS execute command. Exits 0
        only when every gate passes (ready for the final manual command).

    execute_once
        The ONLY path that can send the single authorized real Demo order,
        and only when run manually on the VPS with ``--allow-real-network``
        and every exact control flag. Sends at most one POST /v5/order/create
        to https://api-demo.bybit.com, then performs read-only verification.

Default invocation and ``--help`` never perform any network I/O and never
send an order.

Exit codes:
    0  ready (preflight all gates pass) / execute_once produced a verified or
       accepted outcome
    1  not ready (a preflight gate failed) / order refused or post failed
    2  hard safety violation / forbidden configuration / ambiguous outcome
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_only_tiny_execution_adapter_single_real_demo_order as bo  # noqa: E402


EXIT_READY = 0
EXIT_NOT_READY = 1
EXIT_SAFETY = 2


# ---------------------------------------------------------------------------
# Offline fixture probe (default preflight, no network)
# ---------------------------------------------------------------------------


class _OfflineFixtureProbe:
    """Returns a representative passing snapshot WITHOUT any network I/O.

    Used for the default offline structural preflight preview only. It is NOT
    an authoritative account read; an authoritative preflight requires
    ``--allow-real-network`` on the VPS.
    """

    def build_account_snapshot(self) -> bo.AccountSnapshot:
        return bo.AccountSnapshot(
            instrument_fresh=True,
            symbol_tradable=True,
            min_order_qty=Decimal("0.1"),
            qty_step=Decimal("0.1"),
            mark_price=Decimal("150"),
            mark_price_fresh=True,
            open_order_symbols=(),
            position_sizes={},
            available_balance_usdt=Decimal("8500"),
            position_mode_one_way=True,
            read_source="fixture",
        )

    # Offline structural preview: report a clean (empty) duplicate check. This
    # is NON-AUTHORITATIVE; the real duplicate check requires --allow-real-network.
    def lookup_order_link_realtime(self, *, order_link_id: str) -> dict:
        return {"retCode": 0, "retMsg": "OK", "result": {"list": []}}

    def lookup_order_link_history(self, *, order_link_id: str) -> dict:
        return {"retCode": 0, "retMsg": "OK", "result": {"list": []}}


# ---------------------------------------------------------------------------
# Real read-only probe (only with --allow-real-network on the VPS)
# ---------------------------------------------------------------------------


class _RealReadOnlyProbe:
    """Read-only api-demo.bybit.com probe used by the manual VPS path.

    Performs signed GET requests to the Demo host ONLY. Never posts an order.
    The API secret is held privately and never returned or printed.
    """

    def __init__(self, *, api_key: str, api_secret: str, recv_window: str) -> None:
        self._transport = bo.RealDemoHttpTransport(
            api_key=api_key, api_secret=api_secret, recv_window=recv_window
        )
        self._api_key = api_key
        self._api_secret = api_secret
        self._recv_window = recv_window

    # NOTE: signed GET helpers are defined here (read-only). They never call
    # /v5/order/create. Kept minimal; the heavy validated read-only client
    # (src/demo_readonly_client.py) is reused for wallet/positions/instruments.
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
        except Exception as exc:  # read failures fail closed at the gate level
            return {"retCode": -1, "retMsg": str(exc), "result": {}}

    def build_account_snapshot(self) -> bo.AccountSnapshot:
        instr = self._signed_get(bo.EP_INSTRUMENTS, {"category": "linear", "symbol": bo.REQUIRED_SYMBOL})
        tick = self._signed_get(bo.EP_TICKERS, {"category": "linear", "symbol": bo.REQUIRED_SYMBOL})
        orders = self._signed_get(bo.EP_OPEN_ORDERS, {"category": "linear", "symbol": bo.REQUIRED_SYMBOL})
        positions = self._signed_get(bo.EP_POSITION_LIST, {"category": "linear", "settleCoin": "USDT"})
        wallet = self._signed_get(bo.EP_WALLET, {"accountType": "UNIFIED"})

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

        mark = None
        try:
            t = (tick.get("result", {}) or {}).get("list", [])[0]
            mark = Decimal(str(t.get("markPrice", t.get("lastPrice", "0"))))
        except (IndexError, KeyError, TypeError, ValueError):
            pass

        open_syms = []
        try:
            for o in (orders.get("result", {}) or {}).get("list", []) or []:
                open_syms.append(str(o.get("symbol", "")))
        except (KeyError, TypeError):
            pass

        pos_sizes: dict[str, Decimal] = {}
        one_way = True
        try:
            for p in (positions.get("result", {}) or {}).get("list", []) or []:
                sym = str(p.get("symbol", ""))
                size = Decimal(str(p.get("size", "0") or "0"))
                if size != 0:
                    pos_sizes[sym] = size
                if int(p.get("positionIdx", 0) or 0) in (1, 2):
                    one_way = False
        except (KeyError, TypeError, ValueError):
            pass

        avail = None
        try:
            acc = (wallet.get("result", {}) or {}).get("list", [])[0]
            tab = acc.get("totalAvailableBalance")
            if tab is not None and str(tab).strip():
                avail = Decimal(str(tab))
        except (IndexError, KeyError, TypeError, ValueError):
            pass

        return bo.AccountSnapshot(
            instrument_fresh=min_qty is not None,
            symbol_tradable=tradable,
            min_order_qty=min_qty,
            qty_step=step,
            mark_price=mark,
            mark_price_fresh=mark is not None,
            open_order_symbols=tuple(open_syms),
            position_sizes=pos_sizes,
            available_balance_usdt=avail,
            position_mode_one_way=one_way,
            read_source="bybit_demo_readonly",
        )

    # Authenticated read-only duplicate detection by the exact fixed orderLinkId.
    def lookup_order_link_realtime(self, *, order_link_id: str) -> dict[str, Any]:
        return self._signed_get(bo.EP_ORDER_REALTIME, {
            "category": "linear", "symbol": bo.REQUIRED_SYMBOL, "orderLinkId": order_link_id})

    def lookup_order_link_history(self, *, order_link_id: str) -> dict[str, Any]:
        return self._signed_get(bo.EP_ORDER_HISTORY, {
            "category": "linear", "symbol": bo.REQUIRED_SYMBOL, "orderLinkId": order_link_id})

    def read_order_realtime(self, *, order_id: str, order_link_id: str) -> dict[str, Any]:
        params = {"category": "linear", "symbol": bo.REQUIRED_SYMBOL}
        if order_id:
            params["orderId"] = order_id
        elif order_link_id:
            params["orderLinkId"] = order_link_id
        return self._signed_get(bo.EP_ORDER_REALTIME, params)

    def read_order_history(self, *, order_id: str, order_link_id: str) -> dict[str, Any]:
        params = {"category": "linear", "symbol": bo.REQUIRED_SYMBOL}
        if order_id:
            params["orderId"] = order_id
        elif order_link_id:
            params["orderLinkId"] = order_link_id
        return self._signed_get(bo.EP_ORDER_HISTORY, params)

    def read_execution_list(self, *, order_id: str, order_link_id: str) -> dict[str, Any]:
        params = {"category": "linear", "symbol": bo.REQUIRED_SYMBOL}
        if order_id:
            params["orderId"] = order_id
        return self._signed_get(bo.EP_EXECUTION_LIST, params)

    def read_position_list(self, *, symbol: str) -> dict[str, Any]:
        return self._signed_get(bo.EP_POSITION_LIST, {"category": "linear", "symbol": symbol})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _actual_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def _manual_command(*, expected_commit: str, body_hash: str) -> str:
    commit = expected_commit if bo.is_full_commit_sha(expected_commit) else "<FULL_40_CHARACTER_CORRECTED_COMMIT_SHA>"
    return (
        "python scripts/run_demo_only_single_real_order.py \\\n"
        "  --mode execute_once \\\n"
        "  --allow-real-network \\\n"
        "  --execute-one-real-demo-order \\\n"
        f"  --authorization-marker {bo.AUTHORIZATION_MARKER} \\\n"
        f"  --expected-commit {commit} \\\n"
        f"  --request-body-hash {body_hash}"
    )


def _preflight_command(*, expected_commit: str) -> str:
    commit = expected_commit if bo.is_full_commit_sha(expected_commit) else "<FULL_40_CHARACTER_CORRECTED_COMMIT_SHA>"
    return (
        "python scripts/run_demo_only_single_real_order.py \\\n"
        "  --mode preflight \\\n"
        "  --allow-real-network \\\n"
        f"  --authorization-marker {bo.AUTHORIZATION_MARKER} \\\n"
        f"  --expected-commit {commit}"
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

    if args.allow_real_network:
        if not credentials.usable:
            probe: Any = _OfflineFixtureProbe()  # gate 3 will fail closed
        else:
            import os as _os

            probe = _RealReadOnlyProbe(
                api_key=_os.environ.get(bo.ENV_DEMO_API_KEY, ""),
                api_secret=_os.environ.get(bo.ENV_DEMO_API_SECRET, ""),
                recv_window=credentials.recv_window,
            )
    else:
        probe = _OfflineFixtureProbe()

    journal = bo.canonical_journal()

    report = bo.run_preflight(
        probe=probe,
        credentials=credentials,
        expected_commit=args.expected_commit,
        authorization_marker=args.authorization_marker or bo.AUTHORIZATION_MARKER,
        actual_commit=actual_commit,
        journal_state=journal.state(),
        expected_body_hash=(args.request_body_hash or None),
        allow_real_network=bool(args.allow_real_network),
        mode="preflight",
    )

    payload = report.to_dict()
    payload["read_source"] = getattr(probe.build_account_snapshot(), "read_source", "fixture")
    payload["allow_real_network"] = bool(args.allow_real_network)
    payload["canonical_journal_path"] = str(bo.CANONICAL_JOURNAL_DIR)
    payload["manual_preflight_command"] = _preflight_command(
        expected_commit=args.expected_commit or actual_commit)
    payload["manual_execute_command"] = _manual_command(
        expected_commit=args.expected_commit or actual_commit,
        body_hash=report.request_body_hash,
    )
    payload["position_open_warning"] = bo.POSITION_OPEN_WARNING

    written = {}
    if args.write_report:
        written = _write_reports(args.output_dir, "task_014bo_preflight", payload)
        payload["report_written"] = True

    if args.json_only:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_READY if report.ready else EXIT_NOT_READY

    print(f"TASK-014BO single real Demo order -- PREFLIGHT (mode={report.mode})")
    print(f"  authorization_marker_matches : {report.authorization_marker_matches}")
    print(f"  expected_commit              : {report.expected_commit or '(none supplied)'}")
    print(f"  actual_commit                : {report.actual_commit or '(unknown)'}")
    print(f"  credentials_source           : {report.credentials_source}")
    print(f"  read_source                  : {payload['read_source']}")
    print(f"  orderLinkId (date-independent): {report.order_link_id}")
    print(f"  request_body_hash            : {report.request_body_hash}")
    print(f"  canonical_journal_path       : {payload['canonical_journal_path']}")
    print(f"  journal_state                : {report.journal_state}")
    if report.duplicate_check is not None:
        print(f"  exchange_dup_check           : {report.duplicate_check.get('detail')}")
    print("  request body preview         :")
    print("    " + json.dumps(dict(report.request_body)))
    print("  gates:")
    for g in report.gates:
        flag = "PASS" if g.passed else "FAIL"
        print(f"    [{g.index:2d}] {flag} {g.name}" + (f"  -- {g.detail}" if not g.passed and g.detail else ""))
    print(f"  ALL GATES PASSED             : {report.all_passed}")
    print(f"  READY FOR MANUAL EXECUTE     : {report.ready}")
    print("")
    print("  " + bo.POSITION_OPEN_WARNING)
    print("")
    print("  EXACT MANUAL VPS EXECUTE COMMAND (run only after review + push + pull + creds):")
    for line in payload["manual_execute_command"].splitlines():
        print("    " + line)
    if written:
        print("")
        print(f"  report written: {written.get('json_latest')}")

    return EXIT_READY if report.ready else EXIT_NOT_READY


# ---------------------------------------------------------------------------
# Execute-once (manual VPS path only)
# ---------------------------------------------------------------------------


def _run_execute_once(args: argparse.Namespace) -> int:
    # Hard refusals before anything else.
    if not args.allow_real_network:
        print("REFUSED: execute_once requires --allow-real-network (manual VPS path only).", file=sys.stderr)
        return EXIT_SAFETY
    if not args.execute_one_real_demo_order:
        print("REFUSED: execute_once requires --execute-one-real-demo-order.", file=sys.stderr)
        return EXIT_SAFETY
    if args.authorization_marker != bo.AUTHORIZATION_MARKER:
        print("REFUSED: authorization marker mismatch/missing.", file=sys.stderr)
        return EXIT_SAFETY
    if not args.expected_commit:
        print("REFUSED: execute_once requires --expected-commit.", file=sys.stderr)
        return EXIT_SAFETY
    if not args.request_body_hash:
        print("REFUSED: execute_once requires --request-body-hash from a fresh preflight.", file=sys.stderr)
        return EXIT_SAFETY

    credentials = bo.load_demo_credentials()
    if not credentials.usable:
        print("REFUSED: Demo credentials (BYBIT_DEMO_API_KEY / BYBIT_DEMO_API_SECRET) absent.", file=sys.stderr)
        return EXIT_SAFETY

    actual_commit = _actual_commit()

    transport = bo.RealDemoHttpTransport(
        api_key=os.environ.get(bo.ENV_DEMO_API_KEY, ""),
        api_secret=os.environ.get(bo.ENV_DEMO_API_SECRET, ""),
        recv_window=credentials.recv_window,
    )
    probe = _RealReadOnlyProbe(
        api_key=os.environ.get(bo.ENV_DEMO_API_KEY, ""),
        api_secret=os.environ.get(bo.ENV_DEMO_API_SECRET, ""),
        recv_window=credentials.recv_window,
    )
    sender = bo.OneShotSenderGuard(transport)
    journal = bo.canonical_journal()

    report = bo.execute_single_real_demo_order(
        probe=probe,
        sender=sender,
        transport=transport,
        credentials=credentials,
        journal=journal,
        expected_commit=args.expected_commit,
        actual_commit=actual_commit,
        authorization_marker=args.authorization_marker,
        execution_flags={
            "mode": bo.REQUIRED_EXECUTE_MODE,
            bo.REQUIRED_EXECUTE_FLAG: True,
        },
        expected_body_hash=args.request_body_hash,
        real_order_count_before=0,
    )

    payload = report.to_dict()
    if args.write_report:
        _write_reports(args.output_dir, "task_014bo_execution", payload)
        payload["report_written"] = True

    print(json.dumps(payload, indent=2, sort_keys=True))
    print("")
    print(bo.POSITION_OPEN_WARNING, file=sys.stderr)

    outcome = report.final_outcome
    if outcome in (
        bo.OUTCOME_FILLED_VERIFIED,
        bo.OUTCOME_PARTIALLY_FILLED_VERIFIED,
        bo.OUTCOME_CANCELLED_VERIFIED,
        bo.OUTCOME_ACCEPTED_STATUS_PENDING,
        bo.OUTCOME_REJECTED_VERIFIED,
    ):
        return EXIT_READY
    if outcome in (bo.OUTCOME_REFUSED_PREFLIGHT, bo.OUTCOME_POST_FAILED):
        return EXIT_NOT_READY
    return EXIT_SAFETY  # ambiguous


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_demo_only_single_real_order.py",
        description=(
            "TASK-014BO demo-only single real Bybit Demo order runner. "
            "Default mode is preflight (read-only, never sends)."
        ),
    )
    p.add_argument("--mode", choices=["preflight", "execute_once"], default="preflight")
    p.add_argument("--allow-real-network", action="store_true",
                   help="enable real api-demo.bybit.com I/O (manual VPS path)")
    p.add_argument("--execute-one-real-demo-order", action="store_true",
                   help="explicit one-shot execute control (execute_once only)")
    p.add_argument("--authorization-marker", default="")
    p.add_argument("--expected-commit", default="",
                   help="full 40-character lowercase hex commit SHA (no short hash/ref)")
    p.add_argument("--request-body-hash", default="")
    p.add_argument("--write-report", action="store_true")
    p.add_argument("--output-dir", default=bo.DEFAULT_JOURNAL_DIR,
                   help="optional report output dir (the one-shot JOURNAL path is canonical "
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
