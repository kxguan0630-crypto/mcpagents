"""集中管理配置，避免业务代码到处 os.getenv。"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model_name: str
    mcp_config: str = "../mcp-clients/servers_config.json"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.environ["BASE_URL"],
            api_key=os.environ["API_KEY"],
            model_name=os.environ["MODEL_NAME"],
            mcp_config=os.getenv("MCP_CONFIG", "../mcp-clients/servers_config.json"),
        )
