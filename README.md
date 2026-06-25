# 量化交易系統

Python 量化研究與受控 Bybit Demo 交易系統。支援歷史回測、Forward 驗證、
Paper Portfolio 模擬與受防護的 Demo 執行。預設執行模式為 Plan-only（僅規劃、
不下單），Live 交易尚未授權。

## 系統功能

- **歷史市場資料**：從 SQLite 載入加密貨幣 OHLCV 日線資料，產生標準化 parquet 快照
- **策略訊號**：3 年回看動量策略，基於時序 market-cap 篩選 universe，排名前/後 N 檔做多/做空
- **目標投組**：Strategy-native V1 建構目標部位，±0.02 等權重，50 檔訊號（25 多 / 25 空）
- **行動規劃**：Planner 透過 REST API 取得即時價格，計算目標數量並依 qty_step 取整
- **新鮮度 / 保證金檢查**：Fail-closed 價格時效驗證與保證金可行性評估
- **Forward 驗證**：每日記錄訊號→部位→PnL，凍結 10,000 USDT 資本基礎
- **Paper Portfolio**：模擬下一交易日開盤成交，含手續費與滑價估算
- **報表產出**：Dashboard（HTML/CSV）、Discord webhook、Notion 同步（皆有開關控制）
- **受防護的 Demo 執行**：僅限 Demo API、需明確授權、受保護標的會被拒絕

## 目前執行流程

```
SQLite OHLCV 日線資料
  → 動量訊號（TargetPortfolio）
    → 目標投組建構
      → Planner（REST 即時價格 → 數量取整）
        → 新鮮度 / 保證金檢查
          → Plan-only 產出物
            → 授權閘門
              → Demo 執行（需明確授權）
                → 報表（JSON / Excel / Discord / Notion）
```

- 整合價格路徑目前使用 **REST**（`/v5/market/tickers`，公開 GET，無需認證）
- 公開 WebSocket 證據收集與 canonical-bound-plan 產出物已完成，但僅作為離線驗證器
- WS-bound 產出物尚未整合進原生執行消費鏈

## 執行模式

| 模式 | 說明 | 是否下單 |
|---|---|---|
| 研究 / 回測 | 歷史訊號產生、成本壓力測試、變體研究 | 否 |
| Forward 驗證 | 每日訊號→部位記錄、PnL 追蹤、overlay 檢查 | 否 |
| Paper Portfolio | 模擬成交（下一交易日開盤 + 手續費 / 滑價） | 否 |
| Plan-only Demo | REST 價格取得、數量取整、批次規劃；不發送 | 否 |
| 授權 Demo 執行 | One-shot tiny adapter（SOLUSDT 鎖定）；明確閘門 | 僅 Demo |
| Live 交易 | 未實作、未授權 | 禁止 |

## 專案結構

```
src/           策略、訊號、規劃器、執行、風控核心模組
apps/          Forward Record、Paper Trading、Monitor 應用程式
scripts/       CLI 入口腳本（回測、驗證、報表、WS 收集）
tests/         單元測試與整合測試
docs/          架構文件、當前狀態、歷史歸檔
configs/       設定檔（credentials 透過 .env 載入，不進 Git）
data/          市場資料快照與 SQLite 資料庫（gitignored）
outputs/       執行時產出物（logs、dashboard、daily records，gitignored）
```

## 安裝

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

相依套件由 `requirements.txt` 管理。目前開發環境使用 Python 3.13；
其他 Python 版本未經正式 CI 驗證。主要相依套件：pandas、numpy、pybit、
yfinance、openpyxl、pyarrow、websocket-client。

## 常用指令

