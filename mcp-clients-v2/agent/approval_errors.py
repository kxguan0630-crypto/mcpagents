"""把“需要人工审批”作为一种正常的 Agent 控制流结果。"""


class AgentApprovalRequired(Exception):
    """Agent 已经暂停，等待用户确认。"""

    def __init__(self, approval: dict) -> None:
        self.approval = approval
        super().__init__("Agent requires human approval")
