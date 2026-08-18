"""Agent 共享状态。

除了消息历史，现在明确保存两类信息：
1. business_facts：已经由 MCP 工具确认的业务事实；
2. attachments：前端传入的文件/图片引用，避免图片只能存在一次 HTTP 请求里。

LangGraph checkpoint 会持久化这些状态，从而支持多轮对话和 interrupt/resume。
"""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """一次 Agent 执行所需要的共享状态。"""

    # add_messages 自动追加消息历史，而不是覆盖已有消息。
    messages: Annotated[list, add_messages]

    # 防止异常情况下模型无限调用工具。
    step: int

    # 只记录已经由真实 MCP Tool 成功执行确认的业务事实。
    # 使用普通 dict，确保 Redis/其他 checkpoint 可以稳定序列化。
    business_facts: dict[str, bool]

    # 前端上传的附件引用/元数据；不把二进制内容塞进 LangGraph checkpoint。
    attachments: list[dict[str, Any]]

    # 当前会话识别出的业务意图；默认保持 general。
    workflow_intent: str
