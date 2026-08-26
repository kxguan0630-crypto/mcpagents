# P10-P14 实施与 Review

> 分支：`feature/p7-p8-p9-agent-engineering`
>
> 范围：P10 Observability / P11 Evaluation / P12 Human-in-the-loop / P13 Memory / P14 MCP Transport

## 1. 实施结果

### P10 — Observability

- AgentRun 增加结构化事件列表。
- 支持 `run_start`、`node_end`、`tool_start`、`tool_end`、`approval_required`、`run_end`。
- 保留 `run_id/session_id/status/error/duration_ms`。
- `snapshot()` 可用于后续落日志、Metrics、OpenTelemetry 或 LangSmith。
- Service 层已经记录 LLM Node、业务 Tool、Approval 等运行事件。

### P11 — Evaluation

- 保留原有文本/Tool Sequence Smoke Evaluation。
- 新增 Behavior Contract：required tools / forbidden tools / required order / required facts。
- `python -m evals.runner` 同时覆盖原有 smoke 与行为契约 smoke。
- Evaluation 不依赖具体 LLM 文案。

### P12 — Human-in-the-loop

- 保留现有 Approval Policy / Manager / Store / Runtime。
- Approval ID 与 session + tool call 绑定，避免 interrupt resume 重复创建审批请求。
- resume 成功后才删除审批请求；resume 失败可以继续恢复。
- AgentEvent 对前端暴露 `approval_required`。

### P13 — Memory

明确分成三层：

1. Session Memory：对话历史。
2. LangGraph Checkpoint：可恢复运行状态。
3. Long-term Memory：明确白名单的业务事实。

新增 `LongTermMemory` Protocol 与 `InMemoryLongTermMemory`，不保存 Token 或完整消息。

### P14 — MCP Transport

- 当前真实 Transport 仍为 STDIO。
- 新增 `MCPTransport` Protocol，明确 connect/list_tools/call_tool/close 边界。
- 没有虚构 Streamable HTTP 已经实现；未来增加远程 Transport 时可以替换连接层，不修改 Agent Workflow。

## 2. Review 结论

### 通过项

- 没有在 `graph.py` 增加业务 intent → Tool 的硬编码分支。
- Token 继续留在 AuthContext，不进入 AgentState/LLM Message。
- Tool 可见性继续由 metadata 控制。
- P10 事件记录不改变 SSE 前端协议。
- P11 Evaluation 不绑定模型输出文案。
- P12 Approval 保持可恢复语义。
- P13/P14 采用接口优先，避免提前绑定 Redis/HTTP MCP。

### 有意保留的边界

P13 当前只提供长期记忆接口，没有自动把所有业务事实写入长期记忆。这是刻意设计：未经业务定义的事实不应该因为“有 Memory”就自动持久化。

P14 当前只提供 Transport Protocol，生产连接仍然使用已有 STDIO MCP Client。远程 HTTP Transport 应在明确服务端协议、连接生命周期和认证方式后再实现。

## 3. 静态 Review 注意项

1. GitHub 侧本轮完成源码级审查和变更对比。
2. 本环境不能替代用户本机真实 MCP Server、JWT、Redis 和业务 API 联调，因此不宣称已经完成真实生产环境验证。
3. 用户本地需要执行：

```bash
pytest -q tests
python -m evals.runner
```

4. 如果两项通过，再进行真实 `/query` 回归：病例创建、患者查询/决策、订单创建、`need_design=1/0`、影像上传与订单后影像更新、Approval resume。

## 4. 最终判断

P10-P14 已完成架构层升级，且没有为了追求“Agent Framework 化”而引入不必要的基础设施。

当前项目更适合定位为：

> **企业业务 Agent Application Runtime：LLM Reasoning + Deterministic Workflow + MCP Tool Runtime + State/Memory + Human-in-the-loop + Observability + Evaluation。**
