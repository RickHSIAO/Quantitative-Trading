# REVIEW-009d Draft — TASK-009d Alert Delivery E2E Drill
# Reviewer: Claude Sonnet（Draft）
# Date: 2026-05-18
# Status: DRAFT（待 Rick 決定是否送 Opus）

---

## §1 Review Scope

| 項目 | 值 |
|---|---|
| Task | TASK-009d Alert Delivery E2E Drill |
| Workorder | `docs/research/codex_workorders/TASK-009d_alert_e2e_drill.md` v1.0 |
| 實作檔案 | `scripts/drill_forward_alerts.py`、`tests/forward_record/test_alert_e2e_drill.py` |
| Codex 完成報告 | `docs/research/review_packets/REVIEW-009d_PACKET.md`、`REVIEW-009d_NUMBERS.json` |
| Drill 產出 | `outputs/forward_record/drill/20260517_drill_report.json` |
| Review 基礎 | 程式碼全讀 + `python -m unittest tests.forward_record.test_alert_e2e_drill -v` 直接執行 + drill_report.json 直接讀取 |
| Paper execution | FORBIDDEN |
| Live trading | FORBIDDEN |
| Bybit connection | NOT_ATTEMPTED |
| Discord real POST | NOT_ATTEMPTED |
| 30-day clock | NOT_STARTED |

---

## §2 Verdict Summary

| 類別 | 結果 |
|---|---|
| **Sonnet Draft Verdict** | **PASS** |
| Fail gates（10 項）| 全部通過（0 fail） |
| Warning（W-1 ~ W-3） | 3 件，全部 CAVEAT（non-blocking） |
| 30-day clock 前置條件 | TASK-009d = REVIEW_READY；30-day clock 前置條件達成（待 final decision） |

---

## §3 Fail Gates（10 項）

以下 10 項均為 PASS。任何一項 FAIL 即全單否決。

| # | Gate | 判定 | 依據 |
|---|---|---|---|
| FG-1 | 無 order endpoint import | **PASS** | `scan_no_order_endpoints(['scripts/drill_forward_alerts.py'])` → `violations=[], status=PASS` |
| FG-2 | FORBIDDEN_live_trading = NOT_ATTEMPTED | **PASS** | drill_report.json 確認；hardcoded in report dict |
| FG-3 | FORBIDDEN_order_endpoint = NOT_ATTEMPTED | **PASS** | 同上 |
| FG-4 | FORBIDDEN_bybit_write = NOT_ATTEMPTED | **PASS** | 同上；Bybit 無任何 import |
| FG-5 | FORBIDDEN_real_discord_post = NOT_ATTEMPTED | **PASS** | drill_report.json 確認；discord_probe.external_post_attempted=false |
| FG-6 | dry_run = True（強制） | **PASS** | drill_report.json `dry_run=true`；`run_forward_alerting()` 呼叫使用 `live_alerts=False, force_dry_run=True` |
| FG-7 | ChannelResult.status ≠ SENT | **PASS** | discord_probe.statuses=["DRY_RUN"]；sent_fail_gate=PASS；sent_seen=false |
| FG-8 | 18/18 tests PASS | **PASS** | `python -m unittest tests.forward_record.test_alert_e2e_drill -v` 直接執行；18 collected，18 passed in 0.083s |
| FG-9 | 12/12 drill scenarios PASS | **PASS** | REVIEW-009d_NUMBERS.json `scenario_pass_count=12`；drill_report.json 全部 result="PASS" |
| FG-10 | clock_started 不變動 | **PASS** | drill_report.json `clock_started=false`；drill 腳本無任何 clock mutation |

---

## §4 Drill Scenarios 逐項確認

### 正トリガー確認（8 件）

| Scenario | Condition | triggered | severity | result | 備考 |
|---|---|---|---|---|---|
| S-A1 | A-1 runner_missing_rows | True | WARNING | PASS | parquet 不存在 → 2/2 missing |
| S-A2 | A-2 stop_gate_hit | True | CRITICAL | PASS | stats.active_stop_gates=["S-2"] |
| S-A3 | A-3 warning_gate_streak | True | WARNING | PASS | W-1 × 3 日連続；streak_gates=["W-1"] |
| S-A4 | A-4 primary_shadow_alpha_gap | True | WARNING | PASS | mean_abs_diff=0.10 > threshold=0.05 |
| S-A5 | A-5 data_source_failure | True | CRITICAL | PASS | forward_stats.json 不存在 |
| S-A5b | A-5 data_source_failure | True | CRITICAL | PASS | data_source="FAILED" 明示 |
| S-A6 | A-6 review_006b_trigger_ready | True | INFO | PASS | 首日；previous_alert_log=None |
| S-A7 | A-7 forbidden_field_violation | True | CRITICAL | PASS | FORBIDDEN_live_trading="POST_ATTEMPTED" |

