# Claude 對話筆記 — Bug 掃描 → Look-ahead 修正 → Walk-forward 驗證

> 本檔由 Claude 重建本次對話的內容與結論。原始對話 transcript 並未直接匯出，這是結構化重整版本，方便日後翻查決策脈絡與實驗數據。
>
> 對應的 git commits：
> - `f072063` — fix: eliminate look-ahead bias and harden backtester (v1.10)
> - `cc18b6d` — feat: v1.11 — re-tune crypto cap=4 and recover BLOB-corrupted volumes
> - `120e2e1` — feat: tune crypto strategy v1.12 candidate（user 自己 commit）
> - `573cb3c` — docs: v1.13 — walk-forward validation establishes OOS as truth

---

## 0. 本次對話的起點與終點

| 階段 | 起點 | 終點 |
|---|---|---|
| 引擎品質 | 含 look-ahead bias，回測虛高約 1.93x | 已修正，回測可實盤複製 |
| Crypto cap | 5（path-dep 推出來的偽最佳） | 4（post-fix sweep 確認） |
| SQLite 資料 | 102 個資產靜默被 skip（BLOB 汙染） | 全部還原，回測跑滿 132 檔 |
| 績效解讀規範 | 看 5y 連續回測 → 容易被 path-dep 騙 | OOS 為真實基準，5y 連續僅供 sanity |
| Crypto-only 真實基準 | 未知（被 +627% 幻覺遮蓋） | OOS 年化 +36% / Sharpe 0.93 / PF 1.35 / MDD −43% |

---

## 1. 起手式：建立 `/check-bugs` Skill

User 要求一個能快速檢查專案 BUG 與邏輯不符的 slash command。

新增檔案：[.claude/skills/check-bugs/SKILL.md](../.claude/skills/check-bugs/SKILL.md)

執行流程：
1. Glob 出所有原始碼（排除 `.venv/`, `__pycache__/`, `output/`, `data/`）
2. 平行靜態檢查（`compileall` + `ast.parse` + 可選的 ruff/mypy）
3. 平行語意審查（`Explore` subagents 分群審 strategies / backtester / risk+executors / fetcher+database+main）
4. 量化交易專屬檢查（look-ahead, 手續費, 槓桿, 時區, DB 一致性）
5. 輸出修復清單（依嚴重度排序，不主動改檔）

安全限制：不安裝套件、不執行回測或下單腳本、不主動改檔。

---

## 2. 第一輪掃描結果

### 2.1 高風險發現（HIGH）

