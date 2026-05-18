# TASK-008 Workorder — Alpha-Space Concentration Cap

**版本：** v1.0
**建立日期：** 2026-05-17
**建立者：** Claude Sonnet
**Owner：** Claude（工單）→ Codex（實作）
**狀態：** TODO
**預估：** M（3–5 天，包含 backtest 重跑 + attribution）
**優先級：** 長期結構性修復；不擋 30-day forward record 計時；是正式 paper 上線的最終版 baseline

---

## ⛔ 重要聲明

**Paper execution 仍 FORBIDDEN。**
**Live trading 仍 FORBIDDEN。**
本工單只授權研究實作與 backtest 重跑，不授權任何委託提交。

**禁止重做 weight-space 設計。**
Weight cap + redistribution 路徑已由 REVIEW-007b（2026-05-17）正式關閉。
本工單所有變體必須在 alpha-space / 策略層介入，不得在 weight-space 做後處理 overlay。

---

## 1. 背景與動機

### 1a. 集中度問題根源（已由研究確認）

REVIEW-007 揭露 `no_DOT` 悖論：移除最大 alpha 貢獻者（DOT，25%+ net alpha），top5_conc 反從 95.56% **升至 116.13%**。這證明集中度不在任何單一 symbol 的 weight，而在 **alpha-space 結構**：策略持續將最高 momentum score 的 symbol 排在 top_N / bottom_N，導致少數 symbol 長期主導 net alpha。

TASK-007b（REVIEW-007b PASS，2026-05-17）量化驗證：
- cap20% / cap15%：完全 no-op（因 run008 等權 max weight = 12.5%，從不觸發）
- cap10% + redistribution：488 個事件全部 `redistribution_has_no_room`（全 symbol 等權超限）；top5_conc 惡化 +3.3pp（95.56% → 98.69%）

**結論：** 集中度問題在 alpha-space（誰被選入 top_N / bottom_N），不在 weight-space（已是等權）。**TASK-008 必須在 ranking / position selection 層解決。**

### 1b. 介入點（在程式碼中）

關鍵函式：`src/signals/prev3y_momentum.py` → `build_prev3y_targets()`

現行邏輯：
```
scores = _scores(...)          # 3-year momentum score（return or risk_adjusted_return）
scores = scores.sort_values()  # rank by score
longs  = scores.head(top_n)    # top N by score
shorts = scores.tail(bottom_n) # bottom N by score
weights = equal-weight (0.5 / N per side)
```

TASK-008 需要在 **scores 排序 → 選入 top_N / bottom_N** 這一步加入 alpha-space 限制，使某些 symbol 即使 momentum score 最高也可能被排除或降分。

**不得修改：** `_scores()` 函式的輸入計算；`ranking_method`；cost model；backtest engine；benchmark logic；universe/data-quality policy。

---

## 2. 三個必須研究的變體

### Variant A — Rolling Alpha-Contribution Cap（滾動 alpha 貢獻上限）

**核心思路：** 計算每個 symbol 在過去 W 個 rebalance periods 的累積 alpha 貢獻占比（alpha share）。若某 symbol 的 rolling alpha share 超過上限 `max_alpha_share`，則將其從本期 long/short 選擇池中降級（降至選擇 cutoff 以下，或以懲罰因子調整 score）。

**參數範圍：**
- `rolling_window_periods`：6 / 12 / 24（月度 rebalance 對應 6m / 1y / 2y）
- `max_alpha_share`：0.15 / 0.20 / 0.25（rolling 視窗內最大 alpha 貢獻比例）
- `cap_method`：`exclude`（完全排除）/ `penalize`（score 乘以懲罰因子 0.5）

**alpha contribution 的定義（與 TASK-003 attribution 一致）：**
```
period_net_return = sum(position_weight × price_return_after_cost) for all symbols
symbol_net_alpha  = position_weight_i × price_return_after_cost_i
symbol_alpha_share = symbol_net_alpha / sum(abs(all symbol net alphas))
rolling_alpha_share = cumsum(symbol_net_alpha, window) / cumsum(sum_abs_net_alphas, window)
```

**注意：** 此變體需要 rebalance 期間的 historical alpha data，即策略 runner 必須維護一個 rolling buffer。第一個 `rolling_window_periods` 內無歷史資料，使用 base behavior（不施加限制）。

**預期效果：** 長期高 alpha contributor（如 DOT）在累積 alpha 觸上限後，被暫時排出選擇池或降分，使其他 symbol 得以進入，top5_conc 下降。

---

### Variant B — Alpha-Share-Based Position Sizing（alpha 貢獻驅動的持倉大小）

**核心思路：** 不再使用純等權（0.5/N），而是根據「反向 alpha share」調整各 symbol 的 weight，使歷史 alpha 貢獻越大的 symbol weight 越小（回歸均值化）。同時保留 long_net / short_net 在 ±X% 以內。

