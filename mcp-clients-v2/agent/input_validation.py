"""Agent 输入校验。

校验放在 AgentService 之前，避免无意义的请求进入 LLM。
这里只做通用校验，不写任何病例、订单等业务规则。
"""


class AgentInputError(ValueError):
    """用户输入不符合 Agent 基础要求。"""


def validate_agent_input(session_id: str, user_input: str, max_chars: int = 4000) -> None:
    """校验一次 Agent 请求的最基本条件。

    为什么限制长度？
    过大的输入会增加 token 成本，也可能让上下文迅速超过模型限制。
    具体业务参数仍然应该由 MCP Tool 自己校验。
    """
    if not session_id or not session_id.strip():
        raise AgentInputError("session_id cannot be empty")

    if not user_input or not user_input.strip():
        raise AgentInputError("user_input cannot be empty")

    if len(user_input) > max_chars:
        raise AgentInputError(
            f"user_input is too long: {len(user_input)} chars; "
            f"maximum is {max_chars}"
        )
