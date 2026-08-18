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


class GraphCheckpointFactory:
    """根据配置创建 LangGraph Checkpointer。"""

    @staticmethod
    def create(settings: Any) -> BaseCheckpointSaver:
        """创建 Checkpointer。

        当前先保留 MemorySaver 作为默认/开发模式。
        Redis Checkpointer 的具体实现需要与当前安装的 LangGraph 版本
        一起验证后再接入，避免凭经验猜测第三方 API。
        """
        if getattr(settings, "graph_checkpoint_backend", "memory") == "memory":
            return MemorySaver()

        raise ValueError(
            "当前仅实现 graph_checkpoint_backend=memory；"
            "Redis 持久化后端将在版本确认后接入。"
        )
