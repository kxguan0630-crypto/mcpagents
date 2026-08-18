"""MCP 连接层。

这里完全不知道具体业务工具叫什么。
它只负责：连接服务器、发现工具、把 MCP 工具适配成 LangChain tools。
"""

import json
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPToolClient:
    """管理一个 MCP Server 连接及其工具。"""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self.tools: list[StructuredTool] = []

    async def connect(self) -> None:
        """读取配置并连接 MCP Server。"""
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        server = config["mcpServers"]["default"]

        params = StdioServerParameters(
            command=server["command"],
            args=server.get("args", []),
            env=server.get("env"),
        )

        read_stream, write_stream = await self.stack.enter_async_context(
            stdio_client(params)
        )
        self.session = await self.stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()
        self.tools = await self._load_tools()

    async def _load_tools(self) -> list[StructuredTool]:
        """动态发现 MCP 工具，不写任何业务工具名。"""
        if self.session is None:
            raise RuntimeError("MCP session is not connected")

        result = await self.session.list_tools()
        tools: list[StructuredTool] = []

        for tool in result.tools:
            async def call_tool(_tool_name=tool.name, **kwargs: Any):
                if self.session is None:
                    raise RuntimeError("MCP session is not connected")
                response = await self.session.call_tool(_tool_name, arguments=kwargs)
                return response.model_dump() if hasattr(response, "model_dump") else response

            tools.append(
                StructuredTool.from_function(
                    coroutine=call_tool,
                    name=tool.name,
                    description=tool.description or f"MCP tool: {tool.name}",
                )
            )

        return tools

    async def close(self) -> None:
        """释放 MCP 子进程和网络资源。"""
        await self.stack.aclose()
