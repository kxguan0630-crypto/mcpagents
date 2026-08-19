"""集中管理配置，避免业务代码到处 os.getenv。"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model_name: str

    # 默认使用当前仓库内的 STDIO MCP 配置。
    # Client 启动后会按照该配置自动拉起 ../mcp-servers/app.py，
    # 因此本地开发时不需要再手工打开一个终端启动 MCP Server。
    mcp_config: str = "config/servers_config.json"

    # LangGraph checkpoint 的存储方式。
    # memory 适合本地学习；redis 用于多 worker / 进程重启后的持久恢复。
    graph_checkpoint_backend: str = "memory"
    graph_checkpoint_redis_url: str = "redis://localhost:6379/0"
    graph_checkpoint_ttl_minutes: int = 60 * 24 * 7

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.environ["BASE_URL"],
            api_key=os.environ["API_KEY"],
            model_name=os.environ["MODEL_NAME"],
            mcp_config=os.getenv("MCP_CONFIG", "config/servers_config.json"),
            graph_checkpoint_backend=os.getenv("GRAPH_CHECKPOINT_BACKEND", "memory"),
            graph_checkpoint_redis_url=os.getenv(
                "GRAPH_CHECKPOINT_REDIS_URL",
                "redis://localhost:6379/0",
            ),
            graph_checkpoint_ttl_minutes=int(
                os.getenv("GRAPH_CHECKPOINT_TTL_MINUTES", str(60 * 24 * 7))
            ),
        )
