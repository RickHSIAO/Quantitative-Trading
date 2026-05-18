# REVIEW-008 Draft — Alpha-Space Concentration Cap
**Reviewer:** Claude Sonnet (draft; Opus final review pending)
**Review ID:** REVIEW-008
**Task:** TASK-008 Alpha-Space Concentration Cap
**Run Date:** 2026-05-17
**Draft Date:** 2026-05-17
**Verdict:** CONDITIONAL_PASS_CANDIDATE *(W-1 caveat: top5_conc 87.95% > 75% target；see § 10)*

---

## 1. Scope

TASK-008 implemented three families of alpha-space concentration controls applied as post-selection modifications to `build_prev3y_targets()` outputs, via the new `src/variants/task008.py`. The main strategy signal (`src/signals/prev3y_momentum.py`) was not modified. 11 parameter combinations were tested across Variants A (rolling alpha cap), B (alpha-share sizing), and C (cooldown blacklist). Baseline reconciliation passed (mismatch 5.55e-17 ≪ 1e-10 threshold). No fail gate triggered.

---

## 2. Fail Gates — All Clear (0 / 8)

| Gate | Status |
|---|---|
| F-1 Baseline reconciliation (max diff ≤ 1e-10) | PASS — 5.55e-17 ✅ |
| F-2 `paper_execution_status = FORBIDDEN` | PASS ✅ |
| F-3 No weight-space overlay code | PASS ✅ |
| F-4 `prev3y_momentum.py` main flow unmodified | PASS ✅ |
| F-5 Attribution formula consistent with TASK-003 | PASS ✅ |
| F-6 top5_conc ≤ 100% for all valid variants | PASS (A/B/C-k3) ✅ — C-k6/k12 > 100% correctly flagged as warning |
| F-7 All required outputs present | PASS ✅ |
| F-8 Reproducibility hash verifiable | PASS — hash `4074c89b…` ✅ |

**Zero fail gates. TASK-008 is not blocked by any hard gate.**

---

## 3. Variant-by-Variant Analysis

### 3a. Baseline Reference

| Metric | Baseline | Combined Paper Safe (ref) |
|---|---|---|
| Sharpe (active) | 0.8918 | 0.8037 |
| top5_conc | **95.56%** | 91.92% |
| single_conc | **25.45%** | 19.73% |
| net_alpha | 28.53% | 24.99% |
| long_net | −5.01% | +4.21% |
| alpha_retention | 100% | 87.59% |

---

### 3b. Variant A — Rolling Alpha-Contribution Cap

**Best configurations (A_roll12_share20_exclude = A_roll12_share20_penalize50 = A_roll24_share20_exclude):**

*Note: All three produce identical results. The 12- vs 24-period rolling window yields identical outcomes because the active period (760 days, monthly rebalance ≈ 25 periods) is long enough that both windows capture the same dominant contributors. The penalize50 method is numerically equivalent to exclude at the 20% threshold because penalized symbols' adjusted scores still rank below the top_N cutoff.*

| Metric | Baseline | A_roll12_share20_exclude | Δ |
|---|---|---|---|
| Sharpe (active) | 0.8918 | **0.9636** | **+8.0%** ✅ |
| IR vs eqw | 0.7168 | **0.7289** | **+0.012** ✅ |
| max_DD | −19.64% | −19.64% | 0 ✅ |
| net_alpha | 28.53% | **31.00%** | **+8.65%** ✅ |
| alpha_retention | 100% | **108.65%** | **+8.65%** ✅ |
| top5_conc | 95.56% | **87.95%** | **−7.61pp** ✅ |
| single_conc | 25.45% | **23.43%** | **−2.02pp** ✅ (< 25%) |
| long_net | −5.01% | **−2.56%** | **+2.45pp** ✅ |
| short_net | +33.56% | +33.56% | 0 ✅ |
| cost_impact | — | **−9.73 bps** | **cost reduced** ✅ |
| turnover_change | 1.00× | 0.964× | turnover reduced ✅ |

**Assessment: Pareto-dominant vs baseline across all 11 measured metrics.** Sharpe, IR, net alpha, alpha retention, long_net, top5_conc, single_conc, cost — all improved or equal. No metric deteriorated. This is an unusual result: the concentration cap not only reduces concentration but improves alpha, implying the capped periods (when DOT alpha share exceeds 20%) correspond to periods of high-funding-cost exposure that was drag, not gain.

