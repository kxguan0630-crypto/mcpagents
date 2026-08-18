"""决定哪些工具需要人工确认。

重要原则：这里允许业务配置审批规则，但 Agent Graph 不应该硬编码业务工具名称。
第一版提供一个清晰的 allow-list：只有明确配置需要审批的工具才会进入审批流程。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApprovalPolicy:
    """人工审批策略。"""

    approval_required_tools: frozenset[str] = field(default_factory=frozenset)

    def requires_approval(self, tool_name: str) -> bool:
        """判断某个工具是否必须经过人工确认。"""
        return tool_name in self.approval_required_tools
