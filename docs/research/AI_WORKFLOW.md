# AI Workflow — Quant Cowork 多模型分工守則

最後更新：2026-05-12
維護者：Rick
狀態：v1.0（草稿，會隨工具增加調整）

---

## 0. 為什麼需要這份文件

本量化研究專案會同時用到 Claude、Codex、ChatGPT、Ollama、Notion 五個 AI / 平台。
如果沒有清楚的分工，會發生：

- 同一份策略被不同模型同時改，產生衝突版本。
- Codex 改了程式、沒人審查就直接跑回測，未來視 / 過擬合很難被發現。
- 研究紀錄散在各個 chat 視窗，半年後完全無法回溯。
- 重要決策（universe 定義、cost 假設等）變成「某次 chat 裡講過」的口頭協議。

這份 workflow 的目標：**每個工具只做它最擅長且最不會出包的事，並且每一個研究產出都有審查與紀錄。**

---

## 1. 工具職責一覽

| 工具 | 角色 | 主要產出 | 不可做 |
|---|---|---|---|
| Claude（本工具） | 研究審查官 + 任務總管 | 審查意見、任務 queue、未來視 / 過擬合檢查、文件 | 不直接改策略程式、不跑回測 |
| Codex | 工程執行者 | 程式碼、回測 CSV、dashboard、monitor | 不自己決定策略邏輯方向、不審查自己跑出來的結果 |
| ChatGPT | 方向討論夥伴 | 想法討論、決策建議、weekly 反思 | 不寫 production code、不替代研究審查 |
| Ollama（本地） | 低成本 log / 文字摘要 | 大量 log 摘要、長文壓縮、敏感資料前處理 | 不做精細推理、不做數學驗算 |
| Notion | 研究知識庫 | 研究紀錄、高層摘要、決策紀錄 | 不存原始程式碼、不存大檔 CSV |

---

## 2. 各工具詳細職責

### 2.1 Claude（研究審查 + 任務總管）

**職責**

- 審查 Codex 跑出來的回測結果、attribution、stress test。
- 主動找未來視（look-ahead bias）、survivorship bias、過擬合、資料對齊錯誤。
- 維護兩個 queue：`CODEX_TASK_QUEUE.md`、`CLAUDE_REVIEW_QUEUE.md`。
- 撰寫每個研究任務的「驗收標準」與「禁止修改範圍」。
- 把研究結論整理成可貼到 Notion 的摘要。

**禁止事項**

- 不直接修改 `strategies/`、`backtest/`、`data/` 底下的核心策略程式。
- 不自行跑回測（避免結果與 Codex 不一致而失去交叉驗證價值）。
- 不在沒有看到實際數據 / log 的情況下下結論。
- 不在沒有獲得 Rick 確認前，把任務狀態從 "review" 改成 "accepted"。

**Claude 的標準動作**

1. 收到 Codex 產出 → 看輸入 / 輸出檔案 → 跑 sanity check 清單。
2. 找出可疑點 → 列在 `CLAUDE_REVIEW_QUEUE.md` 對應條目下。
3. 給 Rick 一份「Pass / Conditional / Fail + 理由 + 建議下一步」。
4. 若需要 Codex 補資料，把補資料任務寫進 `CODEX_TASK_QUEUE.md`。

### 2.2 Codex（工程執行者）

**職責**

- 依照 `CODEX_TASK_QUEUE.md` 的條目寫程式、修 bug、跑回測。
- 嚴格遵守每個任務的「輸入檔案」「輸出檔案」「禁止修改範圍」。
- 產出格式固定的 CSV / parquet / log，以便 Claude 審查。
- 修 bug 時必須附 minimal reproduction 與 diff。

**禁止事項**

- 不自行擴大任務範圍（例如「順便重構一下 universe 模組」）。
- 不在沒有 Claude review 通過前，把實驗分支 merge 回 main。
- 不刪除歷史回測結果，只能新增帶日期的版本。
- 不在策略邏輯上自行做「優化」（例如改參數、加 filter），這屬於研究決策。

### 2.3 ChatGPT（方向討論）

**職責**

- 跟 Rick 討論「下一步要不要做 X」「這個假設值不值得驗證」。
- 幫 Rick 做 weekly 反思、把混亂的想法整理成研究問題。
- 在 Claude 審查意見出來後，幫 Rick 想「要怎麼回應」。

**禁止事項**

- 不寫會直接 commit 進 repo 的程式碼。
- 不做正式的 review（沒有完整 context，會產生不可信的結論）。
- 不取代 Notion 作為紀錄載體（chat 會消失）。