**A_roll12_share25_exclude:** Nearly identical to baseline (top5 95.49%, Sharpe 0.8925). The 25% threshold is too loose — DOT's rolling alpha share rarely exceeds 25% when measured over a 12-month window. Essentially a no-op.

---

### 3c. Variant B — Alpha-Share-Based Position Sizing

| Metric | Baseline | B_roll12_share20_floor0 | B_roll24_share20_floor0 |
|---|---|---|---|
| Sharpe | 0.8918 | 0.8954 | 0.8977 |
| top5_conc | 95.56% | **95.48%** | **95.22%** |
| single_conc | 25.45% | **25.16%** | **24.94%** |
| net_alpha | 28.53% | 28.66% | 28.74% |
| alpha_retention | 100% | 100.45% | 100.74% |
| long_net | −5.01% | −4.66% | −4.62% |
| cost_impact | — | +0.55 bps | −0.97 bps |

**Assessment:** Variant B achieves minimal concentration reduction. top5_conc moves only 0.3pp (95.56% → 95.22%), single_conc drops from 25.45% → 24.94% — marginal. The reason: since baseline weights are already equal (0.5/N), re-weighting by inverse alpha share causes only small weight adjustments (~±few percent). The attribution-measured concentration is driven almost entirely by **which symbols are selected** (i.e., who is in top_N), not their exact weight magnitude. Variant B attacks the wrong lever.

**Verdict for B: Weak. Not recommended as new baseline. No warning gates triggered (single_conc < 25%), but the concentration improvement is negligible.**

---

### 3d. Variant C — Cooldown Blacklist

| Variant | Sharpe | top5_conc | single_conc | alpha_retention | Assessment |
|---|---|---|---|---|---|
| C_k3_cd2_shared | 0.8925 | 95.49% | 25.43% | 100.07% | No-op — k=3 triggers too rarely |
| C_k12_cd3_side | 0.6236 | **142.9%** | 36.6% | 69.45% | W gates: Sharpe < 0.70, conc explosion |
| C_k6_cd2_side | 0.2144 | **470.5%** | 120.1% | 26.19% | Catastrophic |
| C_k6_cd3_side | 0.1552 | **642.3%** | 163.7% | 18.75% | Catastrophic |

**Assessment: Variant C at k≥6 triggers catastrophically confirms the no_DOT paradox at scale.** When DOT and other top contributors are forcibly cooled out, the denominator of the attribution ratio (total abs net alpha) collapses faster than the numerator (top-5 abs net alpha from remaining symbols), causing top5_conc to explode beyond 100%. This is a mathematical consequence of momentum strategies: the top contributors are top contributors because they generate outsized alpha — remove them, and the strategy's remaining alpha is tiny, but the concentration ratio of what's left is extreme.

The `cooldown_filtered_symbols` count confirms: C_k6_cd3 filtered 259 symbol-periods, C_k6_cd2 filtered 178 — removing meaningful contributors. The effect on the portfolio is equivalent to running with a heavily reduced universe of mediocre-momentum symbols, producing near-random returns where the few remaining positive contributors dominate the attribution ratio.

**C_k3_cd2_shared** is essentially a no-op (same numbers as A_roll12_share25_exclude), indicating k=3 periods is too short to trigger blacklisting in a monthly rebalance cadence with limited universe size.

**Verdict for C: Do not use. Counterproductive for k≥6; no-op for k=3.**

---

## 4. Warning Gates Summary (19 triggered)

| Gate | Variants Triggering | Interpretation |
|---|---|---|
| W-1 top5_conc > 75% | All 11 variants | See § 5 — structural limit of alpha-space cap |
| W-2 Sharpe < 0.70 | C_k6_cd2, C_k6_cd3, C_k12_cd3 | Variant C severe degradation |
| W-3 alpha_retention < 85% | C_k6_cd2, C_k6_cd3, C_k12_cd3 | Variant C severe degradation |
| W-6 long_net < −10% | C_k6_cd2, C_k6_cd3 | Variant C long-side collapse |

**Variant A and B trigger only W-1 (top5_conc).** All other warning gates clear for A and B.

---

## 5. The 75% Top5_Conc Target: Caveat Analysis

**Was the target achieved?** No. Best is A at 87.95% (vs baseline 95.56%).

**Should this be blocking?**

Arguments that it is **not blocking (CAVEAT):**

