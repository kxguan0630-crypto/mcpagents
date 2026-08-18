# Human-in-the-loop

本阶段把人工审批真正接入 LangGraph。

## 执行流程

```text
用户请求
  ↓
LLM 决定调用 Tool
  ↓
ApprovalRuntime
  ↓
需要审批？
  ├─ 否 → Tool
  └─ 是 → interrupt()
             ↓
          SSE: approval_required
             ↓
          用户确认
             ↓
POST /approvals/decision
             ↓
Command(resume=...)
             ↓
继续原来的 Graph
             ↓
Tool
```

## 为什么使用 LangGraph interrupt

不要自己写一个 `while waiting_for_user`。

Agent 暂停以后，LangGraph 会把当前执行位置保存到自己的 Checkpoint，
用户确认后使用 `Command(resume=...)` 从原来的 interrupt 位置继续。

这样“暂停”和“恢复”都是 Graph 的一部分，而不是 HTTP 层自己模拟状态机。

## 当前限制

本阶段使用 `MemorySaver`，它只适合本地学习和单进程演示。

如果部署成多个 worker，或者进程重启后仍然需要恢复审批，必须把 LangGraph
的 checkpointer 换成持久化实现（例如 Redis/Postgres 对应的 LangGraph saver）。

注意：项目里的 `AgentCheckpoint` 是应用层历史消息存储；LangGraph 的
interrupt/resume 需要另一层专门的 Graph Checkpointer。两者职责不同，
不要混成一个类。
