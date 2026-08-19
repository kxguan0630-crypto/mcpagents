"""MCP Tool 参数适配。

这里放业务 Tool 与 HTTP 输入之间的少量兼容逻辑，避免 Graph 直接知道具体 Tool 名称。
"""

from __future__ import annotations

from typing import Any


def prepare_arguments(tool_name: str, arguments: dict[str, Any], attachments: list[dict[str, Any]]) -> dict[str, Any]:
    """在调用 MCP Tool 前补齐来自请求上下文的参数。"""
    prepared = dict(arguments)
    # image_process 的 Server schema 使用 image_list；前端附件可能只提供 file_id/fileId/url。
    if tool_name == "image_process" and not prepared.get("image_list") and attachments:
        prepared["image_list"] = attachments
    return prepared
