# 量化交易系統

## ⚠️ 績效解讀規範（v1.13 後）

任何績效數字都要附上「**範圍 + 期間**」才有意義。本專案用 silo 切資金池，
不同 `--profile` 跑法的數字尺度完全不同，跨範圍對比沒意義。

| 範圍 | 起始資金 | OOS 2y 真實基準 |
|---|---|---|
| `--profile Crypto`（單 silo） | $10k | **+87.17% / 年化 36% / Sharpe 0.93 / PF 1.35** |
| 預設多 silo（Crypto+TW+US+Comm） | $30k | +30.82% / PF 1.25（被 TW/US 拖累） |

**任何新策略改動，必須以 walk-forward OOS 績效是否提升為準**，不能只看連續回測或 IS 數字。

---

## Demo Trading Guarded Lifecycle Status（updated by TASK-014BR_PILOT_DAILY_RUNNER, 2026-06-21）

共同狀態板，供 Rick / ChatGPT / Claude / Codex / Opus 三方協作對齊。本區塊由
TASK-014BR_PILOT_DAILY_RUNNER 同步更新；不解除 G20、不開啟自動 real trading。

> **TASK-014BR_DEMO_STRATEGY_PILOT_DAILY_RUNNER_DRY_RUN_WIRING**（2026-06-21, Opus 4.8 / DRY-RUN orchestration / 未送任何 order、未連任何網路）
> 實作 7–14 天 Bybit Demo 策略 pilot 的**每日編排層（dry-run）**：把策略/forward-record 訊號、TASK-014BQ pilot reporting 資料模型、
> append-only store、真實 `.xlsx` 匯出、Notion 每日 upsert、Discord 中文日報、每日 run journaling 與重跑保護串起來。
> **本任務不授權、不送出任何 Bybit order**（無 order-create POST／無 Demo/live 下單／無自動進出場／無倉位變動）。
> Runner 只產出可稽核的**每日執行計畫 preview**，不執行。`order_execution_authorized=false`、
> `reason_execution_not_authorized=TASK-014BR_IS_DRY_RUN_REPORTING_WIRING_ONLY`。
>
> **重用的 30 天 forward validation 策略識別碼（未臆測）：** primary forward-record run key `prev3y_crypto`，
> 策略標籤 `prev3y_crypto_combined_paper_safe_variant`（由 `apps/forward_record/stats_updater.py` 產生；
> `prev3y_crypto_shadow_a_roll12` 為 shadow，非 primary）。若權威 summary 指向 shadow 或不同策略 → fail-closed（`StrategyAmbiguousError`）。
>
> **新增檔案（重用、不複製、不修改 BO/BP）：**
> - `src/demo_strategy_pilot_daily_runner.py`（15 個有序 phase、`PilotDailyExecutionPlan` frozen、plan/dry_run/reconcile_outputs 三模式）
> - `src/demo_strategy_pilot_daily_journal.py`（canonical 每日 journal、狀態歷史、atomic、path-traversal 防護、SHA-256 fingerprint）
> - `src/demo_strategy_pilot_notion_sync.py`（gated Notion upsert，idempotency key `pilot_id:date`，注入式 transport，token 不外洩）
> - `src/demo_strategy_pilot_discord_notify.py`（gated Discord 中文日報，注入式 transport，webhook 不外洩）
> - `scripts/run_demo_strategy_pilot_daily.py`（CLI：plan/dry_run/reconcile_outputs；無 execute/send-order/qty/symbol/endpoint/scheduler/reset 等旗標）
> - `tests/demo_trading/test_demo_strategy_pilot_daily_runner.py`
>
> **每日 journal（版控外）：** `outputs/demo_trading/pilot/<pilot_id>/daily_runs/<YYYY-MM-DD>/`，
> 檔案 `run_journal.json / daily_plan.json / notion_payload.json / discord_summary.txt / run_result.json`；
> atomic、保留完整狀態歷史、不刪歷史、無 reset/force/ignore-journal 選項。
> 相同重跑 → `ALREADY_COMMITTED_IDEMPOTENT`；同日 input/plan fingerprint 變動 → `DAILY_PLAN_CONFLICT`（fail-closed）。
> Fingerprint：input = SHA-256(pilot_id、date、策略識別碼、source data date、sanitized metadata、normalized 訊號)；
> plan = SHA-256(input fingerprint、normalized 訊號、proposed actions、目前持倉、execution_authorized=false、未授權原因)；不含時間/UUID/PID/host/密鑰。
>
> **每日紀錄（dry-run）：** `order_count=0`、`filled_count=0`、`closed_trade_count=0`，不寫任何 PilotTradeRecord，
> PnL 全為 0（尚無真實 pilot 交易；不捏造任何 trade/fill/price/fee/slippage）；TASK-014BO/BP 手動驗證交易**不納入** pilot 績效。
> 提議的 hypothetical 動作分類：`ELIGIBLE_FOR_FUTURE_DEMO_PILOT` / `PROTECTED_SYMBOL_BLOCKED` / `INVALID_SIGNAL_BLOCKED` / `NO_ACTION`；
> protected symbols（ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT）一律封鎖、絕不轉成可執行動作。
>
> **Excel：** dry-run 後呼叫既有 openpyxl builder 產生真實 `.xlsx` + dated snapshot；每日列恰好一筆；不含 BO/BP 驗證交易；
> Excel 失敗不會重跑或重複每日紀錄（回報 partial-output failure）。
>
> **Notion / Discord：** 預設 config 可 enabled，但網路動作**僅在** `--allow-notion-network` / `--allow-discord-network` 明示時才執行；
> 測試全用注入式 fake transport，零 HTTP；token/webhook 不印出、不序列化、不入 journal/payload/audit/例外訊息。
> Discord 中文日報明確標示 `DRY-RUN／尚未授權自動下單`。輸出遞送失敗只記 `FAIL`、不更動交易資料、不重跑每日紀錄；
> `reconcile_outputs` 只重建 Excel 並重試「失敗/略過」的 Notion/Discord 遞送，永不重算策略、永不新增紀錄、永不觸發下單。
>
> **Exit codes：** 0 完成/冪等；2 參數錯誤；3 紀錄前輸入失敗；4 已寫紀錄但輸出同步部分失敗；5 fingerprint 衝突；6 安全拒絕。
>
> **本地驗證（Windows 11 / .venv Python 3.13；全程 offline / fake transport / temp 路徑）：**
> - py_compile（6 檔）→ PASS
> - Focused pilot_daily_runner: **53 passed**
> - `-k "pilot_reporting or pilot_daily_runner or tiny_execution_adapter or reduce_only_close"`: **1087 passed, 7701 deselected**
>
> **安全不變項：** Bybit 網路呼叫: **0**；order POST: **0**；real orders sent: **0**；Notion HTTP: **0**；Discord HTTP: **0**；
> 新模組/腳本內無 order endpoint 字串、未 import live executor / `main.py` / `src/risk.py`、未改任何策略參數、未安裝 scheduler/cron；
> runtime outputs（journal/workbook/JSONL/previews）皆留在版控外、未 commit。
> **下一步：** 下一任務為獨立、經審查的 Demo order-execution adapter；**啟動真實 7–14 天 Pilot 仍須使用者明確授權。**

---

> **TASK-014BQ_DEMO_ROUND_TRIP_CLOSEOUT_AND_PILOT_REPORTING_FOUNDATION**（2026-06-21, Opus 4.8 / offline / 未送任何 order、未連任何網路）
> 完成 Bybit Demo 開倉（TASK-014BO）+ reduceOnly 平倉（TASK-014BP）round trip 的永久 closeout 記錄，
> 並建立 7–14 天 Bybit Demo 策略 pilot 的離線 reporting 基礎。**本任務未送任何 order、未連 Bybit、未做任何 Notion/Discord 網路請求、未啟動 scheduler、未把策略訊號接上執行。**
>
> **已驗證 round trip（sanitized）：**
> - 開倉 TASK-014BO：SOLUSDT Buy Market IOC 0.1，order id `77173918-71f6-4829-91c9-025bd8cd76fa`，
>   orderLinkId `BO1-4696d511edf11b50`，均價 `74.11`，成交 `0.1`，手續費 `0.00407605`，持倉後 `0.1`，結論 `DEMO_ORDER_FILLED_VERIFIED`。
> - 平倉 TASK-014BP：SOLUSDT Sell Market IOC 0.1 reduceOnly，close order id `4ae9e849-655c-4ac3-b830-d49d587c4f4c`，
>   orderLinkId `BC1-566b8509e96b2def`，均價 `73.8`，成交 `0.1`，手續費 `0.004059`，持倉前 `0.1`、持倉後 `0`、無空單，結論 `DEMO_REDUCE_ONLY_CLOSE_FILLED_POSITION_ZERO_VERIFIED`。
> - **Round-trip PnL（Decimal）：** gross price PnL = `-0.031`；total fees = `0.00813505`；
>   estimated net PnL（不含 funding）= **`-0.03913505` USDT**。
> - **分類：** `MANUAL_EXECUTION_PIPELINE_VALIDATION`，`included_in_strategy_performance=false`、
>   `included_in_pilot_performance=false`。此為手動授權的執行管線驗證交易，**非策略交易、非 pilot 績效**，不得混入未來 pilot 指標。
>
> **永久 closeout 產物（已 commit、sanitized、無任何密鑰）：**
> `docs/research/review_packets/TASK-014BQ_DEMO_ROUND_TRIP_CLOSEOUT.json` 與 `.md`（不複製 runtime journal 進 Git）。
>
> **Pilot reporting 基礎（offline，code modified）：**
> - `src/demo_strategy_pilot_reporting.py`：frozen dataclasses `PilotConfig` / `PilotDailyRecord` /
>   `PilotTradeRecord` / `PilotAuditEvent`（金額與數量皆 Decimal；預設 `environment=BYBIT_DEMO_ONLY`、
>   `maximum_calendar_days=14`、`excel_enabled=true`）+ round-trip closeout builder。
> - `src/demo_strategy_pilot_store.py`：append-only JSONL 本地 store（config/latest_summary atomic、
>   daily/trade/audit append-only、Decimal 以字串序列化、重複日期/重複 trade_id fail-closed、
>   壞掉的 JSONL 會丟明確錯誤、無自動刪除/覆寫、無網路、無密鑰；runtime 路徑
>   `outputs/demo_trading/pilot/<pilot_id>/`，留在版控外）。
> - `scripts/build_demo_strategy_pilot_workbook.py`：以 **openpyxl** 產生真實 `.xlsx`
>   `outputs/demo_trading/pilot/<pilot_id>/demo_strategy_pilot_results.xlsx`（+ `snapshots/...<YYYYMMDD>.xlsx`），
>   六個工作表（Pilot Summary / Daily Performance / Trades / Execution Quality / Forward Comparison / Audit Log）、
>   凍結表頭、篩選、百分比/金額為數值格、空資料仍產出有效工作簿、tmp+atomic replace。
> - `scripts/preview_demo_strategy_pilot_notion_payload.py`：**preview only**，輸出 sanitized Notion upsert payload
>   （idempotent key=`pilot_id+date`），零 HTTP、不讀 token、不 import 生產 Notion client。
> - `scripts/preview_demo_strategy_pilot_discord_summary.py`：**preview only**，輸出中文每日摘要，零 HTTP、不讀 webhook。
>
> **本地驗證（Windows 11 / .venv Python 3.13 / openpyxl 3.1.5；全程 offline）：**
> - py_compile（6 檔）→ PASS
> - Focused pilot_reporting: **39 passed**
> - `-k "tiny_execution_adapter or reduce_only_close or pilot_reporting"`: **1034 passed, 7701 deselected**
>
> **安全不變項：** Real order POST calls: **0**；Real orders sent: **0**；Notion HTTP: **0**；Discord HTTP: **0**；
> 未 import live executor / `main.py` / `src/risk.py` / 任何網路 client；新 reporting 模組/腳本內無 order endpoint 字串；
> outputs（workbook/JSONL/snapshots）皆留在版控外、未 commit。
> **下一步：** push → 下一任務將把真實 pilot 每日 runner 與策略 trade records 接上；**7 天策略 pilot 已可在此 reporting 基礎上啟動**（執行串接由後續任務負責）。

---

> **TASK-014BP_DEMO_REDUCE_ONLY_CLOSE**（2026-06-21, Opus 4.8 / 實作 single reduce-only close gate / 實作期間未送任何 order）
> 實作一條「手動觸發、fail-closed」的單筆 Bybit Demo reduce-only Market 平倉路徑，用以關閉 TASK-014BO 已驗證成交的多單。
> **本實作任務未送出任何真實 order。** 真實平倉僅能由 Rick 於 VPS 上以一條明確手動指令執行。
>
> **Rick 的唯一一筆平倉授權（immutable）：**
> 「我授權關閉目前 TASK-014BO 建立的 Bybit Demo SOLUSDT 0.1 多單，只允許一筆 reduceOnly Market 平倉單，
> 不得反向開倉、不得超過目前持倉、不得自動重試。」
> scope：Bybit Demo only / `api-demo.bybit.com` / `POST /v5/order/create` / linear / SOLUSDT / **side=Sell** /
> Market / qty=`"0.1"` / IOC / **reduceOnly=true** / closeOnTrigger=false / 最多 1 筆 POST / 最多 1 筆平倉 / 禁止自動 retry。
> 來源持倉：TASK-014BO 開倉單 order id `77173918-71f6-4829-91c9-025bd8cd76fa`、orderLinkId `BO1-4696d511edf11b50`、
> 結果 `DEMO_ORDER_FILLED_VERIFIED`、預期持倉 `SOLUSDT Buy 0.1`。
> 不含：live/mainnet、Testnet、其他 symbol、qty≠0.1、開空、第二筆平倉、自動清殘倉、自動 retry、TP/SL、stop、
> 槓桿/保證金/倉位模式變更、取消無關訂單、scheduler/cron/loop/batch/策略自動化。
>
> **新增檔案（獨立 close-only 模組，重用但不修改 TASK-014BO 開倉模組）：**
> - `src/demo_only_single_reduce_only_close.py`
> - `scripts/run_demo_only_single_reduce_only_close.py`
> - `tests/demo_trading/test_demo_only_single_reduce_only_close.py`
>
> **精確平倉 body（恰好九欄位）：** `category, symbol, side=Sell, orderType=Market, qty="0.1", timeInForce=IOC,
> reduceOnly=true, closeOnTrigger=false, orderLinkId`。不加 price/positionIdx/TP/SL/triggerPrice/trailingStop/
> orderFilter/marketUnit。要求 one-way 倉位模式；若需 hedge positionIdx=1/2 則 fail-closed 不送、不改帳戶模式。
>
> **永久 close orderLinkId（與 commit/日期無關）：** `BC1-` + `sha256(TASK_ID|CLOSE_AUTHORIZATION_MARKER|
> CLOSE_AUTHORIZATION_SCOPE_IDENTITY)[:16]`（本次 `BC1-566b8509e96b2def`，≤36 字元，呼叫者不可覆寫，跨未來 commit 不變）。
> 完整 40 字元小寫 hex commit 仍是獨立 runtime code-identity gate。
>
> **Canonical close journal（不可覆寫，置於版控外）：** `outputs/demo_trading/task_014bp_single_reduce_only_close/`，
> 不更動/不刪除既有 TASK-014BO 開倉 journal。送單前：通過全部 gate → 重查當前持倉與交易所重複 → 持久化 close body hash 與
> 永久 orderLinkId → atomically 寫入 `ARMED_BEFORE_CLOSE_POST` → flush → 才允許唯一一次 POST。之後轉為
> `CLOSE_POST_RESPONSE_RECEIVED` / `CLOSE_POST_TIMEOUT_AMBIGUOUS` / `CLOSE_POST_EXCEPTION_AMBIGUOUS` /
> `CLOSE_POST_REJECTED_BEFORE_NETWORK` / `CLOSE_RESULT_VERIFIED` / `CLOSE_RESULT_UNVERIFIED`。
> 任何「可能已送出」的狀態永久阻擋再次 POST；無 force/reset/ignore/new-id/delete 選項。
>
> **32 道 fail-closed preflight gates：** 完整 HEAD SHA、endpoint host、`BYBIT_DEMO_*` credentials、close marker、
> 來源 TASK-014BO journal 存在 + 狀態 POST_RESULT_VERIFIED + 結論 DEMO_ORDER_FILLED_VERIFIED + order id 相符 +
> orderLinkId 相符、恰好一筆 SOLUSDT 多單、side=Buy、size 精確=0.1（非 0/非 <0.1/非 >0.1）、one-way 模式、
> 無空單、無持倉列模糊、instrument 可交易、qty step/min、九欄位 body、side=Sell、reduceOnly=true、closeOnTrigger=false、
> 無既有 BP 平倉單、realtime/history 皆無永久 close orderLinkId 且兩來源確實檢查且結構合法、close journal 無前狀態、
> sender count=0、無 retry、無 scheduler、body hash 相符、execute flag。任一缺失/失敗/過期/模糊即在 POST 前拒絕；qty 絕不自動調整。
> 若當前持倉非精確 `Buy 0.1`，fail-closed 並回報實際持倉，**不送較小或較大平倉單**。
>
> **離線 preflight：** 預設/無網路 preflight 不做 HTTP、`ready=false`、把已驗證持倉與重複檢查標記為 not performed、
> 不建立 journal、不送單、永不宣稱可平倉。唯有 `--allow-real-network` + 可用 Demo credential 才做已驗證 preflight。
>
> **execute_once 送單前獨立重查：** 重新驗證來源開倉 journal、`/v5/position/list`、`/v5/order/realtime`、
> `/v5/order/history`（依永久 close orderLinkId）、body/body-hash、sender count=0；順序：完整 HEAD SHA →
> 來源 journal → 確認當前多單精確 0.1 → realtime/history 無重複 → sender count=0 → atomically arm → flush → 至多一次 POST。
> 若持倉已為 0 則不送；若任一 close orderLinkId 已存在於任何狀態則不送。
>
> **No-retry / no-reversal：** 逾時/連線重置/格式錯誤/SSH 中斷/崩潰/nonzero retCode/未知/驗證延遲/部分成交皆**不重送**。
> `reduceOnly=true` 強制。任何疑似新開空單的結果分類為 critical safety failure。部分成交留殘倉須**新的明確授權**。
>
> **送出後唯讀驗證：** 以 `/v5/order/realtime`、`/v5/order/history`、`/v5/execution/list`、`/v5/position/list`
> 記錄 close order id/orderLinkId、retCode/retMsg、最終狀態、累計成交量、均價、手續費、平倉前後持倉、是否歸零、
> 驗證來源、verified/ambiguous、sender/POST count、no-retry。可能結論：`DEMO_REDUCE_ONLY_CLOSE_FILLED_POSITION_ZERO_VERIFIED` /
> `_PARTIAL_RESIDUAL_LONG_VERIFIED` / `_CANCELLED_POSITION_REMAINS` / `_REJECTED` / `_ACCEPTED_STATUS_PENDING` /
> `_POST_FAILED` / `_OUTCOME_AMBIGUOUS` / `_REFUSED_PREFLIGHT` / `_CRITICAL_SHORT_POSITION_DETECTED`。
> **完整平倉**僅當 close order 經驗證 Filled、累計成交量恰為 0.1、平倉後 SOLUSDT 持倉恰為 0、且未產生空單。
>
> **本地驗證（Windows 11 / .venv Python 3.13，全程 fake transport / fake probe，0 網路）：**
> - py_compile（3 檔）→ PASS
> - Focused reduce-only-close: **66 passed**
> - `-k "tiny_execution_adapter or reduce_only_close"`: **995 passed, 7701 deselected**
> - Complete one-shot family: **186 passed**
> - Postfill audit focused: **155 passed**
>
> **安全不變項（實作期間）：** Real close `/v5/order/create` POST calls: **0**；Real close orders sent: **0**；
> 未讀取/印出/commit 任何 credential；未 import/使用 `BybitExecutor` / `main.py` / `src/risk.py`；
> 未更動 TASK-014BO 模組或其 journal。下一步：push → VPS pull → 已驗證 close preflight；
> **7 天策略 pilot 僅在驗證持倉歸零平倉後才啟動。**

---

> **TASK-014BO_REAL_DEMO_ONE_SHOT_FINAL_DEDUP_IDENTITY_AND_OFFLINE_PREFLIGHT_CORRECTION**（2026-06-21, Opus 4.8 / fail-closed 修正 / 仍未送任何 order）
> 在第一筆真實 Bybit Demo preflight 前修正最後兩個阻斷點（就地 amend 未推送的 commit `55e6121`）。**本修正送出 0 筆真實 order POST。**
> 授權 scope 不變（Bybit Demo / SOLUSDT 0.1 Buy Market IOC / 最多一筆 / 無 retry / 無自動平倉 TP/SL）。
>
> **修正 1 — orderLinkId 與 commit SHA 脫鉤、跨未來 commit 永久不變：** 新增不可變常數
> `AUTHORIZATION_SCOPE_IDENTITY`，orderLinkId 改為僅由
> `sha256(TASK_ID|AUTHORIZATION_MARKER|AUTHORIZATION_SCOPE_IDENTITY)[:16]` → `BO1-<16 hex>` 推導，
> **不含 commit SHA / 日期 / 時間 / UUID / 隨機 / PID / hostname**，呼叫者無法覆寫（≤36 字元）。
> 因此未來的文件/結果/closeout commit、process 重啟、不同有效 Git commit 都**不會**產生新的去重身份——
> 交易所端 orderLinkId 對此授權永久固定（本次為 `BO1-4696d511edf11b50`），即使本地 journal 遺失仍可用於查核。
> 完整 40 字元小寫 hex `--expected-commit` 仍是**獨立**的 runtime code-identity gate（HEAD 須完全相符），
> 但 commit 身份**不**影響 orderLinkId / 去重身份 / journal 檔名 / 授權身份。
>
> **修正 2 — 離線/無網路 preflight 一律 fail-closed：** 離線（未帶 `--allow-real-network`）或無 Demo credential 時，
> 去重結果固定為 `clean=False, realtime_checked=False, history_checked=False, ambiguous=True,
> detail="authenticated exchange duplicate checks not performed"`，且**絕不**呼叫網路。
> gate `no_existing_exchange_order_for_fixed_order_link_id` 唯有在
> 「real-network 明確開啟 + Demo credential 存在 + realtime 與 history 兩個請求都成功 + 兩者 retCode==0 +
> 結構合法 + 皆無該固定 orderLinkId + 皆非 stale/malformed/timeout/unauthorized/rate-limited/ambiguous」時才通過。
> **絕不**把「未嘗試網路」當成「無重複單」。預設離線 preflight：`ready=False`、去重 gate 失敗、不建立/不 arm journal、不送單；`--help` 無網路。
>
> **execute_once 送單前獨立重查：** 在 atomically 寫入 `ARMED_BEFORE_POST` 之前，execute_once 會以固定 orderLinkId
> **重新**執行已驗證唯讀 `GET /v5/order/realtime` 與 `GET /v5/order/history`（不信任先前 preflight 結果）。
> 順序：驗證完整 HEAD SHA → marker/flags/body hash/credentials/account+instrument gates → 檢查 canonical 本地 journal →
> 新鮮已驗證 realtime/history 去重 → 確認 sender count=0 → atomically 寫入 `ARMED_BEFORE_POST` → flush → 至多一次 POST。
> 任一去重查詢失敗或 ambiguous 即在 arm 與 POST 前拒絕。one-shot 保證可跨後續 commit / 文件 commit / process 重啟 /
> cwd 變更 / 本地 journal 遺失 / operator 誤重跑 存活；無 force/reset/new-id/ignore 選項、無自動刪 journal、無第二次 POST。
>
> **本地驗證（Windows 11 / .venv Python 3.13，全程 fake transport / fake probe，0 網路）：**
> - py_compile（3 檔）→ PASS
> - Focused single-real-demo-order: **117 passed**
> - Scoped tiny-execution-adapter regression: **929 passed, 7701 deselected**
> - Complete one-shot family: **186 passed, 8444 deselected**
> - Postfill audit focused: **155 passed**
>
> **安全不變項（修正期間）：** Real `/v5/order/create` POST calls: **0**；Real Demo orders sent: **0**；
> 未讀取/印出/commit 任何 credential。下一步：push → VPS pull → 設定 credential → 已驗證唯讀 preflight
> （`--allow-real-network`）；`execute_once` 仍等待最終 preflight review 後由 Rick 手動執行。

---

> **TASK-014BO_REAL_DEMO_ONE_SHOT_DEDUPLICATION_AND_JOURNAL_HARDENING**（2026-06-21, Opus 4.8 / fail-closed 修正 / 仍未送任何 order）
> 在第一筆真實 Bybit Demo order 被允許前，修正三個 fail-closed 缺口（就地 amend 未推送的 commit `b6f7498`）。**本修正仍未送出任何真實 order。**
> 授權 scope 不變（Bybit Demo / SOLUSDT 0.1 Buy Market IOC / 最多一筆 / 無自動 retry / 無自動平倉 TP/SL）。
>
> **修正 1 — Journal 路徑不可覆寫：** 移除 CLI `--journal-dir`。`preflight` 與 `execute_once` 一律使用 source 內定義、
> 錨定於 repo root（非 cwd）的 canonical 路徑 `CANONICAL_JOURNAL_DIR =
> <repo>/outputs/demo_trading/task_014bo_single_real_demo_order`，無法經 CLI 參數 / 環境變數 / 設定檔 / cwd 改變；
> `canonical_journal()` 會驗證解析後路徑未逸出 repo root（拒絕 symlink/traversal）。呼叫者無法藉由換目錄繞過既有 journal。
>
> **修正 2 — orderLinkId 永久穩定、與日期無關：** orderLinkId 改為僅由不可變授權身份決定：
> `sha256(f"{TASK_ID}|{AUTHORIZATION_MARKER}|{full_commit_sha}")[:16]` → `BO1-<16 hex>`（≤36 字元、TASK-014BO 專屬 prefix）。
> 不含 UTC 日期 / timestamp / 隨機 / UUID / hostname / PID；不同時鐘日期、process 重啟、preflight 與 execute_once 皆推導出相同值；
> 呼叫者無法覆寫。即使本地 journal 遺失，固定 orderLinkId 仍可用於交易所端查核。
>
> **修正 3 — 交易所端重複偵測：** POST 前以已驗證唯讀呼叫，依固定 orderLinkId 查詢
> `GET /v5/order/realtime` 與 `GET /v5/order/history`（category=linear, symbol=SOLUSDT, orderLinkId=<fixed>）。
> 新增 gate `no_existing_exchange_order_for_fixed_order_link_id`：唯有兩個來源都成功檢查且皆無該 orderLinkId 才通過。
> 任何 match（New/PartiallyFilled/Filled/Cancelled/Rejected/Deactivated/Pending/unknown/malformed-but-matching）即拒送；
> 查詢 missing/failed/stale/malformed/unauthorized/rate-limited/timeout/ambiguous 一律 fail-closed（絕不視為「無單」）。
>
> **完整 SHA 強制：** `--expected-commit` 必須為精確 40 字元小寫 hex SHA；拒絕 7 字元短 hash、縮寫、大寫、`HEAD`/`main`、prefix、含空白；
> runtime 取得 repo 實際 HEAD 完整 SHA 後須完全相等。本任務修正後產生的新 commit SHA 才是最終手動指令的 approved commit（非 `b6f7498`）。
>
> **去重合併邏輯：** 唯有 canonical journal 無任何 armed/attempted/ambiguous/completed 狀態、realtime 無 match、history 無 match、
> in-process sender count=0、且其餘所有 gate 通過時才允許 POST。本地 journal 缺失但交易所有該 orderLinkId → 拒送；交易所乾淨但本地 journal 顯示可能已嘗試 → 拒送。
> **無** `--force` / `--reset` / `--ignore-journal` / `--new-order-link-id` / 自動 journal 重置或刪除選項。
>
> **本地驗證（Windows 11 / .venv Python 3.13，全程 fake transport / fake probe，0 網路）：**
> - py_compile（3 檔）→ PASS
> - Focused single-real-demo-order: **99 passed**
> - Scoped tiny-execution-adapter regression: **911 passed, 7701 deselected**
> - Complete one-shot family: **186 passed, 8426 deselected**
> - Postfill audit focused: **155 passed**
>
> **安全不變項（修正期間）：** Real `/v5/order/create` POST calls: **0**；Real Demo orders sent: **0**；
> 未讀取/印出/commit 任何 credential；未送任何 order。下一步：push → VPS pull → 設定 credential → 唯讀 preflight；
> `execute_once` 仍等待最終 preflight review 後由 Rick 手動執行。

---

