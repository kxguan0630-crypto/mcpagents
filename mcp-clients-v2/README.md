# MCP Agents Client v2

这是一个面向学习和生产演进的 Agent 客户端骨架。

核心思想只有三层：

1. `mcp/`：负责连接 MCP Server、发现工具、调用工具。
2. `agent/`：负责 Agent 的决策循环：LLM -> Tool Call -> Tool Result -> LLM。
3. `api/`：负责 HTTP 接口和认证，把 Web 层与 Agent 解耦。

## 为什么重写客户端

旧客户端把 HTTP、Redis、MCP 生命周期、模型调用、工具循环、热加载、鉴权等大量职责集中在一个文件中。
新客户端不再根据工具名称硬编码业务流程，而是让模型根据 MCP 暴露的工具描述自主选择工具。

## 运行思路

```text
HTTP Request
    |
    v
AgentService
    |
    v
AgentGraph
    |
    +--> LLM
    |      |
    |      +--> normal response -> END
    |      |
    |      +--> tool call ------+
    |                             |
    +<----------------------------+
    |
    v
HTTP Response
```

## 设计原则

- MCP Server 只负责业务工具，不负责 Agent 决策。
- Agent Client 不硬编码 `if tool_name == ...`。
- Tool discovery 来自 MCP。
- LangGraph 负责状态和循环，不把状态机逻辑塞进 HTTP handler。
- 业务状态可以后续接 Redis/Postgres checkpoint，但 Agent 核心不依赖具体存储。
- 每个模块只做一件事，代码优先可读性。

> 当前版本首先建立清晰骨架。生产环境的认证、流式输出、持久化 checkpoint、观测和重试可以逐步加入。