```bash
# 研究回測：執行 prev3y_crypto baseline
python scripts/run_prev3y_crypto_baseline.py

# Forward 驗證：產生每日紀錄
python scripts/run_forward_record.py

# Plan-only Demo 日執行（不下單）
python scripts/run_demo_strategy_pilot_native_daily.py --pilot-id <ID> --date <YYYY-MM-DD>

# 離線 WS 證據綁定
python scripts/bind_plan_prices_to_ws_evidence.py \
  --plan-json <PLAN_JSON> \
  --ws-ticker-evidence-json <WS_EVIDENCE_JSON> \
  --bind-plan-prices-to-ws-evidence \
  --require-complete \
  --out <BOUND_PLAN_JSON> \
  --json-only

# 建立可信任的 review anchor manifest（CH3C1，純離線）
python scripts/build_demo_strategy_ws_review_anchor_bundle.py \
  --ch2-summary-json <CH2_PASS_SUMMARY_JSON> \
  --ch2-summary-sha256 sha256:<64hex> \
  --ws-bound-plan-wrapper-json <CH2_WRAPPER_JSON> \
  --ws-ticker-evidence-json <WS_EVIDENCE_JSON> \
  --expected-strategy-symbols-json <SYMBOLS_JSON> \
  --expected-strategy-symbols-sha256 sha256:<64hex> \
  --output-anchor-manifest-json <ANCHOR_MANIFEST_JSON> \
  --date <YYYY-MM-DD>

# WS-bound Plan 唯讀審查（review-only，純離線、終止於審查前的所有執行路徑）
python scripts/run_demo_strategy_pilot_native_daily.py \
  --pilot-id <ID> --date <YYYY-MM-DD> \
  --ws-bound-plan-review-only \
  --ws-bound-plan-anchor-manifest-json <ANCHOR_MANIFEST_JSON> \
  --ws-bound-plan-anchor-manifest-sha256 sha256:<64hex> \
  --ws-bound-plan-wrapper-json <CH2_WRAPPER_JSON> \
  --ws-ticker-evidence-json <WS_EVIDENCE_JSON> \
  --ws-bound-plan-review-output-json <REVIEW_OUTPUT_JSON>

# 執行測試
pytest tests/
```

不含任何 send / order 指令。Demo 執行需另外透過 one-shot adapter 明確授權。

### review-only 模式（TASK-014CH3B2，明確 opt-in）

審查一份既有的 CH2 WS-bound Plan wrapper，需提供：可信任的外部 anchor manifest
檔（其 SHA256 由操作者於 CH2 當下另外保存、以 `--ws-bound-plan-anchor-manifest-sha256`
傳入，**絕不由 CLI 從 manifest 反推**）、原始 source-WS 證據檔、以及一個全新的審查
輸出路徑。四個路徑必須互異。此模式：

- 僅為**歷史 binding-time** 審查；**不評估當前市場 freshness**
  （`current_market_freshness_status = NOT_EVALUATED`）；
- 投影保證金費率不可得（`UNAVAILABLE_NO_INDEPENDENT_RATE`，投影保證金審查未完成）、
  帳戶保證金可行性不可得（`UNAVAILABLE_NOT_EVALUATED`）；
- `execution_readiness = false`；不下單、不動 Pilot、不走 readiness / 執行 gate /
  native execution / sender / 對帳 / Notion / Discord，**無 REST fallback**；
- 以 race-safe、no-clobber（`os.link` create-if-absent）方式只寫一份審查 envelope。

此模式**不是執行核可**；它只證明歷史證據在其 binding epoch 當下有效。

### anchor bundle builder（TASK-014CH3C1，純離線）

`scripts/build_demo_strategy_ws_review_anchor_bundle.py` 由一份**外部釘選的 CH2 PASS
summary**（其 SHA256 由操作者於 CH2 當下另外保存、以 `--ch2-summary-sha256` 傳入，
**絕不由工具從 summary 反推**）、精確的 CH2 wrapper 與 source-WS 位元組、以及一個
**獨立的 50 檔標的來源**（檔案 + 外部 SHA256；倉庫沒有不可變的內建 50 檔常數，因此
標的集合必須由外部檔案提供，不得由 wrapper 反推、也不得隱性採用 Forward Record 的
`latest_date`）建立 CH3 review anchor manifest。它會重跑 CH1 歷史驗證後，以 race-safe、
no-clobber 方式寫出一份 manifest，並印出該 manifest 檔案的 SHA256。