> **TASK-014BO_REAL_DEMO_ONE_SHOT**（2026-06-21, Opus 4.8 / 實作 single real Demo order gate / 實作期間未送任何 order）
> 實作一條「手動觸發、fail-closed」的單筆 Bybit Demo order 執行路徑。**本實作任務未送出任何真實 order。**
> 真實 Demo order 僅能由 Rick 在 code review、push、VPS pull、credential 設定、最終 preflight 通過後，
> 於 VPS 上以一條明確的手動指令執行（見下方）。
>
> **Rick 的唯一一筆授權（immutable scope）：**
> environment=Bybit Demo only / host=`https://api-demo.bybit.com` / endpoint=`POST /v5/order/create` /
> category=`linear` / symbol=`SOLUSDT` / side=`Buy` / orderType=`Market` / qty=`"0.1"` /
> timeInForce=`IOC` / reduceOnly=`false` / closeOnTrigger=`false` / 最多 order-create POST=1 /
> 最多 submitted orders=1 / 自動 retry 禁止。
> 授權原文："I authorize one Bybit Demo SOLUSDT 0.1 Buy Market IOC order test. Live endpoints are
> forbidden. More than one order is forbidden. Automatic retries are forbidden."
> 此授權不含：live/mainnet、Testnet、第二筆 order、自動平倉、reduce-only 平倉、TP/SL、stop order、
> 倉位管理、攤平/加碼、scheduler/cron、策略訊號自動化、任何 protected symbol、逾時/例外後自動重送。
>
> **新增檔案：**
> - `src/demo_only_tiny_execution_adapter_single_real_demo_order.py`
> - `scripts/run_demo_only_single_real_order.py`
> - `tests/demo_trading/test_demo_only_tiny_execution_adapter_single_real_demo_order.py`
>
> **Endpoint lock：** 僅允許 `https://api-demo.bybit.com`，order path `/v5/order/create`。
> 拒絕 `api.bybit.com`、`api-testnet.bybit.com`、任何其他 host、跨 host redirect（拒絕而非跟隨）、
> 呼叫端任意 URL、環境變數 endpoint override、proxy 置換、batch order endpoint。
>
> **精確 request body（恰好九個欄位）：** `category, symbol, side, orderType, qty, timeInForce,
> reduceOnly, closeOnTrigger, orderLinkId`。不加 price / positionIdx / takeProfit / stopLoss /
> triggerPrice / trailingStop / orderFilter / marketUnit。要求 one-way 倉位模式；若帳戶為 hedge
> 模式或需要 positionIdx=1/2，fail-closed 不送、不改帳戶模式。
>
> **30 道 preflight gates（全部 fail-closed）：** git/commit identity、endpoint host、`BYBIT_DEMO_*`
> credentials、九欄位逐項精確值、qty=Decimal("0.1")、max order count=1、no retry、no scheduler、
> 新鮮 instrument 規則 + SOLUSDT 可交易、min qty/step、新鮮 mark price、`0.1 × mark ≤ 20 USDT`、
> 無 qty 調整、無既有 SOLUSDT order/position、倉位模式相容、Demo 餘額足夠、protected symbol 未觸及、
> 無衝突的 one-shot journal、精確 authorization marker、精確 execution flags、body hash 相符、
> POST 前 real order count=0。任一 gate 失敗即拒送。
>
> **One-shot journal（crash-safe，置於版控外 `outputs/demo_trading/task_014bo_single_real_demo_order/`）：**
> POST 前 atomically 寫入 `ARMED_BEFORE_POST` 並 flush 後才允許唯一一次 POST；之後轉為
> `POST_RESPONSE_RECEIVED` / `POST_EXCEPTION_AMBIGUOUS` / `POST_TIMEOUT_AMBIGUOUS` /
> `POST_REDIRECT_REJECTED` / `POST_REJECTED_BEFORE_NETWORK` / `POST_RESULT_VERIFIED` /
> `POST_RESULT_UNVERIFIED`。任何「POST 可能已發生」的 journal 狀態都會讓 rerun 拒絕重送
> （逾時/連線重置/格式錯誤/程式崩潰/缺回應/未知結果皆不允許自動重送）；operator 須以 orderLinkId 調查。
>
> **No-retry / sender 計數：** in-process `OneShotSenderGuard` 起始計數 0，僅能呼叫一次，再呼叫即丟硬性安全錯誤；
> POST 周圍無 loop、無 retry decorator、無 fallback/batch/第二 sender。
>
> **送出後唯讀驗證：** `retCode=0` 的 create 回應不等於成交。之後僅做唯讀查詢：最多 3 次
> `/v5/order/realtime`、最多 1 次 `/v5/order/history`、1 次 `/v5/execution/list`、1 次 `/v5/position/list`，
> 以 orderId/orderLinkId 查詢。可能結論：`DEMO_ORDER_FILLED_VERIFIED` /
> `DEMO_ORDER_PARTIALLY_FILLED_VERIFIED` / `DEMO_ORDER_CANCELLED_VERIFIED` /
> `DEMO_ORDER_REJECTED_VERIFIED` / `DEMO_ORDER_ACCEPTED_STATUS_PENDING` / `DEMO_ORDER_POST_FAILED` /
> `DEMO_ORDER_OUTCOME_AMBIGUOUS` / `DEMO_ORDER_REFUSED_PREFLIGHT`。非經唯讀證據不得宣稱 FILLED。
>
> **倉位警告：** 此授權為 opening Buy（reduceOnly=false），成交後可能留下 SOLUSDT Demo 多單。
> 本模組不送平倉、不設 TP/SL、不 reduce；平倉需另一筆獨立明確授權。
>
> **CLI：** `preflight`（預設，唯讀，永不送單，列出全部 gate、sanitized 預覽、body hash、orderLinkId、
> journal state，並印出最終手動指令）；`execute_once`（唯一可送單路徑，需
> `--mode execute_once --allow-real-network --execute-one-real-demo-order
> --authorization-marker <marker> --expected-commit <commit> --request-body-hash <hash>` 全部齊備，
> 且 preflight 全通過、無衝突 journal）。預設與 `--help` 永不送單、無網路。
>
> **最終手動 VPS 執行指令範本（review + push + pull + 設定 credential 後才執行）：**
> ```
> python scripts/run_demo_only_single_real_order.py \
>   --mode execute_once \
>   --allow-real-network \
>   --execute-one-real-demo-order \
>   --authorization-marker DEMO_ONLY_SOLUSDT_0_1_BUY_MARKET_IOC_ONE_SHOT_RICK_AUTHORIZED_20260621 \
>   --expected-commit <FULL_40_CHARACTER_CORRECTED_COMMIT_SHA> \
>   --request-body-hash <BODY_HASH_FROM_FRESH_PREFLIGHT>
> ```
> （經 TASK-014BO 強化修正後已移除 `--journal-dir`；journal 路徑改為不可覆寫的 canonical 路徑。
> `--expected-commit` 必須為完整 40 字元小寫 hex SHA。）
>
> **本地驗證（Windows 11 / .venv Python 3.13，全程 fake transport / fake probe，0 網路）：**
> - py_compile（3 檔）→ PASS
> - Focused single-real-demo-order: **75 passed**
> - Scoped tiny-execution-adapter regression: **886 passed, 7701 deselected**
> - Complete one-shot family: **186 passed, 8402 deselected**
> - Postfill audit focused（確認 fake 與 real 證據仍分開分類）: **155 passed**
>
> **安全不變項（實作期間）：** Real `/v5/order/create` POST calls: **0**；Real Demo orders sent: **0**；
> `real_order_network_attempted=False`、`real_order_endpoint_called=False`；未讀取任何 credential；
> 無法選到 live/Testnet endpoint；未 import/使用 `BybitExecutor` / `main.py` / `src/risk.py`；
> postfill audit 仍將 real Demo transport 與 `FAKE_SENDER` 分開；Stage 1 fake-only 預設行為不變。
> Real Demo 執行：**等待 Rick 於 VPS 手動執行上方唯一指令；平倉需另行授權。**

---

> **TASK-014BNB_POSTFILL_AUDIT_VPS_CLOSEOUT**（2026-06-21, VPS Ubuntu 24.04.4 / Python 3.12.3 / pytest 9.1.1 / commit 546ecdb）
> VPS Stage 1 postfill audit validation COMPLETE。以下為在 Ubuntu VPS 上對 commit `546ecdb` 的完整驗證結果。
> Validated commit: `546ecdb TASK-014BN_POSTFILL_AUDIT: add offline fake-only postfill audit scaffold`
>
> **欄位語意：**
> - `audit_passed` = 權威稽核完整性結果。Fail-closed 決定式公式：
>   `audit_passed = auditable AND integrity_all_passed AND audit_status ∈
>   {SIMULATED_ACCEPTED, SIMULATED_REJECTED, SIMULATED_TRANSPORT_ERROR}`。
>   `audit_passed=True` 僅代表離線 fake-only 證據內部一致且滿足 Stage 1 postfill contract。
>   **不代表** real order 成功、real order 已送出、Bybit Demo 接受了 real order、或 Stage 2 已被授權。
> - `auditable` = 是否存在足夠 fake-only 證據以進行稽核。
> - `integrity_all_passed` = 30 個命名檢查是否全數通過。
> - SIMULATED_REJECTED 與 SIMULATED_TRANSPORT_ERROR 可有 `audit_passed=True`，因為稽核完整性通過，
>   但 order/transport 本身並未成功。
>
> **VPS 驗證結果：**
> - py_compile（3 檔）→ PASS
> - Focused postfill audit: **155 passed** (8.09s)
> - Combined postfill + orchestrator + audit-semantics-split: **216 passed** (18.92s)
> - Complete one-shot family: **186 passed, 8327 deselected** (54.10s)
> - Scoped tiny-execution-adapter regression: **812 passed, 7701 deselected** (88.61s)
>
> **CLI fixture 驗證：**
> - `simulated_accepted`: audit_passed=true, exit 0（稽核完整性通過；不代表 real order 成功）
> - `simulated_rejected`: audit_passed=true, exit 0（稽核完整性通過，但 business outcome 為 rejected）
> - `simulated_transport_error`: audit_passed=true, exit 0（稽核完整性通過，但非 transport/order 成功）
> - `not_auditable`: audit_passed=false, exit 1（證據不足，failed_check_count=12）
>
> **Report writer 驗證：** `--write-report --output-dir .vps_postfill_report_test --json-only` exit 0, report_written=true。
> 產出檔案：`demo_only_tiny_execution_adapter_tiny_order_postfill_audit_20260621T052825Z.json`,
> `demo_only_tiny_execution_adapter_tiny_order_postfill_audit_20260621T052825Z.md`,
> `latest_demo_only_tiny_execution_adapter_tiny_order_postfill_audit.json`,
> `latest_demo_only_tiny_execution_adapter_tiny_order_postfill_audit.md`。
>
> **安全不變項：** Real Bybit Demo `/v5/order/create` calls: **0**；Real Bybit Demo orders sent: **0**；
> `real_order_network_attempted=False`；`real_order_endpoint_called=False`；`real_order_sent=False`；
> 未讀取任何 real 或 demo credential；未調用任何 sender 實作；Stage 1 real sender 仍不可達；
> Stage 2 real Demo dispatch: **未授權。**
>
> **Cleanup：** `.venv-vps-postfill-validation`、`.pytest_vps_postfill`、`.vps_postfill_report_test` 已移除。
> VPS REVIEW-009 修改、dashboard outputs、`.env.discord`、既有 pytest basetemp、`outputs/demo_trading/`、
> forward-record 日誌、paper portfolio 輸出皆保留未動。
>
> **下一步建議：** 下一任務須保持 offline/fake-only 或為獨立 review task。不授權 dispatch。

---

> **TASK-014BN_POSTFILL_AUDIT_AUTHORITATIVE_PASS_FIELD_CORRECTION**（2026-06-21, Opus 4.8 / 嚴格 offline / fake-only）
> 修正 `PostfillAuditReport` 與 CLI contract，使權威欄位 `audit_passed`、
> `audit_reason`、`audited_at_utc` 確實存在、序列化、文件化並有測試覆蓋；
> 下游消費者不再需要自行組合 `auditable` + `integrity_all_passed` 推導 `audit_passed`。
> 就地 amend 未推送的 commit `d0d6c83`（不 push）。
>
> **欄位語意：**
> - `audit_passed` = 權威稽核完整性結果。Fail-closed 決定式公式：
>   `audit_passed = auditable AND integrity_all_passed AND audit_status ∈
>   {SIMULATED_ACCEPTED, SIMULATED_REJECTED, SIMULATED_TRANSPORT_ERROR}`。
>   `audit_passed=True` **不代表** real order 成功、real order 已送出、
>   Bybit Demo 接受了 real order、或 Stage 2 已被授權。Real order 仍需
>   `real_order_sent=True`；Stage 1 保證 `real_order_sent=False`。
> - `auditable` = 是否存在足夠 fake-only 證據。
> - `integrity_all_passed` = 30 個命名檢查是否全數通過。
> - `audit_reason` = 非空、決定式、已脫敏的說明，明確區分
>   稽核完整性 / business outcome / real order activity（不含 key / secret /
>   signature / authorization-marker 內容）。
>
> **各狀態 `audit_passed` 值：** `SIMULATED_ACCEPTED` → True；
> `SIMULATED_REJECTED` → True（稽核完整性通過，但 order 未被接受）；
> `SIMULATED_TRANSPORT_ERROR` → True（稽核完整性通過，但非 transport/order 成功）；
> `NOT_AUDITABLE` → False；`FORBIDDEN_REAL_TRANSPORT` → False；
> 任一必檢失敗或竄改 → False。
>
> **CLI：** normal stdout 與 `--json-only` 皆輸出 `task_id`、`audit_status`、
> `audit_passed`、`audit_reason`、`simulated_business_outcome`、
> `order_transport_kind`、`sender_call_count`、`simulated_order_sent`、
> `legacy_order_sent`、`real_order_sent`、`actual_request_body_qty`、
> `actual_request_body_qty_source`、`resolved_notional`、`failed_check_count`、
> `failed_check_names`、`report_written`。Exit code 直接以 `audit_passed` 表示：
> `0`（audit_passed=True）/ `1`（audit_passed=False：NOT_AUDITABLE 或
> contract/integrity 不符）/ `2`（FORBIDDEN_REAL_TRANSPORT / 無效 fixture / 安全違規）。
>
> **本地驗證（Windows 11 / .venv Python 3.13）：**
> - py_compile（3 檔）→ PASS
> - Focused postfill audit: **155 passed**
> - Combined postfill + orchestrator + audit-semantics-split: **216 passed**
> - Complete one-shot family: **186 passed, 8327 deselected**
> - Scoped tiny-execution-adapter regression: **812 passed, 7701 deselected**
>
> **安全不變項：** Real `/v5/order/create` calls: **0**；Real Bybit Demo orders sent: **0**；
> 未讀取任何 credential；postfill 模組內無任何 sender 實作；未 import `main.py` /
> `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor`；未變動全域 tiny cap /
> `MAX_ORDER_COUNT=1` / protected denylist / BL packet `DEFAULT_QTY=0.01` / 20 USDT 上限；
> Stage 2 real Demo dispatch: **未授權。**

---

> **TASK-014BN_POSTFILL_AUDIT**（2026-06-21, Opus 4.7 / 嚴格 offline / fake-only）
> 新增 Stage 1 fake-sender 後置稽核 scaffold。該模組消費既有的
> `OrchestrationReport`（由 one-shot orchestrator 產生），離線重核
> simulated transport / cap-escalation contract / business outcome 完整性，
> 對任何 real transport 證據 fail-closed。不送任何 order、不開任何 HTTP、
> 不讀任何 credential、不授權 Stage 2 real Demo dispatch。
>
> **新增檔案：**
> - `src/demo_only_tiny_execution_adapter_tiny_order_postfill_audit.py`
> - `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_postfill_audit.py`
> - `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_postfill_audit.py`
>
> **稽核 5 級狀態：** `POSTFILL_AUDIT_SIMULATED_ACCEPTED`、`POSTFILL_AUDIT_SIMULATED_REJECTED`、
> `POSTFILL_AUDIT_SIMULATED_TRANSPORT_ERROR`、`POSTFILL_AUDIT_NOT_AUDITABLE`、
> `POSTFILL_AUDIT_FORBIDDEN_REAL_TRANSPORT`。
>
> **30 個 deterministic 命名檢查：** transport 種類 / fake_sender 用量 / sender call count /
> simulated network attempted / real network NOT attempted / Stage 1 real execute disabled /
> SOLUSDT-linear-Buy-Market-IOC contract / qty=0.1 (CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY 來源) /
> body_qty_authorized_override / candidate+resolved notional ≤ 20 USDT / cap gate authorized /
> wiring authorized / no real transport evidence / accepted-outcome 一致性 / protected symbol untouched。
>
> **本地稽核驗證（Windows 11 / .venv Python 3.13）：**
> - py_compile: `python -m py_compile src/demo_only_tiny_execution_adapter_tiny_order_postfill_audit.py scripts/preview_demo_only_tiny_execution_adapter_tiny_order_postfill_audit.py tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_postfill_audit.py` → PASS
> - Focused postfill audit: `python -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_postfill_audit.py -q --basetemp=.pytest_local_pf` → **131 passed**
> - Postfill + orchestrator + split focused: **192 passed**
> - Complete one-shot family: `python -m pytest tests/demo_trading -k "one_shot" -q --basetemp=.pytest_local_pf/family` → **186 passed, 8303 deselected**
> - Scoped tiny-execution-adapter regression: `python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local_pf/scoped` → **788 passed, 7701 deselected**
>
> **安全不變項：** Real Bybit Demo `/v5/order/create` calls: **0**；Real Bybit Demo orders sent: **0**；
> 未讀取任何 credential；未 import `main.py` / `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor`；
> 未變動全域 tiny cap / `MAX_ORDER_COUNT=1` / protected denylist / BL packet `DEFAULT_QTY=0.01` / 20 USDT cap-escalation 上限；
> Stage 2 real Demo dispatch: **未授權，須獨立 human authorization task 後方可執行。**
>
> **下一步建議：** `TASK-014BNB_demo_only_tiny_execution_postfill_audit_vps_validation`
> （Ubuntu VPS 上 clean-environment 重跑同一稽核 scaffold；純 documentation closeout）。

---

> **TASK-014BM_AUDIT_SEMANTICS_VPS_CLOSEOUT**（2026-06-21, VPS Ubuntu 24.04.4 / Python 3.12.3 / pytest 9.1.1 / commit 1453ff6）
> VPS Stage 1 audit-semantics-split validation COMPLETE。以下為在 Ubuntu VPS 上對 commit 1453ff6 的完整驗證結果。
> Validated commit: `1453ff6 TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT: distinguish simulated and real order activity`
>
> **語意結論：**
> - Legacy `order_sent` 保留 accepted-order/business-outcome 語意（`retCode==0 AND non-empty orderId`）；`simulated_order_sent=True` 不代表 Bybit 接單。
> - Bybit `retCode` 非 0 → `simulated_order_sent=True`、legacy `order_sent=False`、`real_order_sent=False`。
> - fake sender 真實丟出例外 → 被捕捉轉成 network-error sentinel；`simulated_order_sent=False`，sender call count 仍為 1，real network call 仍為 0。
> - `REAL_DEMO_SENDER` 及未知 transport-kind → fail-closed（`OneShotAuthorizedExecutionOrchestratorError`），不 silently rewrite。
> - Stage 1 保證：`real_order_network_attempted=False`、`real_order_endpoint_called=False`、`real_order_sent=False`。
>
> **VPS py_compile PASS（6 files）：**
> `src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`、
> `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`、
> `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_stage1_real_vs_simulated_order_audit_semantics_split.py`、
> `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py`、
> `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`、
> `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py`
>
> **VPS 測試結果：**
> - Focused audit-semantics split: `python -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_stage1_real_vs_simulated_order_audit_semantics_split.py -q --basetemp=.pytest_vps/focused` → **27 passed**
> - Combined Stage 1 + discovery-gate: `python -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1_discovery_gate_fix.py -q --basetemp=.pytest_vps/stage1` → **66 passed**
> - Complete one-shot family: `python -m pytest tests/demo_trading -k "one_shot" -q --basetemp=.pytest_vps/family` → **186 passed, 8172 deselected**
> - Scoped tiny-execution-adapter regression: `python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_vps/full` → **657 passed, 7701 deselected**
>
> **安全不變項：** Real Bybit Demo `/v5/order/create` calls: **0**；Real Bybit Demo orders sent: **0**；
> 未使用真實 credential；Stage 1 real sender unreachable；
> Stage 2 real Demo dispatch: **未授權，須獨立 human authorization task 後方可執行。**
> Cleanup: `.venv-vps-validation` 和 `.pytest_vps` 已移除。
>
> **下一步建議：** `TASK-014BN_demo_only_tiny_execution_postfill_audit`（offline/fake-only postfill-audit scaffold）


> **TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION**（2026-06-21, semantic + safety correction）
> 在不削弱任何 Stage 1 安全邊界的前提下，修正前次 AUDIT_SEMANTICS_SPLIT 留下的 3 個語意/安全缺口：
>
> 1. **Legacy `order_sent` 還原 business-outcome 語意。** 先前被改寫成
>    `order_sent = simulated_order_sent OR real_order_sent`，導致 fake sender 正常返回但 Bybit
>    `retCode` 非 0 時 legacy `order_sent` 也變 `True`，破壞向後相容。修正後 legacy `order_sent`
>    直接取自 BM 既有的 `SendOutcome.order_sent`（亦即 `retCode == 0 AND non-empty orderId`）。
>    Consumers 想驗證 transport 用 `simulated_order_sent`；想驗證 accepted-order/business outcome
>    用 `bybit_ret_code` + `bybit_order_id` + `bm_final_status` + legacy `order_sent`；想驗證
>    real Bybit Demo 單用 `real_order_sent`（Stage 1 永遠 `False`）。
> 2. **真實丟出例外的 fake sender 也安全。** 新增 `counting_sender` wrapper 的 `try/except`：
>    任何被注入的 fake sender 真的 raise 時，會被重塑為 BM 既有理解的
>    `{"_network_error": True, "_error_repr": ...}` sentinel，
>    final status 變 `STATUS_REJECTED_BM_NETWORK_ERROR`，`simulated_order_sent=False`，
>    sender call count 仍為 1，real network call 仍為 0；公開 orchestration surface 不漏例外。
> 3. **不再 silently normalize 禁止 transport-kind。** 新增 `_validate_stage1_order_transport_kind`
>    helper，在 `_build_rejection_report` / `_build_full_report` 建構時 fail-closed 驗證
>    `order_transport_kind`，輸入 `REAL_DEMO_SENDER` 或任何未知值直接 raise
>    `OneShotAuthorizedExecutionOrchestratorError`，不再 rewrite 成 `NONE` / `FAKE_SENDER`，
>    避免 Stage 1 對禁止值輸出 misleading 報告。real sender 仍 unreachable。
>
> **變更檔案：**
> - [`src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：`_validate_stage1_order_transport_kind` helper + `__all__` 同步；`_build_rejection_report` / `_build_full_report` 改用 fail-closed validator；`_build_full_report` legacy `order_sent` 改取 `bm_report.order_sent`；`_invoke_bm` 的 `counting_sender` wrap `try/except` 轉成 network-error sentinel。
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_stage1_real_vs_simulated_order_audit_semantics_split.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_stage1_real_vs_simulated_order_audit_semantics_split.py)：split helper 拆成 `_assert_legacy_transport_aggregates` + `_assert_legacy_order_sent_is_business_outcome`；新增 retCode==0+orderId 的 legacy `order_sent=True` 斷言；新增 retCode==0+empty orderId 案例；新增真實 raise 的 fake sender 案例；新增 4 個 validator 直接測試（reject `REAL_DEMO_SENDER` / unknown，accept `NONE` / `FAKE_SENDER`，rejection-report builder 在禁止/未知值 fail-closed）。
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py)：`test_real_demo_fake_sender_bybit_reject_fails_closed` 回復為 legacy `order_sent=False`。
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：`test_fake_sender_bybit_reject_surfaces_bm_bybit_not_executed` 回復為 legacy `order_sent=False`。
>
> **驗證（local，於 d189382 之上 amend）：**
> - py_compile PASS（6 files）
> - focused split 測試：**27/27 PASS**（原 20 + 新增 7：1 業務結果 + 1 empty orderId + 1 raised exception + 4 validator）
> - 66/66 combined Stage 1（real-demo + discovery-gate-fix）PASS
> - 186/186 one-shot orchestrator-family PASS（原 179 + 7 新）
> - scoped 迴歸：`python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local/full` → **657 passed, 7701 deselected**（650 prior + 7 new）
>
> **安全不變式：** 0 real Bybit Demo order sent；0 `/v5/order/create` real call；
> 無 live endpoint、無 live/demo secret 讀取方式新增；
> 不動 `main.py` / `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor`；
> 不動 BM signing 實作、endpoint 實作、global tiny caps、`MAX_ORDER_COUNT=1`、protected symbols、
> BL packet `DEFAULT_QTY=0.01`、cap escalation 授權 gate、20 USDT notional cap；
> orchestrator `_invoke_bm` 真實 sender 仍 unreachable；real sender 解鎖仍須另一個獨立 human authorization task。
>
> **未送出任何 real Bybit Demo 單。未呼叫 `/v5/order/create`。** Local amend 之 commit only，未 push。


> **TASK-014BM_STAGE1_REAL_VS_SIMULATED_ORDER_AUDIT_SEMANTICS_SPLIT**（2026-06-21, Stage 1 audit clarification）
> 移除 `OrchestrationReport` 中 fake-sender simulated execution 與真實 Bybit Demo
> network order 之間的曖昧性。新增 7 個 explicit audit 欄位：
>
> - `simulated_order_network_attempted`
> - `simulated_order_endpoint_called`
> - `simulated_order_sent`
> - `real_order_network_attempted`
> - `real_order_endpoint_called`
> - `real_order_sent`
> - `order_transport_kind`（allowlist：`NONE` / `FAKE_SENDER` / `REAL_DEMO_SENDER`）
>
> **Stage 1 hard invariant：`order_transport_kind` 絕對不會輸出 `REAL_DEMO_SENDER`；**
> **`real_order_*` 三個欄位永遠是 `False`。** 公開 `STAGE1_FORBIDDEN_ORDER_TRANSPORT_KINDS`
> 常數列出該禁止值，便於 consumer 在外層斷言。
>
> **語意：**
> - **No dispatch（readiness、所有 rejection、Stage 1 真實送單 refusal）：** 6 個 boolean 全部 `False`，`order_transport_kind="NONE"`。
> - **Fake sender 正常返回（包括 Bybit `retCode` 非 0）：** 3 個 `simulated_*` 全部 `True`，3 個 `real_*` 全部 `False`，`order_transport_kind="FAKE_SENDER"`。Bybit business 拒絕透過 `bybit_ret_code` / `bm_final_status` 揭露，不再改寫 transport facet。
> - **Fake sender 引發例外（network error）：** `simulated_order_network_attempted=True`、`simulated_order_endpoint_called=True`、`simulated_order_sent=False`，`order_transport_kind="FAKE_SENDER"`。
>
> **Legacy 欄位語意（CORRECTION 後）：**
> - `order_network_attempted = simulated_order_network_attempted OR real_order_network_attempted`（transport-attempt OR aggregate）
> - `order_endpoint_called = simulated_order_endpoint_called OR real_order_endpoint_called`（endpoint-call OR aggregate）
> - `network_attempted = read_only_network_attempted OR order_network_attempted`（網路 OR aggregate）
> - **`order_sent` 保留先前 accepted-order / business-outcome 語意**（`retCode==0 AND non-empty orderId`），**不是 `simulated_order_sent OR real_order_sent`**。`simulated_order_sent=True` 只代表 simulated transport 完成一次正常 call，不代表 Bybit 接單；想驗證 accepted-order 用 `bybit_ret_code` + `bybit_order_id` + `bm_final_status` + legacy `order_sent`；想驗證 real Bybit Demo 單用 `real_order_sent`（Stage 1 保證 `False`）。
>
> **變更檔案：**
> - [`src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：新增 7 個 audit 欄位（safe default）、`ORDER_TRANSPORT_KIND_*` 常數 + `ORDER_TRANSPORT_KINDS` + `STAGE1_FORBIDDEN_ORDER_TRANSPORT_KINDS`、legacy aggregate OR、markdown render section、`__all__` 同步
> - [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：stdout 新增 `order_transport_kind` + 6 個 split boolean
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_stage1_real_vs_simulated_order_audit_semantics_split.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_stage1_real_vs_simulated_order_audit_semantics_split.py)：20/20 PASS（常數 / 所有 no-dispatch 路徑 / fake-sender 成功 / Bybit retCode 非 0 / network error / aggregate OR / CLI stdout / markdown）
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py)：兩個既有 fake-sender 測試對齊新語意（Bybit retCode 非 0 → `simulated_order_sent=True`；network error → `simulated_order_sent=False`）
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：`test_fake_sender_bybit_reject_surfaces_bm_bybit_not_executed` 對齊新語意
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py)：SimpleNamespace mock 新增 7 個欄位
>
> **安全不變式：** 0 real Bybit Demo order sent；0 `/v5/order/create` real call；
> 無 live endpoint、無 live/demo secret 讀取方式新增；
> 不動 `main.py` / `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor`；
> 不動 global tiny caps、`MAX_ORDER_COUNT=1`、protected symbols、BL packet `DEFAULT_QTY=0.01`、
> cap escalation 授權 gate、20 USDT notional cap；
> orchestrator `_invoke_bm` 真實 sender 仍 unreachable；real sender 解鎖仍須另一個獨立 human authorization task。
>
> **驗證（local，commit 31b0bf8 之後新 commit）：**
> - py_compile PASS（6 files：orchestrator src、CLI preview script、fixtures、3 個測試模組）
> - 20/20 focused split 測試 PASS
> - 66/66 combined Stage 1（real-demo + discovery-gate-fix）PASS
> - 179/179 one-shot orchestrator-family PASS（含 20 個新增）
> - scoped 迴歸：`python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local/full` → **650 passed, 7701 deselected**（630 prior + 20 new）
>
> **未送出任何 real Bybit Demo 單。未呼叫 `/v5/order/create`。** Local commit only，未 push。
>
> **下次 VPS 驗證指令（real send 仍未開放，仍需另一個 authorization task）：**
> ```
> python scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --mode execute_real_demo_order --ir-mode discover --i-understand-this-performs-one-public-read-only-instrument-rules-get --explicit-demo-min-qty-cap-authorization-flag --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1 --explicit-real-demo-order-flag --real-demo-authorization-marker DEMO_ONLY_SOLUSDT_ONE_SHOT_REAL_ORDER_RICK_AUTHORIZED_v1
> ```
> 期望輸出：印出 `REJECTED: Stage 1 forbids any real /v5/order/create call.`；exit code `2`；stdout 包含 `order_transport_kind='NONE'`、`simulated_order_*=False`、`real_order_*=False`。

