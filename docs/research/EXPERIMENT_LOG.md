# 量化策略實驗紀錄

本文件用來持續追加每次研究測試的結果。每次實驗請保留完整背景、命令、參數、主要指標與結論，避免只記錄「最好的數字」。

## 固定紀錄規則

每一筆實驗都必須明確記錄：

1. 沒改什麼：例如「本次只改成本模型，不改策略訊號、進出場條件、倉位管理」。
2. 通過標準：例如 PF > 1.2、Sharpe 不低於 0.7、MDD 不超過 -50%、Calmar 不能明顯惡化。
3. 結論只能是三選一：保留、淘汰、需要更多測試。

若缺少任一項，該實驗紀錄視為不完整，不能用來決定策略是否升級。

## 紀錄格式

```markdown
## YYYY-MM-DD - 實驗名稱

- 狀態：待測 / 已完成 / 失敗 / 暫停 / 需重測
- 研究問題：
- 假設：
- 測試區間：
- 資產範圍：
- 起始資金：
- 程式版本 / commit：
- 修改範圍：
- 不變條件：
- 沒改什麼：
- 通過標準：
- 結論：保留 / 淘汰 / 需要更多測試
- 執行命令：
- 輸出檔案：

### 結果

| 情境 | 總報酬 | 年化 | 最大回撤 | PF | Sharpe | Calmar | 勝率 | 平均 R | 交易數 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|

### 觀察

- 

### 結論

- 

### 後續動作

- 
```

## 2026-05-07 - Crypto OOS 基準確認

- 狀態：已完成
- 研究問題：目前 Crypto 策略在 walk-forward OOS 是否仍有正邊際？
- 假設：若策略有基本優勢，OOS 應維持 PF > 1.2，Sharpe 接近或高於 0.8，且不是只靠交易次數堆出報酬。
- 測試區間：2024-05-01 至 2026-05-07
- 資產範圍：Crypto-only
- 起始資金：10,000 USD
- 程式版本 / commit：v1.13 研究基準；最新紀錄 commit 為 `573cb3c docs: v1.13 - walk-forward validation establishes OOS as truth`
- 修改範圍：無
- 不變條件：策略訊號、成本模型、資產池、倉位邏輯皆維持目前基準
- 執行命令：

```powershell
python main.py backtest --profile Crypto `
  --start-date 2024-05-01 --end-date 2026-05-07 `
  --output output\v113_crypto_OOS.xlsx --note v1.13_crypto_OOS
```

- 輸出檔案：`output/v113_crypto_OOS.xlsx`

### 結果

| 情境 | 總報酬 | 年化 | 最大回撤 | PF | Sharpe | Calmar | 勝率 | 平均 R | 交易數 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Crypto OOS 基準 | +87.17% | +36.49% | -43.01% | 1.346 | 0.930 | 0.848 | 43.81% | +0.035 | 226 |

### 觀察

- OOS 仍有正期望，PF 1.346 可接受。
- Sharpe 接近 1，但 Calmar 未達 1，最大回撤偏深。
- 平均 R 僅 +0.035，代表策略邊際偏薄，對成本與成交假設敏感。
- IS 勝率約 54% 降至 OOS 約 44%，仍有過度擬合跡象。

### 結論

- 策略暫時可視為「可能有優勢，但需要壓力測試」。
- 不應以 5 年連續回測作為主要宣稱數字。
- 下一步優先檢查成本、K 棒路徑、策略模組拆解與 point-in-time universe。

### 後續動作

- 執行成本壓力測試。
- 執行 TP-first / SL-first / Conservative K 棒路徑測試。
- 建立 ablation 測試腳本。

## 2026-05-07 - Crypto 成本壓力測試

- 狀態：已完成
- 研究問題：當 TP 成交、滑價與 funding cost 更接近保守實盤假設時，策略是否仍有正邊際？
- 假設：如果策略優勢穩健，較嚴格成本下 PF 應仍大於 1，且年化報酬仍為正。
- 測試區間：2024-05-01 至 2026-05-07
- 資產範圍：Crypto-only
- 起始資金：10,000 USD
- 程式版本 / commit：本地工作區，新增成本壓力測試開關與腳本
- 修改範圍：僅成本模型與測試腳本；未修改策略訊號
- 不變條件：策略指標、進出場訊號、資產池、倉位邏輯維持不變
- Funding 假設：每日名目成本 0.03%
- 執行命令：

```powershell
python scripts\crypto_cost_stress.py --output output\crypto_cost_stress.csv
```

- 輸出檔案：`output/crypto_cost_stress.csv`

### 結果

| 情境 | 總報酬 | 年化 | 最大回撤 | PF | Sharpe | Calmar | 勝率 | 平均 R | 交易數 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A 目前設定 | +87.17% | +36.49% | -43.01% | 1.346 | 0.930 | 0.848 | 43.81% | +0.035 | 226 |
| B TP taker + TP market slippage | +85.22% | +35.78% | -43.07% | 1.340 | 0.919 | 0.831 | 43.81% | +0.032 | 226 |
| C 總滑價 0.2% | +93.84% | +38.88% | -41.77% | 1.384 | 0.971 | 0.931 | 42.58% | -0.003 | 209 |
| D 總滑價 0.3% | +73.62% | +31.49% | -43.40% | 1.304 | 0.846 | 0.726 | 42.31% | -0.019 | 208 |
| E funding cost | +56.86% | +25.03% | -47.37% | 1.254 | 0.754 | 0.528 | 40.28% | -0.055 | 211 |
| F 最悲觀組合 | +37.42% | +17.09% | -48.96% | 1.172 | 0.592 | 0.349 | 40.28% | -0.090 | 211 |

### 觀察

- A 情境對齊既有 Crypto OOS 基準。
- B 情境影響不大，代表 TP maker/taker 差異不是最大風險。
- C 情境反而改善，應視為 path-dependent 現象：成本影響淨損益後，改變 SYM 勝率濾網、Kelly 或熔斷路徑，少做部分後續交易；不可解讀為滑價有利。
- D 情境仍維持 PF 1.304，但 Sharpe 與 Calmar 下降。
- Funding 是最大壓力來源，E 與 F 明顯壓低 Sharpe、Calmar 與平均 R。

### 結論

- 策略在 0.3% 總滑價下仍有正邊際，但風險效率下降。
- 加入 funding 後，策略仍為正報酬，但平均 R 轉負，顯示原始邊際不足以舒適吸收持倉成本。
- 最悲觀組合仍 PF > 1，但 Calmar 僅 0.349，不適合作為可實盤承受狀態。

### 後續動作

- 拆解 funding cost 對不同持倉天數與不同子策略的影響。
- 檢查 BB / VP / trend 哪一類交易最容易被 funding 吃掉。
- 做 K 棒路徑測試，確認成交模型沒有額外樂觀偏差。

## EXP-001 - 成本壓力測試：TP taker + 滑價提高 + funding 假設

## 日期

2026-05-07

## 測試目的

確認目前 Crypto 策略是否只是受惠於過度樂觀的成本假設。

## 修改範圍

- 修改成本模型
- 不修改策略訊號
- 不修改進出場條件
- 不修改倉位管理

## 沒改什麼

- 沒有修改策略訊號。
- 沒有修改進出場條件。
- 沒有修改倉位管理。
- 沒有修改資產池。
- 沒有新增策略指標。

## 通過標準

- Stress A：PF 需維持大於 1.20，Sharpe 不低於 0.70，MDD 不超過 -50%，Calmar 不可明顯惡化。
- Stress B：PF 需維持大於 1.15，年化報酬需為正，MDD 不超過 -50%。
- Stress C：PF 需大於 1.05，總報酬需為正，若 Calmar 低於 0.50 則不得視為可放大策略。
- 若加入 funding 後平均 R 轉負，結論不得直接寫「保留」，至少需列為「需要更多測試」。

## 測試設定

| 情境 | Entry Fee | Exit Fee | Slippage | Funding |
|---|---:|---:|---:|---:|
| Baseline | 原設定 | 原設定 | 原設定 | 無 |
| Stress A | taker | taker | 0.1% | 無 |
| Stress B | taker | taker | 0.2% | 每日名目 0.03% |
| Stress C | taker | taker | 0.3% | 每日名目 0.03% |

## 結果

| 情境 | 總報酬 | 年化 | MDD | PF | Sharpe | Calmar | 勝率 | 平均 R | 交易數 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | +87.17% | +36.49% | -43.01% | 1.346 | 0.930 | 0.848 | 43.81% | +0.035 | 226 |
| Stress A | +85.22% | +35.78% | -43.07% | 1.340 | 0.919 | 0.831 | 43.81% | +0.032 | 226 |
| Stress B | +46.07% | +20.69% | -48.20% | 1.209 | 0.667 | 0.429 | 40.28% | -0.074 | 211 |
| Stress C | +37.42% | +17.09% | -48.96% | 1.172 | 0.592 | 0.349 | 40.28% | -0.090 | 211 |

## 結論

需要更多測試。

策略不是完全靠 TP maker 或低滑價才成立；Stress A 幾乎沒有破壞績效。但加入 funding 後，平均 R 轉負、Sharpe 與 Calmar 明顯下降，代表目前 Crypto 策略的優勢很薄，持倉成本是主要風險。Stress B / C 仍維持 PF > 1，但 Calmar 已低於 0.5，不適合作為可直接放大的實盤狀態。

