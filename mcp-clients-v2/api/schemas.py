"""HTTP API 的数据结构。

把 Web 请求格式独立出来，可以避免 FastAPI 和 Agent 业务代码互相污染。
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """客户端发送的一条消息。"""

    session_id: str = Field(min_length=1, description="会话 ID")
    message: str = Field(min_length=1, description="用户消息")


class ChatResponse(BaseModel):
    """Agent 返回给客户端的结果。"""

    session_id: str
    answer: str