> **TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1**（2026-06-20, Stage 1 only）
> 新增一個**隔離的** real-demo-order 一次性執行入口
> `ORCH_MODE_EXECUTE_REAL_DEMO_ORDER` 與專屬 marker
> `EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER = "DEMO_ONLY_SOLUSDT_ONE_SHOT_REAL_ORDER_RICK_AUTHORIZED_v1"`。
> 此入口 reuse 既有完整鏈：public read-only IR discovery → exchange min candidate
> derivation → cap escalation auth gate → authorized execution qty wiring → BM
> exact-body signing。final request body qty 只能來自
> `CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY`；never fall back to BL packet `qty=0.01`。
>
> **Stage 1 hard contract（強制驗證 by 新測試 + 既有測試）：**
> - **Stage 1 從未真的呼叫 `/v5/order/create`。** 即使 flag、marker、credentials 三者齊備，
>   orchestrator 的 `_invoke_bm` 仍 hard-refuse 真實 send path；只在注入 `bm_fake_sender`
>   的情境下做 offline validation。
> - real demo 真實送單之前**另有一個獨立的 human authorization task** 要核可。
> - default CLI 呼叫不可能到達 order endpoint。
> - CLI 對 real-demo mode 缺少 flag → exit 1；缺少 marker → exit 1；
>   未開啟 `--stage1-allow-fake-sender-execute-mode` → exit 2（並印出 "Stage 1 forbids…"）。
>
> **新增 audit / report 欄位（全部有 safe default）：**
> `real_demo_execute_requested`, `real_demo_execute_authorized`,
> `real_demo_authorization_marker_match`, `credentials_source`,
> `resolved_execution_qty`, `resolved_execution_qty_source`,
> `resolved_notional`, `bybit_ret_msg`, `final_status`。
>
> **新增狀態：**
> - `STATUS_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED`（缺 flag）
> - `STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH`（marker 不符）
> - `STATUS_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1`（給 creds 但沒 fake sender → Stage 1 拒絕真實送單）
>
> **變更檔案：**
> - [`src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：新增 mode + marker + 2 statuses + 9 audit 欄位 + 對應 pre-flight gate；`__all__` 更新
> - [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：新增 `execute_real_demo_order` mode、`--explicit-real-demo-order-flag`、`--real-demo-authorization-marker`；CLI 對真實 sender 一律 refuse；新增 audit 欄位 stdout 行
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py)：43/43 PASS
> - [`tests/demo_trading/fixtures_orchestrator_fake_senders.py`](tests/demo_trading/fixtures_orchestrator_fake_senders.py)：CLI 測試所需 importable fake sender
> - 既有 orchestrator/taxonomy/audit/opt-in 測試 93/93 仍 PASS（只調整 1 條 supported-modes 斷言 + 1 條 SimpleNamespace fake）
>
> **安全不變項：** 0 real Bybit Demo order sent；0 `/v5/order/create` real call；
> 無 live endpoint、無 live/demo secret 讀取程式變更；
> 不動 `main.py` / `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor`；
> 不動 global tiny caps、`MAX_ORDER_COUNT=1`、protected symbols、BL packet `DEFAULT_QTY=0.01`、
> cap escalation 既有 gate、20 USDT notional cap。
>
> 驗證（local）：py_compile PASS；43/43 新 Stage 1 測試 PASS；
> 既有 orchestrator + taxonomy + audit + opt-in family 共 93/93 PASS；
> 607/607 tiny_execution_adapter scoped regression PASS（command:
> `python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local/full`；
> result: 607 passed, 7701 deselected — 先前 README 寫的「7921/7921 PASS」為**錯誤標示**，
> 已在 TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1_DISCOVERY_GATE_FIX 更正）。
> **未送出任何 real Bybit Demo 單。未呼叫 `/v5/order/create`。** Local commit only — 未 push。
>
> **下一步 VPS 驗證指令（real send 仍未開放，需要下一個 authorization task）：**
> ```
> python scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --mode execute_real_demo_order --explicit-real-demo-order-flag --real-demo-authorization-marker DEMO_ONLY_SOLUSDT_ONE_SHOT_REAL_ORDER_RICK_AUTHORIZED_v1
> ```
> 期望輸出：印出 "REJECTED: Stage 1 forbids any real /v5/order/create call."；exit code 2；
> `order_endpoint_called=False`；`order_sent=False`。
>
> **TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1_DISCOVERY_GATE_FIX**（2026-06-20, Stage 1 correction，已 amend 進 efe9d74）
> 修正先前 Stage 1 surface 的兩個缺口：
> (1) `execute_real_demo_order` mode 沒有強制要求 fresh public read-only IR discovery，
>     允許 cached/pre-parsed IR 進入 chain，可能造成 stale rules 做真實送單前置驗證；
> (2) README/NEXT_ACTION/COMMAND_LOG 錯誤標示 7921/7921 PASS，實際是
>     `-k "tiny_execution_adapter"` 的 scoped 607/607 PASS（7701 deselected）。
>
> **新增的 pre-flight discovery gate（execute_real_demo_order 專用，readiness 不受影響）：**
> - 必須 `ir_mode == MODE_DISCOVER` 且 `ir_pre_parsed_response is None`；
>   否則 → `STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED`，無任何 IR / order sender 被呼叫
> - 必須 `allow_real_ir_get=True`；否則 → `STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED`
> - CLI 對 `execute_real_demo_order` 額外拒絕：
>   `--ir-pre-parsed-response-json` → exit 1；
>   `--ir-mode != discover` → exit 1；
>   缺 `--i-understand-this-performs-one-public-read-only-instrument-rules-get` → exit 1
> - readiness mode 仍可用 offline/pre-parsed IR；非 real-demo 的 `execute_with_fake_sender` 完全相容
>
> **新增狀態（safe default、加入 `__all__`）：**
> - `STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED = "ORCHESTRATION_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED"`
> - `STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED = "ORCHESTRATION_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED"`
>
> **變更檔案：**
> - [`src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：新增 2 狀態 + discovery gate（fire 於 marker 檢查後、chain 之前）；`__all__` 更新
> - [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：CLI 對 real-demo mode 額外 3 條 rejection（pre-parsed / non-discover / 缺 opt-in）
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py)：43 條既有測試改走 discover + injected `ir_sender`（沒削弱原 contract，所有 reject 路徑仍斷言相同 status / 0 sender call）；新增 `_ir_sender_factory()` helper
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1_discovery_gate_fix.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1_discovery_gate_fix.py)：新增 23 條 focused tests
>
> **安全不變項：** 0 real Bybit Demo order sent；0 `/v5/order/create` real call；
> 無 live endpoint、無 live/demo secret 讀取程式變更；
> 不動 `main.py` / `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor`；
> 不動 global tiny caps、`MAX_ORDER_COUNT=1`、protected symbols、BL packet `DEFAULT_QTY=0.01`、
> cap escalation 既有 gate、20 USDT notional cap、readiness mode 行為。
>
> 驗證（local）：py_compile PASS（src + scripts + 兩個 Stage 1 測試檔）；
> 23/23 新 discovery-gate-fix 測試 PASS；
> 43/43 既有 Stage 1 測試（已改走 discover + injected sender 後）PASS；
> 共 66/66 Stage 1 PASS；
> 159/159 orchestrator-family PASS；
> scoped 結果：`python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local/full`
> → **630 passed, 7701 deselected**
> （先前記錄的「611 passed + 19 errors」係因 `.pytest_local` 父目錄不存在導致 test-environment setup error，
> 非 application / strategy 失敗；建立目錄後全部通過）。
> **未送出任何 real Bybit Demo 單。未呼叫 `/v5/order/create`。** Local commit only — 已 `git commit --amend --no-edit` 進 c5f1a89，未 push。
>
> **下一步 VPS 驗證指令（real send 仍未開放）：**
> ```
> python scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --mode execute_real_demo_order --ir-mode discover --i-understand-this-performs-one-public-read-only-instrument-rules-get --explicit-demo-min-qty-cap-authorization-flag --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1 --explicit-real-demo-order-flag --real-demo-authorization-marker DEMO_ONLY_SOLUSDT_ONE_SHOT_REAL_ORDER_RICK_AUTHORIZED_v1
> ```
> 期望輸出：印出 "REJECTED: Stage 1 forbids any real /v5/order/create call."；exit code 2；
> `order_endpoint_called=False`；`order_sent=False`。
>
> **TASK-014BM_STAGE1_VPS_VALIDATION_CLOSEOUT**（2026-06-20, VPS Ubuntu 24.04.4 / Python 3.12.3 / pytest 9.1.1 / commit d732273）
> VPS Stage 1 validation COMPLETE。以下為在 VPS 上對 commit d732273 的完整驗證結果。
>
> **VPS py_compile PASS（5 files）：**
> ```
> python -m py_compile \
>   src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py \
>   scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py \
>   tests/demo_trading/fixtures_orchestrator_fake_senders.py \
>   tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py \
>   tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1_discovery_gate_fix.py
> ```
>
> **VPS 測試結果：**
> - 23/23 focused discovery-gate-fix 測試 PASS
> - 66/66 combined Stage 1 PASS
> - 159/159 one-shot orchestrator-family PASS
> - scoped 迴歸：`python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local/full`
>   → **630 passed, 7701 deselected**
>
> **Real sender refusal（VPS 實測）：**
> 執行 `execute_real_demo_order`（無 `--stage1-allow-fake-sender-execute-mode`）：
> ```
> REJECTED: Stage 1 forbids any real /v5/order/create call.
>           Real-demo-order can only be validated offline with a fake sender.
> ```
> exit code 2；0 real Bybit Demo API 網路請求；0 real order sent。
>
> **Injected fake-sender path（VPS 實測，offline 模擬）：**
> ```
> status=ORCHESTRATION_OK_FAKE_SENDER_EXECUTED_DEMO_ONLY
> instrument_rules_loaded=True
> candidate_qty='0.1'           candidate_notional='10.0'
> cap_gate_status='ESCALATION_AUTHORIZED'
> wiring_status='WIRING_AUTHORIZED_CANDIDATE_QTY'
> original_packet_qty='0.01'    actual_request_body_qty='0.1'
> actual_request_body_qty_source='CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY'
> body_qty_authorized_override=True
> read_only_network_attempted=True   order_network_attempted=True
> network_attempted=True             order_endpoint_called=True
> order_sent=True                    fake_sender_used=True
> sender_call_count=1                real_execute_disabled_stage1=True
> bybit_order_id='fake-cli-1'        credentials_source='injected_demo_credentials'
> resolved_notional='10.0'
> ```
> ⚠️ **audit 欄位語意說明：** `order_network_attempted=True`、`order_endpoint_called=True`、
> `order_sent=True` 描述的是透過 injected fake sender 的**模擬** BM 執行，
> **並非真實 Bybit 網路請求**。
> - Simulated endpoint-shaped fake-sender calls: **1**
> - Real Bybit Demo `/v5/order/create` network calls: **0**
> - Real Bybit Demo orders sent: **0**
> - Stage 1 real sender: **unreachable**
> - Stage 2 real Demo dispatch: **需要獨立的 human authorization task，目前未授權**
>
> **安全不變項：** 0 real order sent；0 real `/v5/order/create` call；
> 無 live endpoint；無 live/demo secret 被讀取；
> `execute_real_demo_order` 仍要求 fresh public IR discovery（cached/pre-parsed 被拒）；
> IR sender call count ≤ 1；fake BM sender call count ≤ 1。
>
> **下一步建議（fail-closed，real Demo 執行仍未授權）：**
> 建議下一個工程 task 為：real-vs-fake audit 欄位的語意標示強化
> （例如 `is_real_order=False` / `real_send_attempted=False` 欄位），
> 或建立 offline/fake-only postfill-audit scaffold，
> **不是** real order dispatch。
>


> **TASK-014BM_ONE_SHOT_ORCHESTRATOR_READINESS_STATUS_TAXONOMY_FIX**（2026-06-20）
> 修正 orchestrator top-level status 語意：真實 public read-only instrument-rules GET
> 之後，top-level status 現在正確回報 `ORCHESTRATION_OK_READINESS_READ_ONLY_NETWORK`
> 而非原本的 `ORCHESTRATION_OK_READINESS_NO_NETWORK`，與 `network_attempted=True` 一致。
> BM inner status（`bm_final_status`）維持 `READINESS_OK_NO_NETWORK` 不變（BM 從未嘗試 order call）。
>
> **新增常數：**
> - `STATUS_OK_READINESS_NO_NETWORK = "ORCHESTRATION_OK_READINESS_NO_NETWORK"` — offline/pre-parsed readiness
> - `STATUS_OK_READINESS_READ_ONLY_NETWORK = "ORCHESTRATION_OK_READINESS_READ_ONLY_NETWORK"` — discover readiness（injected sender 或 stdlib）
>
> **狀態路徑對照：**
> - offline readiness（`ir_mode=offline` + pre-parsed）：`STATUS_OK_READINESS_NO_NETWORK`，
>   `read_only=False`, `order=False`, `aggregate=False`
> - real/injected discover readiness（`ir_mode=discover`）：`STATUS_OK_READINESS_READ_ONLY_NETWORK`，
>   `read_only=True`, `order=False`, `aggregate=True`，`order_endpoint_called=False`, `order_sent=False`
>
> **CLI exit code：** 兩者皆為 0；`STATUS_OK_READINESS_READ_ONLY_NETWORK` 已加入 exit-0 set。
>
> **變更檔案：**
> - [`src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：新增常數；`_bm_terminal_status_to_orchestration_status()` ir_network_attempted branch 改回傳新狀態；`__all__` 更新
> - [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：exit-0 set 加入 `STATUS_OK_READINESS_READ_ONLY_NETWORK`
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：1 條 injected sender 路徑測試改為斷言新狀態
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py)：4 條 discover 路徑斷言改為新狀態
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_readiness_status_taxonomy_fix.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_readiness_status_taxonomy_fix.py)：24 條新 focused tests（全 PASS）
>
> **安全不變項：** 無 real order network call；無 real order sent；無 live endpoint；
> 無 live secret；不動 `main.py` / `src/risk.py` / `BybitExecutor`；
> 不改 global tiny caps / `MAX_ORDER_COUNT=1`；cap escalation opt-in / fake-sender-only Stage 1 全部不變。
>
> 驗證（local）：py_compile PASS；24/24 taxonomy 測試 PASS；23/23 audit semantics 測試 PASS；
> 12/12 opt-in 測試 PASS；33/34 orchestrator 邏輯測試 PASS（1 error = pre-existing Windows tmp_path 問題）；
> 7921/7921 tiny_execution_adapter regression PASS（250 errors = 同一 Windows tmp_path 問題，1 failure = pre-existing `test_demo_emergency_close_sender::test_dry_run_cli_writes_report`，與本 task 無關）。
> **未送出任何 real Bybit Demo 單。未呼叫 `/v5/order/create`。** Local commit only — 未 push。
>
> 下一步 VPS 驗證指令：
> ```
> python scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --ir-mode discover --i-understand-this-performs-one-public-read-only-instrument-rules-get --explicit-demo-min-qty-cap-authorization-flag --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1
> ```
> 確認 `status=ORCHESTRATION_OK_READINESS_READ_ONLY_NETWORK`、`read_only_network_attempted=True`、
> `order_network_attempted=False`、`network_attempted=True`、`order_endpoint_called=False`、`order_sent=False`。
>

> **TASK-014BM_ONE_SHOT_ORCHESTRATOR_NETWORK_AUDIT_SEMANTICS_FIX**（2026-06-20）
> 修正 orchestrator audit/report 語意：真實 public read-only instrument-rules GET
> 現在被正確記錄為一次 network attempt，但不暗示任何 order endpoint 被呼叫。
>
> **新增三個不可變 report 欄位：**
> - `read_only_network_attempted=True` — 僅在真實 public IR GET 被 attempted 時為 True
> - `order_network_attempted=True` — 僅在 BM 透過 fake sender 嘗試 order network call 時為 True
> - `network_attempted` — 以上兩者的 aggregate OR（現修正為正確語意）
>
> **語意對照：**
> - real read-only readiness discovery：`read_only=True`, `order=False`, `aggregate=True`,
>   `order_endpoint_called=False`, `order_sent=False`
> - offline/pre-parsed readiness：`read_only=False`, `order=False`, `aggregate=False`
> - fake BM sender execute：`read_only=False` (offline IR), `order=True`, `aggregate=True`
>
> **reason 字串修正：** 真實 read-only readiness 不再說 "no network attempted"，
> 改為 "BM readiness ok; one authorized public read-only instrument-rules GET
> completed; no order network call attempted."
>
> **變更檔案：**
> - [`src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：OrchestrationReport 新增兩欄位；to_dict() / markdown 更新；report builders 修正；ir_network_attempted 追蹤
> - [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：CLI terminal 輸出新增三個 network 欄位
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py)：更新 2 條測試以反映正確 semantics
> - [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_network_audit_semantics_fix.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_network_audit_semantics_fix.py)：23 條新 focused tests（全 PASS）
>
> **安全不變項：** 無 real order network call；無 real order sent；無 live endpoint；
> 無 live secret；無 retry；無 scheduler；不動 `main.py` / `src/risk.py` /
> `BybitExecutor`；不改 global tiny caps / protected symbols / `MAX_ORDER_COUNT=1`；
> cap escalation opt-in / fake-sender-only Stage 1 execute 限制全部不變。
>
> 驗證（local）：py_compile PASS；23/23 audit semantics 測試 PASS；12/12 opt-in 測試 PASS；
> 33/34 orchestrator 邏輯測試 PASS（1 errors = pre-existing Windows tmp_path 權限問題）；
> 521/540 tiny_execution_adapter regression PASS（19 errors = 同一 Windows tmp_path 問題）。
> VPS 驗證見下方指令。**未送出任何 real Bybit Demo 單。** Local commit only — 未 push。
>
> 下一步 VPS 驗證指令：
> ```
> python scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --ir-mode discover --i-understand-this-performs-one-public-read-only-instrument-rules-get --explicit-demo-min-qty-cap-authorization-flag --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1
> ```
> 確認 `read_only_network_attempted=True`、`order_network_attempted=False`、
> `network_attempted=True`、`order_endpoint_called=False`、`order_sent=False`。
>

> **TASK-014BM_ONE_SHOT_ORCHESTRATOR_READ_ONLY_DISCOVERY_OPT_IN_FIX**（2026-06-20）
> 在 TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR（Stage 1）之上，為 preview CLI
> 新增一個 **narrow explicit opt-in flag**，讓 `--ir-mode discover` 能正確傳遞
> `allow_real_ir_get=True` 給 orchestrator，而不是讓 orchestrator raise
> `OneShotAuthorizedExecutionOrchestratorError`（VPS 上驗到的問題）。
>
> **新增 CLI flag：**
> `--i-understand-this-performs-one-public-read-only-instrument-rules-get`
>
> **Default 仍然 fail-closed：** `--ir-mode discover` 沒有帶新旗標時，CLI 在 *網路之前*
> 輸出 REJECTED 訊息並退出 code 1，不呼叫 orchestrator，不觸及網路。
>
> **唯一允許的真實 network 請求：**
> `GET https://api-demo.bybit.com/v5/market/instruments-info?category=linear&symbol=SOLUSDT`
> （只讀；不需要憑證；不授權 `/v5/order/create`、`/v5/order/cancel`、
> `/v5/position/set-trading-stop`、任何 live Bybit host、或 WebSocket endpoint。）
>
> **安全不變項：** real BM execute mode 仍未開放；fake-sender-only execution 限制不變；
> `order_endpoint_called=False`；`order_sent=False`；不動 `main.py` /
> `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor`；
> 不改 global tiny caps / protected symbols / `MAX_ORDER_COUNT=1`。
>
> 新增測試檔
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py)
> （12 條 focused tests）覆蓋：CLI discover 無 opt-in → exit 1 no network；
> CLI discover 帶 opt-in + monkeypatched stdlib → exit 0，no order；
> CLI 正確傳 `allow_real_ir_get=True`；orchestrator `allow_real_ir_get=True` +
> monkeypatched stdlib → 單一 GET、正確 URL、無 order；injected ir_sender 收到
> 正確 URL、只被呼叫一次；full chain resolves `instrument_rules_loaded=True`,
> `candidate_qty='0.1'`, `cap_gate_status=ESCALATION_AUTHORIZED`,
> `wiring_status=WIRING_AUTHORIZED_CANDIDATE_QTY`,
> `actual_request_body_qty='0.1'`，`order_endpoint_called=False`,
> `order_sent=False`；既有 34 條 orchestrator 測試 + 517/517 regression 全部 PASS。
>
> 驗證：py_compile PASS；12/12 opt-in 測試 PASS；34/34 orchestrator 回歸 PASS；
> 517/517 tiny_execution_adapter 回歸 PASS（先前 505 + 12 新 opt-in）。
> **未送出任何新 real Bybit Demo 單。未呼叫 `/v5/order/create`。未讀任何 secret。**
> Local commit only — 未 push。
>
> 下一步 VPS 驗證指令：
> ```
> python scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --ir-mode discover --i-understand-this-performs-one-public-read-only-instrument-rules-get --explicit-demo-min-qty-cap-authorization-flag --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1
> ```
>

> **TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR**（2026-06-19，Stage 1）
> 在 TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH（Stage 2）之上，新增一個
> **narrow、decision-+-validation-only、demo-only 的 one-shot orchestration 層**，
> 把完整授權執行鏈（`BM_MIN_QTY_FIX` 取得 SOLUSDT instrument rules →
> `BM_CAP_ESCALATION_GATE` 雙重授權通過 → `BM_WIRE_AUTHORIZED_CANDIDATE_QTY`
> 解析為 `execution_qty="0.1"` → `BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH`
> 把 actual request body qty 從 `"0.01"` 切換到 `"0.1"`）封裝為單一進入點，
> 讓 BM 真正規劃並（在 fake-sender 模式下）簽署的 HTTPS request body
> 帶上 `qty="0.1"`，而不是 BL packet 的無效 `"0.01"`。
> **Stage 1 仍不送任何 real demo 單**：公開介面只支援
> `readiness` 與 `execute_with_fake_sender` 兩種模式；後者**強制**
> 同時需要 `bm.DemoCredentials` 與一個 caller 注入的可呼叫 fake sender，
> 真正的 `MODE_EXECUTE_DEMO_ORDER` 對網路發送透過 orchestrator 介面
> 完全不可達。CLI 預設 `readiness`；`execute_with_fake_sender` 必須同時
> 帶上 `--stage1-allow-fake-sender-execute-mode` 與
> `--fake-sender-import-path` 與 fake credential 三件套才會啟用。
> 在 `ir_mode="discover"` 但未注入 `ir_sender` 的情況下，orchestrator 會
> 主動 raise `OneShotAuthorizedExecutionOrchestratorError`（除非 caller
> 明確帶上 `allow_real_ir_get=True`，而 Stage 1 callers 從不帶它）。
> 具體變更：
> (1) 新增 [`src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：
> 唯一進入點 `run_one_shot_authorized_execution_orchestration(...)`、frozen
> `OrchestrationReport` 浮出 12 個必填欄位
> (`instrument_rules_loaded`, `candidate_qty`, `candidate_notional`,
> `cap_gate_status`, `wiring_status`, `original_packet_qty`,
> `actual_request_body_qty`, `actual_request_body_qty_source`,
> `body_qty_authorized_override`, `network_attempted`,
> `order_endpoint_called`, `order_sent`) 加 nested raw reports，以及
> `write_report()` helper 一次寫 4 個檔
> (`latest_*.json`, `latest_*.md`, 時間戳對) 到
> `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator/`。
> Identity：`TASK_ID="TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR"`,
> `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-ONE-SHOT-AUTHORIZED-EXECUTION-ORCHESTRATOR"`,
> `IMPLEMENTATION_PATH_PHASE="tiny_order_one_shot_authorized_execution_orchestrator"`,
> `IS_REVIEW_CHAIN_SUFFIX=False`,
> `UPSTREAM_TASKS=(BH, BM, BM_FIX, BM_MIN_QTY_FIX, BM_CAP_ESCALATION_GATE, BM_WIRE_AUTHORIZED_CANDIDATE_QTY, BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH)`,
> `NEXT_REQUIRED_TASK="TASK-014BN_demo_only_tiny_execution_postfill_audit"`。
> (2) 新增 CLI
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)：
> 預設 `readiness`、不送網路；`execute_with_fake_sender` 預設關閉，需顯式
> 加 `--stage1-allow-fake-sender-execute-mode` 與 `--fake-sender-import-path`
> 與 `--fake-api-key`/`--fake-api-secret` 才會啟用；浮出 12 個必填欄位；
> 退出碼 0/1/2 分別對應 OK / 鏈拒絕 / 缺憑證或 fake sender。
> (3) 新增測試檔
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)
> （34 條 focused-core 測試）覆蓋：identity / 鎖死常數；readiness happy
> path 浮出 `actual_request_body_qty="0.1"` 且 no network；fake-sender
> happy path 浮出 body `qty="0.1"`，且 caller 收到的 UTF-8 body bytes 等於
> 簽章 prehash 字串中的 body 部分，且 `X-BAPI-SIGN-TYPE=2`，且 sender
> 只被呼叫一次；unsupported mode 拒絕；rules not loaded / wrong symbol /
> wrong status / wrong min_order_qty 全部 pre-network fail-closed；cap-gate
> 在 flag 缺 / marker 缺 / marker 錯時均拒絕；missing credentials /
> missing fake sender 均拒絕；`ir_mode="discover"` 無 sender 注入時
> raise `OneShotAuthorizedExecutionOrchestratorError`；注入 ir_sender
> 走過 discover 分支；fake-sender `retCode=10004` 映射到
> `STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED`；fake-sender network error
> 映射到 `STATUS_REJECTED_BM_NETWORK_ERROR`；模組 executable code 從未
> 提到 `main.py` / `src.risk` / `BybitExecutor` / `BYBIT_LIVE_*` env / live
> URL host（docstring 提及允許）；`write_report()` 寫 4 檔且 JSON
> round-trip；`OrchestrationReport` 是 frozen；`to_dict()` 浮出 12 個必填
> 欄位；任何 rejection 路徑均不會浮出 `actual_request_body_qty="0.01"`；
> tiny caps + protected-symbols snapshot 不變。
>
> 驗證：`python -m py_compile <all 3 new files>` PASS；
> `pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py
> --basetemp=.pytest_tmp/bt` → **34/34 PASS**；
> BH→BM family regression `-k tiny_execution_adapter` →
> **505/505 PASS**（471 prior BH→BM + 34 new Stage 1）；
> readiness preview smoke：
> `actual_request_body_qty='0.1' actual_request_body_qty_source='CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY'
> body_qty_authorized_override=True network_attempted=False
> order_endpoint_called=False order_sent=False`；
> fake-sender preview smoke：posted body bytes decoded JSON 帶
> `"qty":"0.1"`、`X-BAPI-SIGN-TYPE=2`、HMAC-SHA256(`secret`,
> `timestamp+apikey+recv_window+body_str`) 等於 `X-BAPI-SIGN`、
> `sender_call_count=1`。
>
> 本任務 **未送出任何新的 real Bybit Demo 單**、未呼叫
> `/v5/order/create`、未讀任何 live secret、未動 `main.py` /
> `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor`、未動
> protected positions、未解除 `MAX_ORDER_COUNT=1` 或雙重授權旗標、未全域
> 抬升 `TINY_QTY_CAP_SOL=0.05` / `TINY_SIZE_CAP_USDT=5`、未改 BL packet
> `DEFAULT_QTY="0.01"`、未動 BM/BM_FIX/BM_MIN_QTY_FIX/BM_CAP_ESCALATION_GATE/
> BM_WIRE_AUTHORIZED_CANDIDATE_QTY/BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH
> 任一現有 src。Local commit only — 未 push。
>

> **TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH**（2026-06-19，Stage 2）
> 在 TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY 之上，把 BM 真正送出的
> HTTPS request body 的 `qty` 從 BL packet 的 `"0.01"`（已被
> BM_MIN_QTY_FIX 證實對 Bybit SOLUSDT 最小單量無效）切換到 cap-escalation
> 授權後的 candidate `qty="0.1"` — **但只有當 ALL of**：wiring
> `status=WIRING_AUTHORIZED_CANDIDATE_QTY`、wiring
> `execution_qty_source=CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY`、
> `execution_qty>0`、`execution_notional_estimate>0 且 ≤ 20 USDT`、
> `environment=bybit_demo`、`symbol=SOLUSDT`、`side=Buy`、
> `orderType=Market`、`TIF=IOC`、`max_order_count=1`、雙重 confirmation
> flag 同時 present、demo credentials present **同時成立才會切換**。任何
> rejected 路徑（missing wiring / unauthorized wiring / over-cap wiring /
> blank execution_qty / 任一 gate 失敗）都會在 *網路之前* 以新狀態
> `WIRING_REQUIRED_NO_NETWORK` fail-closed，**絕不**靜默退回
> `qty=0.01`。本任務 **仍不送任何新的 real demo 單**（所有驗證透過
> fake `sender` 完成）、不呼叫 `/v5/order/create`、不讀 live secret、不動
> `main.py` / `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor`、
> 不動 protected positions、不解除 `MAX_ORDER_COUNT=1` 或雙重授權旗標、
> 不全域抬升 `TINY_QTY_CAP_SOL=0.05` / `TINY_SIZE_CAP_USDT=5`、不改 BL
> packet `DEFAULT_QTY="0.01"`。具體變更：
> (1) [`src/demo_only_tiny_execution_adapter_tiny_order_execution.py`](src/demo_only_tiny_execution_adapter_tiny_order_execution.py)
> 新增 `STATUS_WIRING_REQUIRED_NO_NETWORK` 與 4 個
> `EXECUTE_BODY_QTY_SOURCE_{BL_PACKET,AUTHORIZED_CANDIDATE,NONE,REJECTED_NO_FALLBACK}`
> 常數、`MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=Decimal("20")` 鏡像、
> `_derive_body_qty_from_wiring()` helper、`ExecutionPlan` +3 / `ExecutionReport`
> +4 defaulted 欄位 (`actual_request_body_qty` /
> `actual_request_body_qty_source` / `body_qty_authorized_override` /
> `body_qty_rejection_reason`)、以及新的 pre-network rejection 分支。
> (2) 新增測試檔
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_body_authorized_qty_source_switch.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_body_authorized_qty_source_switch.py)
> （20 條 focused-core 測試，涵蓋常數、happy-path body.qty=0.1、HMAC body
> equality、missing/unauthorized/over-cap 全部 fail-closed、retCode 映射、
> 單一 sender call、helper boundary、`to_dict()` Stage 2 欄位）。
> (3) 既有 88 條 BM + 18 條 BM_FIX execute-mode 測試透過新的 `_authorized_wiring()`
> helper 串接真實 BM_MIN_QTY_FIX → BM_CAP_ESCALATION_GATE →
> BM_WIRE_AUTHORIZED_CANDIDATE_QTY upstream，仍 PASS；BM happy-path
> body qty assertion 從 `"0.01"` 更新為 `"0.1"`。
> (4) preview script 額外列印 4 個 Stage 2 欄位。
>
> 驗證：`pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_body_authorized_qty_source_switch.py
> --basetemp=.pytest_tmp/bt` → **20/20 PASS**；BH→BM full chain
> regression `-k demo_only_tiny_execution_adapter` → **471/471 PASS**；
> preview readiness smoke exit 0，`actual_request_body_qty='0.01'
> actual_request_body_qty_source='BL_PACKET_QTY'
> body_qty_authorized_override=False
> body_qty_rejection_reason='no authorized_execution_qty_wiring report supplied'`。
>
> 本任務 **未送出任何新的 real Bybit Demo 單**。Local commit only — 未 push。
>