## 下一步

- 拆解 funding cost 對 trend、VP、BB 各子策略的影響。
- 統計 funding 成本與持倉天數的關係，確認是否需要縮短特定類型交易的持有期。
- 接續執行 TP-first / SL-first / Conservative K 棒路徑測試，確認成交路徑沒有額外樂觀偏差。

## EXP-002 - TP-first / SL-first / Conservative K棒路徑測試

## 日期

2026-05-07

## 測試目的

確認目前 Crypto 日線回測是否受惠於同一根 K 棒同時觸及 TP 與 SL 時的 TP-first 假設。

## 修改範圍

- 修改回測成交路徑測試開關
- 不修改策略訊號
- 不修改成本模型
- 不修改進出場條件
- 不修改倉位管理

## 沒改什麼

- 沒有修改策略訊號。
- 沒有修改技術指標。
- 沒有修改進出場條件。
- 沒有修改倉位管理。
- 沒有修改資產池。
- 沒有修改成本假設。

## 通過標準

- Conservative 模式下 PF 需大於 1.15。
- SL-first 模式下策略不得由正期望轉為明顯負期望。
- MDD 不應超過 -50%。
- Calmar 不應相對基準明顯惡化。
- 同根 TP/SL 衝突交易不得貢獻超過總 PnL 的 20%。

## 測試設定

| 情境 | 同根 K 棒 TP/SL 衝突解析 | 成本 | Funding |
|---|---|---|---|
| TP-first | 先視為 TP 成交 | 原設定 | 無 |
| SL-first | 先視為 SL 成交 | 原設定 | 無 |
| Conservative | 採對策略不利方向，本測試等同 SL-first | 原設定 | 無 |

## 執行命令

```powershell
python scripts\crypto_intrabar_path_stress.py --output output\crypto_intrabar_path_stress.csv
```

## 輸出檔案

- `output/crypto_intrabar_path_stress.csv`

## 結果

| 情境 | 總報酬 | 年化 | MDD | PF | Sharpe | Calmar | 勝率 | 平均 R | 交易數 | 衝突交易數 | 衝突 PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TP-first | +87.17% | +36.49% | -43.01% | 1.346 | 0.930 | 0.848 | 43.81% | +0.035 | 226 | 8 | +3449.77 |
| SL-first | +77.90% | +33.09% | -53.72% | 1.356 | 0.911 | 0.616 | 42.00% | +0.011 | 200 | 6 | +2289.37 |
| Conservative | +77.90% | +33.09% | -53.72% | 1.356 | 0.911 | 0.616 | 42.00% | +0.011 | 200 | 6 | +2289.37 |

## 結論

需要更多測試。

SL-first / Conservative 下策略仍維持正報酬與 PF > 1.15，代表策略不是完全靠 TP-first 才成立。但最大回撤惡化到 -53.72%，超過本次通過標準；TP-first 的同根衝突交易 PnL 也偏高，表示日線 OHLC 成交路徑仍可能高估風險效率。此結果不能支持直接保留目前成交假設。

## 下一步

- 拆出同根 TP/SL 衝突交易清單，確認主要來自哪個策略、哪幾個幣、哪幾段行情。
- 補做 Open-proximity heuristic 或更保守的「同根衝突直接跳過進場/出場」測試。
- 若可取得較低週期資料，優先用 4H 或 1H 只驗證衝突交易的日內路徑，不新增策略訊號。

## EXP-003 - 策略 ablation 訊號拆解測試

## 日期

2026-05-07

## 測試目的

拆解目前 Crypto 策略中 Supertrend、VP POC、Bollinger、BTC moat、symbol rolling winrate、geometric RR 與 EMA score 的貢獻，確認哪些模組提供穩定 edge，哪些可能只是過度擬合。

## 修改範圍

- 新增 ablation 測試腳本。
- 只改測試用訊號/濾網開關。
- 不修改原始策略參數。

## 沒改什麼

- 沒有新增策略指標。
- 沒有修改原始策略參數。
- 沒有修改成本設定。
- 沒有修改倉位管理。
- 沒有修改資產池。
- 沒有修改 OOS 切點。

## 通過標準

- OOS PF 需大於 1.15。
- OOS Sharpe 不低於 0.70。
- OOS MDD 不超過 -50%。
- OOS Calmar 不可明顯惡化。
- rolling OOS 不可只有單一年份有效；rolling PF 應盡量全數大於 1。
- 若單一模組 OOS PF < 1，該模組不得視為穩定 edge。

## 測試設定

| Variant | 說明 |
|---|---|
| baseline | 全部開啟 |
| supertrend_only | 只開 Supertrend raw signal |
| vp_only | 只開 VP POC raw signal |
| bb_only | 只開 Bollinger raw signal |
| no_btc_moat | baseline 關閉 BTC moat |
| no_symbol_wr | baseline 關閉 symbol rolling winrate |
| no_geometric_rr | baseline 關閉 geometric RR |
| supertrend_btc | 只保留 Supertrend + BTC moat |
| supertrend_ema | 只保留 Supertrend + EMA score |
| vp_bb | 只保留 VP + BB |

## 執行命令

```powershell
python scripts\crypto_ablation.py --output output\crypto_ablation.csv
```

## 輸出檔案

- `output/crypto_ablation.csv`
- `docs/research/experiment_results.csv`

## OOS 結果

| Variant | PF | Sharpe | Calmar | MDD | 勝率 | 平均 R | 交易數 | 總報酬 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 1.346 | 0.930 | 0.848 | -43.01% | 43.81% | +0.035 | 226 | +87.17% |
| supertrend_only | 0.757 | -0.500 | -0.378 | -61.55% | 36.49% | -0.193 | 211 | -41.35% |
| vp_only | 0.734 | -1.318 | -0.558 | -62.61% | 42.50% | -0.085 | 480 | -57.98% |
| bb_only | 1.110 | 0.481 | 0.364 | -30.70% | 68.30% | +0.016 | 224 | +23.79% |
| no_btc_moat | 1.292 | 0.884 | 0.680 | -49.46% | 45.26% | +0.045 | 232 | +79.38% |
| no_symbol_wr | 1.266 | 0.799 | 0.587 | -48.76% | 43.06% | +0.017 | 346 | +66.11% |
| no_geometric_rr | 1.274 | 0.860 | 0.621 | -50.99% | 41.45% | -0.016 | 234 | +74.08% |
| supertrend_btc | 0.873 | -0.100 | -0.176 | -61.55% | 38.97% | -0.113 | 195 | -20.65% |
| supertrend_ema | 0.779 | -0.435 | -0.354 | -59.89% | 37.44% | -0.174 | 211 | -38.16% |
| vp_bb | 0.847 | -0.678 | -0.445 | -56.58% | 49.36% | -0.062 | 628 | -44.23% |

## Rolling OOS 摘要

| Variant | rolling PF min | rolling PF avg | rolling Sharpe avg | rolling Calmar avg | worst MDD |
|---|---:|---:|---:|---:|---:|
| baseline | 1.248 | 1.556 | 1.322 | 2.405 | -37.74% |
| no_btc_moat | 1.248 | 1.666 | 1.440 | 2.733 | -37.74% |
| no_symbol_wr | 1.043 | 1.419 | 1.115 | 2.024 | -46.66% |
| no_geometric_rr | 0.718 | 1.248 | 0.625 | 1.084 | -48.97% |
| bb_only | 0.873 | 0.977 | 0.056 | -0.106 | -35.49% |
| supertrend_only | 0.941 | 1.379 | 0.637 | 1.225 | -45.19% |
| supertrend_btc | 0.941 | 1.330 | 0.644 | 0.916 | -45.19% |
| supertrend_ema | 0.968 | 1.392 | 0.683 | 1.272 | -44.47% |
| vp_only | 0.624 | 0.809 | -0.877 | -0.551 | -49.45% |
| vp_bb | 0.896 | 0.936 | -0.190 | -0.290 | -42.00% |

## 模組判斷

| 模組 / 測試 | 判斷 | 理由 |
|---|---|---|
| Supertrend raw | 淘汰 | IS 很強但 OOS PF 0.757、總報酬 -41.35%，明顯 regime dependent。 |
| VP POC raw | 淘汰 | IS 接近無效，OOS PF 0.734，交易數高但負期望。 |
| Bollinger raw | 需要更多測試 | OOS 為正且 MDD 較低，但 PF 1.110 未達通過標準，rolling PF 多數低於 1。 |
| BTC moat | 需要更多測試 | 關閉後 OOS 變差，但 rolling 平均反而略高；像風險控管，不是穩定獨立 alpha。 |
| Symbol rolling winrate | 保留 | 關閉後交易數暴增、OOS PF/Sharpe/Calmar/MDD 全部變差，顯示它能抑制低品質交易。 |
| Geometric RR | 保留 | 關閉後 OOS MDD 超過 -50%，平均 R 轉負，rolling 2024 PF 只有 0.718。 |
| EMA score | 淘汰 | Supertrend + EMA score 在 IS 很強但 OOS PF 0.779、總報酬 -38.16%，高度疑似過擬合或 regime filter。 |
| VP + BB | 淘汰 | OOS PF 0.847，交易數 628 但負報酬，組合不提供穩定 edge。 |
| baseline 組合 | 需要更多測試 | OOS 與 rolling OOS 最穩，但單一 raw 模組多數失效，代表組合可能有互補，也可能有過度擬合風險。 |

