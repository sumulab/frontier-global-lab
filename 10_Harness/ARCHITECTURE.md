# Frontier Harness Architecture — v0.5

This document describes the public engine contract. The bundled `10_Harness/`
tree is an empty synthetic example; real domain authorities live in a separate
private workspace.

## 1. 产品边界

Frontier 是领域执行与专业知识层，负责能源研究、英语实践、国际市场行动、来源 Evidence、Claim、Canonical Knowledge 与人工审核。

Frontier 不拥有 CogniTrace 的目标、盲区、行动前评价合同或最终评价，也不共享 CogniTrace 数据库。

## 2. 分层

```text
Research Execution
  -> Run / Provider / Prompt / Skill / Budget
  -> Source / Evidence / Research Claim / Human Review

Canonical Knowledge Authority
  -> Canonical Claim JSONL ledger
  -> Claim Relationship JSONL ledger
  -> Document and Evidence provenance snapshots

Derived Read Models
  -> Canonical Claim SQLite projection
  -> Knowledge FTS index
  -> CLI health and review-due reports
```

Git 跟踪 JSONL 是权威历史。SQLite 与 FTS 都是可删除、可重建的投影。

## 3. Canonical Claim

Research Claim 不因有 Evidence 自动晋升。显式人工控制的创建操作产生 Canonical Claim，初始状态为 `needs_review`；人工审核后才成为 `active`。

持久生命周期：

```text
needs_review -> active -> needs_review
needs_review | active -> superseded
needs_review | active | superseded -> archived
```

非法转换失败关闭。到达 `next_review_at` 只形成派生 review-due 结果，不静默修改权威账本。

## 4. Claim Relationship

`supports / contradicts / qualifies / supersedes` 是独立不可变事实，具有自己的 ID、方向、理由、actor、时间和 provenance。

关系和生命周期分别投影。Legacy v0.4 contradiction 通过兼容适配器读取，新 writer 不再产生 legacy 事件。

## 5. 来源冻结

新的 v0.5 research-evidence promotion 冻结：

- 确定性 Document ID 与 Document Version ID；
- normalized URL、publisher、published/retrieved time；
- 强制 SHA-256 content hash；
- excerpt、context、location；
- reviewer、reviewed_at、review note；
- run、workflow、provider/prompt/skill/budget provenance 的稳定引用。

## 6. 写入安全

- 所有 CLI 写入默认 dry-run；
- append 前验证当前权威账本；
- 候选文件完整回放验证后才原子替换；
- 使用内容哈希做乐观并发检查；
- commit 后再次回放并验证唯一 ID。

## 7. 非目标

v0.5 不引入多 Agent、向量数据库、知识图谱 UI、自动置信度、决策自动化或正式 CogniTrace 集成代码。
