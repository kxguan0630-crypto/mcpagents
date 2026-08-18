# LangGraph 持久化 Checkpoint

## 为什么需要它？

`MemorySaver` 只把 Graph 的暂停位置保存在当前 Python 进程内。
进程重启后，`interrupt()` 产生的状态就不存在了。

生产模式需要把 LangGraph checkpoint 放到持久化存储中。
本项目这一阶段使用 Redis。

## 结构

```text
AgentService
    |
    v
AgentGraph
    |
    v
LangGraph Checkpointer
    |
    +-- memory  -> 本地开发
    |
    +-- redis   -> 生产持久化
```

`graph.py` 不直接 import Redis。它只接收一个 `checkpointer`。
这样以后更换 PostgreSQL 等后端时，Agent Graph 不需要重写。

## 配置

```bash
export GRAPH_CHECKPOINT_BACKEND=redis
export GRAPH_CHECKPOINT_REDIS_URL=redis://localhost:6379/0
export GRAPH_CHECKPOINT_TTL_MINUTES=10080
```

`10080` 分钟约等于 7 天。

## Redis 要求

`langgraph-checkpoint-redis` 使用 RedisJSON 和 RediSearch。
如果使用 Redis 8+，这些模块已经包含在 Redis 中；较老版本建议使用 Redis Stack。

## 一个关键概念

```text
session_id == LangGraph thread_id
```

因此同一个 `session_id` 的 Agent 可以在另一个 worker 中读取同一个持久化 checkpoint，
前提是所有 worker 使用同一个 Redis。

## 注意

本阶段只把 checkpoint 持久化做好，不把 Redis 连接代码塞进 `graph.py`。
Human-in-the-loop 的 resume 依赖的正是这个 checkpoint。

如果 Redis checkpoint 版本升级，应该先在测试环境验证 interrupt/resume，再上线。