## 結論

需要更多測試。

目前沒有任何單一 raw 訊號能獨立提供穩定 edge。baseline 的績效主要來自多模組組合與風險濾網共同作用，而不是 Supertrend、VP 或 BB 其中一個單獨賺錢。Symbol rolling winrate 與 geometric RR 比較像真正有用的風險控管；EMA score 在 Supertrend 單獨測試下顯示出明顯 IS/OOS 斷裂，應列為過擬合嫌疑。BTC moat 在目標 OOS 有幫助，但 rolling 結果不夠一致，暫時不能宣稱是穩定 edge。

## 下一步

- 優先拆解 baseline 的獲利來源：依策略標籤、年份、幣種、出場原因分解 PnL。
- 對 geometric RR 做更細的 on/off + 年度檢查，確認它不是只擋掉特定年份的虧損。
- 對 EMA score 做分數分層統計，檢查高分交易是否真的比低分交易有更高 PF。
- 若下一步只能選一個，應先做「baseline by strategy / by exit reason / by year」歸因，而不是繼續調參。

## EXP-004 - Baseline Attribution 歸因分析

## 日期

2026-05-07

## 測試目的

拆解 baseline Crypto OOS 交易紀錄，確認獲利與虧損主要來自哪一類訊號、出場原因、年份、幣種、持倉天數、BTC regime，以及日 K 同根 TP/SL 衝突交易。

## 修改範圍

- 新增 attribution 分析腳本。
- 新增 output 報表。
- 追加研究紀錄。

## 沒改什麼

- 沒有修改策略訊號。
- 沒有修改策略參數。
- 沒有修改成本模型。
- 沒有修改倉位管理。
- 沒有修改資產池。
- 沒有修改 OOS 期間。

## 通過標準

- baseline 整體績效需重現既有 Crypto OOS 基準。
- 每個分組至少輸出 trades、win_rate、profit_factor、total_R、avg_R、median_R、max_loss_R、max_win_R、total_return_contribution、average_holding_days。
- 若主要正貢獻高度集中在少數幣、單一年份、或同根 TP/SL 衝突交易，結論不得寫「保留」。
- 若 BTC below EMA200、短持倉、或某類訊號明顯負貢獻，需列為下一步風險控制候選。

## 執行命令

```powershell
python scripts\crypto_baseline_attribution.py
```

## 輸出檔案

- `output/crypto_baseline_attribution_by_strategy.csv`
- `output/crypto_baseline_attribution_by_exit_reason.csv`
- `output/crypto_baseline_attribution_by_year.csv`
- `output/crypto_baseline_attribution_by_symbol.csv`
- `output/crypto_baseline_attribution_by_holding_days.csv`
- `output/crypto_baseline_attribution_by_btc_regime.csv`
- `output/crypto_baseline_attribution_conflicts.csv`
- `output/crypto_baseline_attribution_summary.md`

## Baseline OOS 整體結果

| 總報酬 | 年化 | MDD | PF | Sharpe | Calmar | 勝率 | 平均 R | 交易數 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| +87.17% | +36.49% | -43.01% | 1.346 | 0.930 | 0.848 | 43.81% | +0.035 | 226 |

## By Strategy / Signal Source

| Signal source | trades | PF | 勝率 | total R | avg R | return contribution |
|---|---:|---:|---:|---:|---:|---:|
| Supertrend | 121 | 1.473 | 44.63% | +6.62 | +0.055 | +58.29% |
| VP POC | 99 | 1.220 | 41.41% | +0.27 | +0.003 | +27.50% |
| combined/overlap | 1 | inf | 100.00% | +1.99 | +1.990 | +1.83% |
| Bollinger | 5 | 0.882 | 60.00% | -1.07 | -0.214 | -0.46% |
| unknown | 0 | 0.000 | 0.00% | +0.00 | +0.000 | +0.00% |

## By Exit Reason

| Exit reason | trades | PF | 勝率 | total R | avg R | return contribution |
|---|---:|---:|---:|---:|---:|---:|
| TP | 60 | inf | 100.00% | +101.61 | +1.694 | +268.46% |
| max_hold | 34 | 24.120 | 91.18% | +22.39 | +0.659 | +57.73% |
| reverse signal | 14 | 1.074 | 35.71% | -2.10 | -0.150 | +0.51% |
| end of backtest | 3 | 0.000 | 0.00% | -1.02 | -0.340 | -2.23% |
| SL | 112 | 0.000 | 0.00% | -114.04 | -1.018 | -240.71% |
| trailing stop | 0 | 0.000 | 0.00% | +0.00 | +0.000 | +0.00% |
| other | 3 | inf | 100.00% | +0.97 | +0.323 | +3.42% |

## By Year

| Year | trades | PF | 勝率 | total R | avg R | return contribution |
|---|---:|---:|---:|---:|---:|---:|
| 2024 | 106 | 0.998 | 33.96% | -13.80 | -0.130 | -0.21% |
| 2025 | 98 | 1.400 | 51.02% | +10.97 | +0.112 | +47.36% |
| 2026 | 22 | 2.001 | 59.09% | +10.64 | +0.484 | +40.01% |

## By Holding Days

| Holding bucket | trades | PF | 勝率 | total R | avg R | return contribution |
|---|---:|---:|---:|---:|---:|---:|
| 15-30 days | 84 | 4.215 | 66.67% | +42.67 | +0.508 | +151.83% |
| 4-7 days | 44 | 0.895 | 34.09% | -5.49 | -0.125 | -6.05% |
| 8-14 days | 54 | 0.905 | 29.63% | -11.19 | -0.207 | -6.37% |
| 0-3 days | 44 | 0.350 | 27.27% | -18.18 | -0.413 | -52.25% |

## By BTC Regime

| BTC regime | trades | PF | 勝率 | total R | avg R | return contribution |
|---|---:|---:|---:|---:|---:|---:|
| BTC above EMA200 | 171 | 1.614 | 46.78% | +18.06 | +0.106 | +85.94% |
| BTC below EMA200 | 55 | 1.011 | 34.55% | -10.25 | -0.186 | +1.23% |

## Intrabar Conflict Flag

| Conflict | trades | PF | 勝率 | total R | avg R | return contribution |
|---|---:|---:|---:|---:|---:|---:|
| True | 8 | inf | 100.00% | +13.94 | +1.743 | +34.50% |
| False | 218 | 1.209 | 41.74% | -6.13 | -0.028 | +52.67% |

## Symbol 集中度

- 交易幣種數：50。
- 前 10 名幣種貢獻約 88.2% 的正向 symbol total R。
- 前 10 名貢獻：ENA、ALGO、ARB、FARTCOIN、EGLD、HYPE、LINK、OP、WIF、XPL。
- 後 10 名拖累：ATOM、BCH、FIL、SNX、SAND、THETA、ONE、TAO、AAVE、HBAR。
- Global MDD window：2024-08-05 到 2024-11-20，drawdown USD -6311.21。

## 結論

需要更多測試。

baseline 不是平均、穩定地從所有訊號與所有幣種賺錢。主要正貢獻來自 TP 出場、15-30 天持倉、BTC above EMA200 regime，以及 baseline 內的 Supertrend 標籤；主要負貢獻來自 SL、短持倉、BTC below EMA200 regime，與一批 0 勝率弱幣。日 K 同根 TP/SL 衝突交易只有 8 筆，但貢獻 +13.94R / +34.50% return contribution，代表成交路徑假設仍是重要風險。

## 模組判斷

| 模組 / 現象 | 判斷 | 理由 |
|---|---|---|
| baseline 內 Supertrend 標籤 | 保留 | 在完整風控與濾網框架內為最大正貢獻來源，但不能單獨使用。 |
| BTC regime / moat | 保留 | BTC above EMA200 明顯較有效；BTC below EMA200 幾乎沒有 R edge。 |
| Symbol rolling winrate | 保留 | EXP-003 顯示關閉後交易數暴增且風險惡化；EXP-004 又顯示弱幣拖累明顯。 |
| Geometric RR | 保留 | EXP-003 顯示關閉後 MDD 破 -50%，本次 SL/短持倉拖累支持保留風險閘門。 |
| VP POC | 需要更多測試 | baseline 內有正報酬貢獻，但 total R 幾乎打平，不能視為獨立 edge。 |
| Bollinger | 淘汰或降權 | baseline 樣本少且 total R 為負；獨立 ablation 也未達通過標準。 |
| EMA score | 淘汰 | EXP-003 顯示 IS/OOS 斷裂，本次沒有看到需要恢復權重的證據。 |

## 下一步

下一個最值得做的實驗是 Point-in-time universe 測試。理由是前 10 名幣種貢獻高度集中，且包含較新上市或高動能幣；在繼續調參前，必須先排除資產池事後選樣、上市存活偏誤與資料可交易性問題。

## EXP-005 - Point-in-time Crypto Top 100 Universe 測試

## 日期

2026-05-07

## 測試目的