**公式（建議起點）：**
```
raw_weight_i = 0.5 / N                         # 等權基準
alpha_share_i = rolling alpha share (variant A 同定義)
adjusted_weight_i = raw_weight_i × (1 - clamp(alpha_share_i, 0, max_alpha_share))
adjusted_weight_i = renormalize so Σ|long_side| = 0.5, Σ|short_side| = 0.5
```

**參數範圍：**
- `rolling_window_periods`：12 / 24
- `max_alpha_share`（懲罰觸發閾值）：0.20 / 0.25
- `sizing_floor`：0.0（允許趨近 0）/ `1/(2N)`（最低保留半個等權份額）

**預期效果：** 高 alpha contributor 的 weight 被壓低，允許其仍被選入 top_N / bottom_N，但持倉比重降低。比 Variant A 更漸進，alpha retention 較高。**Trade-off：可能使 Sharpe 略降，但 top5_conc 下降更平滑。**

---

### Variant C — Top Contributor Cooldown / Blacklist（冷卻期排除）

**核心思路：** 若某 symbol 在過去連續 K 個 rebalance periods 均被選入 top_N（多頭貢獻者）或 bottom_N（空頭貢獻者），則強制進入冷卻期（排除出選擇池）M 個 periods。冷卻結束後自動解除。

**參數範圍：**
- `consecutive_periods_trigger`：3 / 6 / 12（連續 K 期觸發冷卻）
- `cooldown_periods`：2 / 3 / 6（排除 M 期）
- `side_independent`：True（多頭多頭算、空頭空頭算）/ False（合計出現次數）

**邏輯：**
```python
# 維護 per-symbol 計數器
if symbol in top_N for K consecutive periods:
    blacklist[symbol] = cooldown_periods  # 排除下 M 次 rebalance
# 每次 rebalance 後 counter -1
blacklist = {s: v-1 for s, v in blacklist.items() if v > 1}
```

**注意：** 此機制在冷卻期間內如果 universe 很小（如初期 2024-04 只有 8 symbol），必須有 fallback：若剩餘 eligible symbol < min_eligible（例如 `top_n + 2`），則忽略 blacklist，恢復全量選擇。這是為了防止在 universe 極小時空手。

**預期效果：** 最激進的集中度控制。DOT 被選入 30+ 期後，強制退出 2–3 期，讓其他 symbol 有機會進入。**Trade-off：可能使 tracking error 升高、增加 turnover。**

---

## 3. 新建檔案

```
src/variants/task008.py            # 三個變體的實作（不修改 prev3y_momentum.py 主流程）
scripts/task008_alpha_conc_cap.py  # 驅動腳本，輸出所有變體的 backtest + comparison
```

### `src/variants/task008.py` 介面設計（建議）

```python
def apply_alpha_contribution_cap(
    targets: list[TargetPortfolio],
    baseline_returns: pd.DataFrame,          # 歷史日報酬（來自既有 backtest CSV）
    variant: str,                            # "A_rolling_cap" | "B_alpha_sizing" | "C_cooldown"
    rolling_window_periods: int = 12,
    max_alpha_share: float = 0.20,
    cap_method: str = "exclude",             # A-only
    sizing_floor: float = 0.0,              # B-only
    consecutive_periods_trigger: int = 6,   # C-only
    cooldown_periods: int = 3,              # C-only
    min_eligible: int = 5,                  # C-only fallback
) -> list[TargetPortfolio]:
    """
    Returns a modified list of TargetPortfolio with weights/selections adjusted.
    Does NOT modify prev3y_momentum.py.
    """
    ...
```

**重要：** `apply_alpha_contribution_cap()` 只接受 `targets`（已由 `build_prev3y_targets()` 生成），在其上做 post-selection 調整。這樣可以最小化對主流程的侵入，且對 cost model / backtest engine 完全透明。

---

## 4. 比較維度（Comparison Metrics）

所有變體必須使用 **active 口徑**（gross_exposure > 0 的 760 天，2024-04-01 至 2026-04-30）計算，與 baseline 一致。