> **TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY**（2026-06-19）在
> TASK-014BM / TASK-014BM_FIX / TASK-014BM_MIN_QTY_FIX /
> TASK-014BM_CAP_ESCALATION_GATE 之上，新增一個 **narrow、decision-only、
> demo-only 的 SOLUSDT authorized execution qty wiring 層**，把 cap-escalation
> 閘的「明確雙重授權通過」結果轉成 BM ExecutionReport 上可被 readiness 路徑
> 讀取的 `execution_qty_resolved` 欄位（值 = TASK-014BM_MIN_QTY_FIX 算出的
> candidate qty=0.1），讓 BM readiness/planning 路徑明確知道「原 BL packet
> `qty=0.01` 已被確認 invalid，授權後的 candidate_qty 才是合法 execution qty」。
> 本任務 **Stage 1 only — 仍不送單、不呼叫 `/v5/order/create`、不重試
> `execute_demo_order`、不接 live endpoint、不讀任何 live/demo secret、不動
> protected positions、不上 retry、不上 scheduler、不掛 stop / TP / SL、不
> 改 BL packet 的 `DEFAULT_QTY="0.01"`、不解除 `MAX_ORDER_COUNT=1` 或雙重
> 授權旗標、不全域抬升 `TINY_QTY_CAP_SOL` / `TINY_SIZE_CAP_USDT`**。具體變更：
> (1) 新增 [`src/demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py`](src/demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py)：
> 單一決策入口 `run_authorized_execution_qty_wiring(instrument_rules_report,
> cap_escalation_report)`；常數鎖死 `ALLOWED_ENVIRONMENT="bybit_demo"` /
> `ALLOWED_SYMBOL="SOLUSDT"` / `ALLOWED_SIDE="Buy"` / `ALLOWED_ORDER_TYPE="Market"` /
> `ALLOWED_TIME_IN_FORCE="IOC"` / `ALLOWED_MAX_ORDER_COUNT=1` /
> `ORIGINAL_PACKET_QTY="0.01"` / `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=Decimal("20")`；
> 12 個 decision status：`WIRING_AUTHORIZED_CANDIDATE_QTY` /
> `WIRING_NOT_REQUIRED_ORIGINAL_PASSES` / `WIRING_NOT_AUTHORIZED_NO_OVERRIDE` /
> `WIRING_REJECTED_RULES_NOT_LOADED` / `WIRING_REJECTED_GATE_MISSING` /
> `WIRING_REJECTED_GATE_OVER_CAP` / `WIRING_REJECTED_WRONG_SYMBOL` /
> `WIRING_REJECTED_WRONG_ENVIRONMENT` / `WIRING_REJECTED_WRONG_SIDE` /
> `WIRING_REJECTED_QTY_MISMATCH` / `WIRING_REJECTED_PROTECTED_SYMBOL` /
> `WIRING_REJECTED_CANDIDATE_INVALID`；3 個 source enum：
> `CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY` (授權成功) /
> `REJECTED_NO_FALLBACK_TO_0_01` (失敗永不退回 0.01) / `NONE` (不需要 override)；
> JSON+MD 報告寫入 `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring/`。
> (2) 決策順序（precedence）嚴格 fail-closed：missing IR → REJECTED_RULES_NOT_LOADED；
> missing gate → REJECTED_GATE_MISSING；non-`bybit_demo` env → REJECTED_WRONG_ENVIRONMENT；
> protected symbol → REJECTED_PROTECTED_SYMBOL；非 SOLUSDT → REJECTED_WRONG_SYMBOL；
> 非 Buy → REJECTED_WRONG_SIDE；gate 回 `ESCALATION_NOT_REQUIRED` 或
> `original_tiny_cap_passed=True` → NOT_REQUIRED_ORIGINAL_PASSES、
> `execution_qty=""`、`execution_qty_source=NONE`；gate 回 `ESCALATION_AUTHORIZED`
> → 驗證 `cap_escalated_demo_only=True` AND `explicit_demo_min_qty_cap_authorized=True`
> AND 閘自身的 `decision.candidate_qty` / `decision.candidate_notional` 合法（**不
> silently fallback 到 IR 的 candidate**） AND notional ≤ 20 AND
> proposed_qty == candidate_qty → AUTHORIZED_CANDIDATE_QTY，
> `execution_qty="0.1"`、`execution_qty_source=CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY`、
> `original_packet_qty="0.01"`、`qty_0_01_confirmed_invalid=True`；
> gate 回 `ESCALATION_REJECTED_NOTIONAL_OVER_CAP` → REJECTED_GATE_OVER_CAP；
> 其他 → NOT_AUTHORIZED_NO_OVERRIDE。**任何 rejected 路徑 `execution_qty=""`、
> source=`REJECTED_NO_FALLBACK_TO_0_01` 或 `NONE`，絕不退回 BL 的 0.01 給
> execute 模式**。
> (3) 在 BM `ExecutionReport` 上再新增 6 個 *defaulted* 欄位
> `wiring_loaded` / `wiring_status` / `original_packet_qty` /
> `execution_qty_source` / `execution_qty_resolved` /
> `execution_notional_estimate_resolved`，並新增 optional
> `authorized_execution_qty_wiring` kwarg 於 `run_explicit_tiny_order_execution()`，
> 未傳時欄位全為安全預設值（False / ""）；既有 BH→BM_CAP_ESCALATION_GATE
> 共 417 條測試完全不變、繼續 PASS。BM `execute_demo_order` 行為（包括
> hardcoded body qty 來源 = BL packet `DEFAULT_QTY="0.01"`）**未被本任務改動** —
> 這層只把授權後的 candidate_qty surface 到 readiness/planning，**並未真把
> BM 的執行 body qty 切換到 0.1**。
> (4) 新增 preview CLI
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py)
> （`--mark-price`；`--ir-mode {offline,discover}` 預設 offline；`--proposed-qty`；
> `--max-demo-min-qty-notional-cap-usdt` 預設 20；授權旗標
> `--i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap` +
> `--authorization-marker`；`--write-report` / `--output-dir`；exit 0 = 任一
> 預期 12 個決策狀態，1 = 其他終態 / 例外）。預設未授權路徑 → exit 0、
> `status=WIRING_REJECTED_RULES_NOT_LOADED`（offline IR 無 rules → fail-closed）。
> (5) 新增 [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py)
> 33 條 Stage 1 focused-core，覆蓋 identity / chain-break / upstream / immutable
> locks；missing IR / missing gate / 兩者皆缺 fail-closed；授權成功路徑
> execution_qty=0.1, notional=10.0, cap_gate_status=ESCALATION_AUTHORIZED；
> 未授權 → WIRING_NOT_AUTHORIZED_NO_OVERRIDE / execution_qty=""；
> mark=250 over-cap → WIRING_REJECTED_GATE_OVER_CAP；ESCALATION_NOT_REQUIRED →
> WIRING_NOT_REQUIRED_ORIGINAL_PASSES / source=NONE；gate 自身 qty mismatch
> 阻斷 wiring；tampered gate 合成 helper 證明即使 gate 被竄改，wiring
> 仍依 wrong_environment / protected symbols (5 parametrize) / wrong_symbol /
> wrong_side / qty_mismatch / candidate_invalid / authorized-but-not-cap-escalated
> 各路徑 fail closed；AST static-source 拒絕 `urllib` / `requests` / `pybit` /
> `aiohttp` / `httpx` / `websocket` / `websockets` / `urllib.request` /
> `http.client` import、拒絕 `BybitExecutor` / `main` / `src.risk` /
> `src.executors.bybit` 引用、拒絕 `os.environ` / `os.getenv`、拒絕 docstring
> 以外的 secret env name string-const、拒絕 docstring 以外的
> `FORBIDDEN_URL_TOKENS` 中任一 token 出現超過 1 次（denylist 行內）、
> 拒絕 `api-demo.bybit.com` string-const；global tiny caps
> (`TINY_QTY_CAP_SOL=0.05` / `TINY_SIZE_CAP_USDT=5` / `TINY_QTY_STEP_SOL=0.01`)
> 與 `PROTECTED_SYMBOLS` frozenset 不被本層改動；報告 writer 寫 4 個檔 +
> JSON round-trip；BM `ExecutionReport` 預設不暴露 wiring 欄位，傳入後正確
> surface 授權與未授權兩種情境。
>
> 安全面：**本任務沒有送出任何真實 demo 單**、**沒有重試 execute_demo_order**、
> **沒有呼叫 /v5/order/create**、**沒接 live endpoint**、**沒讀任何 live/demo
> secret env**、**沒動 protected positions**、**沒動 `main.py` / `src/risk.py` /
> `src/executors/bybit.py` / `BybitExecutor`**、**沒解除 max_order_count=1
> 或 double-confirmation 旗標**、**沒全域抬升 `TINY_QTY_CAP_SOL` /
> `TINY_SIZE_CAP_USDT`**、**沒改 BL packet 的 `DEFAULT_QTY="0.01"`**、
> **沒新增 stop endpoint / TP / SL / retry / scheduler**、**沒把 BM 的執行
> body qty 切到 0.1**。本層只在 cap-escalation 閘明確授權的前提下，把
> candidate_qty=0.1 浮出到 readiness/planning 欄位，提供 Stage 2 任務做
> 後續 BL packet 切換的事實基礎。
>
> 本次驗證：`py_compile` 4 個 changed/added Python 檔 PASS；
> `pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py`
> → **33/33 PASS**；BH→BM 鏈 10 個 adapter 測試檔合計 **450/450 PASS**
> (417 既有 + 33 新增)；offline 預覽 smoke (`--mark-price 100 --proposed-qty 0.1`，
> 未授權路徑) → exit 0、`status=WIRING_REJECTED_RULES_NOT_LOADED`、
> `network_attempted=False`、`order_endpoint_called=False`、`order_sent=False`；
> cap-escalation preview / BM readiness preview / BM_MIN_QTY_FIX preview
> 皆仍 exit 0、`order_sent=False`。
>
> 後續 next-step：Rick 在 VPS 上跑 wiring preview 觀察「offline rules-not-loaded
> → discover 模式 IR 載入 → 加 explicit 雙重授權」三種狀態轉換，再決定是否
> 啟動 Stage 2 — 把 `execution_qty_resolved` 真的接到 BM execute_demo_order
> 的 body qty（會涉及 BL packet `DEFAULT_QTY="0.01"` 來源切換 + 一輪新的雙重
> 授權任務）。
>
> 上一個 CAP_ESCALATION_GATE banner 保留於下方。

> **TASK-014BM_CAP_ESCALATION_GATE**（2026-06-19，已歸檔）在
> TASK-014BM / TASK-014BM_FIX / TASK-014BM_MIN_QTY_FIX 之上新增一個
> **narrow、decision-only、demo-only 的 SOLUSDT cap escalation 授權閘**，用來在
> Rick 明確簽署授權的前提下、針對「Bybit Demo 當前對 SOLUSDT linear 的
> `minOrderQty` 已超過原本 `TINY_QTY_CAP_SOL=0.05` / `TINY_SIZE_CAP_USDT=5`」
> 這條單一路徑進行授權記錄。本任務 Stage 1 only — **不送單、不呼叫
> `/v5/order/create`、不重試 `execute_demo_order`、不接 live endpoint、不讀
> 任何 live/demo secret、不動 protected positions、不上 retry、不上 scheduler、
> 不掛 stop / TP / SL**。具體變更：
> (1) 新增 [`src/demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py`](src/demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py)：
> 單一決策入口 `run_cap_escalation_gate(instrument_rules_report, request,
> max_demo_min_qty_notional_cap_usdt)`；常數鎖死 `ALLOWED_ENVIRONMENT="bybit_demo"` /
> `ALLOWED_SYMBOL="SOLUSDT"` / `ALLOWED_SIDE="Buy"` / `ALLOWED_ORDER_TYPE="Market"` /
> `ALLOWED_TIME_IN_FORCE="IOC"` / `ALLOWED_MAX_ORDER_COUNT=1`；新增
> `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=Decimal("20")`（**只作用在這條 SOLUSDT demo
> 路徑**，BH 的 `TINY_QTY_CAP_SOL` / `TINY_SIZE_CAP_USDT` 全域常數**完全不動**）；
> 新增明確授權旗標 `EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_FLAG_NAME =
> "--i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap"` 與
> 授權標記 `EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER =
> "DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1"`，**兩者
> 必須同時存在才會授權**；任一缺一即 `ESCALATION_NOT_AUTHORIZED` fail-closed。
> (2) 閘輸入嚴格鎖：non-`bybit_demo` 環境、non-`SOLUSDT` symbol、`PROTECTED_SYMBOLS`
> （ENA / TIA / AIXBT / POLYX / EDU）、Sell side、Limit / 非 Market、非 IOC、
> `reduce_only=True` / `close_on_trigger=True`、非空 `stop_loss` / `take_profit`、
> `max_order_count != 1`、`proposed_qty != candidate_qty`、`endpoint_url_hint`
> 含 `api.bybit.com` / `api.bytick.com` / `wss://stream.*` / `/v5/order/create` /
> `/v5/order/cancel` / `/v5/position/set-trading-stop` 任一 token — **全部 fail
> closed，回傳 `ESCALATION_REJECTED_*` 對應狀態，永不授權**。
> (3) 即便授權旗標 + marker 齊備，仍要求 `candidate_notional <=
> max_demo_min_qty_notional_cap_usdt`（預設 20 USDT）— 例如 mark_price=250 使
> candidate qty=0.1 推出 notional=25 > 20 cap，會回 `ESCALATION_REJECTED_NOTIONAL_OVER_CAP`
> 並標 `explicit_demo_min_qty_cap_authorized=True` / `cap_escalated_demo_only=False`。
> (4) 在 BM `ExecutionReport` 上新增 6 個 *defaulted* 欄位
> `original_tiny_cap_passed` / `exchange_min_qty_cap_escalation_required` /
> `explicit_demo_min_qty_cap_authorized` / `cap_escalated_demo_only` /
> `cap_escalation_status` / `max_demo_min_qty_notional_cap_usdt`，並新增 optional
> `cap_escalation` kwarg 於 `run_explicit_tiny_order_execution()`，未傳時欄位全
> 為安全預設值（False / ""）；既有 BM / BM_FIX / BM_MIN_QTY_FIX 共 368 條
> 測試完全不變。BM `execute_demo_order` 行為（包括 hardcoded body qty 來源 =
> BL packet `DEFAULT_QTY="0.01"`）**未被本任務改動** — 真正把 candidate qty=0.1
> 接到 BM 執行路徑需要另一個 Stage 2 授權任務。
> (5) 新增 preview CLI
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py)
> （`--mark-price`；`--proposed-qty`；`--max-demo-min-qty-notional-cap-usdt`
> 預設 20；授權旗標 `--i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap` +
> `--authorization-marker`；`--write-report` / `--output-dir`；exit 0 = 任一
> 預期決策狀態，1 = 其他終態）。
> (6) 新增 [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py)
> 49 條 Stage 1 focused-core，覆蓋 identity / chain-break / upstream / immutable
> locks / 授權旗標 + marker 兩者必須齊備 / `candidate_notional <= 20` 強制執行 /
> 自訂 cap 仍能拒絕、不合法 cap 回退預設 / `ESCALATION_NOT_REQUIRED`
> 當原 tiny cap 已通過 / 非 SOLUSDT / 非 bybit_demo / 非 Buy / 非 Market / 非
> IOC / `max_order_count != 1` / qty mismatch / 空 qty / `PROTECTED_SYMBOLS`
> 五個 symbol parametrize 拒絕 / `endpoint_url_hint` 含 live host / `/v5/order/create` /
> `wss://` 四種 parametrize 拒絕 / reduce_only / close_on_trigger / stop_loss /
> take_profit 拒絕 / 報告永遠 `order_endpoint_called=False`、`order_sent=False`、
> `network_attempted=False` / 全域 tiny caps 不被閘改動 / `PROTECTED_SYMBOLS`
> 內容未變 / AST static-source 拒絕 third-party HTTP client import 與
> `BybitExecutor` / `main` / `src.risk` 引用 / docstring-排除的 secret env name
> 出現檢查 / source 中 live host token 至多出現一次（denylist 行內）/ JSON +
> Markdown 報告 round-trip / BM ExecutionReport 預設不暴露 cap-escalation 欄位 /
> BM ExecutionReport 傳入 ce report 後正確 surface 授權與未授權兩種情境。
>
> 安全面：**本任務沒有送出任何真實 demo 單**、**沒有重試 execute_demo_order**、
> **沒有呼叫 /v5/order/create**、**沒接 live endpoint**、**沒讀任何 live/demo
> secret env**、**沒動 protected positions**、**沒動 `main.py` / `src/risk.py` /
> `src/executors/bybit.py` / `BybitExecutor` 任何行為**、**沒解除 max_order_count=1
> 或 double-confirmation 旗標**、**沒全域抬升 `TINY_QTY_CAP_SOL` / `TINY_SIZE_CAP_USDT`**、
> **沒新增 stop endpoint / TP / SL / retry / scheduler**。原 5 USDT / 0.05 SOL
> tiny cap 仍是全域預設；本閘只在 Rick 明確雙重授權（flag + marker）的單一
> SOLUSDT demo 路徑上、且 candidate_notional <= 20 USDT 的前提下，把這條單獨
> 升級為 `cap_escalated_demo_only=True`。
>
> 本次驗證：`py_compile` 4 個 changed/added Python 檔 PASS；
> `pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py`
> → **49/49 PASS**；BH→BM 鏈 9 個 adapter 測試檔合計 **417/417 PASS** (368 既有 +
> 49 新增)；offline 預覽 smoke (`--mark-price 100 --proposed-qty 0.1`，未授權路徑)
> → exit 0、`status=ESCALATION_NOT_AUTHORIZED`、`authorized=False`、`network_attempted=False`、
> `order_endpoint_called=False`、`order_sent=False`；BM readiness preview 與
> BM_MIN_QTY_FIX preview 皆仍 exit 0、`network_attempted=False`、`order_sent=False`。
>
> 後續 next-step：Rick 可在 VPS 上跑 cap-escalation preview 觀察「未授權 →
> 授權但超 cap → 授權且在 cap 內」三種決策狀態，然後再決定是否要在另一個
> 明確 Stage 2 授權任務中把 candidate qty=0.1 接到 BM 執行路徑（會涉及 BL
> packet 內 hardcoded qty 來源切換，需要更謹慎的 chain-break 設計）。
>
> 上一個 BM_MIN_QTY_FIX banner 保留於下方。

> **TASK-014BM_MIN_QTY_FIX**（2026-06-19, 已歸檔）在 TASK-014BM / TASK-014BM_FIX 之上新增
> **demo-only、唯讀的 SOLUSDT instrument rules discovery 層**，用來解決 FIX 之後
> 觀察到的 `retCode=10001 "The number of contracts exceeds minimum limit allowed"`
> 阻塞：當前 Bybit Demo 對 SOLUSDT linear 的 `minOrderQty` 已大於先前 hardcode 的
> `qty=0.01`，繼續送 0.01 一律會被退。本任務 Stage 1 only — **不重試 real order
> 執行、不呼叫 /v5/order/create、不接 live endpoint、不讀任何 live/demo secret、不
> 動 protected positions**。具體變更：
> (1) 新增 [`src/demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py`](src/demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py)，
> 單一聚合入口 `run_instrument_rules_discovery(mode, mark_price, category, symbol,
> sender, pre_parsed_response)`；常數鎖死 `ALLOWED_DEMO_HOST="api-demo.bybit.com"` /
> `ALLOWED_READONLY_URL="https://api-demo.bybit.com/v5/market/instruments-info"` /
> `ALLOWED_CATEGORY="linear"` / `ALLOWED_SYMBOL="SOLUSDT"`；任何其他 category / symbol /
> endpoint URL 都會在進入網路之前被 `_assert_locked_inputs` 阻擋；`build_readonly_request_url`
> 拒絕一切 live host、`/v5/order/create`、`wss://` token；公共 GET sender
> `_real_public_get_via_urllib` hard-assert URL prefix 必須為 `ALLOWED_READONLY_URL + "?"`，
> 否則直接 raise（即使是 demo host 上的 `/v5/order/create` 也會被退）；mode 預設
> `offline`（無 network、no rules loaded），`discover` mode 才會打單次 bounded GET，
> 無 retry、無 scheduler、無 signing、無 API key、無 recv-window。
> (2) 新增解析器 `parse_instrument_rules(parsed)`：嚴格從 V5 `result.list` 找 SOLUSDT entry，
> 必要欄位 `lotSizeFilter.{minOrderQty, qtyStep, minNotionalValue}` 缺一即 raise；額外暴露
> `lotSizeFilter.maxMktOrderQty`（若存在）與 `priceFilter.tickSize`（若存在）。
> (3) 新增 `compute_candidate_tiny_qty(rules, mark_price, tiny_qty_cap_sol, tiny_size_cap_usdt)`：
> 以 `max(minOrderQty, qty_step)` 開始向上對齊 `qty_step`；若 `mark_price * candidate <
> minNotionalValue`，再向上補到滿足 `minNotionalValue` 的最小 `qty_step` 倍數；最後跟
> BH 的 `TINY_QTY_CAP_SOL=0.05` / `TINY_SIZE_CAP_USDT=5` 比對，**任一 cap 被超過即 fail
> closed** → status `TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN`、`is_executable_under_tiny_caps=False`、
> 絕不偷偷把 tiny cap 拉高、絕不送單。額外回報 `confirms_qty_0_01_invalid`（當
> `0.01 < minOrderQty`）。
> (4) 在 BM `ExecutionReport` 上新增 9 個 *defaulted* 欄位
> `instrument_rules_loaded` / `instrument_rules_discovery_status` /
> `instrument_rules_min_order_qty` / `instrument_rules_qty_step` /
> `instrument_rules_min_notional_value` / `computed_candidate_qty` /
> `computed_candidate_notional` / `candidate_is_executable_under_tiny_caps` /
> `qty_0_01_confirmed_invalid`；新增 optional `instrument_rules` 參數於
> `run_explicit_tiny_order_execution()`，未傳時欄位皆為安全預設值，**現有 88 條 BM /
> BM_FIX 測試與既有呼叫端皆完全不變**。execute_demo_order 行為（包括 hardcoded
> body qty 來源 = BL packet）**未被本任務改動** — 改動 qty 需要另一個明確授權任務。
> (5) 新增 preview CLI [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py)
> （`--mode {offline,discover}` 預設 offline；`--mark-price`；`--write-report` /
> `--output-dir`；exit code 0 = OK / OFFLINE / 預期 fail-closed 報告，1 = 其他終態）。
> (6) 新增 [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py)
> 52 條 Stage 1 focused-core，覆蓋 identity / chain-break、endpoint+category+symbol
> 鎖死、live URL 與 `/v5/order/create` token 阻擋、parser 對 V5 `lotSizeFilter` 的
> 嚴格解析、parser 拒絕缺 lotSizeFilter、parser 拒絕非 SOLUSDT entry、candidate
> 對齊 qty_step、candidate 補到 minNotionalValue、tiny-cap fail-closed、`qty=0.01`
> 確認 invalid、injected sender 永不收到 order-create URL、network error 路徑、
> 非零 retCode 路徑、AST static-source 拒絕 third-party HTTP client import 與
> `BybitExecutor` / `main` / `src.risk` 引用、docstring-排除的 secret env name 出現
> 檢查、JSON + Markdown 報告 round-trip、BM ExecutionReport 預設不暴露 instrument
> rules 欄位、BM ExecutionReport 傳入 ir report 後正確surface 三組欄位。
>
> 安全面：**本任務沒有送出任何真實 demo 單**、**沒有重試 execute_demo_order**、
> **沒有呼叫 /v5/order/create**、**沒接 live endpoint**、**沒讀任何 live/demo secret
> env**、**沒動 protected positions（ENA / TIA / AIXBT / POLYX / EDU）**、**沒動
> `main.py` / `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor`**、**沒新增
> stop endpoint / TP / SL / retry / scheduler**。
>
> 本次驗證：`py_compile` 4 個 changed/added Python 檔 PASS；
> `pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py`
> → **52/52 PASS**；BH→BM 鏈 8 個 adapter 測試檔合計 **368/368 PASS** (316 既有 +
> 52 新增)；offline 預覽 smoke (`--mode offline --mark-price 100`) → exit 0、
> `discovery_status=DISCOVERY_OFFLINE_NO_NETWORK`、`network_attempted=False`、
> `order_endpoint_called=False`、`order_sent=False`；BM readiness preview
> (`--mode readiness`) 仍 exit 0、`final_status=READINESS_OK_NO_NETWORK`、`network_attempted=False`、
> 與 FIX 後一致。
>
> 後續 next-step：Rick 可在 VPS 上於 `--mode discover` 跑一次唯讀 instruments-info
> 抓真實 SOLUSDT 當前 `minOrderQty` / `qtyStep` / `minNotionalValue`，然後依
> `candidate_is_executable_under_tiny_caps` 決定是否需要另外一個明確授權任務來
> 同步調整 BL packet 的 hardcoded qty，或先把 tiny cap 上限重新評估 — 本任務
> 不替 Rick 做這個決定。

> 上一個 FIX banner 保留於下方。

> **TASK-014BM_FIX**（2026-06-19）在 TASK-014BM 上的 **corrective patch**：
> 修復 Bybit V5 HMAC 簽名路徑（先前一次真實 demo 嘗試被 Bybit 回 `retCode=10004
> "Error sign, please check your signature generation algorithm"`），並收緊
> `final_status` 對應關係。具體變更：
> (1) 新增 `_serialize_signed_body(body_preview) -> (json_body_string, body_bytes)`
> 提供唯一 canonical compact JSON 序列化
> （`json.dumps(..., separators=(",", ":"), ensure_ascii=False)`），且斷言
> `body_bytes.decode("utf-8") == json_body_string`，保證 **POST 出去的 bytes
> 與 HMAC prehash 用的 body string byte-identical**；
> (2) `_sign_bybit_v5` 改為直接吃 `json_body_string: str`，prehash 形式為
> `timestamp_ms + api_key + recv_window + json_body_string`；
> (3) 補上先前缺失的 `X-BAPI-SIGN-TYPE: "2"` header，與 `X-BAPI-API-KEY` /
> `X-BAPI-TIMESTAMP` / `X-BAPI-SIGN` / `X-BAPI-RECV-WINDOW` /
> `Content-Type: application/json` 同時送出；
> (4) 新增終態 `STATUS_BYBIT_REJECTED_NO_ORDER_SENT = "BYBIT_REJECTED_NO_ORDER_SENT"`；
> (5) `final_status` 改為 5-condition 連言式 — **只有** `network_attempted AND
> order_endpoint_called AND order_sent AND bybit_ret_code == 0 AND bybit_order_id
> 非空** 才會被標為 `EXECUTED_DEMO_ONLY`；任何非零 retCode（含觀察到的 `10004`）
> 或空 `bybit_order_id` 都對應到 `BYBIT_REJECTED_NO_ORDER_SENT` 並保證
> `order_sent=False`；sender 拋網路錯誤仍優先對應 `NETWORK_ERROR_DEMO_ONLY`；
> (6) 新增 `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_fix.py`
> 19 條 FIX 專屬 regression，含 `retCode=10004` 精確重現、parametrize 多種非零
> retCode、posted body bytes vs. signed body string byte-equality、compact JSON
> 與 lowercase JSON booleans、`X-BAPI-SIGN-TYPE="2"`、`X-BAPI-SIGN` lowercase
> hex SHA-256、完整 6-header V5 envelope、`MAX_ORDER_COUNT`/`ALLOWED_DEMO_ENDPOINT_URL`/
> demo-only env 名稱維持不動。
>
> 安全面：FIX **沒有再送出第二次真實 demo 單**；preview CLI 行為旗標不變
> （只更新 docstring 把 `BYBIT_REJECTED_NO_ORDER_SENT` 標到 exit code 1）；
> 沒動 `main.py` / `src/risk.py` / `src/executors/bybit.py`；沒動
> `BybitExecutor` live 行為；沒新增 stop endpoint；沒加 TP/SL；沒加 retry；
> 沒加 scheduler；沒接 live secret；16 個 gate、`MAX_ORDER_COUNT=1`、
> `ALLOWED_DEMO_ENDPOINT_URL`、protected positions（ENA/TIA/AIXBT/POLYX/EDU）
> 全部維持。
>
> 本次驗證：`py_compile` 三個 changed Python 檔 PASS；
> `pytest test_demo_only_tiny_execution_adapter_tiny_order_execution.py
> + test_demo_only_tiny_execution_adapter_tiny_order_execution_fix.py` → **88/88 PASS**
> (69 原 BM + 19 FIX)；BH→BL→BM 鏈 7 個 adapter 測試檔合計 **316/316 PASS**；
> preview readiness smoke exit 0、`final_status=READINESS_OK_NO_NETWORK`、
> `network_attempted=False`、`order_sent=False`、`live_endpoint_denied=True`、
> `protected_symbols_untouched=True`、`max_order_count=1`、
> `all_pre_network_gates_passed=True`。

> **TASK-014BM 在 BH/BI/BJ/BK/BL 安全鏈上加 explicit demo-only tiny order execution 路徑**。
> 新增 BM 三件套：
> [`src/demo_only_tiny_execution_adapter_tiny_order_execution.py`](src/demo_only_tiny_execution_adapter_tiny_order_execution.py)
> （新增 frozen dataclass `DemoCredentials` / `ExecutionGate` / `ExecutionPlan` / `SendOutcome` /
> `ExecutionReport`；單一聚合入口 `run_explicit_tiny_order_execution(mode, execute_flag,
> confirm_flag, existing_positions, endpoint_target, credentials, env, sender)` 順序執行：
> (1) `bl.run_tiny_order_preparation()` 取得 `PreparationPacket`，packet 不通過直接 fail-fast；
> (2) 從環境變數讀取 demo-scoped credentials（`BYBIT_DEMO_API_KEY`／`BYBIT_DEMO_API_SECRET`／
> `BYBIT_DEMO_RECV_WINDOW`，找不到→產生 `MISSING_DEMO_CREDENTIALS` 安全報告而非失敗，也絕不
> fallback 讀取 live 名稱）；(3) 在固定順序中評估 **16 個 gate**，前 13 個 pre-network gate
> `bl_packet_loaded`、`bl_packet_all_passed`、`packet_marked_not_execution_authorization`、
> `packet_audit_status_from_bh`、`environment_is_bybit_demo`、`symbol_is_solusdt`、
> `qty_within_tiny_cap`、`order_type_market`、`time_in_force_ioc`、`reduce_only_false`、
> `endpoint_target_demo_only`、`protected_symbols_not_in_scope`、`order_count_locked_to_one`，
> 後 3 個 execute gate `explicit_execute_flag`、`explicit_confirm_flag`、`demo_credentials_present`；
> (4) 任何 pre-network gate 失敗→`STATUS_GATE_REJECTED_NO_NETWORK`，sender 絕不呼叫；
> (5) 三種 mode：`dry_run` / `readiness`（兩者皆無 network、無 secret 讀取）/ `execute_demo_order`
> （**僅當** 雙旗標 `--execute-demo-order` + `--i-understand-this-sends-one-bybit-demo-order`
> 同時呈現且 16 gate 全 pass + creds present，才會經 sender injection 點呼叫 stdlib `urllib.request`
> POST 一次到 `https://api-demo.bybit.com/v5/order/create`，使用 Bybit V5 HMAC-SHA256
> 簽名 `HMAC(secret, timestamp+api_key+recv_window+body)` + 標準 V5 headers
> `X-BAPI-API-KEY` / `X-BAPI-TIMESTAMP` / `X-BAPI-SIGN` / `X-BAPI-RECV-WINDOW`，
> 內建 `_real_sender_via_urllib` hard-assert URL == `ALLOWED_DEMO_ENDPOINT_URL`；
> body 只含九欄位 `category` / `symbol` / `side` / `orderType` / `qty` / `timeInForce` /
> `reduceOnly` / `closeOnTrigger` / `orderLinkId`，**完全沒有 stopLoss / takeProfit /
> trading-stop 欄位**；最多送一單 `MAX_ORDER_COUNT=1`，無 retry、無 scheduler）；
> module import 時即呼叫 `bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)`；
> `write_report` 輸出 JSON+Markdown 到
> `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_execution/`
> （`latest_*.{json,md}` + 時間戳 `*_<UTC_TS>.{json,md}`）；chain-break markers
> `TASK_ID="TASK-014BM"`、`IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-EXECUTION"`、
> `IMPLEMENTATION_PATH_PHASE="tiny_order_execution"`、`IS_REVIEW_CHAIN_SUFFIX=False`、
> `UPSTREAM_TASKS=("TASK-014BH","TASK-014BI","TASK-014BJ","TASK-014BK","TASK-014BL")`、
> `NEXT_REQUIRED_TASK="TASK-014BN_demo_only_tiny_execution_postfill_audit"`、
> `EXECUTION_CONTRACT_VERSION="demo_only_tiny_execution_adapter_tiny_order_execution_v1"`），
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py)
> （CLI 預設 `--mode readiness`（無 network、無 secret 讀取）；`--mode execute_demo_order`
> 必須同時帶 `--execute-demo-order` + `--i-understand-this-sends-one-bybit-demo-order`
> 雙旗標，缺一就走 GATE_REJECTED；`--endpoint-target` 覆寫測試用；`--write-report` /
> `--output-dir`；含 ROOT sys.path 注入；exit code 0=DRY_RUN_OK/READINESS_OK/EXECUTED_DEMO_ONLY、
> 2=MISSING_DEMO_CREDENTIALS、1=其他），
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py)
> （Stage 1 focused-core **69 tests**：identity / chain-break markers / BM pointer 不是
> review-chain 後綴且明確指向 `demo_only_tiny_execution_postfill_audit` / `EXECUTION_CONTRACT_VERSION` /
> 預設 `--mode dry_run` 不呼叫 sender / `readiness` 通過 13 個 pre-network gate 但無 network
> 且 plan 已 build / execute mode 無旗標→`STATUS_GATE_REJECTED_NO_NETWORK` 且 sender
> 絕不被呼叫 / execute mode 雙旗標但 creds 缺→`STATUS_MISSING_DEMO_CREDENTIALS` /
> execute mode 雙旗標 + creds + injected fake sender→`STATUS_EXECUTED_DEMO_ONLY` 且 sender
> 被呼叫且僅被呼叫一次（counter 驗證）並擷取 `bybit_order_id` / network error →
> `STATUS_NETWORK_ERROR_DEMO_ONLY` / 任何 pre-network reject 路徑（3 個 live URL、3 個非
> SOLUSDT、5 個 protected symbol、5 個 protected existing position、4 個 qty 超 cap、
> reduceOnly=True、packet 缺失、packet `_demo_only_bh_audit_response_status` 被竄改、
> `packet_is_not_execution_authorization=False` 竄改）都 parametrize 驗證 sender 絕不被
> 呼叫 / credential 載入只用 demo-scoped 名稱（明確檢查 LIVE 名稱 `BYBIT_API_KEY` / `BYBIT_API_SECRET`
> 不被讀取）/ `_real_sender_via_urllib` 對 non-demo URL hard-raise / `ExecutionPlan` / `ExecutionReport`
> frozen 不可變 / AST-based static-source 檢查 BM 不 import 任何 network library
> （`requests` / `pybit` / `aiohttp` / `httpx`），不 import `main` / `src.risk` / `src.executors.bybit`
> / `BybitExecutor` Name/Attribute / docstring 剝除後也不引用 LIVE env 名稱、無 set-trading-stop /
> stopLoss / takeProfit / retry / scheduler token / BM source 同時 import BH/BI/BJ/BK/BL 五個上游
> module（無平行實作）/ BH chain-break suffix guard 接受 BM 自身 `NEXT_REQUIRED_TASK` + 拒絕 3
> 個 forbidden suffix parametrize / BK checklist 與 BL preparation 在 BM 之下仍 `all_passed=True`
> / cross-module `BybitExecutor` / `main` / `src.risk` 未被載入 / 4 個檔案寫入 + JSON round-trip +
> Markdown 含 `TASK-014BM` / `tiny_order_execution` / `READINESS_OK_NO_NETWORK` / `max_order_count` /
> plan symbol SOLUSDT / qty 0.01 / IOC / 等明文 / body preview 形狀只有 9 欄位（無 stop/TP 欄位）/
> 簽名 request headers 含完整 Bybit V5 envelope（`X-BAPI-API-KEY` / `X-BAPI-TIMESTAMP` /
> `X-BAPI-SIGN` 長度為 SHA-256 hex 64 字元 / `X-BAPI-RECV-WINDOW`））。BM 直接消費
> BH/BI/BJ/BK/BL — sender 採 dependency-injection 模式（預設 `_real_sender_via_urllib`，
> 測試覆寫成 fake sender 計數呼叫；real sender 內 hard-assert URL）；module 不開
> socket、不讀 live secret、不修改 position；最多送一次 demo POST。下一棒
> `TASK-014BN_demo_only_tiny_execution_postfill_audit`（**implementation path 下一步；
> 不是 review-chain 後綴**；需 Rick 在 NEXT_ACTION.md 另行授權才會啟動）。仍無 stop endpoint、
> 無 TP/SL 附加、無 retry、無 scheduler、無 G20 lift、無 position 修改、無 live secret 讀取。
> main.py / src/risk.py / BybitExecutor 仍未動。
>
> （下方 BL 區塊保留為前一棒的 tiny order preparation 完成紀錄。）