檢查目前 Crypto 策略是否受到 survivorship bias / universe selection bias 影響，尤其是 EXP-004 發現前 10 名幣種貢獻約 88.2% 正向 symbol total R 後，需要確認這些標的是否在當時可被 point-in-time universe 選中。

## 修改範圍

- 新增 universe 建構與測試腳本。
- 新增 universe comparison 輸出報表。
- 新增 universe methodology 文件。
- 追加研究紀錄。

## 沒改什麼

- 沒有修改策略訊號。
- 沒有修改策略參數。
- 沒有修改成本模型。
- 沒有修改倉位管理。
- 沒有修改回測成交判定。

## 通過標準

- `current_top100_bias_check` 必須標示為 biased benchmark，不可當真實績效。
- `static_pit_top100` 必須只使用 OOS 起點前一日已知排名。
- `rolling_pit_top100_quarterly` 必須只使用 rebalance date 前一日或前一月底已知排名。
- 若缺歷史市值排名資料，必須標記 `missing_market_cap_history`，不得產生假 PIT 績效。
- 若 PIT universe 跑出後 PF < 1.15、Sharpe < 0.70、MDD 超過 -50%，不得判定策略已通過 survivorship bias 檢查。

## 測試設定

| Mode | 說明 | 本次狀態 |
|---|---|---|
| current_top100_bias_check | 使用目前 config / 本地 DB 可用 crypto universe 回測歷史，只能當偏誤對照 | biased_benchmark |
| static_pit_top100 | OOS 起點前一日的歷史市值 top 100，OOS 固定 | missing_market_cap_history |
| rolling_pit_top100_quarterly | 每季用當時已知市值 ranking 重新選 top 100 | missing_market_cap_history |

## 執行命令

```powershell
python scripts\crypto_point_in_time_universe.py
```

## 輸出檔案

- `output/crypto_universe_static_pit_top100.csv`
- `output/crypto_universe_rolling_pit_top100_quarterly.csv`
- `output/crypto_universe_bias_comparison.csv`
- `docs/research/crypto_universe_methodology.md`

## 結果

| Mode | status | total return | annual return | MDD | PF | Sharpe | Calmar | win rate | avg R | trades | universe symbols | traded symbols |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current_top100_bias_check | biased_benchmark | +168.09% | +63.13% | -52.14% | 1.637 | 1.414 | 1.211 | 46.72% | +0.089 | 229 | 50 | 50 |
| static_pit_top100 | missing_market_cap_history |  |  |  |  |  |  |  |  |  | 0 | 0 |
| rolling_pit_top100_quarterly | missing_market_cap_history |  |  |  |  |  |  |  |  |  | 0 | 0 |

## Top / Worst Contributors（biased benchmark）

- Top contributors：UNI、ENA、HYPE、AVAX、CRV、1000PEPE、ARB、OP、EGLD、SUI。
- Worst contributors：BCH、PIPPIN、AAVE、GRT、BNB、VET、ONE、THETA、MINA、FLOW。

## 資料缺口

本地資料庫沒有歷史 crypto market-cap ranking。`static_pit_top100` 與 `rolling_pit_top100_quarterly` 已輸出資料缺口列，狀態為 `missing_market_cap_history`。因此本次不能宣稱已完成真正的 point-in-time universe 驗證。

需要補齊的資料檔：

```text
data/crypto_market_cap_rankings.csv
```

必要欄位：

```text
date,rank,symbol
```

可選欄位：

```text
market_cap
```

## 問題回答

1. 現有 universe 是否明顯高估績效？
   - 疑似有高估風險，但本次無法完整定量判定。current-biased benchmark 不能當真實績效；它的報酬高於 EXP-004 baseline，且 MDD 也惡化，顯示 universe 選樣非常敏感。
2. static point-in-time top100 是否仍有 edge？
   - 無法判定。缺歷史市值 ranking，不能產生假 PIT 結果。
3. rolling top100 是否比固定 top100 更穩？
   - 無法判定。缺歷史市值 ranking。
4. 績效是否集中在少數幣？
   - 是。EXP-004 已顯示前 10 名幣種貢獻約 88.2% 的正向 symbol total R；本次 biased benchmark 的 top contributors 也高度集中。
5. 是否值得繼續研究這個策略？
   - 需要更多測試。策略還值得研究，但 PIT universe 資料補齊前，不應提高信心或繼續做參數最佳化。

## 結論

需要更多測試。

本次最重要的結果不是 current-biased benchmark 的高報酬，而是確認「目前沒有足夠資料宣稱策略已通過 survivorship bias / universe selection bias 檢查」。下一步應先補齊歷史市值 ranking，再重跑 `static_pit_top100` 與 `rolling_pit_top100_quarterly`。

## 下一步

- 補齊 `data/crypto_market_cap_rankings.csv`，至少涵蓋 2024-04-30 到 2026-05-07 的月度或季度 snapshot。
- 確認 ranking source 是否包含退市、改名、合併、wrapped/stablecoin 標記。
- 重跑 `python scripts\crypto_point_in_time_universe.py`。
- 若 PIT 後仍 PF > 1.15、Sharpe >= 0.70、MDD 不超過 -50%，再做 symbol cap / liquidity throttle。

## EXP-005 補充 - CoinMarketCap historical + 前三年平均市值年度 Universe

## 日期

2026-05-08

## 補充目的

使用 CoinMarketCap historical snapshots 補齊歷史市值資料，建立「回測年 Y 使用 Y-3 到 Y-1 三年平均市值前 100」的年度 point-in-time-like universe。例：2021 回測使用 2018-2020 平均市值前 100，2022 使用 2019-2021，依此類推。

## 修改範圍

- 新增 CoinMarketCap historical ranking 抓取腳本。
- 新增 previous-3-year average market-cap universe 年度回測腳本。
- 新增 SQLite table `crypto_market_cap_rankings`。
- 新增年度 universe 與年度績效輸出。

## 沒改什麼

- 沒有修改策略訊號。
- 沒有修改策略參數。
- 沒有修改成本模型。
- 沒有修改倉位管理。
- 沒有修改回測成交判定。

## 資料抓取

```powershell
python scripts\fetch_cmc_historical_rankings.py --start-year 2018 --end-year 2025 --freq monthly --max-rank 200 --sleep 0.5 --output-csv output\cmc_rankings_2018_2025_monthly.csv
```

結果：

| 項目 | 數值 |
|---|---:|
| snapshot 起點 | 2018-01-28 |
| snapshot 終點 | 2025-12-28 |
| snapshot 數 | 96 |
| 每次抓取 rank | Top 200 |
| SQLite rows | 19,200 |
| distinct symbols | 989 |

## 年度 Universe 回測

```powershell
python scripts\crypto_prev3y_market_cap_universe_backtest.py --start-year 2021 --end-year 2026 --end-date 2026-05-07
```

輸出：

- `output/crypto_prev3y_mcap_top100_yearly.csv`
- `output/crypto_prev3y_mcap_top100_universe.csv`
- `output/crypto_universe_bias_comparison.csv`

## 結果

| Year | Lookback | status | total return | annual | MDD | PF | Sharpe | Calmar | win rate | avg R | trades | eligible local OHLCV |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 2018-2020 | no_backtest_result |  |  |  |  |  |  |  |  |  | 0 |
| 2022 | 2019-2021 | ok | +15.34% | +15.39% | -22.77% | 1.218 | 0.574 | 0.676 | 52.08% | +0.211 | 48 | 10 |
| 2023 | 2020-2022 | ok | +45.80% | +45.99% | -22.44% | 1.689 | 1.376 | 2.049 | 46.92% | +0.134 | 130 | 36 |
| 2024 | 2021-2023 | ok | +3.20% | +3.20% | -48.72% | 1.023 | 0.278 | 0.066 | 43.48% | +0.047 | 138 | 38 |
| 2025 | 2022-2024 | ok | -0.45% | -0.45% | -45.18% | 0.995 | 0.219 | -0.010 | 47.24% | -0.015 | 127 | 36 |
| 2026 | 2023-2025 | ok | +22.64% | +80.70% | -16.10% | 1.586 | 1.650 | 5.012 | 48.21% | +0.168 | 56 | 36 |

## 判讀

| 問題 | 回答 |
|---|---|
| 現有 universe 是否明顯高估績效？ | 是，有明顯高估風險。current-biased benchmark 為 +168.09%，但 previous-3-year universe 在 2024 只有 +3.20%，2025 為 -0.45%。 |
| static point-in-time top100 是否仍有 edge？ | 這次做的是前三年平均市值年度 universe，不是單一 OOS 起點 static snapshot；結果顯示 edge 不穩，2024/2025 未通過。 |
| rolling top100 是否比固定 top100 更穩？ | 年度 rolling previous-3-year universe 不穩；季度 rolling 仍待補做。 |
| 績效是否集中在少數幣？ | 是。EXP-004 與本次 top/worst contributors 都顯示高度集中。 |
| 是否值得繼續研究？ | 需要更多測試，但信心下降。應先完成真正 static/quarterly PIT top100，再決定是否繼續調參。 |

## 結論

需要更多測試。

