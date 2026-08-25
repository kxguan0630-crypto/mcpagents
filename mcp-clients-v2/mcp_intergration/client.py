"""MCP 连接层。

职责只有三个：连接 MCP Server、动态发现 Tools、提供统一的 Runtime Tool Metadata。
认证参数只在执行时从 AuthContext 注入，LLM 永远看不到 authorization。
"""

import asyncio
import copy
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.errors import MCPToolError
from agent.retry import retry_async
from auth.context import get_auth_context


class MCPToolClient:
    """管理 MCP Server 连接，并动态发现结构化工具。"""

    def __init__(self, config_path: str, tool_timeout: float = 30.0,
                 max_retries: int = 0, retryable_tools: frozenset[str] | None = None):
        self.config_path = Path(config_path)
        self.tool_timeout = tool_timeout
        self.max_retries = max_retries
        self.retryable_tools = retryable_tools or frozenset()
        self.stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self.tools: list[StructuredTool] = []

    def _resolve_server_args(self, args: list[str]) -> list[str]:
        config_dir = self.config_path.resolve().parent
        return [str((config_dir / arg).resolve()) if not Path(arg).is_absolute() and (config_dir / arg).exists() else arg for arg in args]

    def _merge_server_env(self, server_env: dict[str, Any]) -> dict[str, str]:
        merged = os.environ.copy()
        merged.update({str(k): str(v) for k, v in (server_env or {}).items()})
        if "PYTHONPATH" in merged:
            config_dir = self.config_path.resolve().parent
            parts = []
            for item in merged["PYTHONPATH"].split(os.pathsep):
                candidate = Path(item)
                parts.append(str((config_dir / candidate).resolve()) if not candidate.is_absolute() and (config_dir / candidate).exists() else item)
            merged["PYTHONPATH"] = os.pathsep.join(parts)
        return merged

    @staticmethod
    def _public_tool_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
        """隐藏 Server Tool 的 authorization 参数，避免把 Token 暴露给 LLM。"""
        schema = copy.deepcopy(input_schema)
        properties = schema.get("properties")
        if isinstance(properties, dict):
            properties.pop("authorization", None)
        required = schema.get("required")
        if isinstance(required, list):
            schema["required"] = [item for item in required if item != "authorization"]
        return schema

    async def connect(self) -> None:
        """读取配置、建立 STDIO MCP 连接并发现工具。"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"MCP config not found: {self.config_path}")
        if self.tool_timeout <= 0 or self.max_retries < 0:
            raise ValueError("invalid MCP runtime limits")
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        server = (config.get("mcpServers") or {}).get("default")
        if not isinstance(server, dict) or not server.get("command"):
            raise ValueError("MCP config must contain mcpServers.default.command")
        params = StdioServerParameters(command=server["command"], args=self._resolve_server_args(server.get("args", [])), env=self._merge_server_env(server.get("env") or {}))
        read_stream, write_stream = await self.stack.enter_async_context(stdio_client(params))
        self.session = await self.stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self.session.initialize()
        self.tools = await self._load_tools()

    async def _load_tools(self) -> list[StructuredTool]:
        """动态发现 MCP Tools，并为每个业务 Tool 声明稳定的 runtime metadata。"""
        if self.session is None:
            raise RuntimeError("MCP session is not connected")
        result = await self.session.list_tools()
        tools: list[StructuredTool] = []
        for tool in result.tools:
            input_schema = getattr(tool, "inputSchema", None) or {"type": "object", "properties": {}}
            public_schema = self._public_tool_schema(input_schema)

            async def call_tool(_tool_name=tool.name, **kwargs: Any):
                """调用 MCP Tool；认证 Token 只来自已验证的 Runtime Context。"""
                if self.session is None:
                    raise MCPToolError("MCP session is not connected")
                try:
                    auth_context = get_auth_context()
                except RuntimeError as exc:
                    raise MCPToolError("Authenticated runtime context is required") from exc
                runtime_arguments = dict(kwargs)
                runtime_arguments["authorization"] = auth_context.authorization
                attempts = self.max_retries if _tool_name in self.retryable_tools else 0

                async def invoke_once():
                    """单次调用独立封装，retry_async 不需要知道 MCP 实现细节。"""
                    return await asyncio.wait_for(
                        self.session.call_tool(_tool_name, arguments=runtime_arguments),
                        timeout=self.tool_timeout,
                    )

                try:
                    response = await retry_async(invoke_once, attempts)
                    return response.model_dump() if hasattr(response, "model_dump") else response
                except Exception as exc:
                    raise MCPToolError(
                        f"MCP tool '{_tool_name}' failed after {attempts + 1} attempt(s): {exc}"
                    ) from exc

            tools.append(StructuredTool.from_function(
                coroutine=call_tool,
                name=tool.name,
                description=tool.description or f"MCP tool: {tool.name}",
                args_schema=public_schema,
                metadata={"visibility": "user", "display_name": tool.name, "category": "mcp_business"},
            ))
        return tools

    async def close(self) -> None:
        await self.stack.aclose()
