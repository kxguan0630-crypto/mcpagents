"""HTTP API 数据结构。

兼容策略：
- 新客户端可以使用 message + attachments；
- 旧客户端可以继续使用 query + image_list；
- 两种输入最终都会在 AgentService 前统一。

这里暂不把图片二进制放进 Pydantic 模型；前端上传服务只需要把 file_id/url
等引用传给 Agent。这样不会把大文件塞进 LangGraph checkpoint。
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class ChatRequest(BaseModel):
    """一次 Agent 请求。message/query 至少提供一个。"""

    session_id: str = Field(min_length=1, description="会话 ID")
    message: str | None = Field(default=None, description="新客户端文本")
    query: str | None = Field(default=None, description="兼容旧 /query 客户端的文本字段")
    attachments: list[dict[str, Any]] | None = Field(default=None, description="附件引用")
    image_list: list[dict[str, Any]] | None = Field(default=None, description="兼容旧客户端的图片引用列表")
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


class ChatResponse(BaseModel):
    """Agent 返回结果。"""

    session_id: str
    answer: str
