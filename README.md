# Frontier Global Lab

**AI × Industry × Global Collaboration**

这是一个用于长期学习、产业研究、产品研发、国际合作与个人能力沉淀的私有知识与研究系统。

## 核心目标

不是“为了学习而学习”，而是把学习、研究、产品、市场和英语统一到真实问题中：

**Learn → Research → Build → Connect → Reflect → Replan**

Frontier Global Lab 的目标不是做一个一次性回答问题的 Agent，而是建立一个：

**可研究、可审计、可复用、可持续更新的人机协作研究系统。**

## 工作原则

1. 英语是工作语言，不是最终目的。
2. AI 是能力杠杆，不是单独赛道。
3. 能源是第一个产业切入口，但不预设答案。
4. 所有市场判断先验证需求，再组织供应链。
5. FACT、INFERENCE、ASSUMPTION、FORECAST、UNKNOWN 必须明确区分。
6. 搜索结果不是证据，Evidence 必须绑定已抓取来源与原文 excerpt。
7. Agent 默认只能写 draft，Canonical Knowledge 必须人工批准。
8. 研究质量不仅看数量，也看来源、独立性、语义质量和可追溯性。
9. 代码负责 Capability，配置负责 Policy，Workflow 负责 Business Intent。
10. 每日、每周、每月复盘，持续修正路线。

## 当前阶段

**Phase 1：Frontier Harness v0.3.0 — Research Operations**

当前第一条真实市场研究工作流：

**Nigeria Distributed Energy / Microgrid Market Scan**

Frontier 已经能够执行：

**Local Knowledge → Web Research → Evidence → Quality Gate → Gap Detection → Augment → Human Review → Draft → Canonical Promotion**

## Frontier Harness v0.3.0

### Research Runtime

- Ollama / Qwen：本地轻量任务与 Revision
- DeepSeek：外部研究任务
- Provider / Model / Transport 按 task class 路由
- 每个 run 使用独立 session，避免历史对话隐式污染新研究

### Runtime Budget Policy

研究预算集中配置于 `10_Harness/config.json`。

目前支持：

- `max_turns`
- `max_web_searches`
- `max_fetches`
- `max_new_evidence`
- `timeout_seconds`

预算按以下优先级解析：

**Mode → Task Class → Global Default**

Web Search、Fetch 和新增 Evidence 均有 Harness Tool Layer 硬限制，不只依赖 Prompt。

### Prompt Policy Center

专业提示词位于：

`10_Harness/prompts/`

当前包括：

- `orchestrator.md`
- `research_base.md`
- `evidence_rules.md`
- `country_market_scan.md`

Prompt 按以下层级组合：

**Base Profile → Task Class Profile → Workflow Profile**

每个 Prompt 均带版本号，并在每次 run 中保存实际使用的 Prompt 快照与 manifest。

### Skill Policy Center

Skills 位于：

`10_Harness/skills/`

当前主要包括：

- `research`
- `curator`

Skill 加载由配置中心统一控制，不再硬编码在 Agent Runner 中。

### Web Evidence Layer

Evidence 生命周期：

**Candidate Source → DISCOVERED → FETCHED → SUPPORTED / CONTRADICTED / INSUFFICIENT → Human Review → CITED**

核心原则：

**Source → Excerpt → Context → Evidence → Claim**

Search snippet 不能作为 verified evidence。

Evidence 会保存：

- source URL
- source title / publisher
- excerpt
- section heading
- context excerpt
- published / retrieved time
- machine assessment
- human review
- revision history

### Human Review

支持：

- approve
- reject
- needs revision
- amend
- Revision Agent

Machine-supported Evidence 不等于 HUMAN_VERIFIED。

Agent 无权自行批准 Evidence，也无权自动写入 Canonical Knowledge。

### Research Quality Gate

当前分为两层。

#### Coverage Quality

检查：

- supported evidence 数量
- unique source URLs
- independent domains
- research topics
- source concentration

Coverage Gate 决定研究是否 PASS / FAIL。

#### Semantic Quality

当前以 warning 方式检查：

- generic homepage URL
- secondary source / primary-source upgrade
- non-standalone claim
- possible multi-proposition claim
- near-duplicate claim

Semantic warnings 暂不直接导致 FAIL，用于辅助人工研究审核与规则校准。

### Incremental Research

当研究没有通过 Coverage Gate 时，可以继续补证，而不是重新从头研究：

```bash
lab research augment <run-id>
```

Augment run：

- 继承父 run Evidence
- 保留父 run 不可变
- 自动读取 Quality Gap
- 只针对缺口继续研究
- 使用独立 augment budget
- 生成新的 child run

形成：

**Research → Quality Gate → Gap Detection → Augment → Re-check**

### Run Provenance

每次运行保存：

- workflow
- provider
- model
- transport
- runtime policy
- prompt policy
- skill policy
- parent run
- `prepared_at`
- `started_at`
- `completed_at`
- `research_as_of`

同时冻结：

- `system_prompt.md`
- `prompt_manifest.json`
- `skill_manifest.json`

因此历史研究可以追溯“当时使用了什么模型、什么 Prompt、什么 Skill、什么预算和什么时间截面”。

### Environment / Secrets

项目根目录支持本地 `.env`：

```text
DEEPSEEK_API_KEY=
TAVILY_API_KEY=
```

`.env` 被 Git 忽略，不进入版本控制。

`.env.example` 只保存变量模板。

Shell 中显式设置的环境变量优先于 `.env`。

## 基本 CLI

```bash
lab index
lab search "<query>"
lab start <workflow>
lab run <workflow>
lab status

lab quality <run-id>
lab research augment <run-id>

lab evidence list <run-id>
lab evidence show <run-id> <evidence-id>
lab evidence approve <run-id> <evidence-id>
lab evidence reject <run-id> <evidence-id>
lab evidence revise <run-id> <evidence-id>
lab evidence amend <run-id> <evidence-id>

lab promote <draft> <destination>
```

## 典型研究流程

```text
1. lab run <workflow>

2. lab quality <run-id>

3. 如果 Coverage FAIL：
   lab research augment <run-id>

4. 检查 Semantic Warnings

5. 人工审核关键 Evidence

6. 修订 FACT / INFERENCE / ASSUMPTION

7. 形成 draft

8. 人工批准后 promote 到 Canonical Knowledge
```

## 目录

- `00_MASTER_PLAN.md`：总纲与唯一战略入口
- `01_Strategy/`：半年路线、决策与里程碑
- `02_Learning/`：AI / 英语 / README 学习体系
- `03_Energy_Research/`：能源产业、技术、市场研究
- `04_International_Outreach/`：国际合作对象与邮件实验
- `05_Projects/`：产品研发与方案
- `06_Content_IP/`：公开内容与个人品牌
- `07_Reviews/`：日 / 周 / 月复盘
- `08_Databases/`：公司、人、供应链、外联记录
- `09_Templates/`：研究与输出模板
- `10_Harness/`：Config、Prompts、Skills、Workflows 与运行态
- `harness/`：Frontier Harness Python 实现

## 下一阶段

v0.3.0 之后的重点不是继续无限增加 Agent 功能，而是提升真实研究与长期知识资产质量。

下一阶段重点包括：

- Temporal Knowledge / Knowledge Versioning
- Canonical Claim lifecycle
- `as_of / last_verified_at / next_review_at`
- `ACTIVE / SUPERSEDED / CONTRADICTED / HISTORICAL / NEEDS_REVIEW`
- 更成熟的 Semantic Quality Gate
- Country Scan 方法论继续通过真实市场研究迭代
