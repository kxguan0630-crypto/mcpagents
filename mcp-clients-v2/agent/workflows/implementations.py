"""把现有确定性 Workflow 规则适配到统一 Workflow 接口。

业务规则仍放在各自的 case_creation/order_creation/rules 文件中，
本文件只负责组合它们，不把业务细节塞回 Graph。
"""

from __future__ import annotations

from typing import Any

from .base import Workflow
from .case_creation import next_required_question as next_case_question
from .order_creation import next_required_question as next_order_question
from .rules import case_add_allowed, image_update_allowed, order_create_allowed


class CaseCreationWorkflow(Workflow):
    """病例创建流程。"""

    intent = "case_creation"

    def next_step(self, facts: dict[str, Any]) -> str | None:
        return next_case_question(facts)

    def check_tool(self, tool_name: str, facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
        if tool_name == "case_add":
            return case_add_allowed(facts, arguments)
        return True, ""


class OrderCreationWorkflow(Workflow):
    """订单创建流程。"""

    intent = "order_creation"

    def next_step(self, facts: dict[str, Any]) -> str | None:
        return next_order_question(facts, facts.get("need_design"))

    def check_tool(self, tool_name: str, facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
        if tool_name == "case_order_add":
            return order_create_allowed(facts, arguments)
        return True, ""


class ImageUpdateWorkflow(Workflow):
    """订单/病例创建后的影像更新流程。"""

    intent = "update_image"

    def next_step(self, facts: dict[str, Any]) -> str | None:
        return None if facts.get("image_processed") else "image_process"

    def check_tool(self, tool_name: str, facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
        if tool_name == "save_case_face":
            return image_update_allowed(facts, arguments)
        return True, ""


def build_default_workflow_registry():
    """创建产品默认 Workflow 集合。

    新增业务流程时在这里注册即可，Graph 无需修改。
    """
    from .registry import WorkflowRegistry

    return WorkflowRegistry([
        CaseCreationWorkflow(),
        OrderCreationWorkflow(),
        ImageUpdateWorkflow(),
    ])
