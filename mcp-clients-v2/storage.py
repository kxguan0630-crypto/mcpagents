"""应用启动时创建 Checkpoint 的地方。

为什么需要这个文件？
--------------------
AgentService 不应该自己判断：

    if REDIS_URL:
        ...

否则基础设施配置又会渗透进 Agent 代码。

这里统一负责「选择存储实现」，AgentService 只依赖 AgentCheckpoint。
"""

import os
from typing import Any

from agent.checkpoint import AgentCheckpoint
from agent.in_memory_checkpoint import InMemoryCheckpoint
from agent.redis_checkpoint import RedisCheckpoint


def create_checkpoint(redis_client: Any | None = None) -> AgentCheckpoint:
    """根据环境变量选择 Checkpoint。

    默认使用内存，方便你第一次启动项目时不需要 Redis。
    设置 CHECKPOINT_BACKEND=redis 后才启用 Redis。
    """
    backend = os.getenv("CHECKPOINT_BACKEND", "memory").lower()

    if backend == "memory":
        return InMemoryCheckpoint()

    if backend == "redis":
        if redis_client is None:
            raise RuntimeError(
                "CHECKPOINT_BACKEND=redis 时必须传入 redis_client"
            )
        ttl = int(os.getenv("CHECKPOINT_TTL_SECONDS", "3600"))
        return RedisCheckpoint(redis_client, ttl_seconds=ttl)

    raise ValueError(f"不支持的 CHECKPOINT_BACKEND: {backend}")
