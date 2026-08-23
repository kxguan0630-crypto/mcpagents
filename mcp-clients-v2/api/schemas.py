"""HTTP API 数据结构。

兼容策略：
- 新客户端可以使用 message + attachments；
- 原客户端可以继续使用 query + image_list；
- 两种输入进入 Agent 前都会统一成 text + attachments。

图片二进制不进入 Pydantic 请求模型，也不进入 LangGraph checkpoint；
前端上传服务只需要提供 file_id、url 等引用。

会话兼容策略：
- 前端第一次请求可能还没有 session_id，此时允许传空字符串；
- 服务端会在请求模型校验阶段生成 UUID；
- 后续请求继续使用前端传回的 session_id。
"""

import uuid
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ChatRequest(BaseModel):
    """一次 Agent 请求。message/query 至少提供一个。"""

    # 前端第一次请求可能传空字符串；空值由下面的 validator 自动生成 UUID。
    session_id: str = Field(default="", description="会话 ID")
    message: str | None = Field(default=None, description="新客户端文本")
    query: str | None = Field(default=None, description="兼容原 /query 的文本字段")
    attachments: list[dict[str, Any]] | None = Field(default=None, description="新客户端附件引用")
    image_list: list[dict[str, Any]] | None = Field(default=None, description="兼容原客户端图片引用列表")
    authorization: str | None = Field(default=None, description="Authorization token")
    we_lang: str = Field(default="zh-CN", description="语言")

    @model_validator(mode="after")
    def validate_request(self):
        """完成请求级兜底校验，并为首次请求生成会话 ID。

        为什么在 Schema 层生成？
        ChatRequest 是 HTTP 请求进入 Agent 的第一道边界。把空 session_id
        在这里转换成正式 ID，可以保证后续 AgentInput 校验和业务服务永远拿到
        一个有效的 session_id，同时不要求前端第一次请求必须先生成 ID。
        """
        if not self.session_id or not self.session_id.strip():
            self.session_id = str(uuid.uuid4())

        if not (self.message or self.query):
            raise ValueError("message 或 query 至少提供一个")
        return self

    @property
    def text(self) -> str:
        """统一得到用户文本。"""
        return self.message or self.query or ""

    @property
    def input_attachments(self) -> list[dict[str, Any]]:
        """统一得到附件；显式提供 attachments 时优先使用它。"""
        return self.attachments if self.attachments is not None else (self.image_list or [])


class ChatResponse(BaseModel):
    """Agent 返回结果。"""

    session_id: str
    answer: str