這次補齊 CMC historical 市值資料後，策略在 previous-3-year market-cap universe 下並不穩定。2023 與 2026 表現好，但 2024/2025 幾乎沒有 edge；2021 因本地 Bybit OHLCV 不足，不能產生有效回測。這支持 EXP-004 對 universe selection bias 的疑慮，不支持直接用 current-biased universe 的績效作為策略有效證據。

## 下一步

- 做真正 `static_pit_top100`：使用 2024-04-30 前最近 CMC snapshot 的市值 top100，跑 2024-05-01 到 2026-05-07。
- 做真正 `rolling_pit_top100_quarterly`：每季用 CMC 前一月底 snapshot 選 universe。
- 補抓 top100 對應 Bybit OHLCV，否則 eligible local OHLCV 長期只有 36-38 檔，會變成交易所覆蓋率偏誤。

## EXP-005 補充 - Static / Quarterly PIT Top 100 OOS 重跑

## 日期

2026-05-08

## 測試目的

在 CMC historical ranking 已存入 SQLite 後，重跑原始 EXP-005 的 `static_pit_top100` 與 `rolling_pit_top100_quarterly`。

## 執行命令

```powershell
python scripts\crypto_point_in_time_universe.py --start-date 2024-05-01 --end-date 2026-05-07
```

## 結果

| Mode | status | total return | annual | MDD | PF | Sharpe | Calmar | win rate | avg R | trades | universe symbols | traded symbols |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current_top100_bias_check | biased_benchmark | +168.09% | +63.13% | -52.14% | 1.637 | 1.414 | 1.211 | 46.72% | +0.089 | 229 | 50 | 50 |
| static_pit_top100 | ok | +47.83% | +21.41% | -51.47% | 1.285 | 0.708 | 0.416 | 41.40% | +0.006 | 186 | 39 | 39 |
| rolling_pit_top100_quarterly | ok | +48.78% | +21.79% | -53.34% | 1.269 | 0.693 | 0.409 | 43.06% | +0.013 | 209 | 42 | 42 |

## 判讀

- 現有 universe 明顯高估績效：biased benchmark +168.09%，static/rolling PIT 約 +48%。
- static PIT 仍有弱 edge，但 MDD -51.47% 超過 -50% 風險標準，Calmar 0.416 偏低。
- rolling quarterly 沒有比 static 更穩，MDD 與 Sharpe 反而略差。
- 結論仍是 `需要更多測試`，且不應再用 current-biased universe 做調參。

## EXP-005 補充 - Bybit-only OHLCV 覆蓋率補強

## 日期

2026-05-08

## 測試目的

因實盤交易所使用 Bybit，本次只納入 Bybit linear USDT perpetual。補齊 CMC PIT universe 候選在 Bybit 上可交易的 OHLCV，降低「本地資料缺漏」造成的 universe 偏誤。

## 修改範圍

- 新增 Bybit instruments / OHLCV 補資料腳本。
- 新增 SQLite table `crypto_bybit_linear_instruments`。
- 新增 SQLite table `crypto_bybit_ohlcv_fetch_log`。
- 重跑 static / rolling PIT 與 previous-3-year universe。

## 沒改什麼

- 沒有修改策略訊號。
- 沒有修改策略參數。
- 沒有修改成本模型。
- 沒有修改倉位管理。
- 沒有納入 Binance。

## 執行命令

```powershell
python scripts\fetch_bybit_pit_universe_ohlcv.py --max-rank 200 --start-date 2018-01-01 --end-date 2026-05-08 --sleep 0.05
python scripts\crypto_point_in_time_universe.py --start-date 2024-05-01 --end-date 2026-05-07
python scripts\crypto_prev3y_market_cap_universe_backtest.py --start-year 2021 --end-year 2026 --end-date 2026-05-07
```

## Bybit 補資料結果

| 項目 | 數值 |
|---|---:|
| Bybit linear USDT perpetual instruments | 553 |
| CMC top200 候選 | 964 |
| CMC / Bybit 交集 | 302 |
| OHLCV fetched | 255 |
| skipped existing fresh | 45 |
| no rows | 2 |
| 本地 Crypto registry 補強後 | 325 |

## Static / Quarterly PIT OOS 結果（Bybit OHLCV 補強後）

| Mode | status | total return | annual | MDD | PF | Sharpe | Calmar | win rate | avg R | trades | traded symbols |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current_top100_bias_check | biased_benchmark | +168.09% | +63.13% | -52.14% | 1.637 | 1.414 | 1.211 | 46.72% | +0.089 | 229 | 50 |
| static_pit_top100 | ok | +52.03% | +23.11% | -42.86% | 1.167 | 0.693 | 0.539 | 49.64% | +0.151 | 415 | 100 |
| rolling_pit_top100_quarterly | ok | +37.49% | +17.12% | -50.87% | 1.115 | 0.583 | 0.336 | 47.16% | +0.088 | 405 | 141 |

## Previous-3-Year 年度結果（Bybit OHLCV 補強後）

| Year | Lookback | status | total return | annual | MDD | PF | Sharpe | Calmar | win rate | avg R | trades | eligible local OHLCV |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 2018-2020 | no_backtest_result |  |  |  |  |  |  |  |  |  | 0 |
| 2022 | 2019-2021 | ok | +7.60% | +7.62% | -28.62% | 1.110 | 0.384 | 0.266 | 52.08% | +0.222 | 48 | 11 |
| 2023 | 2020-2022 | ok | +41.66% | +41.83% | -22.77% | 1.453 | 1.275 | 1.837 | 49.21% | +0.189 | 191 | 61 |
| 2024 | 2021-2023 | ok | +6.51% | +6.52% | -42.70% | 1.039 | 0.367 | 0.153 | 45.56% | +0.041 | 180 | 61 |
| 2025 | 2022-2024 | ok | -9.89% | -9.92% | -47.42% | 0.922 | -0.035 | -0.209 | 48.89% | +0.055 | 180 | 67 |
| 2026 | 2023-2025 | ok | +20.27% | +70.73% | -13.33% | 1.519 | 1.530 | 5.308 | 53.33% | +0.129 | 75 | 69 |

## 判讀

| 問題 | 回答 |
|---|---|
| 現有 universe 是否明顯高估績效？ | 是。current-biased benchmark +168.09%，Bybit-only static PIT +52.03%，rolling PIT +37.49%。 |
| static point-in-time top100 是否仍有 edge？ | 有弱 edge，但未明確通過。PF 1.167 略高於 1.15，Sharpe 0.693 低於 0.70，Calmar 0.539 偏低。 |
| rolling top100 是否比固定 top100 更穩？ | 沒有。rolling PF 1.115、Sharpe 0.583、MDD -50.87%，比 static 更弱。 |
| 績效是否集中在少數幣？ | 是。top/worst contributors 仍高度集中。 |
| 是否值得繼續研究？ | 需要更多測試，但策略信心下降。下一步應做 liquidity throttle / symbol cap / BTC regime filter，不應繼續用 current-biased universe 調參。 |

## 結論

需要更多測試。

Bybit OHLCV 補強後，static PIT 可以交易完整 100 檔，績效仍大幅低於 current-biased benchmark。這代表原本 universe selection bias 的疑慮成立。rolling quarterly 沒有改善穩定性，反而略差。策略仍可能有弱 edge，但目前更像是需要嚴格風控與 universe 約束，而不是可以直接放大部位的 alpha。

## 下一步

- 做 liquidity throttle：提高 90 天成交額門檻，觀察 PF / Sharpe / MDD 是否改善。
- 做 symbol cap：限制單一幣種貢獻與連續虧損後冷卻。
- 做 BTC below EMA200 降權或停做測試。

## EXP-006 - Bybit PIT Universe Liquidity Throttle 測試

## 日期

2026-05-08

## 測試目的

檢查 Bybit-only PIT universe 是否因低流動性標的拖累績效。透過提高 selection date 前 90 天 median dollar volume 門檻，觀察 PF、Sharpe、Calmar、MDD、交易數與交易幣種數是否改善。

## 修改範圍

- 新增 liquidity throttle 測試腳本。
- 新增 liquidity throttle 輸出報表。
- 不修改策略本身。

## 沒改什麼

- 沒有修改策略訊號。
- 沒有修改策略參數。
- 沒有修改成本模型。
- 沒有修改倉位管理。
- 沒有修改成交判定。
- 沒有納入 Binance。

## 通過標準

- PF 需大於 1.15。
- Sharpe 不低於 0.70。
- MDD 不超過 -50%。
- Calmar 不可明顯惡化。
- 交易數不可過度萎縮；若交易數低於 150 或 traded symbols 過少，需標記為集中風險。
- 不以單一高報酬門檻直接判定保留，需同時看風險與樣本數。

## 執行命令

```powershell
python scripts\crypto_liquidity_throttle.py
```

## 輸出檔案

- `output/crypto_liquidity_throttle.csv`

## 結果

