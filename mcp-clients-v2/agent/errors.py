"""Agent 层的错误类型。

把错误分类放在这里，而不是让 HTTP 层自己猜异常是什么。
这样以后增加日志、监控或不同的 HTTP 状态码时会更容易。
"""


class AgentError(Exception):
    """所有 Agent 运行错误的基类。"""


class AgentConfigurationError(AgentError):
    """配置错误，例如 LLM 或 MCP 配置缺失。"""


class AgentExecutionError(AgentError):
    """Agent 执行过程中发生的错误。"""


class MCPToolError(AgentExecutionError):
    """MCP 工具调用失败。"""