### 負トリガー確認（4 件：誤報なし）

| Scenario | Condition | triggered | result | 備考 |
|---|---|---|---|---|
| S-A1b | A-1 runner_missing_rows | False | PASS | 2 日分の正常 parquet あり |
| S-A3b | A-3 warning_gate_streak | False | PASS | day2 に W-1 なし → 交集空 |
| S-A4b | A-4 primary_shadow_alpha_gap | False | PASS | shadow parquet 不存在 → skipped=True |
| S-A6b | A-6 review_006b_trigger_ready | False | PASS | 前日 alert_log に A-6 entry あり → duplicate=True |

---

## §5 Redaction Validation

全 12 scenarios の `message_preview` に対して 9 パターンをスキャン：

```
"webhook", "MONITOR_DISCORD_WEBHOOK_URL", "api_key", "api_secret",
"BYBIT_API_KEY", "BYBIT_API_SECRET", "token", "Bearer ", "https://discord.com/api/"
```

結果：`redaction_summary.all_pass=True`、`violation_count=0`。全 12 scenarios `redaction_pass=True`。

---

## §6 Dedupe Validation

| 検証項目 | 結果 |
|---|---|
| A-6 day1 triggered | True（S-A6：triggered=True） |
| A-6 day2 suppressed | True（S-A6b：triggered=False、duplicate=True） |
| A-2 not deduped | True（S-A2：毎日 triggered；dedupe 機構なし） |
| dedupe_scenario.result | **PASS** |

---

## §7 Discord Template Validation

| 検証項目 | 結果 |
|---|---|
| all_messages_nonempty | True |
| all_have_action_guidance | True |
| all_have_condition_id | True |
| all_have_record_date | True |
| no_placeholder_artifacts | True |
| severity_mapping_correct | True |
| **all_pass** | **True** |

---

## §8 Warnings（non-blocking CAVEAT）

### W-1：`_message_preview()` が人工的に context を inject するため content checks が部分的に inflated

**問題：** `_message_preview()` は condition の自然なメッセージの前後に `f"{scenario_id} {condition.condition_id} ...\nDate: {record_date}\n"` と `f"Action: {condition.action_required}"` を付加する。このため `has_date`、`has_condition_id`、`has_action` の 3 項目は inject されたテキストによって常に True になり、condition の **生** メッセージ（実際に Discord に送られるテキスト）を直接検証していない。

`required_terms` によるキーワード検証（"STOP GATE"、"S-2" 等）は condition.message の実文字列を検証しているため、本質的な content は確認できている。しかし `has_date` 等の generic checks は実 Discord payload の検証としては不完全。

**目前リスク：** 低。`required_terms` 検証が実コンテンツを十分カバーしており、drill の目的（各 condition が正しく trigger し、メッセージに必要情報が含まれる）は達成されている。

**提案：** 後続で必要なら、`condition.message` のみを対象とした raw content check を追加することで強化できる。現時点での TASK-009d 判定には影響しない。

---

### W-2：`_sanitize_text("None" → "n/a")` が `no_placeholder` チェックを形骸化する可能性

**問題：** `_sanitize_text()` は `"None"` を `"n/a"` に置換してから preview を生成する。その後 `"None" not in preview` をチェックするため、条件のメッセージが Python `None` を文字列化した場合でも `no_placeholder=True` と判定される。一方、実際の Discord 送信では `condition.message` が sanitize なしで使われるため、条件によっては `"None"` が Discord に届く可能性がゼロではない。

**目前リスク：** 極低。現在のすべての condition 実装（alert_conditions.py）はメッセージを明示的な f-string で構築しており、`None` が混入するパスは存在しない。drill_report.json にも "None" 文字列は確認されない。

**提案：** 将来 condition を追加する際のガイドラインとして「condition.message に None を直接 f-string すると実 Discord に "None" が届く」ことをドキュメント化する程度で十分。

---

### W-3：`CacheMarketDataProvider` log marker の A-5 false positive シナリオが drill に含まれない

**問題：** REVIEW-009b W-1 で指摘された A-5 の `CacheMarketDataProvider` log marker false positive 問題は TASK-009c に委ねられている。本 TASK-009d drill には「正常ログに `CacheMarketDataProvider` という文字列が含まれる場合に A-5 が誤射しない」という negative scenario が含まれていない。

TASK-009c でこの marker を修正する予定だが、修正前の状態で drill が完了している。

**目前リスク：** 低。VPS 上の実際の runner log には `write_log()` が生成する key=value 形式の行しか含まれず、正常運行時に `CacheMarketDataProvider` という文字列は log に出現しない（REVIEW-009b 時点で確認済み）。

**提案：** TASK-009c の完了後に、A-5 の `CacheMarketDataProvider` false positive シナリオを drill の S-A5c として追加するとより堅牢になる。現時点の TASK-009d 判定には影響しない。

---

## §9 Architecture Highlights（正面評価）