| 指標 | 計算方式 | 歷史 baseline 參考 | 目標方向 |
|---|---|---|---|
| `sharpe` | 同 TASK-001a 公式（annualization=365.25，ddof=1） | 0.9267 | 盡量接近；容忍 ≥ 0.70 |
| `ir_vs_eqw` | net return - equal-weight benchmark return，÷ tracking error | 0.7227 | 盡量接近 |
| `max_dd` | equity curve drawdown | −19.50% | 不大幅惡化（< −25%）|
| `net_alpha_pct` | cumulative net return after cost（active days） | 28.53% | 不大幅惡化（> 20%）|
| `top5_conc_pct` | sum of top 5 symbol abs net alpha / total abs net alpha（attribution 口徑） | 95.56% | **顯著降低（目標 < 75%）** |
| `single_conc_max_pct` | max single symbol abs net alpha share（attribution 口徑） | ~25%（DOT） | **< 25%（硬性目標）** |
| `long_net_pct` | cumulative long-side net alpha | −5.10% | 改善（目標 > −5%，或至少不惡化）|
| `short_net_pct` | cumulative short-side net alpha | +33.65% | 維持（不大幅降低）|
| `alpha_retention_pct` | variant net alpha / baseline net alpha × 100 | 100%（baseline）| ≥ 85% |
| `cost_impact_bps` | variant total cost (bps) - baseline total cost (bps) | 0（baseline）| 增加 < 30 bps（年化）|
| `turnover_change_x` | variant annual turnover / baseline annual turnover | 1.0（baseline）| ≤ 1.5×（不超過 50% 額外 turnover）|

**注意：** `top5_conc_pct` 和 `single_conc_max_pct` 使用 **attribution 口徑**（alpha contribution share），而非 weight 口徑，與 TASK-003 attribution 一致。

---

## 5. 輸出檔案

```
outputs/variants/prev3y_crypto/
├── <YYYYMMDD>_task008_comparison.json          # 所有變體 × 指標的 comparison table
├── <YYYYMMDD>_task008_comparison.csv           # 同上，CSV 格式
├── <YYYYMMDD>_task008_A_baseline.csv           # Variant A 日報酬 / 持倉 CSV
├── <YYYYMMDD>_task008_B_baseline.csv           # Variant B 日報酬 / 持倉 CSV
├── <YYYYMMDD>_task008_C_baseline.csv           # Variant C 日報酬 / 持倉 CSV
└── <YYYYMMDD>_task008_attribution.json         # 每個變體的 top5 / single_conc attribution

outputs/logs/prev3y_crypto/
└── <YYYYMMDD>_task008_alpha_conc.log

docs/research/review_packets/
├── REVIEW-008_PACKET.md
└── REVIEW-008_NUMBERS.json
```

---

## 6. Fail Gates（觸發任何一條 → TASK-008 FAIL，不得提交 REVIEW-008）

| Gate | 觸發條件 |
|---|---|
| F-1 | baseline reconciliation 失敗：任何變體的 no-cap 設定（max_alpha_share=1.0）與原始 baseline 的 net return 差異 > 1e-10 |
| F-2 | `paper_execution_status` 或 `live_trading_status` 不為 `FORBIDDEN` |
| F-3 | weight-space overlay 程式碼存在（在 task008.py 或 task008 腳本中）—— 僅允許 alpha-space 介入 |
| F-4 | `prev3y_momentum.py` 主流程被修改（task008 變體只可在 `apply_alpha_contribution_cap()` post-process） |
| F-5 | attribution 口徑與 TASK-003 公式不一致（annualization / ddof 偏離）|
| F-6 | 任何變體的 `top5_conc_pct > 100%`（即負 alpha 導致分母計算錯誤，需 debug）|
| F-7 | missing_outputs：comparison table / attribution / log / review packet 任一缺失 |
| F-8 | 重現性 hash 無法由輸入計算重現（reproducibility check FAIL）|

---

## 7. Warning Gates（記錄，不擋 REVIEW-008）

| Gate | 觸發條件 |
|---|---|
| W-1 | 所有變體的 `top5_conc_pct` 均 > 75%（目標未達成，需在 review 中解釋）|
| W-2 | 任何變體的 `sharpe < 0.70`（Sharpe 代價過大）|
| W-3 | 任何變體的 `alpha_retention_pct < 85%`（alpha 保留不足）|
| W-4 | 任何變體的 `turnover_change_x > 1.5`（turnover 過度增加）|
| W-5 | Variant C cooldown 導致某 rebalance 日 eligible symbol < min_eligible（記錄 fallback 次數）|
| W-6 | `long_net_pct < -10%`（多頭虧損惡化）|
| W-7 | `cost_impact_bps > 30`（成本代價過高）|
| W-8 | universe size 不足（early period 2024-04 < 10 symbols）導致 cap 機制頻繁 fallback（記錄比例）|

---

## 8. Red Lines（不得觸碰）

**以下任何操作均構成工單違反，Codex 必須停止並回報：**

