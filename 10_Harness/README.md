# Frontier Harness — v0.2 Quick Start

## 目标
今天开始实际工作，而不是继续搭平台。

v0.2 只有一个 Orchestrator。它具备：
- 本地知识库检索
- Web Research
- Workflow 驱动
- SQLite Session
- Draft-only 写入
- Human approval 后提升为正式知识
- Run log

## 安装
```bash
./scripts/bootstrap.sh
```

或者：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
lab index
```

## 不调用模型也可以先运行
```bash
lab search "microgrid energy"
lab start energy-research-001
lab status
```

## 启动第一条真实 Agent Workflow
```bash
export OPENAI_API_KEY="..."
export LAB_MODEL="gpt-5.6-sol"
lab run energy-research-001
```

Agent 产物进入：
`10_Harness/runtime/drafts/<run-id>/`

## 人工批准入库
```bash
lab promote \
  10_Harness/runtime/drafts/<run-id>/research_brief.md \
  03_Energy_Research/ENERGY_RESEARCH_001_RESULT.md

lab index
```

这一步故意是人工操作：v0.2 不允许 Agent 直接覆盖正式知识。

## 今天的第一条闭环
1. `lab index`
2. `lab run energy-research-001`
3. 查看 drafts
4. 人工修改/批准
5. `lab promote ...`
6. `lab index`
7. 更新 Daily Review