- 印出的 `output_anchor_manifest_sha256` 必須**另外保存**，稍後作為
  `--ws-bound-plan-anchor-manifest-sha256` 傳入 review-only 模式。
- 此工具**不執行 review-only、不查詢當前市場資料、不檢查帳戶保證金、不核可執行**；
  無 Pilot / readiness / gate / native execution / sender / 對帳 / Notion / Discord /
  REST / 網路。CH2 與 CH3B2 的行為皆不變。

### 當前可行性（read-only，TASK-014CH4A）

`scripts/run_demo_strategy_current_feasibility.py
--current-market-demo-account-feasibility-read-only` 是一個明確、終端、**唯讀**模式：
CH3 完成的是**歷史綁定**審查，CH4A 則僅**重新驗證當前市場與 Demo 帳戶**。

```bash
python scripts/run_demo_strategy_current_feasibility.py \
  --current-market-demo-account-feasibility-read-only \
  --review-artifact-json final_review.json --review-artifact-sha256 sha256:... \
  --anchor-manifest-json manifest.json --anchor-manifest-sha256 sha256:... \
  --wrapper-json wrapper.json \
  --strategy-symbols-json symbols.json --strategy-symbols-sha256 sha256:... \
  --market-evidence-output-json market_evidence.json \
  --account-evidence-output-json account_evidence.json \
  --feasibility-review-output-json feasibility_review.json \
  --summary-output-json summary.json \
  --allow-real-network
```

- 以**精確位元組 + 外部 SHA256** 釘選受信任的 CH3C2 輸入（Review / Anchor Manifest /
  canonical wrapper / 50 檔標的來源）並交叉驗證 lineage chain。
- 對 50 檔標的收集**當前**公開線性市場價格 + instrument rules，並以**當前價格**用 Decimal
  floor-to-step 重新計算當前可執行數量（**不沿用歷史綁定數量**）。
- 以認證的 **Demo-only 唯讀 GET** 收集錢包 / 持倉 / 帳戶模式證據，證明 Demo 主機並拒絕 Live。
- Decimal 保證金模型：在缺少獨立 initial-margin rate 時**永不判 PASS**（→ `UNAVAILABLE`），
  並保留可設定的安全餘裕。
- 僅 GET 唯讀讀取（無 POST/PUT/PATCH/DELETE、無下單 / 改單 / 撤單 / 槓桿 / 保證金模式 /
  倉位模式變更、無 Live 端點）；不 import 也不呼叫 sender / readiness / gate / native
  execution / Pilot，永不核可或送出訂單。所有 order 計數器恆為 0，Pilot 維持 0/7。
- 輸出四份不可變、atomic、no-clobber 工件（當前市場證據 / Demo 帳戶證據 / 可行性審查 /
  摘要），各含 network audit、credential-leak check、fingerprint。
- **PASS 僅代表「在收集時間點」技術/帳戶可行**；任何後續執行核可前都必須重新收集當前證據。

## 安全性

- `.env`、`.env.demo` 與 credentials YAML 皆列入 `.gitignore`，不進入 Git
- 預設模式為非發送（`order_execution_authorized = False`）
- Demo 執行需明確的每次 session 授權，受保護標的會被拒絕
- Live 交易未實作、未授權
- 詳細架構與安全設計參見 `docs/ARCHITECTURE.md`

## 文件

| 文件 | 說明 |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 系統架構事實來源：資料流、模組對照、價格路徑 |
| [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) | 當前專案狀態：Git、驗證進度、授權狀態 |
| [`docs/archive/README.md`](docs/archive/README.md) | 歷史歸檔索引（2026-H1 任務紀錄，已凍結） |

歸檔的 AI / 任務紀錄為歷史參考，預設不載入。開發歷程請查閱 `git log`。

## 當前狀態

- 30 天 Forward 驗證已啟動（2026-05-18 起，REVIEW_READY）
- 公開 WebSocket 證據收集完成
- Canonical WS-bound plan 產出物已完成，但無整合的下游執行消費者
- Pilot 尚未推進（Demo 執行需額外授權）
- Live 交易未授權
- 倉庫清理進行中（runtime 產出物已 untrack、架構文件已建立）
