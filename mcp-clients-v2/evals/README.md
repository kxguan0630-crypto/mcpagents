# Agent Evaluation

这里不是“测 LLM 文案好不好”，而是验证企业 Agent 最重要的行为契约：

- 是否调用了正确的业务 Tool；
- 是否跳过了 Workflow 前置条件；
- 是否把内部 Workflow fact tool 暴露给用户；
- Tool 失败后是否允许 Runtime/LLM 恢复；
- 最终回答是否包含业务结果。

## 使用

`runner.py` 是一个轻量离线评估器，不需要真实 LLM/MCP Server。

```bash
python -m evals.runner
```

它适合提交前做快速回归；真实模型回归仍建议在部署环境执行完整病例/订单链路。

## 目录

```text
evals/
├── cases.py      # 可读的场景定义
├── runner.py     # 通用评估器
└── README.md
```

新增 Agent Workflow 时，优先增加一个场景，而不是只靠人工测试。
