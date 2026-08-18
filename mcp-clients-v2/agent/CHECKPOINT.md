# Agent Checkpoint 是什么？

Checkpoint 可以简单理解成：**把 Agent 最近一次运行到的状态保存下来。**

## 为什么需要它？

如果没有 Checkpoint：

```text
请求 1 -> Agent 记住了内容
请求 2 -> 换了 worker / 进程 -> 内容可能丢失
```

有 Checkpoint：

```text
请求 1 -> AgentState -> Redis
请求 2 -> Redis -> AgentState -> Agent
```

## 本项目的分层

```text
AgentService
     |
     v
AgentCheckpoint       <- Agent 只依赖这个接口
     |
     +-- InMemoryCheckpoint   <- 本地开发/测试
     |
     +-- RedisCheckpoint       <- 多 worker / 生产环境
```

### 最重要的原则

Redis 是**存储层**，不是 Agent。

它不负责：

- 选择工具
- 调用 LLM
- 判断业务流程
- 决定下一步动作

它只负责保存和恢复 AgentState。

## Redis Key

本项目使用简单的 key：

```text
agent:checkpoint:<session_id>
```

一个 session 对应一个 checkpoint，先把这个关系讲清楚，再考虑更复杂的 checkpoint / history / long-term memory。