1. 修改 `src/signals/prev3y_momentum.py` 的 `_scores()`、`build_prev3y_targets()` 主邏輯
2. 修改 `ranking_method` 的計算方式
3. 修改 `src/backtest/long_short.py`（backtest engine）
4. 修改 `src/attribution/` 任何既有函式（只可新增呼叫）
5. 修改 `src/costs/` 任何既有函式
6. 修改 `configs/prev3y_crypto.yaml`（只可在腳本 CLI 中 override 參數）
7. 新增任何 weight-space overlay（e.g., 再次嘗試 cap + redistribution）
8. 連接任何 exchange API
9. 建立 paper_trading / live_trading 相關程式碼
10. 修改官方 baseline outputs（`outputs/backtests/prev3y_crypto/20260513_run008_*`、`20260515_cost_stress_*`）

---

## 9. 參數格點（建議起點，Codex 可依結果調整）

Codex 至少應測試以下組合，在 review packet 中列出全部結果：

### Variant A
| rolling_window_periods | max_alpha_share | cap_method |
|---|---|---|
| 12 | 0.20 | exclude |
| 12 | 0.25 | exclude |
| 12 | 0.20 | penalize (×0.5) |
| 24 | 0.20 | exclude |

### Variant B
| rolling_window_periods | max_alpha_share | sizing_floor |
|---|---|---|
| 12 | 0.20 | 0.0 |
| 12 | 0.25 | 1/(2N) |
| 24 | 0.20 | 0.0 |

### Variant C
| consecutive_periods_trigger | cooldown_periods | side_independent |
|---|---|---|
| 6 | 3 | True |
| 6 | 2 | True |
| 12 | 3 | True |
| 3 | 2 | False |

**最終 REVIEW-008 只需比較每個 Variant 的 best-parameter 配置（由 Codex 判斷「最佳」= 集中度 + Sharpe 最平衡）。**

---

## 10. 歷史基準數字（Codex 比較用）

| 指標 | Baseline（active 口徑） | Combined Paper Safe Variant |
|---|---|---|
| Sharpe | 0.9267 | 0.80 |
| IR vs eqw | 0.7227 | — |
| Max DD | −19.50% | — |
| Net alpha | 28.53% | — |
| top5_conc（attribution） | 95.56% | — |
| single_conc max（attribution） | ~25.45%（DOT） | 19.73%（DOT cap via overlay）|
| long_net | −5.10% | +4.21% |
| short_net | +33.65% | — |
| Alpha retention | 100%（baseline）| — |
| cap10 top5_conc | 98.69%（惡化）| — |

**TASK-008 目標：在 Sharpe ≥ 0.70 的前提下，top5_conc < 75%，single_conc < 25%。**

---

## 11. Review 要求

TASK-008 完成後產出 `REVIEW-008_PACKET.md` + `REVIEW-008_NUMBERS.json`，由 **Opus 做 final review**（REVIEW-008）。

Opus REVIEW-008 應判斷：
1. 是否有至少一個變體達到目標（top5_conc < 75% 且 Sharpe ≥ 0.70）
2. 推薦哪個變體作為新 baseline（取代 `combined_paper_safe_variant` 作為正式 paper 版本）
3. 若無任何變體達到目標，是否有其他 alpha-space 設計方向值得探索

TASK-008 DONE 後，使用 Opus 推薦的新 baseline 重跑 `scripts/run_prev3y_crypto_baseline.py`，更新官方 baseline。此新 baseline 為正式 paper trading 上線版本（需 Opus REVIEW-008 明確 PASS + Rick 批准）。

---

## 12. 與其他任務的關係

| 任務 | 關係 |
|---|---|
| TASK-006（paper trading plan）| TASK-008 完成後的新 baseline 才是正式版；TASK-006 現有的 combined_paper_safe_variant 是「過渡版」|
| TASK-007b（weight cap）| 路徑已關閉，不得重做；TASK-008 是替代路徑 |
| TASK-007c（variant C threshold）| 獨立 sensitivity 分析，不擋 TASK-008；可並行 |
| 30-day forward record | 與 TASK-008 並行進行；forward record 用 combined_paper_safe_variant；TASK-008 完成後可切換 baseline |
| REVIEW-006b | 可在 30-day record 完成後啟動（不等 TASK-008）；TASK-008 完成後有更好的 baseline 可進 REVIEW-008 |

---

## 13. Codex 回報格式

完成後請回報：

```
TASK-008 完成。

best variant: <A / B / C>
best params: <parameter set>
top5_conc_pct: <值>
single_conc_max_pct: <值>
sharpe: <值>
alpha_retention_pct: <值>

所有變體 comparison: <comparison.json 路徑>
reproducibility_hash: <hash>
paper_execution_status: FORBIDDEN
live_trading_status: FORBIDDEN
```

---

*本工單不授權任何 paper execution 或 live trading。*
*所有程式碼修改限於 `src/variants/task008.py` 和 `scripts/task008_alpha_conc_cap.py`。*
*官方 baseline 不得修改，直到 Opus REVIEW-008 明確 PASS。*
