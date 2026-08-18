"""统一前端附件输入。

前端负责上传文件；Agent 只接收文件引用。
这里把旧的 image_list 和新的 attachments 统一成同一种简单结构，
让后面的 LangGraph / image_process 不需要关心 HTTP 参数名称。
"""

from __future__ import annotations

from typing import Any


class AttachmentInputError(ValueError):
    """附件结构无法被 Agent 识别。"""


def normalize_attachments(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """把前端附件转换成 Agent 内部统一格式。

    只保留引用信息，不读取文件内容，也不把二进制写入 checkpoint。
    支持常见的 file_id/fileId 和 url/image_url 字段。
    """
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items or []):
        if not isinstance(item, dict):
            raise AttachmentInputError(f"attachment[{index}] must be an object")

        file_id = item.get("file_id") or item.get("fileId")
        url = item.get("url") or item.get("image_url")
        name = item.get("name") or item.get("filename")

        if isinstance(url, dict):
            url = url.get("url")

        if not file_id and not url:
            raise AttachmentInputError(
                f"attachment[{index}] must contain file_id/fileId or url/image_url"
            )

        normalized.append(
            {
                "file_id": str(file_id) if file_id else None,
                "url": str(url) if url else None,
                "name": str(name) if name else None,
            }
        )

    return normalized
