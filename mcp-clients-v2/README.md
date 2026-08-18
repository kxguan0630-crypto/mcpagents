# MCP Agents Client v2

这是一个面向学习和生产演进的 Agent 客户端骨架。

**目标不是把代码写得“高级”，而是让你能顺着源码读懂一次 Agent 请求到底发生了什么。**

## 目录结构

```text
mcp-clients-v2/
├── agent/
│   ├── state.py       # Agent 状态
│   ├── graph.py       # LLM -> Tool -> LLM 的核心循环
│   ├── memory.py      # Session 对话记忆
│   ├── limits.py      # Agent 最大执行步数 / 重试限制
│   ├── errors.py      # Agent 错误分类
│   ├── events.py      # 对外统一的流式事件
│   └── service.py     # Agent 应用层入口
├── mcp/
│   └── client.py      # MCP 连接、工具发现、超时、重试
├── api/
│   ├── schemas.py     # HTTP 请求/响应模型
│   └── app.py         # 很薄的 FastAPI + SSE 适配层
├── tests/             # 不依赖真实 LLM/MCP 的最小单元测试
├── config.py          # 环境变量配置
└── main.py            # 本地 CLI 启动入口
```

## 一次普通请求怎么走

```text
HTTP POST /chat
       |
       v
  api/app.py
       |
       v
 AgentService
       |
       +---- SessionMemory 读取历史
       |
       v
   AgentGraph
       |
       +---- LLM 判断
       |       |
       |       +---- 直接回答 -> END
       |       |
       |       +---- 调用工具
       |                |
       |                v
       |            MCP Client
       |                |
       |                v
       |            MCP Server
       |                |
       |                v
       |            Tool Result
       |                |
       +<---------------+
       |
       v
   保存 Session
       |
       v
    HTTP Response
```

## 流式请求怎么走

```text
POST /chat/stream
       |
       v
 AgentService.run_stream()
       |
       v
 LangGraph astream()
       |
       +--> llm update -----> AgentEvent(answer)
       |
       +--> tools update ---> AgentEvent(tool_end)
       |
       +--> error ----------> AgentEvent(error)
       |
       v
     SSE
```

API 层只认识 `AgentEvent`，不认识 LangGraph 的内部事件格式。这样以后换 Graph 实现，HTTP 接口仍然稳定。

## 三个最重要的概念

### 1. MCP Server 是“能力”

Server 提供病例、患者、订单等业务工具。Client 不应该知道这些业务细节。

### 2. Agent 是“决策”

Agent 不根据工具名称写死流程，而是把 MCP 动态发现的工具交给 LLM，由模型决定什么时候调用哪个工具。

### 3. LangGraph 是“流程和状态”

Graph 负责控制 Agent 循环，并设置最大执行步数。以后增加人工确认、长期记忆时，都可以继续在 Graph 层演进。

## 稳定性设计

### MCP Tool Timeout

每次工具调用都有明确的超时时间，避免某个业务 API 卡住后一直占用 Agent 请求。

### MCP Tool Retry

临时失败允许有限次数重试；重试耗尽后转换成 `MCPToolError`。这里不会无限重试。

### Agent Step Limit

默认最多执行 8 次 LLM 推理。达到上限就停止 Agent，避免模型异常造成无限工具循环。

### Error Boundary

错误类型集中在 `agent/errors.py`。未来可以在 API 层把不同错误映射成不同 HTTP 状态码，也可以统一接入日志和监控。

## Memory 的设计

当前 `SessionMemory` 使用进程内内存，故意没有直接把 Redis 写死在 Agent 中。

后续生产化时可以实现：

```text
SessionMemory interface
        |
        +-- InMemorySessionMemory  # 本地开发 / 测试
        |
        +-- RedisSessionMemory     # 生产环境
```

这样 Agent Graph 不需要修改。

## 为什么不一次性做成“超级 Agent”

因为这个项目首先是你的学习项目。代码必须能读懂。

推荐的演进顺序：

1. Agent Core
2. Session Memory
3. HTTP API
4. Streaming
5. Retry / Timeout / Error Handling
6. Redis Checkpoint
7. Observability
8. Human Approval
9. 再考虑 Multi-Agent

**下一阶段重点：Redis Checkpoint。**
届时会把现在的进程内 SessionMemory 换成清晰的 Redis 实现，并保持 Agent Graph 不直接依赖 Redis。
