# Frontier Harness v0.5 Quick Start

This directory is a synthetic public example workspace. It contains executable
schemas and empty ledgers, but no real Frontier learning, market, Evidence,
review, outreach, or Canonical Knowledge data. Operational data belongs in a
separate private workspace.

## 安装

```bash
uv sync --dev
```

所有开发、测试与 smoke 命令都通过 uv 受管环境执行：

```bash
uv run lab --help
uv run pytest -q
./scripts/smoke_test.sh
```

## 研究运行

不调用模型的本地路径：

```bash
uv run lab index
uv run lab search "workspace boundary"
uv run lab start local-smoke
uv run lab status
```

需要模型的研究运行仍由外部 workspace 的 workflow、runtime policy、prompt、skill 和预算控制，输出先进入该 workspace 的 `10_Harness/runtime/drafts/`，不得自动写入 Canonical Knowledge。

## Canonical Claim

```bash
uv run lab claim status
uv run lab claim create --help
uv run lab claim review --help
uv run lab claim mark-needs-review --help
uv run lab claim supersede --help
uv run lab claim archive --help
```

所有改变账本的命令默认 dry-run；只有显式 `--write` 才追加事件。

生命周期只有：

```text
needs_review
active
superseded
archived
```

## Claim Relationship

```bash
uv run lab claim relate --help
uv run lab claim relationships
```

关系只有 `supports / contradicts / qualifies / supersedes`，且关系不会隐式改变任一 Claim 生命周期。

## 派生索引

```bash
uv run lab claim rebuild-index
uv run lab claim index-status
```

`10_Harness/runtime/knowledge/canonical_claims.sqlite` 是可删除派生数据。权威历史始终是 Git 跟踪的 Claim 与 Relationship JSONL 账本。

## 发布检查

```bash
./scripts/release_check.sh
```

正式发布还必须在私有 workspace 完成真实领域案例的人工审核与兼容性验证；公仓测试和空白样例不能替代领域人工判断，也不得复制真实案例作为公开 fixture。