| Mode | 90D median dollar volume | total return | annual | MDD | PF | Sharpe | Calmar | win rate | avg R | trades | traded symbols |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| static PIT | 0 | +52.03% | +23.11% | -42.86% | 1.167 | 0.693 | 0.539 | 49.64% | +0.151 | 415 | 100 |
| rolling PIT | 0 | +37.49% | +17.12% | -50.87% | 1.115 | 0.583 | 0.336 | 47.16% | +0.088 | 405 | 141 |
| static PIT | 1,000,000 | +52.03% | +23.11% | -42.86% | 1.167 | 0.693 | 0.539 | 49.64% | +0.151 | 415 | 100 |
| rolling PIT | 1,000,000 | +74.88% | +31.97% | -35.76% | 1.219 | 0.868 | 0.894 | 49.38% | +0.136 | 401 | 137 |
| static PIT | 5,000,000 | +105.21% | +42.87% | -42.38% | 1.357 | 1.038 | 1.012 | 48.19% | +0.132 | 386 | 85 |
| rolling PIT | 5,000,000 | +42.40% | +19.17% | -55.02% | 1.128 | 0.609 | 0.349 | 49.18% | +0.165 | 368 | 123 |
| static PIT | 10,000,000 | +112.54% | +45.38% | -32.25% | 1.380 | 1.090 | 1.407 | 46.88% | +0.083 | 288 | 60 |
| rolling PIT | 10,000,000 | +86.52% | +36.25% | -50.68% | 1.259 | 0.905 | 0.715 | 49.70% | +0.152 | 330 | 100 |
| static PIT | 25,000,000 | +29.48% | +13.68% | -47.46% | 1.168 | 0.547 | 0.288 | 42.51% | -0.066 | 167 | 34 |
| rolling PIT | 25,000,000 | +13.88% | +6.66% | -54.10% | 1.073 | 0.362 | 0.123 | 44.06% | -0.012 | 202 | 59 |
| static PIT | 50,000,000 | +13.98% | +6.71% | -51.03% | 1.101 | 0.368 | 0.132 | 42.48% | +0.017 | 113 | 23 |
| rolling PIT | 50,000,000 | +107.59% | +43.69% | -45.88% | 1.585 | 1.090 | 0.952 | 46.84% | +0.076 | 158 | 43 |

## 判讀

- Liquidity throttle 有效，但不是越高越好。
- Static PIT 最佳候選是 10M 門檻：PF 1.380、Sharpe 1.090、MDD -32.25%、Calmar 1.407，交易數 288，traded symbols 60。
- Rolling PIT 在 1M 門檻改善最均衡：PF 1.219、Sharpe 0.868、MDD -35.76%、交易數 401，traded symbols 137。
- Rolling PIT 的 50M 門檻雖然 PF 1.585，但交易數 158、traded symbols 43，集中風險較高，不可直接視為最佳。
- Static PIT 的 25M / 50M 門檻交易數與幣種數明顯萎縮，且 Sharpe / Calmar 變差。

## 結論

需要更多測試。

流動性過濾確實能改善 PIT universe 的風險調整績效，尤其 static PIT 的 10M 門檻與 rolling PIT 的 1M 門檻。這支持「低流動性幣拖累策略」的假設。但不同模式最佳門檻不一致，且高門檻會造成樣本集中，所以不能直接把 10M 或 50M 當成新參數上線。

## 下一步

- 對 static PIT 10M 與 rolling PIT 1M 做年度拆解，確認不是單一年份有效。
- 對 liquidity throttle 做 symbol contribution / concentration 檢查。
- 再做 BTC below EMA200 降權或停做測試，因 EXP-004 已顯示 BTC below EMA200 的 R edge 不足。

## EXP-007 - Prev3Y Top100 Universe OOS 主回測

## 日期

2026-05-08

## 測試名稱

Crypto OOS：原 config universe vs 前三年平均市值 Top100 universe

## 測試目的

確認把 `main.py backtest` 的 Crypto universe 換成「每年使用前三年平均市值 Top100」後，OOS 實際績效是否改善，並檢查原本 config universe 是否可能高估策略 edge。

## 修改範圍

- 新增 `main.py backtest --crypto-universe prev3y-mcap-top100` 回測 universe 模式。
- 使用 SQLite `crypto_market_cap_rankings` 建構年度 universe。
- 使用 Bybit 本地 OHLCV 與 180 天回測前歷史資料門檻。

## 沒改什麼

- 沒改策略訊號。
- 沒改策略參數。
- 沒改成本模型。
- 沒改倉位管理。
- 沒改 TP / SL / trailing stop 判定。
- 沒加入新指標。

## 測試設定

| Variant | Universe | OOS 區間 | 說明 |
|---|---|---|---|
| config_oos_benchmark | 原本 `config.py` Crypto 清單 | 2024-05-01 ~ 2026-05-07 | 只能作為 biased benchmark 對照 |
| prev3y_top100_oos_raw | 每年以前三年平均市值 Top100 | 2024-05-01 ~ 2026-05-07 | Bybit-only；排除 stable/wrapped/leveraged；至少 180 天歷史資料 |

## 執行指令

```powershell
python main.py backtest --profile Crypto --crypto-universe config --start-date 2024-05-01 --end-date 2026-05-07 --output output\crypto_config_oos_main.xlsx --note crypto_config_oos_main
python main.py backtest --profile Crypto --crypto-universe prev3y-mcap-top100 --start-date 2024-05-01 --end-date 2026-05-07 --output output\crypto_prev3y_top100_oos_main.xlsx --note crypto_prev3y_top100_oos_main
```

## 輸出檔案

- `output/crypto_config_oos_main.xlsx`
- `output/crypto_prev3y_top100_oos_main.xlsx`

## 結果

| Variant | 總報酬 | 年化 | MDD | PF | Sharpe | Calmar | 勝率 | 平均 R | 交易數 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| config_oos_benchmark | +87.17% | +36.49% | -43.01% | 1.346 | 0.930 | 0.848 | 43.81% | +0.035 | 226 |
| prev3y_top100_oos_raw | +7.25% | +3.54% | -49.74% | 1.030 | 0.289 | 0.071 | 43.61% | +0.026 | 321 |

## 通過標準

- PF 需要大於 1.20。
- Sharpe 需要不低於 0.70。
- MDD 不超過 -50%。
- Calmar 不能明顯惡化，理想需接近或高於 0.75。
- 平均 R 不應明顯低於原 config benchmark。
- 交易數需足夠，不可只靠少數交易撐起績效。

## 判斷

| Variant | 判斷 | 原因 |
|---|---|---|
| config_oos_benchmark | 需要更多測試 | 績效較好，但 universe 是人工/目前清單，可能含 selection bias，不可當真實 PIT 績效 |
| prev3y_top100_oos_raw | 淘汰 | PF 1.030、Sharpe 0.289、Calmar 0.071，幾乎只剩打平，沒有通過 OOS edge 標準 |

## 結論

淘汰。

Raw Prev3Y Top100 universe OOS 沒有保留價值。把 universe 改成較接近 point-in-time 的 Bybit Top100 後，策略 edge 明顯消失；這支持原本 config universe 可能高估績效的疑慮。

## 下一步

需要更多測試。

下一個最值得做的是在 PIT / Prev3Y Top100 universe 上加入 liquidity throttle，只測 universe 流動性門檻，不改策略訊號與參數。優先測 90 日成交量門檻 1M、5M、10M、50M，確認是否只有高流動性幣保留 edge。

## EXP-008 - Prev3Y 成交量 Top100 Universe 測試

## 日期

2026-05-08

## 測試目的

驗證「Top100 的重點是否其實是成交量，而不是市值」。本次使用 CoinMarketCap historical snapshot 的 `volume_24h`，每個測試年以前三年平均 24h 成交量選 Top100，再映射到 Bybit USDT perpetual 與本地 OHLCV。

## 修改範圍

- 泛化 `scripts/crypto_prev3y_market_cap_universe_backtest.py`，新增 `--rank-by volume_24h`。
- 新增 `main.py backtest --crypto-universe prev3y-volume-top100`。
- 只改 universe 排名方式，不改策略訊號、策略參數、成本模型、倉位管理。

## 執行指令

```powershell
python scripts\crypto_prev3y_market_cap_universe_backtest.py --rank-by volume_24h --start-year 2021 --end-year 2026 --end-date 2026-05-07
python main.py backtest --profile Crypto --crypto-universe prev3y-volume-top100 --start-date 2024-05-01 --end-date 2026-05-07 --output output\crypto_prev3y_volume_top100_oos_main.xlsx --note crypto_prev3y_volume_top100_oos_main
```

## 結果

| Variant | 總報酬 | 年化 | MDD | PF | Sharpe | Calmar | 交易數 |
|---|---:|---:|---:|---:|---:|---:|---:|
| prev3y_mcap_top100_oos_raw | +7.25% | +3.54% | -49.74% | 1.030 | 0.289 | 0.071 | 321 |
| prev3y_volume_top100_oos_raw | -24.26% | -12.88% | -57.05% | 0.907 | -0.148 | -0.226 | 367 |

年度切片：

| Year | Rank by volume lookback | 總報酬 | MDD | PF | Sharpe | Calmar | eligible OHLCV |
|---|---|---:|---:|---:|---:|---:|---:|
| 2022 | 2019-2021 | +7.60% | -28.62% | 1.110 | 0.384 | 0.266 | 11 |
| 2023 | 2020-2022 | +7.51% | -34.30% | 1.081 | 0.382 | 0.220 | 67 |
| 2024 | 2021-2023 | +52.65% | -43.84% | 1.278 | 1.178 | 1.202 | 68 |
| 2025 | 2022-2024 | +18.20% | -36.16% | 1.135 | 0.625 | 0.505 | 65 |
| 2026 | 2023-2025 | +21.64% | -14.72% | 1.460 | 1.485 | 5.194 | 73 |

