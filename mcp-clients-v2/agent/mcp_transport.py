"""MCP Transport 抽象。

当前项目仍以 STDIO 为默认实现；这里把 Transport 能力与 Agent Graph 解耦，
后续接 Streamable HTTP 时只需要提供同样的 connect/list_tools/call_tool/close 接口。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class MCPTransport(Protocol):
    """MCP 传输层最小接口。"""

    async def connect(self) -> None: ...
    async def list_tools(self) -> list[Any]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...
    async def close(self) -> None: ...


@dataclass(frozen=True)
class MCPServerHealth:
    """MCP Server 的轻量健康状态。"""

    name: str
    connected: bool
    tool_count: int = 0
    error: str | None = None
