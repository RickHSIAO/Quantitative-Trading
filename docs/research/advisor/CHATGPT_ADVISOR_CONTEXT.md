# ChatGPT Advisor Context

## Last Updated

2026-05-15 Asia/Taipei

---

## Status Lock

- **TASK-002**: REVIEW pending Opus final decision — 不可提前標 `DONE`
- **Codex**: Do not implement new tasks — 等待 Opus 裁定後再依 queue 開新任務
- **Sonnet**: Do not mark TASK-002 DONE — 草稿審查權限只到 `PASS_CANDIDATE`
- **Opus**: Only final decision may update TASK-002 / TASK-003 / TASK-004 / TASK-005 state
- **Live trading**: Forbidden — 任何模型皆不得授權 live trading

---

## ChatGPT Latest Recommendation

- TASK-002 已由 Codex 完成正式 cost / funding / slippage stress，Sonnet draft 給出 `PASS_CANDIDATE`。
- 目前不要讓 Codex 再修改或重跑，也不要把 TASK-002 直接標 `DONE`。
- 下一步應由 Claude Opus 執行 `REVIEW-002 final decision`。
- Opus 應判斷 TASK-002 是否 PASS、是否解鎖 TASK-003 / TASK-004 / TASK-005，以及 paper trading 是否只能開始規劃。
- 目前初步判斷：成本沒有殺死策略，但策略仍不具 BTC alpha；應該是「需要更多測試」，而不是立即上線。

---

## Suggested Next Action

1. 使用 Opus 執行 `REVIEW-002 final decision`。
2. 若 REVIEW-002 為 `PASS` / `CONDITIONAL_PASS`：
   - TASK-002 可轉 `DONE`。
   - TASK-003 attribution 可解鎖。
   - TASK-004 dashboard 可開始規劃。
   - TASK-005 VPS / monitor 可開始規劃。
   - Paper trading 可開始規劃，但 live trading 仍禁止。
3. REVIEW-002 final 前不要重跑 cost stress，不要改策略，不要改 run008。

---

## Risk Warnings

- 不要把 Sonnet draft 當 final verdict。
- 不要使用舊架構 `output/crypto_cost_stress.csv` 或 `scripts/crypto_cost_stress.py`。
- TASK-002 結果看起來健康，但 active sample 仍只有 760 天。
- 策略相對 BTC 仍幾乎沒有 alpha。
- Funding gap / outlier caveats 必須保留。
- Paper trading 可以規劃，但不代表能立即執行，更不代表 live trading。

---

## Prompt To Claude

請使用 Opus，執行 `REVIEW-002 final decision`。

請只讀最小審查包：

1. `docs/research/context_packets/TASK-002_CONTEXT_PACKET.md`
2. `docs/research/review_drafts/REVIEW-002_DRAFT_BY_SONNET.md`
3. `outputs/backtests/prev3y_crypto/20260515_cost_stress_summary.json`
4. `outputs/backtests/prev3y_crypto/20260515_cost_stress.csv`
5. `outputs/logs/prev3y_crypto/20260515_cost_stress.log`

請不要重述完整背景。
請不要修改策略程式。
請不要重新跑回測或 stress test。

請做最終決策：

1. TASK-002 是否 `PASS` / `CONDITIONAL_PASS` / `FAIL`？
2. `realistic_combo` 是否通過 fail gate？
3. `conservative_combo` 是否通過 fail gate？
4. `worst_case_combo` 是否只作壓力測試，不作淘汰依據？
5. cost / slippage / funding 哪一類吃掉最多 alpha？
6. 策略 edge 是否足以進入下一階段研究？
7. 是否允許 TASK-002 轉 `DONE`？
8. 是否解鎖 TASK-003 attribution？
9. 是否解鎖 TASK-004 dashboard？
10. 是否解鎖 TASK-005 VPS / monitor？
11. 是否允許 paper trading 規劃？
12. 是否仍禁止 live trading？
13. 策略目前判定是：保留 / 淘汰 / 需要更多測試。

請把結果追加到：

- `docs/research/CLAUDE_REVIEW_LOG.md`

並更新：

- `docs/research/CODEX_TASK_QUEUE.md`
- `docs/research/CLAUDE_REVIEW_QUEUE.md`

---

## Prompt To Codex

目前暫時不要讓 Codex 做任何新實作。

等待 Claude Opus `REVIEW-002 final decision` 後，再依 queue 開 TASK-003 / TASK-004 / TASK-005。
