"""MCP 连接层。

职责只有三个：
1. 连接 MCP Server；
2. 动态发现 MCP Tools；
3. 把 MCP 的真实 inputSchema 原样交给 LangChain。

这里不硬编码业务工具名称，也不把业务流程写进 MCP Client。
"""

import asyncio
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.errors import MCPToolError


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

        # PYTHONPATH 是本地 Server 启动的关键路径。支持配置文件里的相对路径，
        # 同时保留父进程已有的 PYTHONPATH，避免覆盖用户环境。
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

    async def connect(self) -> None:
        """读取配置、建立 STDIO MCP 连接并发现工具。

        这里沿用原项目的通信方式：Client 根据 servers_config.json 启动
        MCP Server 子进程，通过 stdin/stdout 建立 MCP ClientSession。
        因此不需要给 MCP Server 配置 HTTP 地址。
        """
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
        """动态发现 MCP Tools，并保留 Server 提供的 JSON Schema。

        这是从旧客户端升级到 Agent 的关键点：LLM 必须看到真实参数结构，
        否则动态 Tool 虽然“存在”，模型却不知道应该传哪些参数。
        """
        if self.session is None:
            raise RuntimeError("MCP session is not connected")

        result = await self.session.list_tools()
        tools: list[StructuredTool] = []
        for tool in result.tools:
            input_schema = getattr(tool, "inputSchema", None) or {"type": "object", "properties": {}}

            async def call_tool(_tool_name=tool.name, **kwargs: Any):
                """调用单个 MCP Tool；默认不重试有副作用的业务动作。"""
                if self.session is None:
                    raise MCPToolError("MCP session is not connected")
                attempts = self.max_retries if _tool_name in self.retryable_tools else 0
                last_error: Exception | None = None
                for attempt in range(attempts + 1):
                    try:
                        response = await asyncio.wait_for(
                            self.session.call_tool(_tool_name, arguments=kwargs),
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
                    # 直接使用 MCP Server 的 JSON Schema，避免丢失参数定义。
                    args_schema=input_schema,
                )
            )
        return tools

    async def close(self) -> None:
        """释放 MCP 子进程和网络资源。"""
        await self.stack.aclose()
