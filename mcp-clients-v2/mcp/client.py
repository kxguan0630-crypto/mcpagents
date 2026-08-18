"""MCP 连接层。

职责只有三个：
1. 连接 MCP Server。
2. 动态发现 MCP Tools。
3. 把工具调用转换成 LangChain 可以使用的工具。

这里完全不知道病例、订单、患者等业务概念。
"""

import asyncio
import json
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.errors import MCPToolError


class MCPToolClient:
    """管理一个 MCP Server 连接及其动态发现出来的工具。"""

    def __init__(
        self,
        config_path: str,
        tool_timeout: float = 30.0,
        max_retries: int = 2,
    ):
        self.config_path = Path(config_path)
        self.tool_timeout = tool_timeout
        self.max_retries = max_retries
        self.stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self.tools: list[StructuredTool] = []

    async def connect(self) -> None:
        """读取配置、建立 MCP 连接，并自动发现工具。"""
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
        """从 MCP Server 动态发现工具，不硬编码工具名称。"""
        if self.session is None:
            raise RuntimeError("MCP session is not connected")

        result = await self.session.list_tools()
        tools: list[StructuredTool] = []

        for tool in result.tools:
            async def call_tool(_tool_name=tool.name, **kwargs: Any):
                """调用单个 MCP Tool，并提供超时与有限重试。"""
                if self.session is None:
                    raise MCPToolError("MCP session is not connected")

                last_error: Exception | None = None

                for attempt in range(self.max_retries + 1):
                    try:
                        response = await asyncio.wait_for(
                            self.session.call_tool(_tool_name, arguments=kwargs),
                            timeout=self.tool_timeout,
                        )
                        return (
                            response.model_dump()
                            if hasattr(response, "model_dump")
                            else response
                        )
                    except Exception as exc:
                        last_error = exc
                        # 最后一次失败不再等待，直接把清晰的错误交给 ToolNode。
                        if attempt == self.max_retries:
                            break
                        await asyncio.sleep(0.5 * (attempt + 1))

                raise MCPToolError(
                    f"MCP tool '{_tool_name}' failed after "
                    f"{self.max_retries + 1} attempts: {last_error}"
                ) from last_error

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
