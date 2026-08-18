# Single Agent 架构封板说明

> 目标：让维护者可以顺着源码读懂一次 Agent 请求，而不是依赖框架黑盒。

## 1. 一次请求怎么走

```text
FastAPI
  -> AgentService
  -> Input Validation
  -> Agent Graph
  -> LLM
  -> Tool Decision
  -> ApprovalRuntime（需要时）
  -> MCP Tool
  -> Tool Result
  -> LLM
  -> Final Answer
```

## 2. 各模块只负责什么

| 模块 | 职责 |
|---|---|
| `api/` | HTTP / SSE 协议转换，不写 Agent 业务逻辑 |
| `agent/service.py` | 一次 Agent 请求的应用层编排 |
| `agent/graph.py` | LangGraph 节点、边和 Agent 决策循环 |
| `agent/state.py` | Graph 使用的状态结构 |
| `agent/checkpoint.py` | 应用层会话历史的抽象 |
| `agent/checkpoint_backend.py` | 创建 LangGraph Checkpointer |
| `agent/approval_policy.py` | 判断哪些 Tool 需要人工确认 |
| `agent/approval_manager.py` | 审批请求生命周期 |
| `agent/approval_runtime.py` | Tool 执行前的审批门 |
| `agent/observability.py` | run_id、耗时、成功/失败状态 |
| `mcp/client.py` | MCP Tool Discovery、调用、timeout/retry |

## 3. 两种 Checkpoint 不要混淆

项目中有两个概念：

### AgentCheckpoint

用于应用层 session 历史，例如恢复过去的消息。

### LangGraph Checkpointer

用于保存 Graph 的执行位置和状态，尤其重要的是 `interrupt()` 后的 resume。

```text
AgentService
   |
   +-- AgentCheckpoint       -> 会话历史
   |
   +-- LangGraph Checkpointer -> Graph 执行状态
```

生产环境使用 Redis 时，Graph 本身不直接操作 Redis；Redis 由 `checkpoint_backend.py` 创建并注入 Graph。

## 4. Human-in-the-loop 为什么必须使用稳定 approval_id

LangGraph 从 `interrupt()` 恢复时，会重新执行 interrupt 所在节点之前的代码。

因此不能这样写：

```python
approval_id = uuid4().hex
```

否则恢复时会生成第二个审批请求。

当前实现使用：

```text
session_id + tool_call_id
        |
        v
稳定 approval_id
```

所以同一个 Tool Call 在第一次暂停和恢复重跑时，会找到同一个审批请求。

## 5. 用户确认后的删除时机

审批请求不能在 `/approvals/decision` 收到确认时立即删除。

正确顺序：

```text
用户确认
  -> 保存 approved decision
  -> LangGraph resume
  -> Tool 执行
  -> Graph 成功结束
  -> 删除 approval request
```

这样即使 worker 在 resume 期间失败，也可以安全重试，不会出现“用户已经批准，但审批记录先被删掉”的问题。

## 6. 为什么现在不做 Multi-Agent

当前单 Agent 已经具备：

- MCP Tool Discovery
- LangGraph Agent Loop
- Memory
- Persistent Graph Checkpoint
- Streaming / SSE
- Timeout / Retry Policy
- Input Validation
- Observability
- Human Approval
- Interrupt / Resume

在这些基础能力没有稳定之前继续拆 Multi-Agent，只会增加复杂度。

下一阶段才进入 Router / Sub-Agent，并且先根据真实业务边界判断是否值得拆分。
