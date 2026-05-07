---
name: check-bugs
description: Quickly scan the entire project source tree for bugs, logic errors, and inconsistencies. Combines static analysis (syntax / import / type checks) with parallel semantic review by Explore subagents. Use when the user asks to "check for bugs", "audit the code", "找bug", "檢查程式碼" or similar.
---

# check-bugs — 快速全專案 Bug / 邏輯檢查

目標：在一輪流程內，把整個專案的程式碼從「會炸」(syntax/import) 到「邏輯不一致」(語意層面) 全掃一次，並輸出可行動的修復清單。

## 執行步驟

### 1. 偵測語言與範圍
- 以 `Glob` 找出主要原始碼：`**/*.py`、`**/*.ts`、`**/*.js`、`**/*.go`、`**/*.rs` 等。
- 排除 `__pycache__/`, `node_modules/`, `dist/`, `build/`, `.venv/`, `output/`, `data/`。
- 先用一句話告訴使用者：偵測到 N 個檔案、主要語言是 X，準備開始掃描。

### 2. 平行靜態檢查（Bash）
依語言一次發出多個 Bash call，全部 **平行** 執行：

**Python（本專案）**
- `python -m compileall -q src/ 2>&1` — 抓 SyntaxError
- `python -c "import ast,sys,glob; [ast.parse(open(f,encoding='utf-8').read(),f) for f in glob.glob('src/**/*.py',recursive=True)]"` — 二次語法驗證
- 若專案有 `ruff` / `pyflakes` / `mypy`：呼叫之；沒有就跳過，**不要**自動安裝。
- `python -c "import src.<entrypoint>"` 嘗試載入主模組，抓 ImportError / 循環依賴。

**JS/TS**：`npx --no-install tsc --noEmit`、`npx --no-install eslint .`（同樣若無則略過）。

把每個指令的回傳整理成一行：`[OK] compileall` 或 `[FAIL] ruff: 12 issues`。

### 3. 平行語意審查（Explore subagents）
把原始碼依職責切 3–6 群（例如本專案：`strategies.py`、`backtester.py`、`risk.py + executor*`、`fetcher.py + database.py`、`indicators.py + reporter.py`），對每群 **同時** 開一個 `Explore` subagent，prompt 範本如下：

> 讀完 `<files>`，找出 bug 與邏輯不一致。重點：
> - 邊界條件（空 DataFrame、NaN、除以零、index 錯位、look-ahead bias）
> - 資料型別與單位（價格/數量/槓桿/百分比 vs 小數）
> - 狀態機與 race（持倉方向切換、訂單覆寫、重複下單）
> - 例外處理是否吞錯、log 是否誤導
> - 與註解 / docstring / 函式名宣稱行為不符之處
> 每個發現輸出：`file:line — 問題 — 為什麼是 bug — 建議修法`。少於 250 字，沒發現就回 `clean`。

**重要**：必傳 file 路徑與行號範圍給 subagent，prompt 要自包含 — 不要寫「依先前討論」。

### 4. 量化交易專案的額外檢查清單
本專案是回測 + 即時下單系統，主代理在 review subagent 回傳後，**自己**再檢一輪以下高風險項：
- **Look-ahead bias**：訊號是否用了 `t` 之後才知道的資料（`.shift(-1)`、未 `shift(1)` 的 indicator）。
- **手續費 / 滑價**：是否在 PnL、CAGR、Sharpe 計算中正確扣除。
- **槓桿與部位**：`risk.py`、`executor*` 的倉位上限、爆倉邏輯。
- **時間軸對齊**：tz-naive vs tz-aware、UTC vs local、resample 後的 `closed`/`label`。
- **資料庫一致性**：`trading.db` 寫入是否在交易內、是否有重複 PK。
- **Crypto vs 股票分流**：profile 切換時參數是否真的隔離。

### 5. 彙整輸出（給使用者）
用以下結構回答，**不要**寫成長文：

```
靜態檢查
- [OK/FAIL] 工具 — 摘要

高風險發現（依嚴重度排序）
1. file.py:42 — <問題> — <建議>
2. ...

中/低風險
- ...

無發現的模組
- file_x.py, file_y.py
```

最後加一句：「要我直接修哪幾項？」交給使用者決定，**不要**未經同意就改檔。

## 不要做的事
- 不要安裝任何套件（`pip install`、`npm install`）。
- 不要執行回測 / 真正下單腳本（會動到 `trading.db` 和交易所 API）。
- 不要改檔案，除非使用者在看完報告後明確同意。
- 不要對 `output/`、`data/`、`__pycache__/` 內的檔案做 review。
- 一個 subagent 不要塞超過 ~6 個檔案，避免 read window 溢出。
