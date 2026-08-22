# Changelog

## v0.6.0 — Unreleased

- 将 CogniTrace 阶段 B 从冻结的 v0.5.0 基线移入 v0.6 开发线。
- 新增任务包、Frontier 结果包与 CogniTrace 回执的独立版本化 JSON 合同。
- 新增稳定 URI、SHA-256 内容引用、审核状态、运行来源和确定性结果封装。
- 新增 `lab integration validate / seal-result / verify-receipt` 文件与 CLI 边界。
- 明确回执由 CogniTrace 权威签发；Frontier 只验证，不共享数据库或领域类型。

## v0.5.0 — 2026-08-22

- 将公开 Harness 引擎与私有真实运营 workspace 拆分为独立 Git 历史。
- 公仓仅保留空账本、脱敏示例、公开 Schema、测试与集成合同。
- CLI 新增 `--project-root` / `FRONTIER_PROJECT_ROOT` 外部 workspace 解析。
- 发布检查新增公仓 allowlist、凭证特征、运行态和真实账本防泄漏门槛。
- 固定 `needs_review / active / superseded / archived` Canonical Claim 生命周期。
- 将 Research Claim 草稿、Canonical 晋升和 Canonical Claim 生命周期分离。
- 加入合法转换失败关闭、legacy v0.4 事件兼容回放和 `status_changed_at` 派生语义。
- 加入独立 `supports / contradicts / qualifies / supersedes` Claim Relationship JSONL 账本。
- 加入确定性 Document / Document Version Identity、SHA-256 来源冻结、context 与 location 合同。
- 加入可删除并由权威 JSONL 账本重建的 Canonical Claim SQLite 投影。
- 加入生命周期、关系、来源冻结、事件回放和索引重建测试。
- 明确 CogniTrace 只在 Frontier v0.5 内部闭环与稳定发布后进入版本化结果合同阶段。

## v0.1 — 2026-08-19
- 建立主知识库结构
- 写入半年总纲
- 写入学习体系、能源研究 001、国际外联机制
- 建立日 / 周 / 月复盘模板
- 建立公司、人、供应链、外联数据库骨架

## v0.2.0 — 2026-08-19
- 将静态 Markdown/Git 知识库升级为最小可运行 Agent Harness。
- 加入 SQLite FTS5 本地检索。
- 加入 One Orchestrator + Skills + JSON Workflow。
- 加入 OpenAI Agents SDK 适配、WebSearchTool、SQLiteSession。
- Agent 仅允许写 runtime/drafts，正式知识采用 human-approved promote。
- 加入统一 CLI：index / search / start / run / promote / status。
- 第一条真实工作流：Energy Research 001。

## v0.2.1 — Naming migration
- Renamed the umbrella project to **Frontier Global Lab**.
- Local repository name is now `frontier-global-lab`.
- The harness product name is **Frontier Harness**.
- Energy remains the first program rather than the boundary of the whole lab.
- Cleared prototype runtime artifacts so the renamed local repository starts with a clean execution state.