### 2.4 Ollama（本地低成本摘要）

**職責**（之後啟用）

- 摘要 VPS bot 的大量 log。
- 把長篇 paper / 文件壓成 1–2 段重點，交給 Claude 做精細審查。
- 對含敏感資訊（API key、帳號）的內容先做本地清洗。

**禁止事項**

- 不做數學驗算、不做策略邏輯判斷。
- 不寫進 Notion 的官方摘要（要經 Claude 改寫）。

### 2.5 Notion（研究知識庫）

**職責**（之後啟用）

- 存放每個研究任務的高層摘要（Why / What / Result / Decision）。
- 紀錄重要決策：universe 定義、cost 假設、risk budget 等。
- 連結到 repo 內的詳細 CSV / log（不複製內容過去）。

**禁止事項**

- 不存程式碼原始檔。
- 不存大型 CSV（>1MB 留在 repo / 雲端硬碟）。
- 不放未審查通過的回測結果（避免被未來的自己誤信）。

---

## 3. 標準研究流程（SOP）

每一個新的研究想法都應該走這條 pipeline：

```
[ChatGPT / Rick]         [Claude]              [Codex]              [Claude]            [Rick + Notion]
   想法 / 假設    →  寫成任務卡（含驗收）  →  寫程式 / 跑回測  →  審查 + 找 bias  →  決策 + 歸檔
```

具體步驟：

1. **發想（ChatGPT 或 Rick 自己）**
   產出一句話假設，例如：「Prev3Y momentum 在 crypto universe 上 IR 應該 > 0.5。」

2. **任務化（Claude）**
   Claude 把假設展開成 `CODEX_TASK_QUEUE.md` 的一筆任務，包含：
   - 目的、重要性、Owner、輸入、輸出、驗收、禁改範圍。

3. **執行（Codex）**
   Codex 依任務卡執行，不擴張範圍。產出固定路徑的 CSV / log。

4. **審查（Claude）**
   - 跑 sanity check：時間對齊、資料分布、極端值、未來視。
   - 寫進 `CLAUDE_REVIEW_QUEUE.md` 對應條目。
   - 結論 Pass / Conditional / Fail。

5. **決策（Rick）**
   - 看 Claude 的審查意見，決定 accept / reject / re-run。
   - Accept 之後寫進 Notion 高層摘要。

> **不可跳步**。特別是「執行 → 決策」中間一定要有 Claude 的審查，否則容易發生「Codex 寫的程式自己跑、自己驗、自己加 filter」的封閉迴圈。

---

## 4. 檔案與命名約定

- 所有研究文件放在 `docs/research/`。
- 每個研究任務有自己的目錄：`docs/research/<task_slug>/`。
- 回測結果 CSV：`outputs/backtests/<task_slug>/<YYYYMMDD>_<desc>.csv`。
- Log：`outputs/logs/<task_slug>/<YYYYMMDD>.log`。
- 一旦命名，**不可覆寫**，新版本另開日期。

---

## 5. 目前 repo 狀態（2026-05-12）

- repo 內目前只有 `src/__init__.py` + `.venv`，**策略程式尚未存在**。
- 因此 `CODEX_TASK_QUEUE.md` 中所列的「輸入檔案」「禁止修改範圍」多為「規劃路徑」，由 Codex 在執行任務時建立。
- 一旦核心模組（universe、data loader、backtester、cost model）建好，這份文件中的「禁止修改範圍」會被加上實際檔案路徑。

---

## 6. 衝突 / 例外處理

- **Codex 想改策略邏輯**：擋下來，先進 ChatGPT 討論 → 走完上面 SOP。
- **Claude 找到嚴重 bias**：對應任務狀態改成 `BLOCKED`，停止任何 downstream 使用。
- **跨工具結論不一致**：以「實際跑出來、Claude 審查通過」的結果為準。chat 內的口頭結論不算數。
- **Rick 趕時間想跳審查**：允許，但要在 Notion 標 `unaudited`，且不可拿去做真錢交易決策。

---

## 7. 待辦（v1.0 後續）

- [ ] Ollama 啟用時補上 log 摘要的標準 prompt。
- [ ] Notion 資料庫 schema 草案（Research Log / Decision Log / Bias Catalogue）。
- [ ] 每月一次 workflow retro，看看哪個工具被誤用。
- [ ] 核心模組建好後，回填 `CODEX_TASK_QUEUE.md` 內各任務的「禁止修改範圍」實際檔案路徑。