1. **The workorder classified top5_conc > 75% as W-1 (warning gate), not a fail gate.** By design, it cannot block TASK-008 DONE.

2. **Meaningful improvement was achieved.** 7.61pp reduction (95.56% → 87.95%) is real, directionally correct. single_conc dropped below the 25% hard threshold (25.45% → 23.43%).

3. **Variant C proves the paradox is structural.** More aggressive concentration removal (C_k6) causes top5_conc to rise to 642% — the strategy's alpha is inherently concentrated because momentum strategies select the highest-return symbols. The alpha contributors cannot be evenly distributed; that would require a different strategy, not a cap.

4. **Variant A is Pareto-dominant.** Every metric is equal to or better than baseline. This is a free lunch — adopting A as new baseline improves the strategy on all dimensions simultaneously.

5. **The 75% target may have been set without full appreciation of the mathematical constraint.** After observing that the no_DOT paradox applies not just to one symbol but to the entire alpha-contributor pool, the practical floor for top5_conc in a Prev3Y momentum strategy with ~10–20 active symbols may be closer to 80–90%.

Arguments that it **is blocking:**

1. Concentration remains very high (87.95%) — the strategy is still vulnerable to single-symbol risk (DOT remains #1 contributor at variant A's attribution, contributing 7.26% of net alpha while having 23.43% overall share).

2. If the intent of TASK-008 was to make the strategy safer for paper trading by reducing concentration to 75%, and we cannot reach 75%, one could argue TASK-008 did not achieve its mission.

**Sonnet recommendation:** CAVEAT, not blocking. W-1 is the correct classification. Adopting A_roll12_share20_exclude as the new baseline is strongly justified by the Pareto-dominance across all metrics. Further pursuing the 75% target via more aggressive parameters risks recreating the Variant C catastrophe.

---

## 6. Recommended Variant: A_roll12_share20_exclude

| Dimension | Result |
|---|---|
| Sharpe (active) | **0.9636** (+8.0% vs baseline) |
| top5_conc | **87.95%** (W-1 caveat; −7.61pp vs baseline) |
| single_conc | **23.43%** (< 25% ✅) |
| net_alpha | **31.00%** (+8.65%) |
| alpha_retention | **108.65%** (better than baseline) |
| long_net | **−2.56%** (improved from −5.01%) |
| short_net | **+33.56%** (maintained) |
| max_DD | **−19.64%** (unchanged) |
| cost_impact | **−9.73 bps** (cost reduced) |
| turnover | **0.964×** baseline (slightly less turnover) |
| Fail gates | **0** ✅ |
| Warning gates (A only) | **1** (W-1 top5_conc) |

**Parameter degeneracy note:** A_roll12_share20_penalize50 and A_roll24_share20_exclude produce identical numbers. Recommend using A_roll12_share20_exclude as the canonical specification (shorter window, simpler method).

---

## 7. Safety Verification

- `paper_execution_status: FORBIDDEN` present in all outputs ✅
- `live_trading: FORBIDDEN` present in all outputs ✅
- `src/signals/prev3y_momentum.py` unmodified (TASK-008 only adds `src/variants/task008.py`) ✅
- No exchange connection ✅
- No weight-space overlay code ✅
- `baseline_mismatch: 5.55e-17` — machine precision, PASS ✅

---

## 8. Reproducibility Hash

`4074c89bc2031783901d16a1a40912d99c44a5de0fb6dbb79b0162feec48ff41`

Input hashes recorded in REVIEW-008_NUMBERS.json for all 8 input files.

---

## 9. Scope Compliance

| Red Line | Status |
|---|---|
| `prev3y_momentum.py` main flow not modified | ✅ Confirmed |
| No weight-space overlay (cap+redistribution) | ✅ Confirmed |
| No exchange API connection | ✅ Confirmed |
| No paper/live trading code | ✅ Confirmed |
| Official baseline outputs not modified | ✅ Confirmed |
| Attribution formula = TASK-003 standard | ✅ Confirmed |

---

## 10. Verdict

> **CONDITIONAL_PASS_CANDIDATE** *(draft — pending Opus final review)*

| Gate | Result |
|---|---|
| Fail gates (8) | All PASS ✅ |
| Baseline reconciliation | PASS (5.55e-17) ✅ |
| paper/live FORBIDDEN | Confirmed in all outputs ✅ |
| Reproducibility | PASS ✅ |
| Safety scan | PASS ✅ |
| Recommended variant (A_roll12_share20_exclude) | Pareto-dominant vs baseline ✅ |
| top5_conc < 75% (W-1) | **NOT achieved — 87.95%** (Caveat, not blocking) |
| single_conc < 25% | **ACHIEVED — 23.43%** ✅ |
| Sharpe ≥ 0.70 (recommended variant) | **ACHIEVED — 0.9636** ✅ |
| alpha_retention ≥ 85% | **ACHIEVED — 108.65%** ✅ |

**The blocking question for Opus:** Is the W-1 caveat (top5_conc 87.95% > 75%) acceptable to adopt A_roll12_share20_exclude as the new production baseline, given that (a) it is Pareto-dominant, (b) Variant C proves more aggressive concentration removal is catastrophic, and (c) the 75% target may be structurally unreachable for this strategy class?

---

## 11. Downstream Implications

If Opus approves CONDITIONAL_PASS → TASK-008 DONE:
1. `A_roll12_share20_exclude` becomes the new baseline for paper trading (replaces `combined_paper_safe_variant` as the structural solution).
2. The rolling alpha cap mechanism should be incorporated into `scripts/run_prev3y_crypto_baseline.py` to produce an updated official baseline CSV + stats.
3. REVIEW-006b can be opened (30-day forward record + 3 補件落地 conditions already met).
4. The 30-day forward record should use the new A_roll12 baseline once adopted (or continue combined_paper_safe_variant if clock already started).

If Opus rules W-1 as BLOCKING → TASK-008 remains TODO:
1. Sonnet to draft TASK-008b with further parameter exploration (e.g., shorter rolling window of 3–6 periods, or a hybrid A+B approach).
2. combined_paper_safe_variant remains the interim paper spec.
3. Acknowledge structural limit: document that top5_conc floor for Prev3Y momentum is likely 80–90%.

---

## 12. Suggested Opus Prompt

```
【本次唯一目標】執行 REVIEW-008 final decision。

請讀：
1. CLAUDE.md
2. docs/research/commands/NEXT_ACTION.md
3. docs/research/codex_workorders/TASK-008_alpha_space_concentration_cap.md
4. docs/research/review_packets/REVIEW-008_PACKET.md
5. docs/research/review_packets/REVIEW-008_NUMBERS.json
6. docs/research/review_drafts/REVIEW-008_DRAFT_BY_SONNET.md
7. outputs/variants/prev3y_crypto/20260517_task008_comparison.csv
8. outputs/variants/prev3y_crypto/20260517_task008_attribution.json

Sonnet draft verdict: CONDITIONAL_PASS_CANDIDATE。
關鍵發現：
- 0 fail gates；fail gates 全 PASS
- 推薦 variant：A_roll12_share20_exclude
  - Sharpe 0.9636（baseline 0.8918，+8.0%）
  - single_conc 23.43%（< 25% ✅）
  - top5_conc 87.95%（baseline 95.56%，−7.61pp；W-1 = 87.95% > 75% 目標未達）
  - net_alpha 31.00%（baseline 28.53%，+8.65%）
  - cost −9.73 bps（成本降低）
  - alpha_retention 108.65%（優於 baseline）
  - Pareto-dominant across all 11 metrics
- Variant B：集中度幾乎無改善（top5 95.22%，比 baseline 95.56% 稍好）
- Variant C（k≥6）：catastrophic，no_DOT 悖論在規模上完全重現（top5 高達 642%）
- A_roll12_share20 = A_roll24_share20 = A_roll12_penalize50（三者完全等效）

核心問題（請 Opus 裁定）：
1. W-1（top5_conc 87.95% > 75%）是 CAVEAT（接受 A 為新 baseline）還是 BLOCKING（需更多研究）？
2. 若 CAVEAT：請確認 A_roll12_share20_exclude 為正式新 baseline，更新 TASK-008 DONE，並指示是否需要重跑官方 baseline script。
3. 若 BLOCKING：請說明 75% 是否仍為合理目標，或應下修（考慮 Variant C 悖論）。

不要標 TASK-008 DONE 除非 final review 明確 PASS。
不要批准 paper execution。
不要批准 live trading。
不要修改策略程式或官方輸出。
```

---

*Draft produced by Claude Sonnet per NEXT_ACTION.md REVIEW-008 instructions.*
*Final decision requires Opus review.*
