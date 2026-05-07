# Project Memory

Last updated: 2026-05-07

## Source Of Truth

- Claude Code raw conversation history was not found in `.claude/`.
- `.claude/settings.local.json` mainly contains local permission history.
- `.claude/skills/check-bugs/SKILL.md` contains a project-specific bug-audit workflow, not conversation memory.
- Current project-level memory should come from:
  - `README.md`
  - recent git commits
  - SQLite backtest history
  - this file

## Current Decision Frame

- Treat walk-forward OOS results as the truth.
- Do not promote 5-year continuous backtest numbers as final performance claims.
- For strategy changes, compare both IS and OOS before calling a change better.
- Sweep results are only candidates; every "best" sweep result must be validated OOS before becoming the project baseline.
- Never mix Crypto-only and multi-silo metrics when comparing path-dependency or expected performance.
- User's target for Crypto:
  - Sharpe > 1
  - Calmar > 1
  - Annual return > 20%
  - Win rate > 30%
  - Annual trades around 70-100
  - Keep per-trade risk capped by 1/4 Kelly.

## Latest Version Notes

- Latest git commit observed: `573cb3c docs: v1.13 - walk-forward validation establishes OOS as truth`.
- Previous implementation commit: `120e2e1 feat: tune crypto strategy v1.12 candidate`.
- Bybit live protection commit: `0cbe299 feat: add Bybit demo live stop protection`.

## Crypto Strategy State

- Crypto uses Bybit USDT perpetual daily data.
- Bybit data timestamps are handled in UTC in `src/fetcher.py`; do not casually change timezone unless explicitly testing a new candle boundary hypothesis.
- Crypto leverage remains 1x:
  - `BYBIT_LEVERAGE = 1`
  - `LEVERAGE_BY_CLASS['Crypto'] = 1.0`
- Risk frame remains 1/4 Kelly:
  - `KELLY_FRACTION = 0.25`
  - Crypto fallback risk is around 6%.

## v1.12 Candidate Implementation

- Crypto universe was expanded from roughly 30 symbols to roughly 50 symbols.
- Crypto max simultaneous positions was raised to 10.
- Crypto-only stop/target overrides were added:
  - `trend`: ATR x 2.0, RR 1:2
  - `combined`: ATR x 2.0, RR 1:2
  - `vp`: ATR x 1.5, RR 1:1.5
  - `bb`: kept as the existing short-term BB exit model.
- Crypto-only symbol win-rate filter:
  - threshold 45%
  - minimum 3 trades
  - rolling window 20 trades
- `calculate_stops()` supports `asset_type` so Crypto-only exits do not affect stocks or commodities.
- Backtester symbol win-rate filter supports class-specific overrides.
- Live mode passes `asset_type='Crypto'` into stop calculation.
- This implementation is not the final truth by itself; it must be judged through the v1.13 walk-forward OOS protocol.

## v1.13 Walk-forward Takeaway

- v1.10 look-ahead fixes are considered complete; the v1.12 result was not caused by a newly discovered look-ahead bug.
- The v1.12 full 5-year +627% result is not a hallucination, but it has path-dependency and in-sample boost.
- Correct path-dependency gap is about +110 pp, not the earlier mistaken +497 pp. The +497 pp number came from incorrectly comparing multi-silo IS/OOS with Crypto-only full 5y.
- 5y continuous backtest numbers may be cited only with the OOS comparison next to them.
- Crypto-only OOS, 2024-05-01 to 2026-05-07, is the main benchmark:
  - total return about +87.17%
  - annual return about +36%
  - Sharpe about 0.93
  - profit factor about 1.35
  - max drawdown about -43%
  - win rate about 44%
- Multi-silo OOS is weaker because TW and US+Commodity drag results.
- Earlier statements that "Sharpe 1.139 is not credible" or "realistic annual return is 14%" only apply to multi-silo context. For Crypto-only, the current realistic expectation is roughly annual +36%, Sharpe ~0.93, PF ~1.35, MDD ~-43%.
- The clearest overfit sign is win-rate degradation: IS about 54% -> OOS about 44%. PF, MDD, and Sharpe remain in a reasonable range.
- SYM filter should remain aggressive: threshold 45%, minimum 3 trades, rolling window 20 trades. OOS comparisons showed aggressive 3/20 performed best; conservative filtering was too restrictive and hurt OOS.
- Any future tuning should try to improve Crypto-only OOS without breaking the risk frame.

## Bybit Live Behavior

- `BYBIT_DEMO = True`, `BYBIT_TESTNET = False` means Bybit Demo Trading, not testnet.
- New live entries submit full-position exchange-side TP/SL.
- Live bot syncs existing Bybit positions each scan.
- If an existing Demo position has no SL/TP, live mode backfills TP/SL from current ATR logic.
- Crypto trailing stop is updated through Bybit `set_trading_stop()`.
- Strategy exits that Bybit cannot express natively, such as signal flip or indicator exits, require `python main.py live` to keep running.

## Important Commands

Crypto OOS benchmark:

```powershell
python main.py backtest --profile Crypto `
  --start-date 2024-05-01 --end-date 2026-05-07 `
  --output output\v113_crypto_OOS.xlsx --note v1.13_crypto_OOS
```

Crypto IS benchmark:

```powershell
python main.py backtest --profile Crypto `
  --start-date 2021-03-01 --end-date 2024-04-30 `
  --output output\v113_crypto_IS.xlsx --note v1.13_crypto_IS
```

Crypto full check:

```powershell
python main.py backtest --profile Crypto --output output\crypto_full_check.xlsx
```

Live Bybit demo:

```powershell
python main.py live --interval 60
```

## Known Cautions

- Do not commit `data/`, `output/`, `__pycache__/`, or `.claude/settings.local.json` unless explicitly requested.
- Worktree often has dirty generated files after backtests.
- `data/trading.db-shm` and `data/trading.db-wal` can appear after SQLite use.
- If asked to commit code, stage only intentional source/doc files.
- Always be careful about look-ahead bias, shifted signals, fee/slippage assumptions, and Crypto-vs-stock parameter isolation.
