"""统一的 Agent 输入对象。

HTTP 层可以兼容旧客户端的字段名，但进入 Agent 后统一成这个结构。
这样前端协议与 Agent 内部实现解耦。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentInput:
    """一次用户输入：文本 + 附件 + 认证/语言上下文。"""

    session_id: str
    text: str
    attachments: list[dict[str, Any]] = field(default_factory=list)
    authorization: str | None = None
    we_lang: str = "zh-CN"


def normalize_attachments(
    image_list: list[dict[str, Any]] | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """把旧客户端常见的 image_list 与新 attachments 统一成一个列表。"""
    values = attachments if attachments is not None else image_list
    if not values:
        return []
    normalized: list[dict[str, Any]] = []
    for item in values:
        if isinstance(item, dict):
            normalized.append(dict(item))
        else:
            # 不猜测二进制格式；只保留可序列化的引用。
            normalized.append({"value": str(item)})
    return normalized
