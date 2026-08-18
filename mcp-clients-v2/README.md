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
│   └── service.py     # Agent 应用层入口
├── mcp/
│   └── client.py      # MCP 连接、工具发现、工具调用
├── api/
│   ├── schemas.py     # HTTP 请求/响应模型
│   └── app.py         # 很薄的 FastAPI 适配层
├── config.py          # 环境变量配置
└── main.py            # 本地 CLI 启动入口
```

## 一次请求怎么走

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

## 三个最重要的概念

### 1. MCP Server 是“能力”

Server 提供病例、患者、订单等业务工具。Client 不应该知道这些业务细节。

### 2. Agent 是“决策”

Agent 不根据工具名称写死流程，而是把 MCP 动态发现的工具交给 LLM，由模型决定什么时候调用哪个工具。

### 3. LangGraph 是“流程和状态”

Graph 只负责控制 Agent 循环。以后增加人工确认、重试、审批、长期记忆时，都可以继续在 Graph 层演进。

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

不要一开始就把项目堆成十几个 Agent。
