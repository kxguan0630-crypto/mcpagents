"""MCP 连接层。

职责只有三个：
1. 连接 MCP Server；
2. 动态发现 MCP Tools；
3. 把 MCP 的业务参数交给 LangChain，并在真正执行 Tool 时由 Runtime 自动注入认证信息。

重要安全边界：MCP Server 仍然可以保留 authorization 参数以兼容现有业务 Service，
但该参数不会暴露给 LLM，也不会接受 LLM 自己生成的 Token。
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
        """把配置文件旁边定义的本地脚本路径转换成绝对路径。"""
        config_dir = self.config_path.resolve().parent
        resolved: list[str] = []
        for arg in args:
            candidate = Path(arg)
            if not candidate.is_absolute() and (config_dir / candidate).exists():
                resolved.append(str((config_dir / candidate).resolve()))
            else:
                resolved.append(arg)
        return resolved

    def _merge_server_env(self, server_env: dict[str, Any]) -> dict[str, str]:
        """合并父进程环境，并解析配置里的本地路径环境变量。"""
        merged = os.environ.copy()
        merged.update({str(k): str(v) for k, v in (server_env or {}).items()})

        if "PYTHONPATH" in merged:
            config_dir = self.config_path.resolve().parent
            parts = []
            for item in merged["PYTHONPATH"].split(os.pathsep):
                candidate = Path(item)
                if not candidate.is_absolute() and (config_dir / candidate).exists():
                    parts.append(str((config_dir / candidate).resolve()))
                else:
                    parts.append(item)
            merged["PYTHONPATH"] = os.pathsep.join(parts)
        return merged

    @staticmethod
    def _public_tool_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
        """隐藏 Server Tool 的 authorization 参数，避免把 Token 暴露给 LLM。

        Server 侧暂时保留 authorization 是为了兼容现有业务 Service；Client 侧把它
        视为 runtime-only 参数。即使模型自己生成 authorization，也会在执行前被覆盖。
        """
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
        if self.tool_timeout <= 0:
            raise ValueError("tool_timeout must be > 0")
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        servers = config.get("mcpServers")
        if not isinstance(servers, dict) or "default" not in servers:
            raise ValueError("MCP config must contain mcpServers.default")
        server = servers["default"]
        if not server.get("command"):
            raise ValueError("MCP server command cannot be empty")

        params = StdioServerParameters(
            command=server["command"],
            args=self._resolve_server_args(server.get("args", [])),
            env=self._merge_server_env(server.get("env") or {}),
        )
        read_stream, write_stream = await self.stack.enter_async_context(stdio_client(params))
        self.session = await self.stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self.session.initialize()
        self.tools = await self._load_tools()

    async def _load_tools(self) -> list[StructuredTool]:
        """动态发现 MCP Tools，并从模型可见 Schema 中剥离认证参数。"""
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

                # 强制覆盖模型可能传入的 authorization，永远使用 HTTP/CLI 入口验证过的 Token。
                runtime_arguments = dict(kwargs)
                runtime_arguments["authorization"] = auth_context.authorization

                attempts = self.max_retries if _tool_name in self.retryable_tools else 0
                last_error: Exception | None = None
                for attempt in range(attempts + 1):
                    try:
                        response = await asyncio.wait_for(
                            self.session.call_tool(_tool_name, arguments=runtime_arguments),
                            timeout=self.tool_timeout,
                        )
                        return response.model_dump() if hasattr(response, "model_dump") else response
                    except Exception as exc:
                        last_error = exc
                        if attempt == attempts:
                            break
                        await asyncio.sleep(0.5 * (attempt + 1))
                raise MCPToolError(
                    f"MCP tool '{_tool_name}' failed after {attempts + 1} attempt(s): {last_error}"
                ) from last_error

            tools.append(
                StructuredTool.from_function(
                    coroutine=call_tool,
                    name=tool.name,
                    description=tool.description or f"MCP tool: {tool.name}",
                    args_schema=public_schema,
                )
            )
        return tools

    async def close(self) -> None:
        """释放 MCP 子进程和网络资源。"""
        await self.stack.aclose()
