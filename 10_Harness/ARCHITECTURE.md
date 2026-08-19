# Frontier Harness Architecture — v0.2

## 1. 架构决策
v0.2 将“知识库规范化”和“最小可运行 Harness”合并为一个版本，但内部按两层实现：

1. **Knowledge Layer**：Markdown/CSV + Git + 本地 FTS 索引。
2. **Execution Layer**：One Orchestrator + Skills + Workflow + Session + Draft-only writes + Human approval。

不是多 Agent 系统。v0.2 的目标是先把闭环跑通。

## 2. 数据流

User Goal
→ Orchestrator
→ Local Retrieval
→ Optional Web Research
→ Reason / Tool Calls
→ Draft Artifact
→ Human Review
→ Promote to Canonical Knowledge
→ Re-index
→ Next Run

## 3. 为什么暂不做重 RAG
当前知识量小，先使用 SQLite FTS5：可解释、零额外服务、便于调试。
当出现以下信号后进入 v0.3 Hybrid RAG：
- 文档达到数百/上千且关键词难以覆盖同义概念；
- 同一问题频繁跨主题检索失败；
- 已有知识重复研究明显增加。

v0.3 再加入 embedding + keyword + metadata filter；向量库只做可重建索引，不做唯一事实源。

## 4. Human Approval
Agent 不直接改正式知识库。
所有 agent 生成内容先进入：
`10_Harness/runtime/drafts/`

人工确认后使用 `lab promote` 写入 canonical path。

## 5. v0.2 成功标准
- `lab index`：建立本地索引。
- `lab search`：能查到知识。
- `lab start <workflow>`：能生成一个 run/context pack。
- `lab run <workflow>`：配置 API Key 后，Orchestrator 能结合本地检索 + Web Search 完成一轮研究并写 draft。
- `lab promote`：人工批准后将 draft 提升到正式知识库。
- 每次 run 有独立日志，可追踪。

## 6. 技术选择
- Python 3.11+
- SQLite FTS5：本地检索
- OpenAI Agents SDK：agent loop / tools / session / tracing
- OpenAI hosted WebSearchTool：需要外部研究时启用
- Git：版本、审计与回滚

## 7. v0.3 以后
- Hybrid RAG
- Metadata schema 强化
- Dashboard
- Evaluations
- 某些 Skill 独立为专门 Agent
- MCP / 外部 CRM / 邮件等连接（按真实需求再加）


## 8. v0.2 的边界
本版本已经具备“真实知识库 + 可运行 Harness”的最小骨架，但不把以下内容提前做复杂：
- 不做独立 Dashboard；先用 CLI + Markdown。
- 不做向量数据库；先以 FTS5 建立可解释检索基线。
- 不做多 Agent；先观察单 Orchestrator 的真实瓶颈。
- 不自动发送邮件、不自动写入正式知识；涉及外部动作与 canonical write 均保留人工批准。
