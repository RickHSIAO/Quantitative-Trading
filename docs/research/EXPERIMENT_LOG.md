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