| # | 檔案 | 問題 |
|---|---|---|
| 1 | [src/backtester.py:574-580](../src/backtester.py#L574-L580) | **Look-ahead bias**：`a_close[sym][i]` 同根 K 棒收盤同時觸發訊號 + 進場 |
| 2 | [src/backtester.py:723](../src/backtester.py#L723) | Sharpe 年化因子寫死 `sqrt(252)`，crypto 應為 365 |
| 3 | [src/fetcher.py:49-50](../src/fetcher.py#L49-L50) | Bybit kline 起訖時戳用本地時區，台北 UTC+8 會差 8 小時 |
| 4 | [src/executors/bybit.py:129](../src/executors/bybit.py#L129) | `place_order` 失敗只回 retCode、不拋例外 |

### 2.2 中風險發現（MED）

| # | 檔案 | 問題 |
|---|---|---|
| 5 | [src/strategies.py:88-93](../src/strategies.py#L88-L93) | EMA50 斜率濾網也含當日 |
| 6 | [src/indicators.py:73-77](../src/indicators.py#L73-L77) | Supertrend NaN 期 direction 預設 +1（應沿用前值） |
| 7 | [src/executors/router.py:45-65](../src/executors/router.py#L45-L65) | `get()` 可能回 None，呼叫端需 guard |
| 8 | [src/executors/bybit.py:97-118](../src/executors/bybit.py#L97-L118) | 槓桿沒 clamp 到 instrument 上限 |
| 9 | shinkong/ibkr | qty 整數截斷無警告 |

### 2.3 低風險（LOW）

| # | 檔案 | 問題 |
|---|---|---|
| 10 | database.py:276 | `LIMIT {limit}` f-string |
| 11 | backtester.py:733 | CAGR `max(years, 1)` cap |
| 12 | reporter.py:60 | `except: pass` 過寬 |

### 2.4 Subagent 誤報（false positives）

驗證後排除：
- ~~backtester.py:186 用 trade.exit_price~~ → 實際用 `actual_exit`，正確
- ~~risk.py:91 除以零~~ → line 82 已先擋
- ~~indicators.py:146 BB 寬度除零~~ → `mid.replace(0, np.nan)` 正確
- ~~indicators.py:221 bsize<=0~~ → 同行已 `continue`
- ~~indicators.py:244 Value Area off-by-one~~ → 70% 是「至少」業界標準

---

## 3. v1.10 修正（commit `f072063`）

### 3.1 核心修正

```python
# src/backtester.py:282-293 — 訊號統一 shift(1)
def _sig_arr(sigs: dict, key: str, n: int) -> np.ndarray:
    # Shift by 1 bar: signal computed at end of bar t-1 acts on bar t.
    ser = sigs.get(key)
    if ser is None:
        return np.zeros(n, dtype=np.int64)
    arr = ser.fillna(0).to_numpy(dtype=np.int64)
    shifted = np.zeros_like(arr)
    if n > 1:
        shifted[1:] = arr[:-1]
    return shifted
```

```python
# src/backtester.py:735-744 — Sharpe 年化因子自動推導
eq_dates_tmp = [e['date'] for e in self.equity_curve]
if len(eq_dates_tmp) > 1:
    span_days = (pd.Timestamp(eq_dates_tmp[-1]) - pd.Timestamp(eq_dates_tmp[0])).days
    years_span = span_days / 365.25 if span_days > 0 else 1.0
    annual_factor = (len(eq_dates_tmp) / years_span) if years_span > 0 else 252.0
else:
    annual_factor = 252.0
sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(annual_factor)
          if daily_ret.std() > 0 else 0.0)
```

```python
# src/fetcher.py:48-50 — UTC 時戳
start_ts = int(datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp() * 1000)
end_ts   = int(datetime.strptime(end,   '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp() * 1000)
```

```python
# src/indicators.py:73-77 — Supertrend NaN direction
direction = np.zeros(n, dtype=int)  # was np.ones
for i in range(1, n):
    if np.isnan(atr[i]) or np.isnan(atr[i - 1]):
        direction[i] = direction[i-1]  # was: continue (kept stale +1)
        continue
```

```python
# src/strategies.py:76-79 — Supertrend 訊號加 prev_dir 守門
dir_chg = df['supertrend_dir'].diff()
prev_dir = df['supertrend_dir'].shift(1)
sig[(dir_chg > 0) & (prev_dir == -1)] = LONG   # 排除 0→±1 暖機假觸發
sig[(dir_chg < 0) & (prev_dir == 1)]  = SHORT
```

Bybit `place_order` 改 `raise OrderRejected`、加槓桿 clamp、qty 截斷 warn（詳見 commit `f072063`）。

### 3.2 修正前後（同份資料、同套參數，多 silo）

| 指標 | Pre-fix (run 52) | Post-fix (run 53) | Δ |
|---|---:|---:|---:|
| 總報酬 | +148.86% | +63.42% | −85.44 pp |
| CAGR | +19.27% | +9.96% | −9.31 pp |
| Sharpe | 0.569 | 0.450 | −0.119 |
| Profit Factor | 1.332 | 1.148 | −0.184 |
| 最大回撤 | −47.11% | −50.94% | −3.83 pp |
| 勝率 | 50.68% | 50.51% | −0.17 pp |
| 總交易 | 296 | 293 | −3 |
| 最佳單筆 | $2,693 | $1,791 | −33.5% |

**為什麼勝率幾乎沒變但報酬腰斬？**
方向判斷正確（勝率不動），但 look-ahead 等同「同根 K 棒收盤偷看 → 進場」。修正後：
- 贏單利潤被砍 33.5%（原本人為加大）
- 輸單金額幾乎不變（方向錯時 t vs t+1 的價差有限）
- 結果：PF 1.332 → 1.148

---

## 4. v1.11 — BLOB 資料修復 + cap 重調（commit `cc18b6d`）

### 4.1 BLOB Volume 汙染

**症狀**：每次回測都看到 `[WARN] XXX: unsupported operand type(s) for +: 'float' and 'bytes'`，102 個資產靜默被 skip。

**根因**：yfinance 偶爾把 Volume 回成 numpy bytes，SQLite 動態型別存成 8-byte little-endian int64 BLOB；pandas 回讀時整列轉 object dtype，indicators 加法直接炸。

**修復**：
```python
# src/database.py upsert_prices — 寫入前統一 coerce
o  = pd.to_numeric(_col('open'),   errors='coerce').to_numpy(dtype=float)
h  = pd.to_numeric(_col('high'),   errors='coerce').to_numpy(dtype=float)
lo = pd.to_numeric(_col('low'),    errors='coerce').to_numpy(dtype=float)
c  = pd.to_numeric(_col('close'),  errors='coerce').to_numpy(dtype=float)
v  = pd.to_numeric(_col('volume'), errors='coerce').to_numpy(dtype=float)
```

**Migration**：對既有 DB 跑一次性還原：
```python
import struct
for sym, dt, blob in cur.execute("SELECT symbol, date, volume FROM prices WHERE typeof(volume)='blob'").fetchall():
    v = float(struct.unpack('<q', blob)[0])
    cur.execute('UPDATE prices SET volume=? WHERE symbol=? AND date=?', (v, sym, dt))
```

3,352 列無損還原，影響資產：`^GSPC`（1,549）、`^TWII`（1,497）、102 檔個股各 3 列。

### 4.2 Crypto sweep 重調 — cap=5 → cap=4

post-fix 引擎下重跑 sweep5：

| cap (max_total_positions) | CAGR | 勝率 | PF | MDD |
|---:|---:|---:|---:|---:|
| 3 | +14.97% | 54.1% | 1.26 | −46.6% |
| **4 (new default)** | **+17.40%** | **52.3%** | **1.28** | **−44.16%** |
| 5 (v1.9) | +9.96% | 50.5% | 1.15 | −50.94% |

### 4.3 EMA50 slope filter A/B（2×2）

| 整體總報酬 | slope ON | slope OFF |
|---|---:|---:|
| **cap=5** (v1.9) | +21.78% | +30.52% |
| **cap=4** (v1.11) | **+43.75%** ✨ | +26.27% |

**最佳組合是 cap=4 + slope ON**（不是兩項各自最佳的疊加）。cap 緊讓資金集中在最強訊號 + slope filter 補品質檢查 → 雙重增強。

### 4.4 v1.11 套用後（commit `cc18b6d`，仍保留 slope ON）

| 階段 | 總報酬 | PF | MDD | 備註 |
|---|---:|---:|---:|---|
| v1.9 (pre-fix biased) | +148.86%* | 1.332 | −47.11% | 含 look-ahead，偽數字 |
| v1.10 (post-fix, cap=5) | +21.78% | 1.095 | −25.56% | 真實表現基線 |
| **v1.11 (cap=4)** | **+43.75%** | **1.184** | **−23.22%** | 重調後可實盤複製 |

\* 僅 30 檔 crypto；v1.10/v1.11 為 132 檔全集。

---

## 5. v1.12 candidate（user 自己 commit `120e2e1`）

User 加了三項變動：
1. `STRAT_PARAMS_BY_CLASS['Crypto']` — 趨勢 ATR/RR 改 (2.0, 2.0)、VP 改 (1.5, 1.5)
2. `SYM_MIN_WINRATE_BY_CLASS = {'Crypto': 0.45}` + `min_trades=3` + `window=20` — 對該幣最近 N 筆勝率 < 45% 就停止新進場
3. `CRYPTO_EXTRA_COUNT = len(CRYPTO_POOL)` — Crypto universe 30 → 51 檔

User 用 `--profile Crypto` 跑，得到：
- 總報酬 +627.44% / 470 trades / WR 51.5% / PF 1.546 / Sharpe 1.139 / MDD −42.13%

**問 Claude 是不是 BUG / 幻覺？**

---

## 6. 第二輪審查 — +627% 成因分析

### 6.1 確認沒有 look-ahead 回滾

- ✅ Signal `shift(1)` 仍在 [backtester.py:282-293](../src/backtester.py#L282-L293)
- ✅ Sharpe 年化因子自動推導仍在 [backtester.py:741-744](../src/backtester.py#L741-L744)
- ✅ `SYM_MIN_WINRATE` 用的 `history_by_sym[sym]` 只含已平倉 trades，point-in-time 正確（不是 look-ahead）

### 6.2 SYM_MIN_WINRATE 機制

```python
# src/backtester.py:517-529
sym_min_wr = _cls_get('SYM_MIN_WINRATE_BY_CLASS', atype_for_score, config.SYM_MIN_WINRATE)
sym_wr_window = _cls_get('SYM_WR_WINDOW_BY_CLASS', atype_for_score, config.SYM_WR_WINDOW)
sym_wr_min_trades = _cls_get('SYM_WR_MIN_TRADES_BY_CLASS', atype_for_score, config.SYM_WR_MIN_TRADES)
if sym_min_wr > 0:
    hist = history_by_sym[sym][-sym_wr_window:]
    if len(hist) >= sym_wr_min_trades:
        wins = sum(1 for t in hist if t.pnl is not None and t.pnl > 0)
        if wins / len(hist) < sym_min_wr:
            continue
```

**問題不是 look-ahead，是 path-dependent overfitting**：
- `min_trades=3` 太小：一個幣前 3 筆運氣差全虧 → **永久驅逐**（hist 只剩 [-20:]，永遠看到那 3 筆都虧）
- 5 年連續回測：filter 從 day 1 累積 history，到第 5 年握有 5 年完整 trade history → 等同事後挑幣
- 同樣的策略在實盤跑，只能往前走，無法重訓

### 6.3 初步隔離實驗（多 silo, 5y full）

| 設定 | 總報酬 | 交易數 |
|---|---:|---:|
| v1.12 含 SYM filter | (用戶提供 +627% — 但那是 `--profile Crypto`，對比錯) |
| v1.12 minus SYM filter（多 silo） | +217.07% | 1285 |

---

## 7. Walk-forward 驗證

### 7.1 切點與 4 組對照（**多 silo**）

切點 2024-05-01：IS = 2021-03 ~ 2024-04（3 年）/ OOS = 2024-05 ~ 2026-05（2 年）。

| 設定 | IS 3y | OOS 2y | 5y full |
|---|---:|---:|---:|
| v1.12 aggressive (3/20) | +75.88% / PF 1.39 / WR 45.6% | +30.82% / PF 1.25 / WR 42.7% | (跑後得 +209%) |
| v1.12 no SYM filter | +84.25% / PF 1.42 / WR 45.1% | +25.17% / PF 1.21 / WR 42.4% | +217% |
| v1.13 conservative (30/50) | +109.98% / PF 1.47 | +23.80% / PF 1.20 | +346.17% |

### 7.2 重大誤判修正：應該用 Crypto-only 對比

我一開始用「多 silo IS/OOS」對比「user 提供的 Crypto-only 5y +627%」算 path-dep gap，得 +497 pp。**錯了**。

正確：補跑 Crypto-only IS/OOS（`--profile Crypto`，$10k）：

| 指標 | IS 3y (run 73) | **OOS 2y (run 74) — 真實基準** | 5y full (run 75) | IS+OOS 複利 |
|---|---:|---:|---:|---:|
| 總報酬 | +229.88% | **+87.17%** | +627.44% | +517.50% |
| 年化 | 45.90% | **36.49%** | 46.71% | — |
| 勝率 | 53.95% | 43.81% | 51.49% | — |
| Profit Factor | 1.533 | **1.346** | 1.546 | — |
| Sharpe | 1.103 | **0.930** | 1.139 | — |
| 最大回撤 | −42.13% | −43.01% | −42.13% | — |
| 交易數 | 291 | 226 | 470 | — |

**Path-dep gap = +627.44% − +517.50% = +110 pp**（不是 +497 pp）。

### 7.3 結論

- ✅ **+627% 不是 BUG**：用的全是 point-in-time 過去資料，無 look-ahead
- ✅ **+627% 也不全是幻覺**：path-dep 加持只佔 +110 pp，OOS 仍有 +87.17%
- ⚠️ **5y 連續數字仍不可作宣傳**：path-dep 是 in-sample 才有的「累積優勢」，實盤無法重現
- ✅ **Sharpe 0.93 是真實的**（之前我誤判為「不可信」，已更正）
- ⚠️ **WR 從 IS 54% → OOS 44% 退化 10 pp**：最明顯的 in-sample overfitting 徵兆
- ✅ **PF 1.35 / Sharpe 0.93 / MDD −43%** 在 1x 槓桿 crypto 永續是合理水準

---

## 8. v1.13 拍板（commit `573cb3c`）

### 8.1 SYM filter 三組 OOS 對照

| 設定 | OOS 多 silo | 5y 多 silo | Path-dep |
|---|---:|---:|---:|
| **aggressive (3/20)** ✅ | **+30.82%** | ~+209% | 中-大 |
| conservative (30/50) | +23.80% | +346.17% | 中 |
| no filter | +25.17% | +217.07% | ~0 |

**OOS 最佳是 aggressive**，最終保留。conservative 過保守反而 OOS 最差（該砍的幣留太久）。

### 8.2 真實期望基準

- **Crypto silo（1x 槓桿、永續）**：年化 +36% / Sharpe 0.93 / PF 1.35 / MDD −43%
- 多 silo 整體：年化 +14%（被 TW Stock +2.63%、US+Comm −2.54% 拖累）

### 8.3 新規範（寫進 README 頂端）

| 數字類型 | 是否可信 | 用途 |
|---|---|---|
| 5 年連續回測 | ⚠️ 含 path-dep | sanity check，不可宣傳 |
| 3 年 IS | ⚠️ in-sample | 對照組 |
| **2 年 OOS** | ✅ 真實基準 | 決策依據 |

任何策略改動必須 OOS 績效提升才能採用，sweep 腳本找出的「最佳」必須 OOS 再驗證才入 main。

### 8.4 重現指令

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

---

## 9. 後續 backlog

| 優先度 | 項目 | 備註 |
|---|---|---|
| 高 | US+Commodity silo OOS 仍 −2.54% | 結構性議題，需單獨檢視該 silo 的訊號 / 出場 |
| 中 | 重跑既有 sweep 腳本並補 OOS 驗證 | 之前找到的「最佳參數」可能都是 in-sample 結果 |
| 中 | 把 walk-forward 流程內化進 sweep 腳本 | 避免下次又被 5y 連續數字騙 |
| 低 | TW Stock OOS 雖然正但偏低（+2.63%） | 是否值得留 silo 待評估 |
| 低 | Sweep 腳本顯示的數字也應加註 IS / OOS 標籤 | 一致性 |

---

## 10. 本次對話的「自我修正」記錄

Claude 在本次對話中犯過 / 修正過的錯誤：

1. **誤判 path-dep gap 為 +497 pp**（實際 +110 pp）
   原因：用「多 silo IS/OOS」對比「Crypto-only 5y」，silo 範圍不同
   修正：補跑 Crypto-only IS/OOS 後重算

2. **誤判 Sharpe 1.139 為「不可信」**
   原因：基於誤判 #1 推論「真實 Sharpe < 0.7」
   修正：Crypto-only OOS Sharpe 0.93，1.139 只略高一點，數字可信

3. **誤判「真實年化 14%」適用所有情況**
   原因：14% 是多 silo 數字（被 TW/US 拖累），Crypto-only 是 36%
   修正：README 標明兩個範圍的差異

4. **conservative SYM filter 推薦失準**
   原本認為 conservative (30/50) 可緩解 path-dep 應為較好選擇
   實測：OOS 反而最差（+23.80% vs aggressive +30.82%）
   修正：roll back 到 aggressive，並在 config 加註說明

教訓：**在多 silo / 多範圍系統下，所有數字都要附「範圍 + 期間」標籤，避免跨範圍比較**。

---

## 附錄 A：本次對話新增 / 修改的檔案

| 檔案 | 性質 | commit |
|---|---|---|
| [.claude/skills/check-bugs/SKILL.md](../.claude/skills/check-bugs/SKILL.md) | 新增 | f072063 |
| [src/backtester.py](../src/backtester.py) | 修正 | f072063 + cc18b6d |
| [src/database.py](../src/database.py) | 修正 | f072063 + cc18b6d |
| [src/executors/bybit.py](../src/executors/bybit.py) | 修正 | f072063 |
| [src/fetcher.py](../src/fetcher.py) | 修正 | f072063 |
| [src/indicators.py](../src/indicators.py) | 修正 | f072063 |
| [src/reporter.py](../src/reporter.py) | 修正 | f072063 |
| [src/strategies.py](../src/strategies.py) | 修正 | f072063 |
| [config.py](../config.py) | 修正 | cc18b6d + 573cb3c |
| [README.md](../README.md) | 文件 | f072063 + cc18b6d + 573cb3c |
| [docs/claude-notes.md](claude-notes.md) | 新增（本檔） | (待 commit) |

## 附錄 B：本次對話用到的 backtest run_id 對照

| run_id | 用途 | 關鍵數字 |
|---|---|---|
| 52 | pre-fix baseline | +148.86% / PF 1.332 / Sharpe 0.569 |
| 53 | post-fix baseline | +63.42% / PF 1.148 / Sharpe 0.450 |
| 54 | post-fix + BLOB migration（cap=5, slope ON） | +21.78% (多 silo) |
| 55 | cap=5 + slope OFF | +30.52% |
| 56 | cap=4 + slope ON | +43.75% |
| 57 | cap=4 + slope OFF | +26.27% |
| 58 | v1.11 cap=4 default | +43.75% |
| 63 | v1.12 candidate `--profile Crypto` | +627.44% |
| 64 | v1.12 minus SYM filter（多 silo） | +217.07% |
| 65 | WF A: v1.12 full IS（多 silo） | +75.88% |
| 66 | WF B: v1.12 full OOS（多 silo） | +30.82% |
| 67 | WF C: no SYM filter IS（多 silo） | +84.25% |
| 68 | WF D: no SYM filter OOS（多 silo） | +25.17% |
| 69 | WF E: conservative SYM IS（多 silo） | +109.98% |
| 70 | WF F: conservative SYM OOS（多 silo） | +23.80% |
| 71 | WF G: conservative SYM full（多 silo） | +346.17% |
| 72 | v1.13 sanity full 5y（多 silo, aggressive） | +209.79% |
| 73 | WF Crypto-only IS | +229.88% / Sharpe 1.103 |
| 74 | **WF Crypto-only OOS（真實基準）** | **+87.17% / Sharpe 0.930** |
| 75 | WF Crypto-only full 5y | +627.44% / Sharpe 1.139 |
