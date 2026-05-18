# Next Action

## Status
WAITING

## Owner
Rick

## Task
Option E 完了。gitignore 全面修正（NTFS truncation 修復 + 残存 untracked artifacts 追加）。
`git status --short` = clean（no modified tracked files, no untracked）。
30-day clock 啟動の準備が整った（Rick の「開始計時」指示待ち）。

## Last Completed
Discord webhook VPS strict guard validation — confirmed on actual VPS（2026-05-18，Rick + Claude Sonnet）
- VPS hostname: instance-20260506-0945 / python: .venv/bin/python
- overall_result=PASS（6/6 gates）
- W-0 PASS：actual webhook_config_present=True  webhook_config_non_empty=True  secret_value_observed=False
- G-1 PASS：dry_run=True  external_post_attempted=False  load_channel_secrets_called=False
- G-2 PASS：URL redaction confirmed
- G-3 PASS：status=DRY_RUN  secret_value_observed=False
- G-4 PASS：violations=[]
- G-5 PASS：dry_run=True  FORBIDDEN_live_trading=NOT_ATTEMPTED  FORBIDDEN_bybit_write=NOT_ATTEMPTED
- clock_started=False  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
- Artifact：`outputs/forward_record/discord_webhook_vps_dry_run/20260518/validation_result.json`

## Paper Execution Gate 現況（5/7）
- TASK-007b DONE ✅
- TASK-005 DONE ✅
- TASK-005a DONE ✅
- TASK-006 三補件 ✅
- Rick test-send ✅
- ❌ 30 天 forward paper record（VPS 部署 + Rick 明示啟動後計時）
- ❌ REVIEW-006b + Rick 批准

## 30-day Clock 啟動前需完成的前置條件

| 條件 | 狀態 |
|---|---|
| TASK-009 runner DONE | ✅ |
| TASK-009b forward monitor alerting DONE | ✅ |
| TASK-009c tech debt 收斂 DONE | ✅ |
| TASK-009d alert E2E drill DONE | ✅ |
| Windows baseline artifact | ✅（90 tests；SHA-256 b8d4fd69…） |
| VPS 部署 + dry-run validation | ✅（Ubuntu 24.04；REVIEW_READY；drill 13/13） |
| Read-only data source validation | ✅（cache + Bybit public GET PASS） |
| Discord webhook dry-run dispatch 安全性（コード解析）| ✅（G-1~G-5 code analysis + G-2/G-4 sandbox） |
| Discord webhook VPS strict guard drill + actual config 確認 | ✅ DONE（2026-05-18；instance-20260506-0945；PASS 6/6） |
| working tree clean（Option C + E commits）| ✅ DONE（2026-05-18；378dc34 / c20bc09 / 2d5d90c / a833f4f / gitignore-fix） |
| Rick 明示「開始計時」 | ❌ 待 Rick 指示 |

## Tracked Modified Files — 解決済み（2026-05-18）

| ファイル | 処置 | 結果 |
|---|---|---|
| `src/backtester.py` | `git show HEAD: \| write` → CRLF→LF 復元 | ✅ HEAD 一致 |
| `src/indicators.py` | 同上 | ✅ HEAD 一致 |
| `src/reporter.py` | 同上 | ✅ HEAD 一致 |
| `src/risk.py` | 同上 | ✅ HEAD 一致 |
| `src/strategies.py` | 同上 | ✅ HEAD 一致 |
| `tests/monitor/test_channels.py` | 同上（NTFS truncation 復元；276L） | ✅ HEAD 一致 |
| `.claude/settings.local.json` | `git rm --cached` | ✅ untracked（on disk） |
| `outputs/monitor/prev3y_crypto/alerts/20260517.jsonl` | `git rm --cached` | ✅ untracked（on disk） |
| `outputs/variants/prev3y_crypto/` (5 files) | `git rm --cached` | ✅ untracked（on disk） |

## gitignore 修正内容（Option E — 2026-05-18）

.gitignore が NTFS truncation により 115B/8L に破損していた。正しい内容（1020B/54L）に修復し以下を追加：

| 追加ルール | 対象 |
|---|---|
| `outputs/attribution/` | ローカル backtesting attribution 成果物 |
| `outputs/backtests/` | ローカル backtesting 成果物 |
| `outputs/data_quality/` | ローカル data quality 成果物 |
| `outputs/paper_trading/` | paper trading ローカル成果物 |
| `outputs/forward_record/alerts/` | forward record alert ローカル成果物 |
| `outputs/forward_record/prev3y_crypto/` | forward record ローカル成果物 |
| `outputs/forward_record/prev3y_crypto_shadow_a_roll12/` | shadow variant ローカル成果物 |
| `data/crypto/` | API-fetched 価格/ユニバースデータ（large） |
| `data/*.malformed_*` | DB crash recovery artifacts |
| `*.zip` | local deploy bundles |

保護された committed 監査成果物（gitignore しない）：
- `outputs/forward_record/baselines/`, `drill/`, `discord_webhook_*/`, `read_only_data_source/`
- `outputs/logs/`

## Next Step Options

### Option D — 30-day clock 啟動（start-date selection）
- 全前置条件 ✅ 完了
- Rick が「開始計時」を宣言して 30-day forward record を開始

### Option F — 暫停，等待 Rick 決定
- 不執行任何新任務

## Do Not
- 不得在沒有 Rick 指示下自行啟動任何 Option
- 不得啟動 30-day forward clock（需 Rick 明示「開始計時」）
- 不得把 discord dry_run 改為 false
- 不得送真實 Discord alert
- 不得使用 --live-alerts
- 不得批准 paper execution
- 不得批准 live trading
- 不得連接 Bybit write API
- 不得修改策略程式或官方輸出
- 不得進行 start-date selection（Rick 指示前）
