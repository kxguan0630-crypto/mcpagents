"""Agent 运行过程中共享的数据结构。

状态模型故意保持简单：消息 + 当前循环次数。
后续接 Redis/Postgres checkpoint 时，只需要持久化这个对象。
"""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """一次 Agent 执行所需要的最小状态。"""

    # add_messages 会自动把新消息追加到历史，而不是覆盖历史。
    messages: Annotated[list, add_messages]

    # 防止模型因为工具错误或异常情况无限调用工具。
    step: int