## 判斷

成交量排序本身不是充分條件。年度切片看起來比市值 Top100 穩一些，但連續 OOS 從 2024-05-01 開始反而失敗，表示 2024 年初的正貢獻與逐年重置資金/濾網狀態會高估結果。不能只用年度切片判斷。

## 結論

淘汰 raw volume Top100。

成交量很可能是重要條件，但不是單獨的 alpha。需要搭配策略狀態或 universe 濾網再驗證。

## EXP-009 - Prev3Y Top100 策略優化

## 日期

2026-05-08

## 測試目的

在 Prev3Y Top100 universe 上做小範圍策略優化，檢查是否能改善 raw Top100 表現，同時判斷改善是否集中於 2026 YTD，避免把近期狀態過擬合成策略。

## 修改範圍

- 新增 `scripts/crypto_prev3y_top100_optimize.py`。
- 候選只測小範圍 runtime overrides：持倉上限、symbol winrate filter、max hold、risk、trend/VP stop-RR。
- 每個候選同時輸出 OOS_ALL、2024H2、2025、2026YTD。

## 執行指令

```powershell
python scripts\crypto_prev3y_top100_optimize.py --rank-by market_cap --limit 10 --output output\crypto_prev3y_mcap_top100_optimize.csv
python scripts\crypto_prev3y_top100_optimize.py --rank-by volume_24h --limit 10 --output output\crypto_prev3y_volume_top100_optimize.csv
```

## 結果

| Variant | 總報酬 | 年化 | MDD | PF | Sharpe | Calmar | 交易數 | 分段判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| mcap_top100_cap8 | +58.06% | +25.51% | -41.25% | 1.183 | 0.742 | 0.618 | 320 | 2024H2 虧損；2025 PF 1.059 |
| volume_top100_sym_filter_off | +80.95% | +34.22% | -35.59% | 1.241 | 0.872 | 0.961 | 394 | 2024H2 PF 1.071；2025/2026 有效 |
| volume_top100_stops_t1.75_rr2 | +64.58% | +28.05% | -44.99% | 1.203 | 0.803 | 0.624 | 378 | 2024H2 虧損；2025 PF 1.076 |

## 判斷

- 市值 Top100 可以靠 `max_total_positions=8` 把總 OOS 拉過最低門檻，但分段仍弱，不適合升級。
- 成交量 Top100 關閉 symbol rolling winrate filter 後是本輪最佳候選，總 OOS 達 +80.95%、MDD -35.59%、PF 1.241。
- 但最佳候選仍沒有完全消除分段風險：2024H2 只小幅正報酬且 PF 1.071，Sharpe 0.471。

## 結論

需要 forward 驗證。

目前不能說「交易量就是唯一重點」，比較精準的說法是：交易量排序加上不要過早用 symbol 歷史勝率汰除標的，會比市值 Top100 更接近有效；但改善仍可能吃到 2025/2026 regime，還沒有足夠證據直接升級為正式策略。

## EXP-010 - Top100 Overfit Check：Nested WF + Stability

## 日期

2026-05-08

## 測試目的

檢查 EXP-009 的 Top100 改善是否只是看過 2024-2026 OOS 後挑出的過擬合結果。這次把候選凍結，做 nested walk-forward 與成交量 TopN / symbol WR 鄰近穩定性測試。

## 修改範圍

- 新增 `scripts/crypto_top100_overfit_checks.py`。
- 新增 nested walk-forward candidate selection。
- 新增 volume TopN 與 symbol WR threshold 穩定性 grid。
- 新增 volume Top125 的 1/2/3 年 lookback focus 測試。

## 沒改什麼

- 沒有修改正式策略設定。
- 沒有修改訊號邏輯。
- 沒有修改成本模型。
- 沒有修改倉位計算公式。
- 沒有用測試段結果反過來改候選。

## 執行指令

```powershell
python scripts\crypto_top100_overfit_checks.py --end-date 2026-05-07 --top-ns 75,100,125 --thresholds 0,0.35,0.40,0.45
python scripts\crypto_top100_overfit_checks.py --skip-nested --top-ns 125 --thresholds 0,0.35,0.45 --lookbacks 1,2,3 --suffix lookback_focus
```

## 輸出檔案

- `output/crypto_top100_candidate_periods.csv`
- `output/crypto_top100_nested_walk_forward.csv`
- `output/crypto_top100_nested_universe_summary.csv`
- `output/crypto_top100_stability_grid.csv`
- `output/crypto_top100_stability_universe_summary.csv`
- `output/crypto_top100_stability_grid_lookback_focus.csv`
- `output/crypto_top100_stability_universe_summary_lookback_focus.csv`

## Nested Walk-forward 結果

每段只用 train 期間選候選，再測下一段。

| Split | Train selected | Train PF | Test return | Test MDD | Test PF | Test Sharpe | Test trades | Test pass | Overfit flag |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 2022-2023 → 2024H2 | mcap_cap8 | 1.572 | -10.84% | -40.42% | 0.905 | -0.159 | 118 | False | True |
| 2022-2024 → 2025 | mcap_cap8 | 1.295 | +6.86% | -30.83% | 1.059 | 0.365 | 155 | False | True |
| 2022-2025 → 2026YTD | volume_baseline | 1.299 | +14.81% | -14.89% | 1.286 | 1.112 | 74 | True | False |

## Nested 判斷

`mcap_cap8` 在 train 期間連續兩次被選中，但下一段都沒有通過測試，這是明確過擬合警訊。2026YTD 的 volume_baseline 通過，但樣本期只有 2026-01-01 到 2026-05-07，不能單獨當作升級依據。

## Stability Grid 結果

| Candidate | Total return | Annual | MDD | PF | Sharpe | Calmar | Trades | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| volume_top125_sym_0.35 | +99.43% | +40.86% | -36.57% | 1.291 | 1.012 | 1.117 | 407 | True |
| volume_top125_sym_0.40 | +99.43% | +40.86% | -36.57% | 1.291 | 1.012 | 1.117 | 407 | True |
| volume_top100_sym_off | +80.95% | +34.22% | -35.59% | 1.241 | 0.872 | 0.961 | 394 | True |
| volume_top125_sym_off | +68.18% | +29.43% | -39.56% | 1.194 | 0.797 | 0.744 | 431 | True |
| volume_top125_sym_0.45 | +63.22% | +27.52% | -37.19% | 1.191 | 0.779 | 0.740 | 401 | True |
| volume_top100_sym_0.35 | -7.60% | -3.85% | -45.16% | 0.972 | 0.093 | -0.085 | 381 | False |
| volume_top75_sym_0.35 | -9.75% | -4.96% | -48.47% | 0.954 | 0.059 | -0.102 | 295 | False |

## Stability 判斷

`volume_top100_sym_off` 有效，但對 symbol WR threshold 很敏感；只要 Top100 加回 0.35/0.40/0.45，OOS 就崩掉。反而 `volume_top125` 形成比較穩定的區域，WR off、0.35、0.40、0.45 都能過最低門檻。這比單點 Top100 off 更不像純粹偶然，但還沒完全解除過擬合疑慮。

## Lookback Focus 結果

| Candidate | Total return | Annual | MDD | PF | Sharpe | Calmar | Trades | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| volume_top125_lb3_sym_0.35 | +99.43% | +40.86% | -36.57% | 1.291 | 1.012 | 1.117 | 407 | True |
| volume_top125_lb3_sym_off | +68.18% | +29.43% | -39.56% | 1.194 | 0.797 | 0.744 | 431 | True |
| volume_top125_lb3_sym_0.45 | +63.22% | +27.52% | -37.19% | 1.191 | 0.779 | 0.740 | 401 | True |
| volume_top125_lb1_sym_off | +53.95% | +23.88% | -46.53% | 1.166 | 0.703 | 0.513 | 452 | True |
| volume_top125_lb2_sym_0.35 | +47.65% | +21.34% | -48.98% | 1.151 | 0.659 | 0.436 | 404 | False |

## Lookback 判斷

三年成交量 lookback 明顯最好；一年仍能勉強過關，兩年未過 Sharpe 門檻。這代表結果不是只有單一參數完全孤島，但對 lookback 視窗仍敏感。不能宣稱已通過強健性檢查，只能說 `volume_top125_lb3_sym_0.35/0.40` 是下一個最值得 forward test 的候選。

## 結論

需要 forward 驗證，不可升級正式策略。

本輪回答「是否過擬合」：

- `mcap_cap8`：高度疑似過擬合。Nested WF 連續兩段 train 選中、test 失敗。
- `volume_top100_sym_off`：有 edge，但單點敏感，仍有過擬合風險。
- `volume_top125_lb3_sym_0.35/0.40`：目前最穩候選；TopN/threshold 鄰近性較好，但 lookback 敏感，仍需 forward。

下一步只做 forward / paper test，不再在 2024-2026 上繼續調參。建議從 2026-05-08 起凍結 `volume_top125_lb3_sym_0.35`，累積至少 50 筆交易或 3 個月，再判定是否真的有效。

## EXP-011 - Top125 Volume Forward Monitor 初始化

## 日期