> **TASK-014BL 在 BH/BI/BJ/BK 安全鏈上加 tiny order preparation 層**，產出未來 TASK-014BM
> explicit demo-only tiny order execution 任務專用的 **離線 authorization packet**。
> 新增 BL 三件套：
> [`src/demo_only_tiny_execution_adapter_tiny_order_preparation.py`](src/demo_only_tiny_execution_adapter_tiny_order_preparation.py)
> （兩個 frozen dataclass `PreparationPacket` / `PreparationReport`；單一聚合入口
> `run_tiny_order_preparation()` 順序執行：(1) `bk.run_final_pre_execution_checklist()`
> 並要求 `all_passed=True`，(2) `bj.integrate_demo_only_tiny_request(IntegrationRequest)`
> 取得 guard-validated payload audit dict（預設 SOLUSDT Buy 0.01 @ mark 100 +
> demo endpoint `https://api-demo.bybit.com/v5/order/create`），(3) 在 BH+BJ 兩層 audit
> markers 上再貼 BL 第三層 markers：`_demo_only_bl_audit_response_status=NOT_SENT_PREPARED_ONLY_NOT_EXECUTED`、
> `_demo_only_bl_target_future_task=TASK-014BM_explicit_demo_only_tiny_order_execution`、
> `_demo_only_bl_authorization_is_not_execution_authorization=True`、
> `_demo_only_bl_preparation_contract_version=demo_only_tiny_execution_adapter_tiny_order_preparation_v1`、
> `_demo_only_bl_implementation_path_task=TASK-014BL`、`_demo_only_bl_is_review_chain_suffix=False`、
> `_demo_only_bl_packet_note`（明文 "PREPARATION ONLY ... does NOT authorize execution"）；
> 額外 `build_preparation_packet()` 直接入口供 unit test 驗證每一個 reject 路徑；
> module import 時即呼叫 `bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)`；
> `write_report` 輸出 JSON+Markdown 到
> `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_preparation/`
> （`latest_*.{json,md}` + 時間戳 `*_<UTC_TS>.{json,md}`）；chain-break markers
> `TASK_ID="TASK-014BL"`、`IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-PREPARATION"`、
> `IMPLEMENTATION_PATH_PHASE="tiny_order_preparation"`、`IS_REVIEW_CHAIN_SUFFIX=False`、
> `UPSTREAM_TASKS=("TASK-014BH","TASK-014BI","TASK-014BJ","TASK-014BK")`、
> `NEXT_REQUIRED_TASK="TASK-014BM_explicit_demo_only_tiny_order_execution"`、
> `TARGET_FUTURE_TASK="TASK-014BM_explicit_demo_only_tiny_order_execution"`、
> `PREPARATION_CONTRACT_VERSION="demo_only_tiny_execution_adapter_tiny_order_preparation_v1"`、
> `BL_AUDIT_RESPONSE_STATUS_NOT_SENT="NOT_SENT_PREPARED_ONLY_NOT_EXECUTED"`），
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_preparation.py`](scripts/preview_demo_only_tiny_execution_adapter_tiny_order_preparation.py)
> （CLI `--write-report` / `--output-dir` / `--symbol` / `--side` / `--qty` / `--mark-price`；
> 含 ROOT sys.path 注入；exit 0 iff `all_passed=True`，否則 exit 1），
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_preparation.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_preparation.py)
> （Stage 1 focused-core **47 tests**：identity / chain-break markers / BL pointer
> 不是 review-chain 後綴且明確指向 `demo_only` + `tiny_order_execution` / `PREPARATION_CONTRACT_VERSION` /
> `BL_AUDIT_RESPONSE_STATUS_NOT_SENT` / `DEFAULT_*` 常數 / packet note 明文宣告
> "NOT authorize execution"、aggregate `run_tiny_order_preparation` `all_passed=True`
> + BK checklist 計數與直接 `bk.run_final_pre_execution_checklist()` 完全一致 + 三層 BH/BI/BJ/BK
> identity snapshot、`PreparationPacket` / `PreparationReport` frozen 不可變、packet 預設
> request 欄位（SOLUSDT、Buy、0.01、mark 100、Market、IOC、reduceOnly=False、
> `DEMO_ONLY_TINY_BH_` prefix orderLinkId、notional 1 USDT ≤ BH 5 USDT cap、qty ≤ 0.05 SOL cap）、
> packet audit 同時帶 BH/BJ/BL 三層 markers + 保留 SOLUSDT / Market / IOC / reduceOnly=False、
> `build_preparation_packet` 直接呼叫被以 parametrize 拒絕 3 個 non-SOLUSDT symbol + 5 個 protected
> symbol + protected-in-existing + live endpoint + qty-cap-fail + notional-cap-fail + bybit_live env、
> BL 自身 source 6 項 tokenize+ast static-source 檢查（no network library import、no
> `getenv`/`environ`/`load_dotenv` token、no `def send`/`.send(`/`place_order`/
> `post_order`/`submit_order` surface、no `main`/`src.risk`/`src.executors.bybit`
> import、`IS_REVIEW_CHAIN_SUFFIX=False` + `IMPLEMENTATION_PATH_PHASE` literal 同時存在）、
> BL source 同時 import BH/BI/BJ/BK 四個上游 module（無平行實作）、cross-module
> `src.executors.bybit` 未被載入 + BK 在 BL 之下仍 `all_passed=True`、4 個檔案寫入 +
> JSON round-trip + Markdown 含 "TASK-014BL"/"tiny_order_preparation"/"NOT_SENT_PREPARED_ONLY_NOT_EXECUTED"/
> target_future_task/"PREPARATION ONLY"、`DEFAULT_OUTPUT_DIR` 與 `REPORT_NAME` 與 contract 一致、
> BH chain-break suffix guard 在 BL 之下對 3 個 forbidden suffix 都 raise、BH guard 接受
> BL 自身 NEXT_REQUIRED_TASK）。Module 不 import 任何 network library、不讀 env、
> 不 reference BybitExecutor、不定義任何 send 方法、不開 socket、不呼叫任何 endpoint；
> 只在記憶體裡呼叫 BK 的 `run_final_pre_execution_checklist`、BJ 的 `integrate_demo_only_tiny_request`
> 並寫 JSON/Markdown 報告到 outputs/。packet 明文 `packet_is_not_execution_authorization=True`，
> 在程式邏輯上 machine-checkable。下一棒
> `TASK-014BM_explicit_demo_only_tiny_order_execution`（**implementation path 下一步；
> 不是 review-chain 後綴**；屬於 explicit demo-only tiny order execution 範疇；
> 需 Rick 在 NEXT_ACTION.md 另行授權 + manual authorization 才會啟動）。仍無 sender、
> 無 real execution adapter、無 endpoint call、無 secret 讀取、無 G20 lift、無 position 修改。
> main.py / src/risk.py / BybitExecutor 仍未動。
>
> （下方 BK 區塊保留為前一棒的 final pre-execution checklist 完成紀錄。）

> **TASK-014BK 把 BH/BI/BJ 三層 safety proofs 匯總成一份 final pre-execution checklist**。
> 新增 BK 三件套：
> [`src/demo_only_tiny_execution_adapter_final_pre_execution_checklist.py`](src/demo_only_tiny_execution_adapter_final_pre_execution_checklist.py)
> （提供 `run_final_pre_execution_checklist()` 唯一聚合入口；module import 時呼叫
> `bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)` 守住下一棒；
> `ChecklistItem` / `ChecklistReport` 兩個 frozen dataclass；36 個 invariant
> 分散在 `identity` / `bh_runtime` / `bj_runtime` / `static_source` / `cross_module`
> 五個 category：BK chain-break 三檢（BK NEXT 不為 review-chain 後綴 + BH→BI→BJ→BK
> pointer 鏈完整 + BH guard 拒絕 3 個 forbidden suffix），BH runtime 七檢
> （ALLOWED_SYMBOL=SOLUSDT、PROTECTED_SYMBOLS={ENAUSDT,TIAUSDT,AIXBTUSDT,POLYXUSDT,EDUUSDT}、
> LIVE_ENDPOINT_DENYLIST 涵蓋 4 條 live host、ALLOWED_ENVIRONMENT=bybit_demo、tiny
> caps 5 USDT/0.05 SOL、BH NOT_SENT marker、BJ NOT_SENT marker、BJ GUARD_STEPS
> 8-step canonical 集合），BI/BJ aggregate 三檢（BI `run_dry_run` `all_match_expectation=True`、
> BJ `run_integration_dry_run` `all_match_expectation=True`、happy-path BJ payload audit
> 同時帶 BH+BJ NOT_SENT markers + `_demo_only_bj_endpoint_target_validated=True`
> + `_demo_only_bj_integration_contract_version`），BH/BI/BJ 各 6 項 tokenize+ast
> static-source invariants（無 network library import、無 `getenv`/`environ`/`load_dotenv`
> token、無 `def send`/`.send(`/`place_order`/`post_order`/`submit_order` surface、
> 無 `main`/`src.risk` import、無 `src.executors.bybit` import、`IS_REVIEW_CHAIN_SUFFIX=False`
> 與 `IMPLEMENTATION_PATH_PHASE` literal 同時存在），BI/BJ 兩項 `from src import ... as bh`
> 直接消費 BH 結構驗證，cross-module 兩項（sys.modules 無 BybitExecutor 模組 + BH/BI/BJ
> 不 transitively import main/src.risk）；`write_report` 輸出 JSON+Markdown 到
> `outputs/demo_trading/demo_only_tiny_execution_adapter_final_pre_execution_checklist/`
> （`latest_*.{json,md}` + 時間戳 `*_<UTC_TS>.{json,md}`）；chain-break markers
> `TASK_ID="TASK-014BK"`、`IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-FINAL-PRE-EXECUTION-CHECKLIST"`、
> `IMPLEMENTATION_PATH_PHASE="final_pre_execution_checklist"`、
> `IS_REVIEW_CHAIN_SUFFIX=False`、`UPSTREAM_TASKS=("TASK-014BH","TASK-014BI","TASK-014BJ")`、
> `NEXT_REQUIRED_TASK="TASK-014BL_demo_only_tiny_order_preparation"`、
> `CHECKLIST_CONTRACT_VERSION="demo_only_tiny_execution_adapter_final_pre_execution_checklist_v1"`），
> [`scripts/preview_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py`](scripts/preview_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py)
> （CLI `--write-report` / `--output-dir` / `--print-items`；exit 0 iff `all_passed=True`，
> 否則 exit 1），
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py)
> （Stage 1 focused-core **31 tests**：identity / chain-break markers / BK pointer
> 不是 review-chain 後綴且明確指向 `demo_only_tiny_order` / `CHECKLIST_CONTRACT_VERSION`
> / `REPORT_NAME` 與 `DEFAULT_OUTPUT_DIR` / `FORBIDDEN_REVIEW_CHAIN_SUFFIXES` 與 BH
> 一致、aggregate `run_final_pre_execution_checklist` `all_passed=True` + 36 個 item
> 全 pass + 五大 category 全覆蓋 / BI+BJ aggregate counts 與 BI default_cases+LIVE_ENDPOINT_CASES
> 及 BJ default_integration_cases 數量一致、`ChecklistItem`/`ChecklistReport` frozen
> 不可變、static-source helper 對 synthetic `import requests` / `os.getenv` /
> `def place_order` 三個負控制 module 都正確 fail、BK 自身 source 通過 6 項 static-source
> 檢查（no network、no secret、no send/post/submit、no main/src.risk、no BybitExecutor、
> 無語意違規）、BH 4 個檔案寫入 + JSON round-trip + Markdown 含 NOT_SENT markers
> 與 chain-break literals、BH `assert_next_task_is_not_review_chain_suffix` 對 3 個
> forbidden suffix 都 raise、`BJ.GUARD_STEPS` 嚴格等於 8-step canonical tuple、
> happy-path BJ payload audit 同時帶 BH+BJ NOT_SENT markers + endpoint_target_validated
> + integration_contract_version）。Module 不 import 任何 network library、不讀 env、
> 不 reference BybitExecutor、不定義任何 send 方法、不開 socket、不呼叫任何 endpoint；
> 只在記憶體裡呼叫 BH 的 pure guard 函式 + BI 的 `run_dry_run` + BJ 的
> `run_integration_dry_run` 並寫 JSON/Markdown 報告到 outputs/。下一棒
> `TASK-014BL_demo_only_tiny_order_preparation`（**implementation path 下一步；
> 不是 review-chain 後綴**；屬於 explicit demo-only tiny order preparation /
> authorization 範疇，BK 不直接寫任何 sender code）。仍無 sender、無 real execution
> adapter、無 endpoint call、無 secret 讀取、無 G20 lift、無 position 修改。
> main.py / src/risk.py / BybitExecutor 仍未動。
>
> （下方 BJ 區塊保留為更上一棒的 endpoint guard integration 完成紀錄。）

> **TASK-014BJ 在 BH/BI implementation path 上加 endpoint guard integration 層**。
> 新增 BJ 三件套：
> [`src/demo_only_tiny_execution_adapter_endpoint_guard_integration.py`](src/demo_only_tiny_execution_adapter_endpoint_guard_integration.py)
> （提供**單一 future-safe integration entry point**
> `integrate_demo_only_tiny_request(request)`，內部依序執行 BH 的 8 個 guard：
> `environment` → `symbol`（含 protected + SOLUSDT-only）→ `existing_positions`
> → `side` → `qty_cap` → `notional_cap`（僅在 `mark_price` 提供時）→
> `order_link_id_prefix` → `endpoint_target`（僅在 caller 傳入時，呼叫
> `bh.assert_endpoint_is_demo_only` 比對 live denylist）；frozen dataclass
> `IntegrationRequest` / `GuardDecision` / `IntegrationResult` /
> `IntegrationCase` / `IntegrationOutcome` / `IntegrationReport`；`default_integration_cases()`
> 20 個 canonical case（4 happy paths：含 demo endpoint、no endpoint、qty-cap
> edge with demo endpoint、no mark_price；16 rejections：BTCUSDT / ETHUSDT、
> 5 個 protected symbols 各一棒、protected-in-existing、bybit_live env、
> 3 個 live URL（root / order endpoint / mirror order endpoint）、live websocket、
> qty cap fail、notional cap fail、unknown side、custom order_link_id 缺前綴）；
> `integrate_demo_only_tiny_request` 內 module import 時呼叫
> `bh.assert_next_task_is_not_review_chain_suffix` 守住 `NEXT_REQUIRED_TASK`；
> built payload 在 BH audit dict 上再貼 `_demo_only_bj_audit_response_status=DEMO_ONLY_TINY_BJ_NOT_SENT`、
> `_demo_only_bj_integration_contract_version=demo_only_tiny_execution_adapter_endpoint_guard_integration_v1`、
> `_demo_only_bj_endpoint_target_validated`、`_demo_only_bj_endpoint_target`；
> `write_report` 輸出 JSON+Markdown 到
> `outputs/demo_trading/demo_only_tiny_execution_adapter_endpoint_guard_integration/`
> （`latest_*.{json,md}` + 時間戳 `*_<UTC_TS>.{json,md}`）；chain-break markers
> `TASK_ID="TASK-014BJ"`、`IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-ENDPOINT-GUARD-INTEGRATION"`、
> `IMPLEMENTATION_PATH_PHASE="endpoint_guard_integration"`、
> `IS_REVIEW_CHAIN_SUFFIX=False`、`UPSTREAM_TASK="TASK-014BI"`、
> `NEXT_REQUIRED_TASK="TASK-014BK_demo_only_tiny_execution_adapter_final_pre_execution_checklist"`、
> `GUARD_STEPS` tuple 對外公開以供未來 caller 驗證），
> [`scripts/preview_demo_only_tiny_execution_adapter_endpoint_guard_integration.py`](scripts/preview_demo_only_tiny_execution_adapter_endpoint_guard_integration.py)
> （CLI `--write-report` / `--output-dir` / `--print-payloads` / `--print-decisions`；
> exit 0 iff 全部 outcomes 與預期一致，否則 exit 1），
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_endpoint_guard_integration.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_endpoint_guard_integration.py)
> （Stage 1 focused-core **61 tests**：identity / chain-break markers / `GUARD_STEPS`
> 完整 / 20-case canonical 覆蓋 / 直接 `integrate_demo_only_tiny_request` 呼叫驗證
> 14 個 reject step + 2 個 happy path、`IntegrationRequest`/`IntegrationResult`
> frozen 不可變、`GuardIntegrationError` 繼承 BH base、aggregate `run_integration_dry_run`
> all_match=True + summary counts consistent + BH identity snapshot / 報告 4 個
> 檔案 + JSON round-trip + Markdown 內容 / tokenize+ast 8 個 static-source
> safety invariants：no network library import、no `src.executors.bybit`、no
> `getenv`/`environ`/`load_dotenv`、no `def send`/`.send(`/`place_order`/
> `post_order`/`submit_order`、no `main`/`src.risk` import、BJ 直接 import BH、
> `IMPLEMENTATION_PATH_PHASE = "endpoint_guard_integration"` 字面 literal 與
> `IS_REVIEW_CHAIN_SUFFIX = False` literal 存在、`final_pre_execution_checklist`
> literal 存在；runtime：BybitExecutor 模組未被載入、BH/BI markers 仍 intact、
> main / src.risk 未被載入）。Module 不 import 任何 network library、不讀 env、
> 不 reference BybitExecutor、不定義任何 send 方法、不開 socket、不呼叫任何
> endpoint；只在記憶體裡呼叫 BH 的 pure guard 函式並寫 JSON/Markdown 報告到
> outputs/。下一棒
> `TASK-014BK_demo_only_tiny_execution_adapter_final_pre_execution_checklist`
> （或等價 explicit demo-only tiny order preparation 變體；**不是** review-chain
> 後綴）。仍無 sender、無 real execution adapter、無 endpoint call、
> 無 secret 讀取、無 G20 lift、無 position 修改。main.py / src/risk.py /
> BybitExecutor 仍未動。
>
> （下方 BI 區塊保留為前一棒的 offline payload dry-run 完成紀錄。）

> **TASK-014BI 在 BH implementation path 上加 offline payload dry-run 層**。新增 BI 三件套：
> [`src/demo_only_tiny_execution_adapter_payload_dry_run.py`](src/demo_only_tiny_execution_adapter_payload_dry_run.py)
> （`DryRunCase` / `DryRunOutcome` / `DryRunReport` 三個 frozen dataclass；
> `default_cases()` 18 個 canonical case（4 happy paths + 14 BH guard
> rejections，涵蓋 BTCUSDT、ETHUSDT、5 個 protected symbols 各一棒、
> protected-in-existing、non-demo env、unknown side、qty 上下界、notional
> 上界、custom order_link_id 缺前綴）；`LIVE_ENDPOINT_CASES` 4 個 live URL
> denial 檢查；`run_dry_run` 直接呼叫 `bh.build_demo_only_tiny_solusdt_entry_payload`
> 與 `bh.assert_endpoint_is_demo_only`，並在 module import 時呼叫
> `bh.assert_next_task_is_not_review_chain_suffix` 守住 `NEXT_REQUIRED_TASK`；
> `write_report` 輸出 JSON+Markdown，含 `latest_*.{json,md}` 與
> 時間戳 `*_<UTC_TS>.{json,md}` 到
> `outputs/demo_trading/demo_only_tiny_execution_adapter_payload_dry_run/`；
> chain-break markers `TASK_ID="TASK-014BI"`、
> `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-PAYLOAD-DRY-RUN"`、
> `IMPLEMENTATION_PATH_PHASE="offline_payload_dry_run"`、
> `IS_REVIEW_CHAIN_SUFFIX=False`、`UPSTREAM_TASK="TASK-014BH"`、
> `NEXT_REQUIRED_TASK="TASK-014BJ_demo_only_tiny_execution_adapter_endpoint_guard_integration"`），
> [`scripts/preview_demo_only_tiny_execution_adapter_payload_dry_run.py`](scripts/preview_demo_only_tiny_execution_adapter_payload_dry_run.py)
> （CLI `--write-report` / `--output-dir` / `--print-payloads`；
> exit 0 iff 全部 outcomes 與預期一致，否則 exit 1），
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_payload_dry_run.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter_payload_dry_run.py)
> （Stage 1 focused-core **44 tests**：identity / chain-break markers /
> 18-case 覆蓋（含 BTCUSDT、ETHUSDT、5 個 protected symbols
> 各一 parametrize）/ 4 live-endpoint denial / `run_dry_run` happy path /
> 報告 4 檔案 + JSON round-trip + Markdown 內容 / tokenize+ast 靜態檢查
> 6 個 safety invariants + BI 直接 import BH / 運行時 BybitExecutor 模組未被載入 /
> `IMPLEMENTATION_PATH_PHASE = "offline_payload_dry_run"` 與 `IS_REVIEW_CHAIN_SUFFIX = False`
> 字面 literal 存在）。Module 不 import 任何 network library、不讀 env、
> 不 reference BybitExecutor、不定義任何 send 方法、不開 socket、
> 不呼叫任何 endpoint；只在記憶體裡呼叫 BH 的 pure 函式並寫 JSON/Markdown
> 報告到 outputs/。下一棒
> `TASK-014BJ_demo_only_tiny_execution_adapter_endpoint_guard_integration`
> （或等價 final demo-only pre-execution checklist 變體；**不是** review-chain
> 後綴）。仍無 sender、無 real execution adapter、無 endpoint call、
> 無 secret 讀取、無 G20 lift、無 position 修改。main.py / src/risk.py /
> BybitExecutor 仍未動。
>
> （下方 BH 區塊保留為前一棒的 implementation-path scaffold 完成紀錄。）

