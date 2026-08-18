"""HTTP API 数据结构。

兼容策略：
- 新客户端可以使用 message + attachments；
- 原客户端可以继续使用 query + image_list；
- 两种输入进入 Agent 前都会统一成 text + attachments。

图片二进制不进入 Pydantic 请求模型，也不进入 LangGraph checkpoint；
前端上传服务只需要提供 file_id、url 等引用。
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class ChatRequest(BaseModel):
    """一次 Agent 请求。message/query 至少提供一个。"""

    session_id: str = Field(min_length=1, description="会话 ID")
    message: str | None = Field(default=None, description="新客户端文本")
    query: str | None = Field(default=None, description="兼容原 /query 的文本字段")
    attachments: list[dict[str, Any]] | None = Field(default=None, description="新客户端附件引用")
    image_list: list[dict[str, Any]] | None = Field(default=None, description="兼容原客户端图片引用列表")
    authorization: str | None = Field(default=None, description="Authorization token")
    we_lang: str = Field(default="zh-CN", description="语言")

    @model_validator(mode="after")
    def validate_text(self):
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