2026-05-08

## 測試目的

把 EXP-010 的最佳候選凍結為 forward / paper test 監控對象。從 2026-05-08 起，只允許更新資料後重跑監控，不再用 2024-2026 歷史回測改參數。

## 凍結候選

| 項目 | 設定 |
|---|---|
| Universe | previous 3-year average `volume_24h` Top125 |
| Lookback | 3 calendar years |
| Symbol WR threshold | 0.35 |
| Strategy params | current baseline |
| Forward start | 2026-05-08 |
| Decision gate | at least 90 days or 50 trades |

## 修改範圍

- 新增 `scripts/crypto_top100_forward_monitor.py`。
- 新增 forward summary / trades 輸出。
- 沒有改正式策略設定。

## 執行指令

```powershell
python scripts\crypto_top100_forward_monitor.py
```

## 初始化結果

| Candidate | Period | eligible symbols | status | reason | trades |
|---|---|---:|---|---|---:|
| forward_volume_top125_lb3_sym_0p35 | 2026-05-08 → 2026-05-08 | 93 | pending | days=1/90, trades=0/50 | 0 |

## 輸出檔案

- `output/crypto_top100_forward_monitor_summary.csv`
- `output/crypto_top100_forward_monitor_trades.csv`

## 結論

pending。

目前 forward 樣本只有 1 天，不能做績效判斷。之後只需要先更新資料，再重跑 `python scripts\crypto_top100_forward_monitor.py`，直到累積至少 90 天或 50 筆交易。

## EXP-011 補充 - Main 候選模式接線

## 日期

2026-05-08

## 目的

讓凍結候選可以透過 `main.py` 跑 backtest / live demo，而不是只存在獨立研究腳本。這不是升級正式策略，只是把候選做成顯式參數，避免手動改 config。

## 修改範圍

- 新增 `--crypto-candidate volume-top125-lb3-sym035`。
- Backtest 使用候選時會自動套用：
  - `--crypto-universe prev3y-volume-top100`
  - `--crypto-top-n 125`
  - Crypto symbol WR threshold `0.35`
- Live 使用候選時會使用當前年份的 prev3y volume Top125 eligible universe，並保留 BTC 作為 cross-asset filter context。

## Smoke test

```powershell
python main.py backtest --profile Crypto --crypto-candidate volume-top125-lb3-sym035 --start-date 2026-05-08 --end-date 2026-05-08 --output output\crypto_candidate_main_smoke.xlsx --note crypto_candidate_main_smoke
```

結果：

| 項目 | 數值 |
|---|---:|
| candidate | volume-top125-lb3-sym035 |
| ranked | 125 |
| bybit_available | 106 |
| eligible | 93 |
| period | 2026-05-08 only |
| trades | 0 |

## 使用方式

Backtest / forward recheck:

```powershell
python main.py backtest --profile Crypto --crypto-candidate volume-top125-lb3-sym035 --start-date 2026-05-08 --end-date YYYY-MM-DD --output output\crypto_candidate_forward.xlsx --note crypto_candidate_forward
```

Demo live:

```powershell
python main.py live --crypto-candidate volume-top125-lb3-sym035 --interval 60
```

## 結論

候選已可由 Main 顯式測試，但仍不是預設策略。正式策略是否切換，要等 forward monitor 達到 90 天或 50 筆交易後再判斷。

## EXP-012 - Top125 Candidate Cost / Intrabar Stress

## 日期

2026-05-08

## 測試目的

針對凍結候選 `volume-top125-lb3-sym035` 補做兩個壓力測試：

1. 成本壓力：TP taker、TP market slippage、額外滑價、funding。
2. 日 K 同根 TP/SL 路徑壓力：TP-first、SL-first、conservative。

這次測試只驗證候選策略抗不抗壓，不用結果回頭調參。

## 修改範圍

- `scripts/crypto_cost_stress.py` 新增 `--candidate volume-top125-lb3-sym035`。
- `scripts/crypto_intrabar_path_stress.py` 新增 `--candidate volume-top125-lb3-sym035`。
- 輸出候選專用 stress CSV。

## 沒改什麼

- 沒有修改正式 live 預設策略。
- 沒有修改候選策略參數。
- 沒有用 stress 結果重新挑 universe / TopN / threshold。
- 沒有把候選升級成正式策略。

## 執行指令

```powershell
python scripts\crypto_top100_forward_monitor.py
python scripts\crypto_cost_stress.py --candidate volume-top125-lb3-sym035 --output output\crypto_cost_stress_top125_candidate.csv
python scripts\crypto_intrabar_path_stress.py --candidate volume-top125-lb3-sym035 --output output\crypto_intrabar_path_stress_top125_candidate.csv
```

## Forward Monitor

| Candidate | Period | eligible symbols | status | reason | trades |
|---|---|---:|---|---|---:|
| forward_volume_top125_lb3_sym_0p35 | 2026-05-08 → 2026-05-08 | 93 | pending | days=1/90, trades=0/50 | 0 |

Forward 仍然沒有足夠樣本，不能做績效判斷。

## Cost Stress 結果

| Scenario | 說明 | 總報酬 | 年化 | MDD | PF | Sharpe | Calmar | 交易數 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | current cost model | +99.43% | +40.86% | -36.57% | 1.291 | 1.012 | 1.117 | 407 |
| B | TP taker fee + TP market slippage | +96.83% | +39.94% | -36.64% | 1.286 | 0.997 | 1.090 | 407 |
| C | 0.2% total market slippage | +88.12% | +36.83% | -37.41% | 1.260 | 0.943 | 0.985 | 407 |
| D | 0.3% total market slippage | +79.19% | +33.57% | -38.24% | 1.244 | 0.886 | 0.878 | 404 |
| E | funding cost 0.03% per day | +72.88% | +31.22% | -38.03% | 1.223 | 0.846 | 0.821 | 407 |
| F | TP taker + 0.3% slippage + funding 0.03% per day | +48.22% | +21.57% | -39.84% | 1.159 | 0.669 | 0.541 | 404 |

## Intrabar Path Stress 結果

| Variant | 總報酬 | 年化 | MDD | PF | Sharpe | Calmar | 交易數 | 同根衝突交易 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TP-first | +99.43% | +40.86% | -36.57% | 1.291 | 1.012 | 1.117 | 407 | 17 |
| SL-first | +84.47% | +35.51% | -36.96% | 1.257 | 0.924 | 0.961 | 407 | 17 |
| Conservative | +84.47% | +35.51% | -36.96% | 1.257 | 0.924 | 0.961 | 407 | 17 |

## 判讀

- 候選策略對一般成本上調仍有韌性：B/C/D/E 都維持 PF >= 1.22、Sharpe >= 0.84。
- 最嚴格成本組合 F 仍有 +48.22% 總報酬與 PF 1.159，但 Sharpe 0.669 低於 0.70、Calmar 0.541 偏弱，因此只能算黃燈。
- 同根 TP/SL 路徑壓力比 baseline 風險小。SL-first / conservative 下仍有 +84.47%、PF 1.257、Sharpe 0.924。
- 同根衝突交易 17 筆，會影響報酬，但不會讓候選失效。

## 結論

需要 forward 驗證。

這次 stress test 支持 `volume-top125-lb3-sym035` 比 raw Top100 / mcap candidate 更合理，但不能取代真正 forward。候選目前通過「成本與日 K 路徑」的基本壓力測試；唯一保留點是極端成本組合下 Sharpe 低於 0.70，所以正式升級前仍要看 live/demo 的真實成交品質與 funding。

## EXP-013 - Default Crypto Strategy Swap

## 日期

2026-05-08

## 目的

依使用者決策，將 `volume-top125-lb3-sym035` 與舊 config baseline 的角色互換：

- `python main.py live` 預設改跑 `volume-top125-lb3-sym035`。
- 舊 config baseline 保留為顯式對照模式：`--crypto-candidate config-baseline`。

## 修改範圍

- `main.py` 新增 `DEFAULT_CRYPTO_CANDIDATE = "volume-top125-lb3-sym035"`。
- `main.py` 新增 `LEGACY_CRYPTO_BASELINE = "config-baseline"`。
- `backtest` 與 `live` 的 `--crypto-candidate` 預設值改成 `volume-top125-lb3-sym035`。
- `_apply_crypto_candidate()` 遇到 `config-baseline` 時不套用候選 universe / WR override，回到舊 config universe。
- README 更新目前正式/舊 baseline 指令。

## 使用方式

正式預設 live：

```powershell
python main.py live --interval 60
```

顯式指定新預設：

```powershell
python main.py live --crypto-candidate volume-top125-lb3-sym035 --interval 60
```

切回舊 baseline 對照：

```powershell
python main.py live --crypto-candidate config-baseline --interval 60
```

## 風險註記

這是策略角色切換，不代表 forward 已通過。`volume-top125-lb3-sym035` 已通過目前歷史 OOS、過擬合檢查、成本壓力、同根 TP/SL 路徑壓力，但 forward monitor 仍只有 1 天 / 0 筆交易。之後若 forward 未達標，需切回 `config-baseline` 或開新候選。

## 結論

forward live。

新策略已成為 `main.py live` 的預設 Crypto 策略；舊 baseline 不刪除，保留為 rollback / 對照模式。