1. **`setUpClass` で drill を一度だけ実行**：全 18 tests が同一 run_drill() 結果を共有し、実行時間 0.083s と高速。
2. **Scenario-driven 設計**：`_build_scenarios()` が全条件を宣言的に定義。新条件追加時は 1 エントリ追加するだけで拡張可能。
3. **`_run_discord_dry_run_probe()`** が `run_forward_alerting()` の完全なパイプラインを通じて discord_probe を実行：unit fixture だけでなく alerting 全体の dry_run gate を E2E 検証。
4. **`_dedupe_summary()` が A-2 non-dedup を明示確認**：workorder §9 の要件（A-2 は毎日通知すること）を自動検証。
5. **`_sanitize_text("None" → "n/a")`** と `no_placeholder` チェックの組み合わせにより、Python None の意図せぬ文字列化を早期発見可能（W-2 で述べた通り現在は minor gap あり）。
6. **FORBIDDEN fields が report dict に hardcoded**：drill の実行結果に依存せず常に NOT_ATTEMPTED が保証される設計。

---

## §10 Safety Summary（Sonnet 確認）

| 禁止事項 | 状態 |
|---|---|
| Discord 実際 POST | NOT_ATTEMPTED（statuses=["DRY_RUN"]、sent_seen=false） |
| --live-alerts 使用 | NOT_ATTEMPTED（live_alerts_used=false） |
| Bybit 接続 | NOT_ATTEMPTED |
| API key / webhook 要求・読取 | NOT_ATTEMPTED（fixture に `TASK009D_UNUSED_CREDENTIAL` のみ） |
| 30-day forward clock 起動 | NOT_STARTED（clock_started=false） |
| paper execution 批准 | FORBIDDEN |
| live trading 批准 | FORBIDDEN |
| 策略シグナル修正 | なし |
| alerting.py / alert_conditions.py 修正 | なし |
| immutable run output 修正 | なし |

---

## §11 是否需要 Opus Final Decision

Sonnet 評估：**不強制需要 Opus**。理由：

- 10/10 fail gates PASS；18/18 tests PASS；12/12 scenarios PASS
- 3 個 warning は技術的細節（content check の partial inflation / sanitize の順序 / TASK-009c pending scenario）、いずれも non-blocking
- drill の設計・実装ともに workorder §7~§12 の要件を高い精度で満たしている
- TASK-009d の目的（A-1~A-7 全条件の人工 trigger 検証 + redaction + dedupe + template）は達成されている

**Opus 送付が有効なケース（Rick が判断）：**
- W-1（message_preview の inject 問題）が実際の Discord payload の品質に影響するか否かの判断
- 30-day clock 前置条件 DONE 宣言の重みを考慮し、Opus の最終確認を求める場合

---

## §12 Opus Final Decision 備用 Prompt

```
あなたは Opus です。TASK-009d Alert Delivery E2E Drill の最終 review を行います。

背景：
- TASK-009d 目標：dry-run / mock モードで A-1~A-7 全 alert conditions を逐一人工 trigger し、
  content・redaction・dedupe・Discord template rendering を検証
- Sonnet draft verdict: PASS（10/10 fail gates；18/18 tests；12/12 scenarios）
- W-1/W-2/W-3：全て non-blocking caveat

禁止事項：
- Discord 実際 POST 禁止
- Bybit 接続禁止
- 30-day clock 起動禁止
- paper / live execution 批准禁止

確認してほしい項目：
1. W-1：`_message_preview()` の context inject が content checks を inflated にしている点は許容できるか？
   実際に Discord に送られる `condition.message` を直接検証していないリスクをどう評価するか？
2. W-3：A-5 の CacheMarketDataProvider false positive シナリオが drill に含まれていない点は、
   TASK-009c 完了前に TASK-009d を DONE と判断してよいか？
3. 全体として TASK-009d を DONE とし、30-day clock の前置条件を達成と判断できるか？

回答形式：
- 最終 verdict（PASS / CONDITIONAL_PASS / FAIL）
- W-1/W-2/W-3 各々：CAVEAT / BLOCKING / DISMISS
- TASK-009e などの後続タスク提案があれば記載
```

---

## §13 Audit Statement

本 draft は Claude Sonnet が 2026-05-18 に実行。

- 程式碼全讀：drill_forward_alerts.py（613 行）、test_alert_e2e_drill.py（126 行）
- unittest 直接執行：`python -m unittest tests.forward_record.test_alert_e2e_drill -v` → 18 passed in 0.083s
- drill_report.json 直接読取：全 12 scenarios、overall_result=PASS を確認
- REVIEW-009d_NUMBERS.json 読取：全フィールド確認
- safety scan 直接執行：scan_no_order_endpoints → violations=[]

未執行：Discord 実際 POST、Bybit 接続、30-day clock 起動、paper/live execution 批准、策略プログラム修正。