> **TASK-014BH 中斷 review chain，開始 demo-only tiny execution adapter
> implementation path**。新增 BH 三件套：
> [`src/demo_only_tiny_execution_adapter.py`](src/demo_only_tiny_execution_adapter.py)
> （strict immutable constants：`ALLOWED_ENVIRONMENT="bybit_demo"`、
> `ALLOWED_SYMBOL="SOLUSDT"`、`PROTECTED_SYMBOLS={ENAUSDT,TIAUSDT,AIXBTUSDT,POLYXUSDT,EDUUSDT}`、
> `TINY_SIZE_CAP_USDT=5`、`TINY_QTY_CAP_SOL=0.05`、
> `LIVE_ENDPOINT_DENYLIST` 含 `api.bybit.com` / `api.bytick.com` /
> `stream.bybit.com` / `stream.bytick.com`、demo-endpoint documented-only
> 集合；pure offline `build_demo_only_tiny_solusdt_entry_payload` 回傳
> frozen `DemoOnlyTinyEntryPayload`，提供 `to_exchange_payload` /
> `to_audit_dict`；guard helpers 拒絕 non-SOL symbol / protected symbol /
> protected position in existing scope / non-demo environment / unknown
> side / qty > 0.05 SOL / qty <= 0 / notional > 5 USDT / live endpoint /
> custom order_link_id 缺前綴 / next-task 含 review-chain 後綴；
> chain-break markers `TASK_ID="TASK-014BH"`、
> `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-IMPLEMENTATION-PATH-SCAFFOLD"`、
> `IS_REVIEW_CHAIN_SUFFIX=False`、
> `CLOSES_DISABLED_REVIEW_CHAIN_UPSTREAM_TASK="TASK-014BG"`、
> `NEXT_REQUIRED_TASK="TASK-014BI_demo_only_tiny_execution_adapter_payload_dry_run"`），
> [`scripts/preview_demo_only_tiny_execution_adapter.py`](scripts/preview_demo_only_tiny_execution_adapter.py)
> （offline preview CLI；exit 0 on payload-built、exit 1 on rejection），
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter.py`](tests/demo_trading/test_demo_only_tiny_execution_adapter.py)
> （Stage 1 focused-core **45 tests**，含 identity / 12 個 guard rejection / 6 個
> static-source safety invariants（tokenize+ast：no network import、no
> BybitExecutor import、no getenv/environ/load_dotenv、no live host
> outside string literals、no `def send`/`.send(`/`place_order`/
> `post_order`/`submit_order`、no `main`/`src.risk` import、
> `IS_REVIEW_CHAIN_SUFFIX = False` literal present）+ runtime
> invariants）。Module 不 import 任何 network library、不讀任何 env var、
> 不 reference `BybitExecutor`、不定義 `send`/`place_order`/`post_order`/
> `submit_order`、不開 socket、不呼叫任何 endpoint。下一棒
> `TASK-014BI_demo_only_tiny_execution_adapter_payload_dry_run`（offline
> payload dry-run，**不是** review-chain 後綴；亦可改為 endpoint guard
> integration 變體）。仍無 sender、無 real execution adapter、無 endpoint
> call、無 secret 讀取、無 G20 lift、無 position 修改。
> main.py / src/risk.py / BybitExecutor 仍未動。
>
> （下方 BG 區塊保留為前一棒的 chain-closing dry-run 完成紀錄。）

> TASK-014BG 新增 guarded entry real execution adapter disabled implementation
> scaffold manual authorization gate final pre-execution review manual authorization
> review final pre-execution review manual authorization review **dry-run**（**chain-closing**）階段
> （TASK-014BF manual-authorization-review final-pre-execution-review manual-authorization-review
> 之後的下一棒、仍非實作或執行；同時是封閉 disabled review chain 的結尾棒）。
> 新增 BG src/scripts/test 三件套：src 含 37 個 hard-fail gate
> （Group A 18 個 BF upstream + Group B 7 個 scope_summary 內容（含 AV guard）
> + Group C 3 個 BF 失敗 passthrough + Group D 9 個 BG 自體 source 安全 invariants），
> dataclass 92 欄位含 17 個 BF upstream 欄位 + 11 個 BF→BE chained proof 欄位
> （短前綴 `bf_chained_be_*` / `bf_scope_summary_*`）+ 3 個 chain-closure boolean
> （`closes_disabled_review_chain=True`、
> `prepares_demo_only_tiny_execution_adapter_implementation_path=True`、
> `spawns_additional_review_chain_suffix=False`）+ 完整 safety invariant 欄位，
> BF artifact loader/parser 與 run 函式以 BF manual-authorization-review
> **final-pre-execution-review manual-authorization-review** JSON 為 direct upstream
> （BE final pre-execution review、BD readiness-review、BC dry-run、BB manual-
> authorization-review、BA final-pre-execution-review、AZ readiness-review 與
> AY/AX/AW/AV/AU/AT/AS/AR/AQ 全部以 BF-proven chained proof 形式被引用，
> BG 不直接消費它們）。scripts 提供 CLI 入口、
> `--from-latest-entry-...-manual-authorization-review-final-pre-execution-review-manual-authorization-review` 旗標、
> `--allow-...-manual-authorization-review-dry-run`（即使加旗標 conclusion 仍鎖死在
> `..._MANUAL_AUTHORIZATION_REVIEW_DRY_RUN_READY_NOT_EXECUTABLE`）、`--allow-real-entry-execution`（仍回
> `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED`），與 `--write-report` JSON+Markdown 報告生成。
> 測試含 Stage 1 focused-core 23 tests
> （identity / scope_summary / 37 gate / AV guard / chain-closure booleans / default
> dataclass safety / BF loader / artifact missing FAIL_CLOSED / status FAIL_CLOSED
> passthrough / mode / next_required_task / real_execution_allowed / send_allowed /
> scope missing BE direct / scope has BF-consumes-BB / scope has BF-consumes-AV /
> --allow flags / to_dict round-trip / BF→BE chained proof exposure）。IDENTITY_STRICT =
> `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-DRY-RUN-ONLY`，
> NEXT_REQUIRED_TASK =
> `TASK-014BH_demo_only_tiny_execution_adapter_implementation_path`（**chain-closing
> — 不再 spawn 新的 readiness_review / final_pre_execution_review /
> manual_authorization_review 後綴**）。
> BF 從不被描述為 readiness review 或 dry-run；BF 才是 final pre-execution review
> manual authorization review 階段，BG 才是 chain-closing dry-run 階段。
> 仍無 sender、無 real execution adapter、無 endpoint call、無 secret 讀取、無 G20 lift、無 position 修改。
> main.py / src/risk.py / BybitExecutor 仍未動。

| 欄位 | 值 |
|---|---|
| latest_completed_task | TASK-014BM |
| latest_commit | pending local — `TASK-014BM: add demo-only tiny execution adapter explicit tiny order execution path (offline default; double-flag gate; consumes BH+BI+BJ+BK+BL; sends at most one Bybit Demo SOLUSDT order when creds present)`（local only；尚未推遠端） |
| current_phase | demo-only tiny execution adapter **explicit tiny order execution path completed (offline default)** — **TASK-014BM**；新增 BM 三件套（src 含 `DemoCredentials` / `ExecutionGate` / `ExecutionPlan` / `SendOutcome` / `ExecutionReport` 五個 frozen dataclass + 唯一聚合入口 `run_explicit_tiny_order_execution()` + 直接 `build_execution_plan()` / `_send_one_demo_order()` 內部 helper + `write_report` JSON+Markdown 報告寫入；module import 時呼叫 `bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)` 守住下一棒；流程：BL preparation → demo-scoped credential 讀取（找不到→safe `MISSING_DEMO_CREDENTIALS` 不失敗、不 fallback 讀 live 名稱）→ 評估 **16 個 gate**（13 個 pre-network + 3 個 execute）→ 任一 pre-network gate 失敗即 `GATE_REJECTED_NO_NETWORK` 且 sender 絕不呼叫 → 三 mode 設計：`dry_run` / `readiness` 永遠 offline、`execute_demo_order` **必須** 同時帶 `--execute-demo-order` + `--i-understand-this-sends-one-bybit-demo-order` 雙旗標 + creds present + 16 gate 全 pass 才透過 sender injection 點呼叫 stdlib `urllib.request` POST 一次到 `https://api-demo.bybit.com/v5/order/create`，使用 Bybit V5 HMAC-SHA256 簽名 + 標準 `X-BAPI-API-KEY` / `X-BAPI-TIMESTAMP` / `X-BAPI-SIGN` / `X-BAPI-RECV-WINDOW` headers，body 只含 9 欄位（`category` / `symbol` / `side` / `orderType` / `qty` / `timeInForce` / `reduceOnly` / `closeOnTrigger` / `orderLinkId`，**無 stopLoss/takeProfit/trading-stop 欄位**），`MAX_ORDER_COUNT=1`，無 retry、無 scheduler；scripts CLI 預設 `--mode readiness`，需 `--mode execute_demo_order` + 雙旗標才會送單，`--write-report` / `--output-dir` / `--endpoint-target`，exit 0=DRY_RUN_OK/READINESS_OK/EXECUTED_DEMO_ONLY、2=MISSING_DEMO_CREDENTIALS、1=其他；tests Stage 1 focused-core **69** tests，含 identity / chain-break markers / BM pointer 指向 `TASK-014BN_demo_only_tiny_execution_postfill_audit`（**不是** review-chain 後綴）/ `EXECUTION_CONTRACT_VERSION` / 16 個 gate 名稱與順序 / 預設 dry_run 無 network / readiness 通過 13 個 pre-network gate / execute mode 無旗標→GATE_REJECTED / 雙旗標但無 creds→MISSING_DEMO_CREDENTIALS / 雙旗標+creds+fake sender→EXECUTED_DEMO_ONLY 且 sender 僅被呼叫一次（counter 驗證）+ 擷取 `bybit_order_id` / network error → NETWORK_ERROR_DEMO_ONLY / pre-network reject 路徑（3 live URL、3 non-SOLUSDT、5 protected symbol、5 protected existing position、4 qty 超 cap、reduceOnly=True、packet 缺失、BH audit marker 竄改、`packet_is_not_execution_authorization` 竄改）均 parametrize 驗證 sender 絕不被呼叫 / credential 載入只讀 DEMO_-prefixed env / `_real_sender_via_urllib` 對 non-demo URL hard-raise / `ExecutionPlan` / `ExecutionReport` frozen / AST-based static-source 檢查不 import network library（`requests` / `pybit` / `aiohttp` / `httpx`）/ 不 import `main` / `src.risk` / `src.executors.bybit` / `BybitExecutor` Name/Attribute / docstring 剝除後也不引用 LIVE env 名稱、無 set-trading-stop / stopLoss / takeProfit / retry / scheduler token / BM source 同時 import BH/BI/BJ/BK/BL 五個上游 module（無平行實作）/ BH guard 接受 BM `NEXT_REQUIRED_TASK` + 拒絕 3 forbidden suffix / BK checklist 與 BL preparation 在 BM 之下仍 `all_passed=True` / cross-module `BybitExecutor`/`main`/`src.risk` 未載入 / 4 報告檔寫入 + JSON round-trip + Markdown 含 `TASK-014BM` / `tiny_order_execution` / `READINESS_OK_NO_NETWORK` / `max_order_count` 等明文 / body preview 形狀只有 9 欄位 / 簽名 request headers 含 V5 envelope 且 `X-BAPI-SIGN` 為 64-char hex SHA-256）。BM 直接消費 BH/BI/BJ/BK/BL — sender 採 dependency-injection 模式（測試覆寫成 fake sender；real sender 內 hard-assert URL）；module 不開 socket、不讀 live secret、不修改 position；最多送一次 demo POST |
| next_required_task | `TASK-014BN_demo_only_tiny_execution_postfill_audit`（**implementation path 下一步；不是 review-chain 後綴**；屬於 demo-only tiny execution postfill audit 範疇；需 Rick 在 NEXT_ACTION.md 顯式授權才會啟動；BM 本身只負責「送一單 demo」這一步，不包含 postfill audit / 對帳 / 倉位 reconcile） |
| real_execution_allowed | **False** |
| actual tiny entry | **FORBIDDEN** |
| actual stop attach | **FORBIDDEN** |
| actual cleanup | **FORBIDDEN** |
| actual runner execution | **FORBIDDEN** |
| live trading | **FORBIDDEN** |
| G20 sender policy | **still active**（無 sender adapter，無 `/v5/order/create`，無 `/v5/position/trading-stop` 真實呼叫） |
| latest validation | `py_compile` BM src + preview + tests → PASS；BM Stage 1 focused-core suite **69 PASS**；BH+BI+BJ+BK+BL regression **228 PASS**（45 + 44 + 61 + 31 + 47）；BH+BI+BJ+BK+BL+BM 安全鏈 **297 PASS**；`pytest tests/demo_trading/ --ignore=test_demo_emergency_close_sender.py --basetemp=.pytest_basetemp` → **7998 PASS**（= BL baseline 7871 + BM stage1 69 + 既有環境差異 58；emergency_close_sender 既有失敗排除）；廣域 `pytest --basetemp=.pytest_basetemp` → 8313 PASS（18 failures + 21 errors 全部與 BH/BI/BJ/BK/BL/BM 安全鏈無關，均為既有 forward_record/* 與 apps/monitor/safety.py SyntaxError）；BM preview smoke `--mode readiness --write-report` exit 0；report `final_status=READINESS_OK_NO_NETWORK`、`network_attempted=False`、`order_endpoint_called=False`、`order_sent=False`、`max_order_count=1`、`bl_packet_loaded=True`、`bl_packet_all_passed=True`、`packet_is_not_execution_authorization=True`、`packet_audit_response_status='NOT_SENT_PREPARED_ONLY_NOT_EXECUTED'`、`live_endpoint_denied=True`、`protected_symbols_untouched=True`、`all_pre_network_gates_passed=True`；execute mode 雙旗標 + fake sender 模擬下 `final_status=EXECUTED_DEMO_ONLY`、`order_sent=True`、sender 計數=1；4 個報告檔寫入 `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_execution/`（latest JSON+MD + 時間戳 JSON+MD） |
| protected positions（never touched） | ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT |
| adapter identity (BH upstream) | `IDENTITY=DEMO-ONLY-TINY-EXECUTION-ADAPTER-IMPLEMENTATION-PATH-SCAFFOLD`、`ADAPTER_CONTRACT_VERSION=demo_only_tiny_execution_adapter_implementation_path_scaffold_v1`（BL 透過 BJ→BH chain 間接消費 BH 的 pure guard 函式，沒有平行實作；BH module 仍不定義 `send` / `place_order` / `post_order` / `submit_order`，仍不 import `BybitExecutor` 或任何 network library） |
| BI identity (BL upstream) | `IDENTITY=DEMO-ONLY-TINY-EXECUTION-ADAPTER-PAYLOAD-DRY-RUN`、`IMPLEMENTATION_PATH_PHASE=offline_payload_dry_run`、`IS_REVIEW_CHAIN_SUFFIX=False`、`UPSTREAM_TASK=TASK-014BH` |
| BJ identity (BL upstream) | `IDENTITY=DEMO-ONLY-TINY-EXECUTION-ADAPTER-ENDPOINT-GUARD-INTEGRATION`、`IMPLEMENTATION_PATH_PHASE=endpoint_guard_integration`、`IS_REVIEW_CHAIN_SUFFIX=False`、`UPSTREAM_TASK=TASK-014BI`、`INTEGRATION_CONTRACT_VERSION=demo_only_tiny_execution_adapter_endpoint_guard_integration_v1`、`GUARD_STEPS=(environment, symbol, existing_positions, side, qty_cap, notional_cap, order_link_id_prefix, endpoint_target)` |
| BK identity (BL upstream) | `IDENTITY=DEMO-ONLY-TINY-EXECUTION-ADAPTER-FINAL-PRE-EXECUTION-CHECKLIST`、`IMPLEMENTATION_PATH_PHASE=final_pre_execution_checklist`、`IS_REVIEW_CHAIN_SUFFIX=False`、`UPSTREAM_TASKS=(TASK-014BH, TASK-014BI, TASK-014BJ)`、`CHECKLIST_CONTRACT_VERSION=demo_only_tiny_execution_adapter_final_pre_execution_checklist_v1` |
| BL identity (BM upstream) | `IDENTITY=DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-PREPARATION`、`IMPLEMENTATION_PATH_PHASE=tiny_order_preparation`、`IS_REVIEW_CHAIN_SUFFIX=False`、`UPSTREAM_TASKS=(TASK-014BH, TASK-014BI, TASK-014BJ, TASK-014BK)`、`PREPARATION_CONTRACT_VERSION=demo_only_tiny_execution_adapter_tiny_order_preparation_v1` |
| BM identity | `IDENTITY=DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-EXECUTION`、`IMPLEMENTATION_PATH_PHASE=tiny_order_execution`、`IS_REVIEW_CHAIN_SUFFIX=False`、`UPSTREAM_TASKS=(TASK-014BH, TASK-014BI, TASK-014BJ, TASK-014BK, TASK-014BL)`、`EXECUTION_CONTRACT_VERSION=demo_only_tiny_execution_adapter_tiny_order_execution_v1`、`NEXT_REQUIRED_TASK=TASK-014BN_demo_only_tiny_execution_postfill_audit`、`ALLOWED_DEMO_ENDPOINT_URL=https://api-demo.bybit.com/v5/order/create`、`MAX_ORDER_COUNT=1`、`DEMO_API_KEY_ENV=BYBIT_DEMO_API_KEY`、`DEMO_API_SECRET_ENV=BYBIT_DEMO_API_SECRET`（下一步指向 demo-only tiny execution postfill audit，**不是** review-chain 後綴；demo creds 名稱與 live 嚴格隔離） |
| order link id prefix | `DEMO_ONLY_TINY_BH_`（offline payload label；BM execute mode 送單時沿用作為 Bybit Demo orderLinkId） |
| audit response_status | `DEMO_ONLY_TINY_BH_NOT_SENT` + BJ 額外貼 `DEMO_ONLY_TINY_BJ_NOT_SENT` + BL 額外貼 `NOT_SENT_PREPARED_ONLY_NOT_EXECUTED`；BM 額外標記 `final_status` 六態之一（`DRY_RUN_OK_NO_NETWORK` / `READINESS_OK_NO_NETWORK` / `GATE_REJECTED_NO_NETWORK` / `MISSING_DEMO_CREDENTIALS` / `EXECUTED_DEMO_ONLY` / `NETWORK_ERROR_DEMO_ONLY`） |
| BM execution gates | 13 個 pre-network + 3 個 execute = 16 個（固定順序：`bl_packet_loaded` / `bl_packet_all_passed` / `packet_marked_not_execution_authorization` / `packet_audit_status_from_bh` / `environment_is_bybit_demo` / `symbol_is_solusdt` / `qty_within_tiny_cap` / `order_type_market` / `time_in_force_ioc` / `reduce_only_false` / `endpoint_target_demo_only` / `protected_symbols_not_in_scope` / `order_count_locked_to_one` / `explicit_execute_flag` / `explicit_confirm_flag` / `demo_credentials_present`） |
| BM execute confirm flags | 必須同時帶 `--execute-demo-order` + `--i-understand-this-sends-one-bybit-demo-order` 兩個旗標（缺一即 `GATE_REJECTED_NO_NETWORK`，sender 絕不被呼叫） |
| BM demo credentials | 只讀 `BYBIT_DEMO_API_KEY` / `BYBIT_DEMO_API_SECRET` / `BYBIT_DEMO_RECV_WINDOW`（從不 fallback 到 live 名稱；缺值→`MISSING_DEMO_CREDENTIALS` 安全報告） |
| BM report output dir | `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_execution/`（含 `latest_*.json` / `latest_*.md` / 時間戳 `*_<UTC_TS>.{json,md}`；已加入 .gitignore，不入 repo） |
| BL report output dir | `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_preparation/`（含 `latest_*.json` / `latest_*.md` / 時間戳 `*_<UTC_TS>.{json,md}`；已加入 .gitignore，不入 repo） |
| implementation_path_phase | `tiny_order_execution`（BM；上游 BL 為 `tiny_order_preparation`、BK 為 `final_pre_execution_checklist`、BJ 為 `endpoint_guard_integration`、BI 為 `offline_payload_dry_run`、BH 為 `scaffold`；下一步 `TASK-014BN_demo_only_tiny_execution_postfill_audit`，**不是** review-chain 後綴；real execution 仍 disabled，需 Rick 在 NEXT_ACTION.md 另行授權才能繼續 BN） |
| main.py / src/risk.py / BybitExecutor | untouched |

### TASK-014BL 完成記錄（archived 2026-06-18 by TASK-014BM）

TASK-014BL 已於 2026-06-18 完成（local commit pending — `TASK-014BL: add demo-only tiny execution adapter tiny order preparation packet (offline; consumes BH+BI+BJ+BK; emits JSON+MD report; NOT execution authorization)`）：新增 BL 三件套
（src 含 `PreparationPacket` / `PreparationReport` 兩個 frozen dataclass + 單一聚合入口 `run_tiny_order_preparation()`
+ 直接 `build_preparation_packet()` entry + `write_report` JSON+Markdown 報告寫入；
scripts CLI `--write-report` / `--output-dir` / `--symbol` / `--side` / `--qty` / `--mark-price`，
exit 0 iff `all_passed=True`；tests Stage 1 focused-core 47 tests）。BM 直接 import BL 並呼叫
`run_tiny_order_preparation()` 取得 `PreparationPacket` 作為 16-gate 評估的第一手輸入，
驗證 `packet_is_not_execution_authorization=True` 仍機器可檢查。
仍無 sender、無 real execution adapter、無 endpoint call、無 secret 讀取、無 G20 lift、無 position 修改。
main.py / src/risk.py / BybitExecutor 未動。

### TASK-014BK 完成記錄（archived 2026-06-18 by TASK-014BL）

TASK-014BK 已於 2026-06-18 完成（local commit `fcc3425 TASK-014BK: add demo-only tiny execution adapter final pre-execution checklist (offline; aggregates BH+BI+BJ; emits JSON+MD report)`）：新增 BK 三件套
（src 含 `ChecklistItem` / `ChecklistReport` 兩個 frozen dataclass + 單一聚合入口 `run_final_pre_execution_checklist()`
+ 36 個 invariant 跨 `identity` / `bh_runtime` / `bj_runtime` / `static_source` / `cross_module` 五大 category
+ `write_report` JSON+Markdown 報告寫入；scripts CLI `--write-report` / `--output-dir` / `--print-items`，
exit 0 iff `all_passed=True`；tests Stage 1 focused-core 31 tests）。BL 直接 import BK 並呼叫
`run_final_pre_execution_checklist()` 確認 `all_passed=True` 後才允許產生 PreparationPacket。
仍無 sender、無 real execution adapter、無 endpoint call、無 secret 讀取、無 G20 lift、無 position 修改。
main.py / src/risk.py / BybitExecutor 未動。

### TASK-014BJ 完成記錄（archived 2026-06-18 by TASK-014BK）

TASK-014BJ 已於 2026-06-18 完成（local commit `3752158 TASK-014BJ: ...`）：新增 BJ 三件套
（src 含單一 future-safe `integrate_demo_only_tiny_request` entry point 串接 BH 8 個 guard step +
6 個 frozen dataclass + 20-case canonical 表 + `run_integration_dry_run` + `write_report`；
scripts CLI；tests Stage 1 focused-core 61 tests）。BK 直接 import BJ markers 確認 chain-break，
透過 `run_integration_dry_run` 驗證 `all_match_expectation=True`，並透過 happy-path BJ payload
audit 驗證 BH+BJ NOT_SENT markers 共存。仍無 sender、無 real execution adapter、無 endpoint
call、無 secret 讀取、無 G20 lift、無 position 修改。main.py / src/risk.py / BybitExecutor 未動。

### TASK-014BI 完成記錄（archived 2026-06-18 by TASK-014BJ）

TASK-014BI 已於 2026-06-18 完成（local commit `d6d028c TASK-014BI: ...`）：新增 BI 三件套
（src 含 `DryRunCase` / `DryRunOutcome` / `DryRunReport` 三個 frozen dataclass + 18-case
canonical 表 + 4 live-endpoint denial 檢查 + `run_dry_run` + `write_report`；scripts CLI；
tests Stage 1 focused-core 44 tests）。BJ 直接 import BI markers 確認 chain-break，並再次 import
BH module（單一上游）。仍無 sender、無 real execution adapter、無 endpoint call、
無 secret 讀取、無 G20 lift、無 position 修改。main.py / src/risk.py / BybitExecutor 未動。

### TASK-014BH 完成記錄（archived 2026-06-18 by TASK-014BI）

TASK-014BH 已於 2026-06-18 完成（local commit `5abe3b9 TASK-014BH: ...`）：新增 BH 三件套
（src 含 strict immutable constants + pure offline `build_demo_only_tiny_solusdt_entry_payload`
+ frozen `DemoOnlyTinyEntryPayload` + 8 個 guard helpers + chain-break markers；
scripts 提供 offline preview CLI；tests Stage 1 focused-core 45 tests）。
**中斷 review chain**，切換到 implementation path；BI 直接 import 並消費此 module。
仍無 sender、無 real execution adapter、無 endpoint call、無 secret 讀取、無 G20 lift、
無 position 修改。main.py / src/risk.py / BybitExecutor 未動。

### TASK-014BG 完成記錄（archived 2026-06-18 by TASK-014BH）

TASK-014BG 已於 2026-06-18 完成（local commit `fd04ecc TASK-014BG: ...`）：新增 BG src/scripts/test
三件套（src 37 hard-fail gate + 92-field dataclass（含 3 個 chain-closure booleans）+ run +
write_report；scripts CLI；tests Stage 1 focused-core 23 tests），以 BF manual-authorization-review
**final-pre-execution-review manual-authorization-review** 為 direct upstream（BE/BD/BC/BB/BA/AZ/AY/AX/AW/AV/AU/AT/AS/AR/AQ 全部以 BF-proven chained proof 形式被引用，BG 不直接消費它們）。
這是 disabled-implementation-scaffold review chain 的**封閉棒**；下一步由 TASK-014BH 切換到
implementation path。仍無 sender、無 real execution adapter、無 endpoint call、無 secret
讀取、無 G20 lift、無 position 修改。main.py / src/risk.py / BybitExecutor 未動。

### TASK-014BF 完成記錄（archived 2026-06-18 by TASK-014BG）

TASK-014BF 已於 2026-06-18 完成（local commit `75ad274 TASK-014BF: ...`）：新增 BF src/scripts/test
三件套（src 37 hard-fail gate + ~92-field dataclass + run + write_report；scripts CLI；
tests Stage 1 focused-core 23 + Stage 3 完整 124 tests）；以 BE final-pre-execution-review
manual-authorization-review 為 direct upstream，BD/BC/BB/BA/AZ/AY/AX/AW/AV/AU/AT/AS/AR/AQ
全部以 BE-proven chained proof 形式被引用，BF 不直接消費它們。仍無 sender、無 real
execution adapter、無 endpoint call、無 secret 讀取、無 G20 lift、無 position 修改。
main.py / src/risk.py / BybitExecutor 未動。

### TASK-014BE 完成記錄（archived 2026-06-18 by TASK-014BF）

TASK-014BE 已於 2026-06-18 完成（local commit `38aca4b TASK-014BE: ...`）：新增 BE src/scripts/test
三件套（src 37 hard-fail gate + ~52-field dataclass + run + write_report；scripts CLI；
tests Stage 1 focused-core 23 + Stage 3 完整 119 tests）；以 BD manual-authorization-review
readiness-review 為 direct upstream，BC/BB/BA/AZ/AY/AX/AW/AV/AU/AT/AS/AR/AQ 全部以 BD-proven
chained proof 形式被引用，BE 不直接消費它們。仍無 sender、無 real execution
adapter、無 endpoint call、無 secret 讀取、無 G20 lift、無 position 修改。
main.py / src/risk.py / BybitExecutor 未動。

### TASK-014BD 完成記錄（archived 2026-06-18 by TASK-014BE）

TASK-014BD 已於 2026-06-17 完成（local commits `a18357e TASK-014BD: ...` + `TASK-014BD-FIX1: harden readiness review upstream scope AV guard`）：新增 BD src/scripts/test
三件套（src 37 hard-fail gate + ~52-field dataclass + run + write_report；scripts CLI；
tests Stage 1 focused-core 17 + Stage 3 完整 112 tests）；以 BC manual-authorization-review
dry-run 為 direct upstream，BB/BA/AZ/AY/AX/AW/AV/AU/AT/AS/AR/AQ 全部以 BC-proven
chained proof 形式被引用，BD 不直接消費它們。仍無 sender、無 real execution
adapter、無 endpoint call、無 secret 讀取、無 G20 lift、無 position 修改。
main.py / src/risk.py / BybitExecutor 未動。

### TASK-014BB 完成記錄（archived 2026-06-17 by TASK-014BC）

TASK-014BB 已於 2026-06-17 完成（commit `c37c401`，local only）：新增 BB src/scripts/test
三件套（src 36 hard-fail gate + ~52-field dataclass + run + write_report；scripts CLI；
tests Stage 1 focused-core 13 + Stage 3 完整 84 tests）；以 BA final-pre-execution-review 為
direct upstream，AZ readiness-review 與 AY/AX/AW/AV/AU/AT/AS/AR/AQ 全部以 BA-proven
chained proof 形式被引用，BB 不直接消費它們。仍無 sender、無 real execution
adapter、無 endpoint call、無 secret 讀取、無 G20 lift、無 position 修改。
main.py / src/risk.py / BybitExecutor 未動。

權威來源（authoritative pointers — 任何不一致以下列檔案為準）：

- [docs/research/commands/NEXT_ACTION.md](docs/research/commands/NEXT_ACTION.md) — 下一步 Rick action、各 TASK-014X 詳細狀態
- [docs/research/commands/COMMAND_LOG.md](docs/research/commands/COMMAND_LOG.md) — 完整 task 紀錄、驗證輸出、檔案改動

提醒（避免三方協作誤觸）：

1. 任何 dry-run adapter（AE / AF / AG / 後續 AH…）皆**不**呼叫 endpoint、**不**讀 secrets、**不**簽 HMAC。
2. `--allow-real-*-execution` 是 guard probe；source 內部一律回 `REAL_*_EXECUTION_NOT_IMPLEMENTED`，
   不會升級為 real trading。
3. 升級為 real execution 必須由 Rick 在 `NEXT_ACTION.md` 顯式授權，**不**可由 agent 自動推進。
4. `main.py` / `src/risk.py` / `BybitExecutor` / G20 sender policy 在整個 TASK-014 sequential safety chain 中持續未被修改。

---

## TASK-001 Prev3Y Crypto Baseline（2026-05-13）

本次建立獨立 Prev3Y momentum baseline pipeline，不改現有 live strategy、不加 cost / funding / slippage。

輸出檔案：

- `outputs/backtests/prev3y_crypto/20260513_baseline.csv`
- `outputs/backtests/prev3y_crypto/20260513_positions.parquet`
- `outputs/backtests/prev3y_crypto/20260513_stats.json`
- `outputs/logs/prev3y_crypto/20260513.log`
- Final non-overwriting rerun: `outputs/backtests/prev3y_crypto/20260513_run002_baseline.csv`,
  `20260513_run002_positions.parquet`, `20260513_run002_stats.json`,
  `outputs/logs/prev3y_crypto/20260513_run002.log`
- TASK-001c reporting supplement: `outputs/backtests/prev3y_crypto/20260513_run003_stats.json`
- TASK-001b benchmark supplement: `outputs/backtests/prev3y_crypto/20260513_run004_baseline.csv`,
  `20260513_run004_positions.parquet`, `20260513_run004_stats.json`,
  `outputs/logs/prev3y_crypto/20260513_run004.log`
- TASK-001d missing-data supplement: `outputs/backtests/prev3y_crypto/20260513_run007_baseline.csv`,
  `20260513_run007_positions.parquet`, `20260513_run007_stats.json`,
  `outputs/logs/prev3y_crypto/20260513_run007.log`,
  `outputs/data_quality/prev3y_crypto/20260513_run007_data_quality_summary.csv`,
  `outputs/data_quality/prev3y_crypto/20260513_run007_data_quality_aggregate.json`

關鍵結果：

| IR | Sharpe | max DD | annual turnover |
|---:|---:|---:|---:|
| -0.061757 | 0.493574 | -19.4996% | 1.228343x |

樣本與資料：

- Baseline CSV 覆蓋 `2019-01-01` 至 `2026-04-30`；warm-up 起點 `2018-01-01`。
- 本地 Bybit OHLCV coverage 從 `2020-10-21` 開始；3 年 lookback 後，第一個有效持倉日為 `2024-04-01`。
- PIT universe 來源是本機 `data/trading.db`：`prices`、`crypto_market_cap_rankings`、`crypto_bybit_linear_instruments`。
- 平均 universe size：全樣本 76.79；rebalance eligible tradable symbols 平均 15.22。
- Benchmark：TASK-001b 起 primary benchmark 為 cash；`benchmark_return = benchmark_cash_return`。
  `benchmark_eqw_return` 保留舊版 run003 的「同日 PIT universe 等權 long-only」benchmark，缺 return 的 symbol 當日剔除。
  `benchmark_btc_return` 使用 `BYBIT:BTCUSDT.P` open-to-open return；BTC 缺資料日期保留 NaN，不補 0。
- `stats.json` 可由 `baseline.csv` 重算重現，誤差小於 `1e-12`；同一 config/data snapshot 內部雙跑 stats hash 相同。

TASK-001b benchmark IR（run004）：

| benchmark | full IR | active IR |
|---|---:|---:|
| cash | 0.493574 | 0.926682 |
| BTC perp (`BYBIT:BTCUSDT.P`) | -0.324759 | -0.017486 |
| PIT equal-weight long-only | -0.061757 | 0.722657 |

Coverage：BTC return 覆蓋 `2021-03-03` 至 `2026-04-30`；full period 缺 `793` 天，active period 缺 `0` 天。Equal-weight benchmark 平均可用 symbols `76.748226`、最小 `0`、缺 benchmark symbols 天數 `660`。

TASK-001d data-quality policy：missing return 不補 0；nonpositive OHLC 不補值；不 forward fill price；volume <= 0 只記 warning；missing volume / quote_volume hard exclusion。run007 DQ 摘要：abnormal symbol-days `332`、holding exclusions `115`、ranking exclusions `0`、forced holding exits `0`；COMP-USD / ICP-USD 已標記。run007 vs run004 的 portfolio_return、exposure、turnover、positions 均相同。

重現指令：

```powershell
python scripts\validate_prev3y_crypto_inputs.py
python scripts\run_prev3y_crypto_baseline.py
```

注意：baseline runner 只接受已存在且 schema 正確的 parquet/config；缺資料時會以 `BLOCKED_BY_DATA` 停止，不會產生隨機或模擬資料。同日正式輸出檔已存在時，腳本會使用 `YYYYMMDD_run001`、`run002` 這類 stem，不會覆寫既有結果。

---

## Current Crypto Status（2026-05-08）

目前有兩套需要分清楚：

| 指令 / 策略 | 狀態 | 用途 |
|---|---|---|
| `python main.py live` | **正式預設策略** | 已切換為 `volume-top125-lb3-sym035`：前三年平均 `volume_24h` Top125 + symbol WR 0.35 |
| `python main.py live --crypto-candidate config-baseline` | **舊 baseline** | 對應曾跑出 5y full `+627%` 的 config universe 邏輯；保留作對照，不再是預設 live 策略 |
| `python main.py live --crypto-candidate volume-top125-lb3-sym035` | **顯式指定新策略** | 與預設 `python main.py live` 相同；仍需繼續 forward / demo 監控 |

重要判斷：

- `+627.44%` 5 年連續回測不是 look-ahead bug，但很可能包含 current-universe selection bias 與 path-dependency；**不可作為未來預期報酬**。
- 現有 baseline 較可信的參考仍是 Crypto-only OOS：`+87.17% / CAGR 36.49% / PF 1.346 / Sharpe 0.930 / MDD -43.01%`。
- Point-in-time-like universe 測試顯示市值 Top100 raw OOS 只剩 `+7.25% / PF 1.030 / Sharpe 0.289`，確認原 config universe 有高估疑慮。
- 目前最合理的 forward 候選是 `volume-top125-lb3-sym035`：
  - Universe：previous 3-year average `volume_24h` Top125
  - Symbol rolling winrate threshold：`0.35`
  - OOS backtest：`+99.43% / CAGR 40.86% / PF 1.291 / Sharpe 1.012 / MDD -36.57%`
  - 但 lookback 視窗仍敏感，因此雖已切成預設策略，仍必須用 forward monitor 監控是否保留。

Forward monitor:

```powershell
# 純監控，不下單
python scripts\crypto_top100_forward_monitor.py

# 透過 Main 跑候選回測
python main.py backtest --profile Crypto --crypto-candidate volume-top125-lb3-sym035 `
  --start-date 2026-05-08 --end-date YYYY-MM-DD `
  --output output\crypto_candidate_forward.xlsx --note crypto_candidate_forward

# 透過 Main 跑 Bybit Demo 正式預設策略
python main.py live --interval 15

# 若要切回舊 config baseline 對照
python main.py live --crypto-candidate config-baseline --interval 15
```

Forward gate：至少 `90` 天或 `50` 筆 forward trades，且 PF >= `1.15`、Sharpe >= `0.70`、MDD 不差於 `-40%` 才保留為正式預設；若未通過就切回舊 baseline 或進入新一輪研究。

---

## 研究紀錄與最新判決（EXP-001 ~ EXP-012）

研究文件已集中到 `docs/research/`：

- [`TEST_PLAN.md`](docs/research/TEST_PLAN.md)：接下來要做的實驗、通過標準、失敗判斷。
- [`EXPERIMENT_LOG.md`](docs/research/EXPERIMENT_LOG.md)：每次測試的完整紀錄與結論。
- [`experiment_results.csv`](docs/research/experiment_results.csv)：可排序、統計、畫圖的結構化結果。

固定研究規則：

1. 每次實驗必須寫清楚「沒改什麼」。
2. 每次實驗必須先定義通過標準。
3. 結論只能寫：`保留` / `淘汰` / `需要更多測試`。

### 已完成實驗

| 實驗 | 主題 | 結論 | 關鍵發現 |
|---|---|---|---|
| EXP-001 | 成本壓力測試 | 需要更多測試 | TP taker 影響不大；funding 會讓平均 R 轉負，策略邊際偏薄。 |
| EXP-002 | TP-first / SL-first / Conservative K棒路徑 | 需要更多測試 | SL-first 仍 PF > 1.15，但 MDD 惡化到 -53.72%，日 K 路徑假設會影響風險評估。 |
| EXP-003 | 策略 ablation 訊號拆解 | 需要更多測試 | 單一 raw 訊號多數 OOS 失效；baseline 主要靠多模組與風險濾網共同作用。 |
| EXP-004 | Baseline attribution | 需要更多測試 | baseline 正貢獻集中於 Supertrend、TP、15-30 天持倉、BTC above EMA200；短持倉與 SL 拖累明顯。 |
| EXP-005 | Point-in-time Top100 universe | 需要更多測試 | current-biased benchmark 明顯高估；Bybit 補資料後 static PIT 只剩 +52.03%，rolling PIT +37.49%。 |
| EXP-006 | PIT liquidity throttle | 需要更多測試 | 流動性門檻能改善 PIT 結果，但部分結果集中、需分段驗證。 |
| EXP-007 | Prev3Y 市值 Top100 主回測 | 淘汰 | raw Prev3Y market-cap Top100 OOS 只有 +7.25%，PF 1.030，Sharpe 0.289。 |
| EXP-008 | Prev3Y 成交量 Top100 raw | 淘汰 | raw Prev3Y volume Top100 OOS 為 -24.26%，PF 0.907，MDD -57.05%。 |
| EXP-009 | Top100 策略優化 | 需要 forward | volume Top100 + symbol WR off 改善，但 Top100 單點敏感。 |
| EXP-010 | Nested WF + stability overfit check | 需要 forward | `mcap_cap8` 顯示過擬合警訊；`volume_top125_lb3_sym_0.35` 是最佳穩定候選但仍需 forward。 |
| EXP-011 | Top125 volume forward monitor | pending | 候選已接進 `main.py --crypto-candidate`，forward 起點 2026-05-08，等待 90 天或 50 筆交易。 |
| EXP-012 | Top125 candidate stress tests | 需要 forward | 成本壓力大多通過；最嚴格成本組合 Sharpe 降到 0.669。SL-first/conservative 路徑仍有 PF 1.257、Sharpe 0.924。 |
| EXP-013 | Swap default Crypto strategy | forward live | `python main.py live` 已改用 `volume-top125-lb3-sym035`；舊 baseline 用 `--crypto-candidate config-baseline` 指定。 |

### Ablation 初步判斷

- `Symbol rolling winrate`：**保留**。關閉後交易數暴增，OOS PF / Sharpe / Calmar / MDD 全部變差。
- `Geometric RR`：**保留**。關閉後 OOS MDD 破 -50%，平均 R 轉負。
- `Supertrend raw`、`VP POC raw`、`VP + BB`、`Supertrend + EMA score`：**淘汰作為獨立 edge**。
- `Bollinger raw`、`BTC moat`、`baseline 組合`：**需要更多測試**。

下一步：正式預設已切到 `volume-top125-lb3-sym035`，只做 forward / demo 監控，不再用 2024-2026 歷史資料回頭調參。

---

## Latest Local Update: v1.13 — Walk-forward 驗證與 OOS 基準確立

針對 v1.12 candidate 的 +627% 連續回測，做了完整 walk-forward 驗證。

### 1. 先確認沒有 BUG

- ✅ v1.10 的 look-ahead 修正仍在（signal `shift(1)` 在 backtester:282-293）
- ✅ Sharpe 年化因子自動推導仍在（backtester:741-744）
- ✅ `SYM_MIN_WINRATE` 用的 `history_by_sym[sym]` 只含已平倉、point-in-time 正確
- 結論：**+627% 不是 look-ahead 幻覺**，而是 path-dependent 加持下的真實 in-sample 數字

### 2. Crypto-silo Walk-forward（`--profile Crypto`，$10k 起始）

切點 2024-05-01：IS = 2021-03 ~ 2024-04（3 年）/ OOS = 2024-05 ~ 2026-05（2 年）。

| 指標 | IS 3y | **OOS 2y（真實基準）** | 5y full | IS+OOS 複利 |
|---|---:|---:|---:|---:|
| 總報酬 | +229.88% | **+87.17%** | +627.44% | +517.50% |
| 年化 | 45.90% | **36.49%** | 46.71% | — |
| 勝率 | 53.95% | 43.81% | 51.49% | — |
| Profit Factor | 1.533 | **1.346** | 1.546 | — |
| Sharpe | 1.103 | **0.930** | 1.139 | — |
| 最大回撤 | −42.13% | −43.01% | −42.13% | — |
| 交易數 | 291 | 226 (~113/yr) | 470 | — |

**Path-dep gap = +627.44% − +517.50% = +110 pp**。確實存在但不致命；初步以為的 +497 pp 是把多 silo IS/OOS 跟 Crypto-only 5y 混比導致的錯誤。

### 3. 真實可期望基準

- **Crypto silo（1x 槓桿、永續）：年化 ~36% / Sharpe ~0.93 / PF ~1.35 / MDD ~−43%**
- 多 silo 整體：被 TW Stock +2.63% 與 US+Comm −2.54% 拖累，OOS 年化 ~14%
- **WR 從 IS 54% → OOS 44% 退化 10 pp** 是最明顯的 in-sample 過擬合徵兆
- PF 從 1.53 → 1.35 退化 0.19，仍在「可交易」門檻 > 1.3 之上

### 4. 三組 SYM filter 對照（多 silo OOS）

| 設定 | OOS 2y 多 silo | 5y 連續多 silo | Path-dep |
|---|---:|---:|---:|
| **aggressive (3/20)** ✅ | **+30.82%** | ~+209% | 中-大 |
| conservative (30/50) | +23.80% | +346.17% | 中 |
| no filter | +25.17% | +217.07% | ~0 |

OOS 最佳是 aggressive，因此最終保留 (3/20)。conservative (30/50) 雖然 path-dep 較小但 OOS 反而最差 — 過保守把該砍的幣留太久。

### 5. 重現指令

```powershell
# 真實基準（Crypto-only OOS，必跑）
python main.py backtest --profile Crypto `
  --start-date 2024-05-01 --end-date 2026-05-07 `
  --output output\v113_crypto_OOS.xlsx --note v1.13_crypto_OOS

# IS 對照
python main.py backtest --profile Crypto `
  --start-date 2021-03-01 --end-date 2024-04-30 `
  --output output\v113_crypto_IS.xlsx --note v1.13_crypto_IS

# 多 silo 整體
python main.py backtest --start-date 2024-05-01 --end-date 2026-05-07 `
  --output output\v113_multi_OOS.xlsx --note v1.13_multi_OOS
```

### 6. 後續觀察點
- 5y 連續回測 +627% 不是 BUG 但**不可作為宣傳數字**，引用時必須註明「同樣參數 OOS = +87%」
- Sweep 腳本找出的「最佳參數」都是 in-sample，**必須再跑 OOS 驗證**才能採用
- 新流程：propose → IS 跑 → OOS 跑 → rolling OOS 跑 → OOS ≥ 基準且 rolling 不崩 → 才入 main
- US+Commodity silo 在 OOS 仍是負報酬，是結構性議題

### 7. Crypto 優化工具

目前優化以 Crypto OOS 為主基準，IS 只用來篩候選，full 5y 與 rolling OOS 用來擋過擬合。

```powershell
# OOS-first 候選檢查
python scripts\crypto_oos_optimize.py --limit 18 --output output\crypto_oos_optimize_final.csv

# 局部網格：trend stop/RR/score + 風險縮放
python scripts\crypto_oos_optimize.py --local-grid --limit 25 --output output\crypto_oos_optimize_local_grid_risk.csv
```

截至目前測試，沒有新參數通過 robust gate；正式 baseline 仍維持 Crypto OOS +87.17% / CAGR 36.49% / PF 1.346 / Sharpe 0.930 / MDD -43.01%。

---

## v1.11 — Post-fix Re-tuning + 資料修復

承接 v1.10 的 look-ahead 修正，本版做兩件事：
1. 修復 SQLite Volume 欄位 BLOB 汙染（救回 102 個資產）
2. 在 de-biased 引擎上重跑 Crypto sweep，找到新的最佳並行倉位數

### 1. BLOB Volume 資料修復

之前每次回測都看到 `[WARN] XXX: unsupported operand type(s) for +: 'float' and 'bytes'`。
根因：yfinance 偶爾把 Volume 回傳成 numpy bytes，SQLite 動態型別照存為 BLOB；
回讀時整列轉成 object dtype，後續 indicators 加法直接炸。

修復：
- `src/database.py upsert_prices` 寫入前統一 `pd.to_numeric(errors='coerce')`，並逐欄 `float()`
- 對既有 DB 跑 in-place migration：3,352 列 BLOB（8-byte little-endian int64）無損還原為 REAL
- 影響資產：`^GSPC`、`^TWII`、102 檔個股（COIN/HOOD/GE/XAUUSD/...）

修復前回測只跑 30 個資產，修復後跑滿 132 個。

### 2. Crypto sweep 重調 — cap=5 → **cap=4**

v1.9 的 cap=5 是基於 pre-fix biased 回測找的最佳值，post-fix 下不再最佳：

| cap (max_total_positions) | CAGR | 勝率 | PF | MDD |
|---:|---:|---:|---:|---:|
| 3 | +14.97% | 54.1% | 1.26 | −46.6% |
| **4** ✨ | **+17.40%** | **52.3%** | **1.28** | **−44.16%** |
| 5 (v1.9) | +9.96% | 50.5% | 1.15 | −50.94% |

### 3. 與 EMA50 slope filter 的非線性互動

跑 2×2 才發現 cap 與 EMA50 slope 不能各自最佳化疊加：

| 整體總報酬 | slope ON | slope OFF |
|---|---:|---:|
| **cap=5** (v1.9) | +21.78% | +30.52% |
| **cap=4** (v1.11) | **+43.75%** ✨ | +26.27% |

各自最佳的疊加（cap=4 + slope OFF）反而負效，最佳是 **cap=4 + slope ON**：cap 緊讓資金集中在最強訊號，slope filter 補上品質檢查 → 雙重增強。

### 修正後完整對比

| 指標 | v1.9 (pre-fix biased) | v1.10 (post-fix, cap=5) | **v1.11 (cap=4)** |
|---|---:|---:|---:|
| 總報酬 | +148.86%* | +21.78% | **+43.75%** |
| Profit Factor | 1.332* | 1.095 | **1.184** |
| 最大回撤 | −47.11%* | −25.56% | **−23.22%** |
| 勝率 | 50.68%* | 43.81% | **44.0%** |
| 總交易 | 296* | 1081 | 1052 |
| Crypto CAGR | +22.35%* | +9.96% | **+17.40%** |
| Crypto MDD | −47.11%* | −50.94% | **−44.16%** |

\* v1.9 數字未含 102 個 BLOB-failed 資產，僅 Crypto silo 30 檔；其餘為 132 檔全集。

### 已知問題（待後續處理）
- **US+Commodity silo 仍是 −2.54%**（cap/slope 在四種組合下均無顯著改善）— 結構性議題，需單獨檢視該 silo 的訊號 / 出場邏輯
- TW Stock +2.63% 偏低，但有正報酬

### 重現指令

```powershell
python main.py backtest --output output\v111_baseline.xlsx --note v1.11_baseline --ver v1.11
```

---

## Latest Local Update: Bybit Live Ledger Reconciliation (2026-05-11)

Bybit Demo live ledger reconciliation was hardened after exchange-side SL fills were found in Bybit but not reflected in Excel:

- `python main.py live --sync-only` now performs a no-order sync of Bybit positions, closed PnL, SQLite, and `output/Bybit_Live_Orders.xlsx`
- Exchange-side TP/SL closes between scan cycles are backfilled from Bybit closed PnL / execution history and recorded as `REMOTE_CLOSED` or `REMOTE_CLOSED_SL`
- Closed-PnL reconciliation is keyed by Bybit exit order id and matched to known ledger `ENTRY` rows, so older exits are not skipped after newer entry backfills
- Open Bybit positions that are outside the current candidate universe are still added to the live monitoring context, so legacy positions are not silently ignored
- Missing `ENTRY` rows for existing remote positions are backfilled from Bybit execution history, keyed by Bybit order id where available
- The live Excel ledger uses Chinese display labels, is ordered by recorded execution time rather than insertion id, and alternates row colors by trading day
- Live mode re-exports `output/Bybit_Live_Orders.xlsx` at the end of each scan, so closing a locked workbook lets the next scan refresh it automatically

Operational sync command:

```powershell
python main.py live --sync-only
```

Validation run on 2026-05-11:

```powershell
python -m py_compile main.py src\executors\bybit.py src\live_ledger.py
python main.py live --sync-only
```

Runtime artifacts remain untracked by design: `data/trading.db`, `data/*-wal`, `data/*-shm`, `data/live_positions.json`, and `output/Bybit_Live_Orders.xlsx`.

---

## Latest Local Update: Bybit Live Order Ledger (2026-05-10)

Bybit live mode now records successful live order events to both SQLite and Excel:

- SQLite table: `bybit_live_orders` in `data/trading.db`
- Excel ledger: `output/Bybit_Live_Orders.xlsx` (`config.BYBIT_LIVE_ORDER_XLSX`)
- `ENTRY` rows are written after successful Bybit market entries
- `EXIT` rows are written after successful strategy-managed exits
- `REMOTE_CLOSED` exit rows are written when the bot syncs a position that was already closed on Bybit
- Recorded fields include symbol, side, direction, quantity, price, SL/TP, strategy, score, signal date, reason, PnL estimate, fee estimate, balance, Bybit order id, retCode/retMsg, and raw response

Operational notes:

```powershell
python main.py live --interval 15
```

`data/trading.db`, `data/*-wal`, `data/*-shm`, and `output/Bybit_Live_Orders.xlsx` are runtime artifacts. The code creates or refreshes them automatically; Git tracks the recorder code, not the generated ledger data.

---

## Latest Local Update: Bybit Demo Live Hardening (2026-05-09)

Live mode now mirrors the Crypto OOS baseline more closely on Bybit Demo:

- Bybit is still configured as demo trading: `BYBIT_DEMO = True`, `BYBIT_TESTNET = False`
- Bybit leverage is explicitly forced to `1x`: `BYBIT_LEVERAGE = 1`
- Startup logs now print Demo Trading and Testnet separately, so `api-demo.bybit.com` is not confused with Bybit Testnet
- Bybit `set_leverage` treats `ErrCode: 110043 / leverage not modified` as success, including the pybit-wrapped `retCode: -1` form
- Live scans use `include_vp=True`, `apply_cross_asset_filters()`, Crypto score gate, SYM win-rate filter, dominant strategy detection, and geometric R:R checks
- Market entries refresh the Bybit ticker price before sizing and SL/TP calculation; when live price differs from the signal close by 2% or more, the bot logs `[PRICE] ... using live`
- Open-position management also refreshes the Bybit ticker price before SL/TP, trailing-stop, BB target-profit, and PnL checks, so stale daily signal closes cannot trigger false live exits
- After a live non-flip exit (`SL`, `TP`, `BB-*`, `SOFT`, `MAXHOLD`, or exchange-side closed position), the bot skips re-entry on the same daily signal candle and waits for the next daily signal
- Before sending a market order, BybitExecutor validates TP/SL against the current ticker price:
  - long: `SL < live price < TP`
  - short: `TP < live price < SL`
- New entries submit full-position exchange-side TP/SL with `tpslMode='Full'`
- Bybit-side protection remains active if the bot is stopped: fixed SL / fixed TP
- Strategy exits still require `python main.py live` to keep running: signal flip, BB mid/RSI/profit exits, max hold, soft stop, and trailing-stop updates
- `Ctrl+C` during `python main.py live` exits cleanly without a traceback
- Live order logs now print `做多` / `做空` instead of corrupted legacy side labels
- The bot syncs existing Bybit positions on every scan and removes local metadata when a position is already closed
- Position metadata is persisted in `data/live_positions.json`:
  - `entry_dt`, `entry`, `strategy`, `score`, `entry_reason`
  - `orig_sl`, `sl`, `tp`, `trail_anchor`
- Existing Bybit positions opened before the bot starts are recovered as far as possible from Bybit execution history; then the bot infers strategy/score from the nearest historical signal date
- If an existing Demo position has no SL/TP, live mode backfills SL/TP from the current ATR stop formula
- Crypto trailing stop is updated through Bybit `set_trading_stop()`:
  - before +2R: stop trails by `ATR x 3.0`
  - after +2R: stop tightens to `ATR x 1.5`

Run:

```powershell
python main.py live --interval 15
```

---

## v1.10 — Look-ahead Bias 修正與引擎硬化

v1.10 是純 bug-fix release，**沒有改任何策略邏輯或參數**，但回測結果會大幅變動，
因為先前的數字含有 look-ahead bias。修正後的數字才是可實盤複製的真實表現。

### 修正項目

| # | 嚴重度 | 檔案 | 修正內容 |
|---|---|---|---|
| 1 | HIGH | [src/backtester.py](src/backtester.py) | 訊號陣列統一 `shift(1)`：t-1 收盤確認的訊號於 t 進場，消除「同根 K 棒收盤同時偵測 + 進場」的 look-ahead |
| 2 | HIGH | [src/backtester.py](src/backtester.py) | Sharpe 年化因子改由 equity curve 自動推導（crypto 7d/週 → 365；股票 5d/週 → 252），不再寫死 252 |
| 3 | HIGH | [src/fetcher.py](src/fetcher.py) | Bybit kline 起訖時戳改用 UTC（原本用本地時區，台北時區會差 8 小時、邊界日少/多一根） |
| 4 | HIGH | [src/executors/bybit.py](src/executors/bybit.py) | `place_order` 失敗改 `raise OrderRejected`，不再回 `{retCode:-1}` 讓上游靜默忽略 |
| 5 | MED | [src/strategies.py](src/strategies.py) | Supertrend 訊號加入 `prev_dir` 守門，避免暖機期 0 → ±1 假觸發 |
| 6 | MED | [src/indicators.py](src/indicators.py) | Supertrend `direction` 初值改 0 + NaN 期沿用前值，不再預設 +1 |
| 7 | MED | [src/executors/bybit.py](src/executors/bybit.py) | 槓桿自動 clamp 到 instrument `maxLeverage`、qty 大幅截斷時 warn |
| 8 | LOW | [src/database.py](src/database.py) | `load_backtest_history` 的 LIMIT 改參數化 |
| 9 | LOW | [src/backtester.py](src/backtester.py) | CAGR 移除 `max(years, 1)` cap（短週期回測會更如實） |
| 10 | LOW | [src/reporter.py](src/reporter.py) | `_auto_width` 收窄 except 範圍 |

### 修正前 vs 修正後 — 同份資料、同套參數

| 指標 | Pre-fix (run 52) | **Post-fix (run 53)** | Δ |
|---|---:|---:|---:|
| 總報酬 | +148.86% | **+63.42%** | **−85.44 pp** |
| 年化 (CAGR) | +19.27% | **+9.96%** | **−9.31 pp** |
| Sharpe | 0.569 | **0.450** | −0.119 |
| Profit Factor | 1.332 | **1.148** | −0.184 |
| 最大回撤 | −47.11% | **−50.94%** | −3.83 pp |
| 勝率 | 50.68% | 50.51% | −0.17 pp |
| 總交易數 | 296 | 293 | −3 |
| 最佳單筆 | $2,693 | $1,791 | −33.5% |

**為什麼勝率幾乎沒變但報酬腰斬？**
交易方向判斷其實是對的（勝率不動），但舊版用「同根 K 棒收盤」同時偵測訊號 + 進場，
等同偷看當天收盤的價格進場。修正後改成 t-1 訊號 → t 進場：
- 贏單利潤被砍 33.5%（原本人為加大）
- 輸單金額幾乎不變（方向錯時，t vs t+1 的價差有限）
- 結果：PF 1.332 → 1.148

### 重現指令

```powershell
python main.py backtest --output output\post_fix.xlsx --note "post bug fixes"
```

### 提醒
- 之前 `scripts/crypto_sweep*.py` 找出的「最佳參數」是基於 biased 回測，**需重跑調參**
- v1.9 README 內 22.35% / Sharpe 等數字是 pre-fix 結果，請以 v1.10 post-fix 為準

---

## v1.9 Crypto-Specific Tuning

v1.9 在保留 v1.8 silo 架構的前提下，針對 **Crypto silo** 做專屬參數最佳化，
其他 silo（TW Stock / US+Commodity）的參數與績效完全不變。

### Crypto silo 改動清單

新增 [config.py](config.py) 類別特化參數（fallback 至全域值）：

```python
MIN_ENTRY_SCORE_BY_CLASS    = {'Crypto': 3}     # 4→3，放寬進場分數
MAX_HOLD_DAYS_BY_CLASS      = {'Crypto': 30}    # 30 天強制平倉，加速資金回收
TSL_USE_CLOSE_BY_CLASS      = {'Crypto': True}  # TSL 用收盤價追蹤，避影線插針掃出
TSL_TIGHT_AFTER_R_BY_CLASS  = {'Crypto': 2.0}   # 浮盈 ≥ 2R 後 TSL 收緊至 1.5×ATR
```

`STRATEGY_PROFILES['Crypto']` 調整：
- `max_total_positions`：2 → **5**
- `max_position_pct`：0.20 → **0.40**（讓 tight stop 時 Kelly 名目不被 cap 砍）

[src/backtester.py](src/backtester.py) 新增 `_cls_get()` helper，於 4 個熱
路徑點（TSL tight、TSL track、max-hold、min-entry-score）按 `pos.asset_type`
查表；其他類別未列在 `*_BY_CLASS` 字典內時 fallback 全域值，行為與 v1.8 相同。

### 五年回測對比（同一份資料、同一條 git commit）

| Silo | v1.8 | **v1.9** | Δ |
|---|---|---|---|
| **Crypto** | +10.08% / 122 筆 / DD -29.86% / PF 1.39 | **+22.35% / 262 筆 / DD -40.63% / PF 1.47** | **+12.27 pp** |
| TW Stock | +3.35% / 383 筆 / DD -13.51% / PF 1.15 | +3.35% / 383 筆 / DD -13.51% / PF 1.15 | 無變化 |
| US+Commodity | +1.43% / 398 筆 / DD -13.37% / PF 1.05 | +1.43% / 398 筆 / DD -13.37% / PF 1.05 | 無變化 |

Crypto 達到使用者目標：
- ✅ 年化報酬 ≥20%（22.35%）
- ✅ 勝率 ≥30%（49.6%）
- ✅ 交易次數 50–100/年（50.7）
- ✅ 1/4 Kelly per-trade 不變（`KELLY_FRACTION=0.25`、Crypto fallback 6%）
- ⚠️ 最大回撤 -40.63%（加密幣特性、5 年含 2022 熊市）

### 已測試但未採用的方向

| 方向 | 結果 | 結論 |
|---|---|---|
| BTC moat → `full`（同時擋多+擋空） | -9.27% / PF 0.79 | 否決：擋空在 BTC 熊市反而砍掉好的空單 |
| BTC moat → 完全關閉 | -4.64% / PF 0.93 | 否決：BTC 熊市的多單虧損會放大 |
| 4H K 線（同樣參數移植） | -4.04% / PF 0.93 / WR 40.5% | 否決：噪音多、勝率掉到 40%；要可行需重調全套指標週期 |
| 1H K 線（同樣參數移植） | +3.68% / PF 1.09 / WR 40.3% | 否決：平均持倉 1.4 天，被 max_hold 提前出場為主 |

### Profile 限額（v1.9）

| Profile | Account | Asset Types | Max Positions | Max Pos % | Class Limits |
|---|---|---|---:|---:|---|
| **Crypto** | Bybit | Crypto | **5** | **0.40** | none |
| TW Stock | Taiwan broker | TW Stock | 6 | 0.20 | none |
| US+Commodity | US broker | US Stock, Commodity | 8 | 0.20 | US Stock 6, Commodity 2 |

### Crypto universe update

Crypto 回測標的已從 18 檔擴充為 30 檔：

- 3 檔固定核心幣：BTC、ETH、ADA
- 12 檔固定高成交量 Bybit USDT 永續合約
- 15 檔從原本 `CRYPTO_POOL` 隨機抽樣

新增的固定高成交量清單：

```text
HYPE, ZEC, FARTCOIN, 1000PEPE, SUI, PIPPIN,
TAO, WIF, ENA, ASTER, PUMPFUN, XPL
```

`python main.py backtest --profile Crypto` 現在只載入 Crypto 標的，
不再掃美股、台股、商品，因此單獨回測 Crypto 會更快，也能確認 30 檔是否全數進入回測。

最新 Crypto 30 檔檢查：

```text
載入 30 個資產
有效資產：30 檔
跳過：0 檔
年化報酬：19.27%
勝率：50.7%
交易：296 筆
Profit Factor：1.332
最大回撤：-47.11%
```

### Report update

Summary 的資金曲線表新增每日交易結果與手續費欄位：

```text
Date | 總資金 | 已配置資金 | 剩餘現金 | 損益 | 手續費 | 累積損益
```

### 重現指令

```powershell
python main.py backtest --output output\Backtest_v19.xlsx --note v19_baseline --ver v1.9
python main.py backtest --profile Crypto --output output\Backtest_Crypto_v19.xlsx --note v19_crypto
```

Sweep 腳本保留在 [scripts/](scripts/) 供後續再調參使用：
- `scripts/crypto_diag.py` — 進場阻塞統計
- `scripts/crypto_sweep[2-5].py` — 漸進式參數網格
- `scripts/crypto_btc_moat.py` — BTC 護城河三模式比較
- `scripts/crypto_intraday.py` — 4H / 1H 時間框架對照

多資產量化交易系統，支援回測、績效報告與即時下單（Bybit 已接通；IBKR / 新光 骨架待完成）。涵蓋美股、台股、加密貨幣與商品，內建 3 種獨立策略訊號、EMA 多空環境濾網、大盤護城河機制、智能熔斷與幾何 R:R 檢查。

---

## 目錄

- [功能概覽](#功能概覽)
- [專案結構](#專案結構)
- [快速開始](#快速開始)
- [指令說明](#指令說明)
- [交易策略](#交易策略)
- [市場環境濾網](#市場環境濾網)
- [風險管理](#風險管理)
- [執行器架構](#執行器架構)
- [資料來源](#資料來源)
- [回測報告](#回測報告)
- [即時交易](#即時交易)
- [資料庫結構](#資料庫結構)
- [依賴套件](#依賴套件)
- [版本記錄](#版本記錄)

---

## 功能概覽

| 功能 | 說明 |
|------|------|
| 資料抓取 | yfinance（股票/商品）+ Bybit REST API（加密貨幣） |
| 技術指標 | Supertrend、EMA20/50/100/200、布林通道、RSI、ATR、MACD、Volume Profile |
| 策略訊號 | 3 種獨立策略 + EMA 比例分數環境濾網 + 信心分數門檻（全域 MIN_ENTRY_SCORE=4，Crypto=3） |
| 市場護城河 | 台股 TAIEX SMA250 / 美股 SPY SMA200，弱市封鎖多單 |
| 智能熔斷 | 連虧 5 筆 **且** 帳戶回撤 ≥ 5% 雙條件觸發，暫停 5 個交易日 |
| 幾何 R:R | 檢查 TP 路徑上是否有近 20 日 swing 阻擋，有阻擋則拒絕進場 |
| 台股特化 | 處置股封鎖 hook、主力籌碼確認 hook（需外部資料） |
| 部位管理 | 1/4 Kelly 倉位計算、**分策略停損/停利**、**分策略並行倉位配額**、ATR Trailing Stop |
| 回測引擎 | 事件驅動日線模擬，追蹤 MAE/MFE、Trailing Stop |
| 績效報告 | 多頁籤 Excel（摘要、月度損益、策略比較、逐筆交易） |
| 即時交易 | 插件式執行器架構（Bybit 已接通；IBKR / 新光 骨架待完成） |
| 歷史查詢 | SQLite 儲存所有回測結果與逐筆交易紀錄 |
| TradingView 驗證 | `compare_tv.py` 逐根 K 棒對照 Pine Script 結果 |

---

## 專案結構

```
量化交易/
├── main.py                  # CLI 入口（fetch / update / backtest / live / history / info）
├── config.py                # 全域設定（資產清單、指標參數、濾網參數、v1.5 新開關）
├── .env                     # API 金鑰（本地保存，不進版本控制）
├── compare_tv.py            # TradingView 驗證腳本
├── requirements.txt
├── src/
│   ├── strategies.py        # 訊號產生（3 策略 + combine_signals + 護城河）
│   ├── indicators.py        # 技術指標計算（含 MACD）
│   ├── backtester.py        # 回測引擎（含熔斷、幾何 R:R、分數倉位）
│   ├── risk.py              # Kelly 準則倉位計算
│   ├── fetcher.py           # 資料下載
│   ├── database.py          # SQLite 讀寫
│   ├── reporter.py          # Excel 報告產生（含護城河狀態頁）
│   ├── executor.py          # 向後相容 shim → 改 import 自 src.executors
│   └── executors/           # 多 Broker 執行器套件
│       ├── __init__.py      # 統一匯出所有執行器
│       ├── base.py          # BaseExecutor 抽象介面
│       ├── bybit.py         # BybitExecutor（已實作，加密貨幣）
│       ├── ibkr.py          # IBKRExecutor（骨架，美股 + 商品，需 IB Gateway）
│       ├── shinkong.py      # ShinKongExecutor（骨架，台股，SDK 待確認）
│       └── router.py        # ExecutorRouter（依 symbol 自動分派 broker）
├── data/
│   └── trading.db           # SQLite 資料庫
└── output/                  # Excel 回測報告輸出
```

---

## 快速開始

### 安裝依賴

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 設定 API 金鑰（即時交易用）

在專案根目錄建立 `.env`，填入 Bybit API Key / Secret（此檔案已加入 `.gitignore`，不會被版本控制）：

```
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
```

`config.py` 中的模擬帳號開關：

```python
BYBIT_DEMO = True   # 改為 False 正式下單
```

### 首次使用流程

```bash
# 1. 下載 5 年歷史資料（120 檔資產）
python main.py fetch

# 2. 執行預設完整模式回測，輸出 Excel 報告
python main.py backtest

# 3. 查看資料庫資產清單
python main.py info
```

---

## 指令說明

```bash
python main.py fetch [--years 5] [--seed 42]
```
下載全部 120 檔資產到 SQLite，預設 5 年歷史。
同時會下載 `^TWII`、`^GSPC` 大盤基準資料到 SQLite，供護城河濾網使用。

```bash
python main.py update [--seed 42]
```
增量更新（只抓上次日期之後的新 K 棒）。
同時會更新 `^TWII`、`^GSPC`，之後回測只需補最新缺口。

```bash
python main.py info
```
列出資料庫資產清單（symbol、日期範圍、K 棒數量）。

```bash
python main.py backtest [--capital 100000] [--no-with-vp] [--output path] [--note "備註"]
                        [--no-moat-tf-only] [--rs-pct 0.03]
                        [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
```
執行完整回測，產生 Excel 報告並將績效摘要寫入 DB。
回測會優先從 SQLite 載入大盤基準資料；若缺最新資料才嘗試下載，下載失敗時會沿用既有快取。

| 參數 | 說明 |
|------|------|
| `--with-vp` / `--no-with-vp` | Volume Profile 策略預設啟用；需要加速或比較舊模式時可用 `--no-with-vp` 關閉 |
| `--moat-tf-only` / `--no-moat-tf-only` | 預設護城河只封鎖 Supertrend 多單，VP/BB 豁免；可用 `--no-moat-tf-only` 關閉 |
| `--rs-pct 0.03` | 護城河豁免門檻（近 10 天個股漲幅超越大盤 N%，預設 3%） |

```bash
python main.py history [--limit 20] [--run-id N]
```
查詢歷史回測紀錄；加上 `--run-id N` 可看該次回測的所有逐筆交易。

```bash
python main.py live [--seed 42] [--interval 15]
```
即時交易循環，每 15 分鐘掃描一次訊號並透過 ExecutorRouter 分派下單（目前 Bybit 已啟用）。

---

## 交易策略

### 策略一：趨勢跟蹤（Supertrend）

- **指標**：Supertrend（ATR 週期 10、乘數 3.0）
- **邏輯**：Supertrend 方向由空翻多 → 做多；由多翻空 → 做空
- **觸發時機**：只在翻轉那根 K 棒觸發，不連續持倉
- **趨勢過濾**：Supertrend 翻多／空時要求 EMA50 5 日斜率同向，過濾掉 chop 年大量「翻紅後立刻被打回」的假訊號。
- **美股額外條件（可選）**：`config.ENABLE_US_MACD_FILTER = True` 時，翻多需 MACD 柱狀圖 > 0；最新回測中此濾網預設關閉

### 策略二：成交量分布 POC 支撐/阻力

- **指標**：Volume Profile（252 日滾動視窗、80 個 bins），取 POC（Point of Control）
- **邏輯**（已修正 look-ahead bias，使用前一日 POC）：
  - 收盤從 POC 上方跌回 POC 附近（±1.5%）且 RSI < 60 → **做多（支撐）**
  - 收盤從 POC 下方漲回 POC 附近（±1.5%）且 RSI > 40 → **做空（壓力）**
- **預設啟用**：目前回測預設採用完整組合並啟用 VP；若要加速或比較舊模式，可加 `--no-with-vp`

### 策略三：布林通道均值回歸

- **指標**：BB(20, 2.0)、RSI(14)
- **邏輯**：
  - Close ≤ 布林下緣 + RSI < 30 + 正常波動 → **做多**
  - Close ≥ 布林上緣 + RSI > 70 + 正常波動 → **做空**
- **波動過濾**：布林帶寬 < 50 日均值 × 1.5（避免在極端行情交易）

### 訊號合併（combine_signals）

EMA 比例分數環境濾網（0–4 分），統計收盤高/低於幾根 EMA（20/50/100/200）：

| 分數 | 含義 |
|------|------|
| 4 | 完美多頭排列 |
| 3 | 強多頭環境 |
| 2 | 溫和多頭（預設門檻） |
| 1 | 混沌，禁止進場 |
| 0 | 完全反向 |

- 多頭方向需 EMA 多頭分數 ≥ 2 才開放做多訊號
- 空頭方向需 EMA 空頭分數 ≥ 2 才開放做空訊號
- **衝突解消**：多空環境同時達標時，以 EMA 分數決勝；完全相同則不進場（FLAT）
- 共識分數 = 訊號方向一致的子策略數（1–3）+ EMA 對齊分數（0–4），最高 7 分
- `MIN_ENTRY_SCORE = 4`：共識分數低於 4 的訊號直接丟棄

---

## 市場環境濾網

### 大盤護城河（v1.2 新增）

防止在大盤弱勢期間開多倉，台股與美股套用不同基準指數：

| 資產類別 | 基準指數 | MA 週期 | 封鎖條件 |
|---------|---------|---------|---------|
| 台股 | ^TWII（加權指數） | SMA250（年線） | 指數跌破年線 → 封鎖做多 |
| 美股 | ^GSPC（S&P 500） | SMA200 | 指數跌破 200MA → 封鎖做多 |
| 加密/商品 | — | — | 不限制 |

**強勢股豁免（弱水三千，只取最強）**：近 10 天個股漲幅超越大盤 3% 以上，即使大盤弱勢仍允許進場。可透過 `--rs-pct` 調整豁免門檻。

### 美股 MACD 假突破過濾（v1.2 新增，可選）

Supertrend 翻多時，可要求 MACD 柱狀圖（hist）> 0 才允許進場，避免橫盤整理後 HFT 演算法洗盤造成的假突破訊號。

最新單因子回測顯示，此濾網開啟後總報酬與 PF 略降，因此目前預設：

```python
ENABLE_US_MACD_FILTER = False
```

### 台股特化 hook（需外部資料）

以下兩個濾網已預留接口，**預設不啟動**，需在計算指標後手動將欄位寫入 DataFrame：

| 欄位名稱 | 型別 | 說明 |
|---------|------|------|
| `is_disposition` | bool | 處置股標記，True = 目前為處置股（分盤交易），所有訊號全部封鎖 |
| `chip_buy_days` | int | 主力連續淨買超天數，需 ≥ 3 天才允許做多 |

資料來源可接 TWSE MOPS API 或台灣證交所每日公告。

---

## 風險管理

| 參數 | 設定值 |
|------|-------|
| 初始資金 | $100,000 USD |
| 每筆風險 | 預設 4% 資金 (上限 5%) |
| 倉位上限 | 單一資產 20% |
| 最大持倉數 | 15 個部位 |
| Trailing Stop | ATR × 3.0（僅向有利方向移動，**BB 抄底單不啟用**） |
| 倉位計算 | 1/4 Kelly（需 ≥ 10 筆歷史，否則預設 4%；以剩餘可用現金為 sizing 基準） |

### 分策略停損/停利（v1.3 新增）

不同進場通道的損益結構不同，因此每個策略有自己的停損距離與風報比：

| 策略 | ATR 停損倍數 | 風報比（RR）| 額外早出條件 |
|---|---:|---:|---|
| trend / combined | 3.0 | 1:3 | — |
| vp（POC 拉回） | 2.0 | 1:2 | — |
| **bb（布林抄底）** | **1.5** | **1:2** | **觸 BB 中軌 / RSI 回中性 50 / 浮盈 ≥ +3%** 任一觸發即出場 |

BB 是逆勢搶反彈策略，硬抱長線會被接下來的跌勢吞回。窄停損 + 早出條件確保它走「高勝率小利」的本質損益結構，不被當趨勢單對待。

### 分策略並行倉位配額（v1.4 新增）

避免某個策略（特別是 trend）把所有部位名額吃光，留空間給其他策略補位：

| 策略 | 同時部位上限 |
|---|---:|
| trend | 12 |
| vp | 8 |
| bb | 4 |
| combined（多策略同向） | 不限 |

`combined` 訊號代表多策略共識度高、品質最佳，不受配額限制。實證顯示 trend 從不限改為 12 後，被擋掉的是品質較差的後段訊號，trend 平均單筆 PnL 反而提升。

### 資產類別限制（與策略配額並存）

| 類別 | 最大同時部位數 |
|------|-------------|
| 美股 | 6 |
| 台股 | 6 |
| 加密貨幣 | **5（v1.9 從 2 上調）** |
| 商品 | 2 |

### 智能熔斷（v1.5 新增）

雙條件觸發，防止系統在策略失效期間持續虧損：

```python
ENABLE_CIRCUIT_BREAKER    = True
CB_CONSEC_LOSS_LIMIT      = 5      # 連虧 N 筆
CB_CONSEC_LOSS_PAUSE_DAYS = 5      # 觸發後暫停 N 個交易日
CB_DAILY_LOSS_PCT         = 0.03   # 當日虧損 ≥ 3% → 當日封盤
CB_MAX_DAILY_TRADES       = 10     # 當日新進場上限
CB_REQUIRE_DRAWDOWN       = True   # 必須同時滿足回撤條件才觸發（避免在低點誤殺反彈）
CB_REQUIRE_DRAWDOWN_PCT   = 0.05   # 帳戶回撤門檻 5%
```

**設計理由**：純連虧計數在趨勢反轉低點會誤觸（連虧最容易出現在行情剛要轉好前），加上 DD ≥ 5% 的雙條件後，熔斷準確率顯著提升。

### 幾何 R:R 檢查（v1.5 新增）

進場前掃描 TP 路徑是否有近期 swing high/low 阻擋：

```python
ENABLE_GEOMETRIC_RR  = True
GEO_RR_LOOKBACK      = 20      # 往前看 20 根 K 棒
GEO_RR_BUFFER_ATR    = 1.0     # 阻擋判定緩衝 = 1 × ATR
```

若 TP 路徑上有 swing 阻擋（多頭：swing high 在 entry~TP 之間；空頭：swing low），拒絕進場。此功能單獨啟用可改善績效 +1.1 pp。

---

## 執行器架構

### 設計原則

統一程式碼庫 + 插件式多 Broker 執行器，由 `ExecutorRouter` 依 symbol 自動分派：

```
symbol → asset_type_of() → ExecutorRouter → 對應 Executor
  'BYBIT:BTCUSDT.P'  →  Crypto   →  BybitExecutor    ✅ 已接通
  'AAPL'             →  US Stock →  IBKRExecutor      🚧 需 IB Gateway
  'XAUUSD'           →  Commodity→  IBKRExecutor      🚧 需 IB Gateway
  '2330.TW'          →  TW Stock →  ShinKongExecutor  🚧 SDK 待確認
```

### 使用方式

```python
from src.executors import ExecutorRouter

router = ExecutorRouter(enable={'Crypto': True, 'US Stock': False,
                                'Commodity': False, 'TW Stock': False})
router.warmup()                        # 主動建構所有啟用的 broker

ex = router.get('BYBIT:BTCUSDT.P')    # → BybitExecutor
ex.place_order('BYBIT:BTCUSDT.P', direction=1, qty=0.01,
               stop_loss=90000, take_profit=95000)

balances = router.get_balances()       # 所有已建構 broker 的餘額
```

### Broker 上線進度

| Broker | 類別 | 狀態 | 前置需求 |
|--------|------|------|---------|
| Bybit | Crypto | **已接通** | `.env` 設好 `BYBIT_API_KEY` / `BYBIT_API_SECRET` |
| Interactive Brokers | US Stock + Commodity | 骨架完成 | 開 IBKR 帳戶 → 安裝 TWS/IB Gateway → `pip install ib_insync` |
| 新光證券 | TW Stock | 骨架完成 | 確認新光 Python SDK 名稱後填入 `src/executors/shinkong.py` |

---

## 資料來源

| 資產類別 | 來源 | 數量 | 範例 |
|---------|------|------|------|
| 美股 | yfinance | 50 檔 | AAPL, MSFT, JPM, XOM |
| 台股 | yfinance | 50 檔 | 2330.TW, 2882.TW, 2609.TW |
| 加密貨幣 | Bybit REST API | 18 檔 | BTC, ETH, SOL, BNB |
| 商品 | yfinance（期貨） | 2 檔 | XAUUSD（黃金）, XAGUSD（白銀） |

---

## 回測報告

Excel 工作簿包含以下頁籤：

| 頁籤 | 內容 |
|------|------|
| 📊 Summary | 所有績效指標 + 權益曲線折線圖 + v1.6 功能啟用狀態 |
| 📈 Monthly P&L | 月度 × 資產類別損益樞紐分析（熱圖著色）+ 長條圖 |
| 🔍 Strategy Stats | 三策略比較、出場分布、多空勝率 |
| 📋 Asset Stats | 逐資產勝率、交易次數、損益；Top 10 / Bottom 10 |
| YYYY-QN | 按年/季分頁，含凍結標題、自動篩選 |
| 📋 All Trades | 所有已平倉交易（進出場日期、價格、R 倍數、MAE/MFE） |
| Per Symbol Stats | 逐 Symbol 摘要（條件格式著色損益與勝率） |

**主要績效指標**：

- 總報酬、年化報酬
- Sharpe Ratio、Calmar Ratio、Recovery Factor
- 勝率（整體 / 多空分開）
- 獲利因子（Profit Factor）、期望值（Expectancy）
- 最大回撤（% 與 USD）
- 平均持倉天數、平均 R 倍數
- 連續獲利/虧損最大值

---

## 即時交易

目前僅 Bybit 加密貨幣永續合約（USDT 保證金）已實際接通。

```bash
python main.py live --interval 15
```

- 每 15 分鐘掃描一次加密貨幣訊號
- 自動計算 Kelly 倉位（從歷史回測紀錄讀取）
- 使用市價單建倉，會先以 Bybit 即時價重算倉位與 SL/TP，並在送單前檢查 TP/SL 是否位於正確方向
- 可在 `config.py` 設定 `BYBIT_DEMO = True` 使用模擬帳號測試
- 按 `Ctrl+C` 可正常停止 live loop，不會輸出 traceback

---

## TradingView 策略腳本與驗證

本專案提供完整的 TradingView Pine Script 策略，方便您在圖表上直接視覺化與執行：

```bash
TradingView_Strategy.pine
```

此腳本已與 Python 端的最新邏輯 (v1.6+) 完全同步，包含：
- **大盤環境濾網 (Market Moat)**：大盤 MA 濾網與相對強弱 (RS) 豁免
- **MACD 過濾**：可選的 Supertrend MACD 假突破過濾
- **早期趨勢反轉偵測**：EMA200 斜率變化提前封鎖反向單
- **共識分數計算**：完全對齊 Python 的 1~7 分計算與 EMA 比例分數

您可以直接將 `TradingView_Strategy.pine` 複製貼上至 TradingView 的 Pine Editor 中使用。

若要確保 Python 端回測與 Pine Script 輸出一致，可執行驗證腳本：

```bash
python compare_tv.py
```
對照 Pine Script 輸出，逐根 K 棒驗證 Python 回測結果，確保指標計算（Wilder's RMA、Supertrend、Volume Profile）與 TradingView 完全一致。

---

## 資料庫結構

```sql
-- 歷史 OHLCV 資料
prices(id, symbol, date, open, high, low, close, volume, asset_type)

-- 資產元資料
asset_registry(symbol, asset_type, first_date, last_date, bar_count)

-- 回測執行摘要
backtest_runs(run_id, run_at, version, initial_capital, final_capital,
              total_return_pct, annual_return_pct, total_trades,
              win_rate, profit_factor, sharpe_ratio, max_drawdown_pct, note)

-- 回測逐筆交易
backtest_trades(id, run_id, symbol, strategy, direction, asset_type,
                entry_date, exit_date, entry_price, exit_price, quantity,
                pnl, return_pct, holding_days, r_multiple, mae, mfe, exit_reason)
```

---

## 依賴套件

```
yfinance>=0.2.40       # 股票/商品歷史資料
python-dotenv>=1.0.0   # .env 金鑰讀取
pandas>=2.0.3          # 資料處理
numpy>=1.24.0          # 數值計算
pybit>=5.6.0           # Bybit API
openpyxl>=3.1.2        # Excel 報告
scipy>=1.11.4          # 科學計算
tqdm>=4.66.0           # 進度條
requests>=2.31.0       # HTTP 請求
# 選配（即時交易其他 broker）
# ib_insync>=0.9.86    # IBKR（美股/商品）
# shioaji / shinkong_api  # 台股（SDK 待確認）
```

---

## 版本記錄

### v1.9（目前）⭐ — Crypto 專屬調參

**動機**：v1.8 Crypto silo 年化 +10%、僅 24 筆/年，遠低於使用者目標
（≥20% CAGR、50–100 筆/年）。本版透過類別特化參數，把 Crypto 推到目標
帶內，**完全不影響** TW / US+Commodity silo（兩者參數與績效逐項相同）。

**改動範圍**（皆為 Crypto-only override，其他類別自動 fallback v1.8 行為）：

1. `STRATEGY_PROFILES['Crypto']`：
   - `max_total_positions` 2 → 5
   - `max_position_pct` 0.20 → 0.40

2. 新增 `*_BY_CLASS` 字典（`config.py` 中段，未列入字典的類別 fallback 全域）：
   - `MIN_ENTRY_SCORE_BY_CLASS = {'Crypto': 3}`
   - `MAX_HOLD_DAYS_BY_CLASS = {'Crypto': 30}`
   - `TSL_USE_CLOSE_BY_CLASS = {'Crypto': True}`
   - `TSL_TIGHT_AFTER_R_BY_CLASS = {'Crypto': 2.0}`

3. `src/backtester.py` 新增 `_cls_get()` helper，4 個熱路徑點（TSL tight、
   TSL track、max-hold、min-entry-score）改為按 `pos.asset_type` 查表。

**Crypto 績效**：

| 指標 | v1.8 | v1.9 | Δ |
|---|---:|---:|---|
| 年化報酬 | 10.08% | **22.35%** | +12.27 pp |
| 交易筆數（5 年）| 122 | 262 | +115% |
| 交易筆數/年 | 23.7 | 50.7 | +114% |
| 勝率 | 53.3% | 49.6% | -3.7 pp |
| Profit Factor | 1.39 | 1.47 | +0.08 |
| 最大回撤 | -29.86% | -40.63% | -10.8 pp |
| avgR | +0.13 | +0.12 | -0.01 |

**已測試但未採用**：BTC moat 改 full / 完全關閉、4H、1H 時間框架——皆使
PF 跌至 < 1.1 或 < 1（詳見頂部「已測試但未採用的方向」表）。

---

### v1.7 — 類別特化 1/4 Kelly

**核心改動**：把 `DEFAULT_RISK_PCT` 從統一 4% 改成**按類別分配真實 1/4 Kelly**，依 v1.6 main 928 筆回測統計反推：

| 類別 | 勝率 | R | 完整 Kelly | 1/4 Kelly | v1.7 預設值 |
|---|---:|---:|---:|---:|---:|
| Crypto | 56.9% | 1.41 | 26.4% | 6.6% | **6.0%** |
| US Stock | 45.9% | 1.57 | 11.4% | 2.85% | **3.0%** |
| TW Stock | 41.0% | 1.73 | 6.98% | 1.74% | **2.0%** |
| Commodity | 54.8% | 1.03 | 11.1% | 2.78% | **3.0%** |

**為什麼這樣設**：v1.6 統一 4% 對台股太大（壓不住 41% 勝率的劣勢）、對 crypto 太小（餵不飽 57% 勝率的優勢）。改按類別分流後，風險預算自動往真實 alpha 集中。

**配套調整**：
- `MAX_RISK_PCT` 0.05 → 0.07（容納 crypto 真實 1/4 Kelly 6.6%）
- `MAX_POSITION_PCT` 維持 0.20（實測放寬到 0.30 在 2024/2025 虧損年放大傷害，反而 -3pp）

**績效（main 無槓桿版）**：

| 項目 | v1.6 main | **v1.7 main** | Δ |
|---|---:|---:|---|
| 年化報酬 | 13.73% | 13.62% | -0.11pp |
| Sharpe | 0.547 | **0.553** | +1% |
| Profit Factor | 1.390 | **1.396** | +0.4% |
| 最大回撤 | -11.31% | -11.94% | -0.6pp |

實質 CAGR 持平（差 0.1pp 屬雜訊範圍），但**語意更乾淨**——每個類別風險預算對齊真實 Kelly。`crypto-2x` 與 `lev-diversified` 兩個 leverage 分支仍停在 v1.6 risk.py（`DEFAULT_RISK_PCT=4%` 統一），需要前移時可手動 cherry-pick / merge main。

---

### v1.8 — 艙位回測 + Bybit 手續費 + 滑點模型

- 引入 `ENABLE_SILO_MODE` 與 `STRATEGY_PROFILES`，三個 silo 對應實際交易所帳戶（Bybit / 台股券商 / 美股券商），資金完全隔離
- 新增 Bybit `BYBIT:BTCUSDT.P` 為 Crypto market proxy 的長偏向護城河（`ENABLE_CRYPTO_BTC_MOAT = True`、`CRYPTO_BTC_MOAT_MODE = 'long_only'`）
- 進場手續費（Taker 0.055%）+ TP 出場（Maker 0.02%）+ SL/翻轉（Taker）；股票/商品單向 0.05%
- 進出場滑點 0.1%（limit TP 不計）
- Bybit 永續合約強制 leverage = 1x（`BYBIT_LEVERAGE = 1`），對齊 main 風險預算

---

### v1.6 ⭐

**三層改善（疊加生效）**：

1. **EMA50 斜率方向確認**：過濾 Supertrend 假翻轉（修 2022 chop）。
2. **倉位上限放寬 + 風險預設值**：把 Kelly 真正解放（`MAX_RISK_PCT` 0.02→0.05、`MAX_POSITION_PCT` 0.10→0.20、新增 `DEFAULT_RISK_PCT=0.04` 取代硬編 0.02 預設值）。
3. **類別槓桿（Leverage by Class）**：可選；放大 crypto / 股票 alpha。

#### 三個版本（git 分支）

從同一份策略碼分出三個 leverage 配置，依風險偏好選用：

| 分支 | LEVERAGE_BY_CLASS | 年化報酬 | 最大回撤 | Sharpe | 單筆風險上限 |
|---|---|---:|---:|---:|---|
| **`main`（無槓桿）** | 全 1.0 | **13.73%** | -11.31% | 0.547 | 5%（全類別一致） |
| `crypto-2x` | Crypto 2.0、其他 1.0 | **19.42%** | -15.74% | 0.688 | crypto 10%、其他 5% |
| `lev-diversified` | Crypto 2.5、股票 1.5、商品 1.0 | **26.08%** | -17.49% | 0.671 | crypto 12.5%、股票 7.5% |

> 切換版本：`git checkout crypto-2x` 或 `git checkout lev-diversified`，回 main 即無槓桿。

#### v1.5 baseline → v1.6 各版本對比

| 項目 | v1.5 | main（無槓桿）| crypto-2x | lev-diversified |
|---|---:|---:|---:|---:|
| 年化報酬 | 9.01% | **13.73%** | 19.42% | **26.08%** |
| 總報酬（6 年）| 56.14% | 95.17% | 150.10% | **231.57%** |
| Sharpe | 0.443 | 0.547 | **0.688** | 0.671 |
| Profit Factor | 1.308 | 1.390 | 1.450 | 1.416 |
| 勝率 | 45.4% | 45.5% | 47.9% | 47.6% |
| 最大回撤 | -9.73% | **-11.31%** | -15.74% | -17.49% |
| 2022 PnL | -$5,314 | **+$4,879** | +$8,402 | +$13,872 |

#### 槓桿與單筆風險的關係（重要）

槓桿在 [risk.py:78](src/risk.py#L78) 直接乘到 `risk_amount` 上：

```python
risk_amount = capital * min(kelly_frac, MAX_RISK_PCT) * leverage
```

意思是 1/4 Kelly 的 **R 單位（單筆 SL 觸發的虧損）會被同步放大**。例：crypto 2x 時，crypto 單筆 SL hit ≈ 8-10% 帳戶資金；lev-diversified 時 crypto 可達 12.5%、股票 7.5%。`main` 因為全 leverage=1.0，所有類別單筆 SL hit 一律 ≤ 5%。

#### 槓桿版真實交易需注意（回測未模擬）

- **保證金利息**：美股/台股融資 5-7% 年息 → 每筆持倉 30 天約 0.2% 拖累 → CAGR 估減 0.5-1pp。
- **永續資金費率**：Bybit ±0.03%/日 → 月持倉約 0.9% 拖累 → CAGR 估減 0.3-0.5pp。
- **gap risk**：crypto 假日跳空可能跌穿 SL，槓桿下虧損超過 -1R 預期。
- **Bybit 帳戶槓桿設定**：使用 `crypto-2x` 分支需在 Bybit 將該交易對的帳戶槓桿設為 ≥ 2x（建議 3-5x 留 buffer）；否則訂單會因保證金不足被拒絕。

---

### v1.5

**新功能**：

- **智能熔斷**（`ENABLE_CIRCUIT_BREAKER = True`）：連虧 5 筆 **且** 帳戶回撤 ≥ 5% 雙條件觸發，暫停 5 個交易日；純連虧版本反而降績效，雙條件顯著避免在反轉低點誤殺
- **幾何 R:R 檢查**（`ENABLE_GEOMETRIC_RR = True`）：進場前掃描 TP 路徑近 20 日 swing 阻擋，有阻擋拒絕進場；單獨啟用 +1.1 pp
- **多 Broker 執行器架構**：拆出 `src/executors/` 套件；`ExecutorRouter` 依 asset_type 自動分派 broker；Bybit 已接通，IBKR / 新光骨架完成待填實作
- **分數分級倉位**（`ENABLE_SCORE_TIER_SIZING`，預設 off）：7 分 × 1.0 / 5–6 分 × 0.6 / 4 分 × 0.3 Kelly

**Bug 修正**：

- VP 訊號 look-ahead：改用 `poc_prev = df['poc'].shift(1)` 避免用當日 POC 比較昨收（修正後總報酬由 62.79% → 44.22%，去除虛假超額）
- NaN ATR fallback：`float(atr or ...)` 對 `np.nan` 為 True；改用 `pd.isna()` 顯式判斷
- 勝率計算：零 PnL 不計入虧損（`p < 0` 而非 `p <= 0`）；WR 分母只含有勝敗的有效交易

**v1.5 回測績效**（120 檔資產，2020-03 至 2026-05，初始資金 $100k）：

| 指標 | v1.4 基線（修正後） | **v1.5** | 變化 |
|---|---:|---:|---:|
| 總報酬 | 44.22% | **57.71%** | **+13.49 pp** |
| 年化報酬 | 7.19% | **9.22%** | +2.03 pp |
| Profit Factor | 1.312 | **1.338** | +0.026 |
| Sharpe Ratio | 0.399 | **0.455** | +14% |
| 最大回撤 | -13.53% | **-12.59%** | 縮小 7% |

---

### v1.4

- **分策略並行倉位配額**：trend 12 / vp 8 / bb 4 / combined 不限
- trend 從不限改為 12 後，被擋掉的是品質較差的後段訊號，trend 平均單筆 PnL 反而提升

### v1.3

- **分策略停損/停利**：trend ATR×3 + RR 1:3、vp ATR×2 + RR 1:2、bb ATR×1.5 + RR 1:2
- **BB 早出邏輯**：觸 BB 中軌 / RSI≥50 (多) 或 ≤50 (空) / 浮盈 ≥ ±3% 任一觸發即出場；BB 不啟用 ATR Trailing Stop
- `calculate_stops` 接收 `strategy` 參數，依進場通道分流計算

### v1.2

- **MACD 指標**：新增 `macd`、`macd_sig`、`macd_hist` 欄位
- **大盤護城河**：台股 TAIEX SMA250 / 美股 SPY SMA200；弱市封鎖多單，強勢股（RS > 大盤 3%）豁免
- **美股 MACD 雙確認改為可選**：`ENABLE_US_MACD_FILTER` 控制是否啟用，預設 `False`
- **Volume Profile 預設啟用**；可用 `--no-with-vp` 關閉
- **倉位 sizing 修正**：回測開倉以 `available_cash` 作為 `position_size()` 基準

### v1.1

- EMA200 斜率濾網（早期趨勢轉向偵測）
- Asset Stats 頁籤新增各類別年化貢獻欄位

### v1.0

- 初始版本：Supertrend + Volume Profile + Bollinger 三策略
- EMA 比例分數環境濾網
- ATR Trailing Stop、1/4 Kelly 倉位、事件驅動回測引擎

---

## 注意事項

- 本系統僅供研究與學習用途，不構成投資建議
- 即時交易前請務必先以 `BYBIT_DEMO = True` 充分測試
- 回測績效不代表未來實際報酬
- API 金鑰存放於 `.env`，已列入 `.gitignore`，請勿手動提交至版本控制
# TASK-014BM_ONE_SHOT_ORCHESTRATOR_READ_ONLY_DISCOVERY_OPT_IN_FIX (2026-06-20)

Narrow preview-CLI fix for the Stage 1 one-shot authorized execution orchestrator. The CLI now exposes the explicit read-only opt-in flag:

`--i-understand-this-performs-one-public-read-only-instrument-rules-get`

Default remains fail-closed: `--ir-mode discover` without that flag rejects before network and prints the required flag. With the flag, the CLI passes `allow_real_ir_get=True` into `run_one_shot_authorized_execution_orchestration()`.

The only allowed real request for this task is one public read-only GET:

`GET https://api-demo.bybit.com/v5/market/instruments-info?category=linear&symbol=SOLUSDT`

This task does not expose real BM execute mode, does not weaken fake-sender-only execution restrictions, does not read credentials for the public GET, and does not modify `main.py`, `src/risk.py`, `src/executors/bybit.py`, global tiny caps, protected symbols, or `MAX_ORDER_COUNT=1`. Readiness remains `order_endpoint_called=False` and `order_sent=False`.

Validation:

- `python -m py_compile scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py` with bytecode cache under `%TEMP%` -> PASS
- `python -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py --basetemp=<temp>/quant-pytest-codex-optin -p no:cacheprovider` -> 12/12 PASS
- `python -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --basetemp=<temp>/quant-pytest-codex-orchestrator -p no:cacheprovider` -> 34/34 PASS
- `python -m pytest tests/demo_trading -k tiny_execution_adapter --basetemp=<temp>/quant-pytest-codex-tiny -p no:cacheprovider` -> 517/517 PASS

Next VPS validation command:

```powershell
python scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --ir-mode discover --i-understand-this-performs-one-public-read-only-instrument-rules-get --explicit-demo-min-qty-cap-authorization-flag --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1
```
