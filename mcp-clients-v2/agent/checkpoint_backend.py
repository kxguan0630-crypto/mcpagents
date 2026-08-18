"""LangGraph Checkpoint 后端。

这一层只负责一件事：创建 LangGraph 使用的 checkpointer。

为什么单独放一个文件？
因为 Agent Graph 不应该知道 Redis 的连接细节。
以后从 Redis 换成 PostgreSQL 等持久化后端，只需要改这里。
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver


async def create_graph_checkpointer(settings: Any) -> BaseCheckpointSaver:
    """创建 LangGraph Checkpointer，并初始化持久化索引。

    memory：本地开发模式，进程重启后数据会消失。
    redis：生产模式，checkpoint 会写入 Redis，可支持多 worker 读取同一线程。

    注意：AsyncRedisSaver 是异步资源，所以由应用启动阶段创建并初始化。
    Agent Graph 只拿到 BaseCheckpointSaver，不直接操作 Redis。
    """
    backend = getattr(settings, "graph_checkpoint_backend", "memory")

    if backend == "memory":
        return MemorySaver()

    if backend == "redis":
        saver = AsyncRedisSaver(
            redis_url=settings.graph_checkpoint_redis_url,
            ttl={
                "default_ttl": settings.graph_checkpoint_ttl_minutes,
                "refresh_on_read": True,
            },
        )
        await saver.asetup()
        return saver

    raise ValueError(
        f"不支持的 graph_checkpoint_backend: {backend}；"
        "可选值为 memory 或 redis。"
    )
