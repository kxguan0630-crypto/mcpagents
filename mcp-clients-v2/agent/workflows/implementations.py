"""把业务 Workflow 适配到统一接口。

业务规则仍放在 case_creation/order_creation/rules 中；
Graph 只通过 Workflow 接口访问这些规则。
"""

from __future__ import annotations

from typing import Any

from .actions import RequiredAction, next_required_action
from .base import Workflow
from .case_creation import next_required_question as next_case_question
from .order_creation import next_required_question as next_order_question
from .rules import case_add_allowed, image_update_allowed, order_create_allowed


class CaseCreationWorkflow(Workflow):
    """病例创建流程。"""

    intent = "case_creation"

    def next_step(self, facts: dict[str, Any]) -> str | None:
        return next_case_question(facts)

    def required_action(self, facts: dict[str, Any]) -> RequiredAction | None:
        """患者信息和主诉齐全后，强制执行患者存在性查询。"""
        return next_required_action(facts)

    def instructions(self) -> str:
        return "病例创建：先收集完整患者基本信息和主诉，再查询患者是否存在；查询完成后必须等待用户明确选择新建患者或使用已有患者。"

    def check_tool(self, tool_name: str, facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
        if tool_name == "case_add":
            return case_add_allowed(facts, arguments)
        return True, ""


class OrderCreationWorkflow(Workflow):
    """订单创建流程。"""

    intent = "order_creation"

    def next_step(self, facts: dict[str, Any]) -> str | None:
        return next_order_question(facts, facts.get("need_design"))

    def instructions(self) -> str:
        return "订单创建：诊断、影像、模型每次都必须询问，用户可以选择不提供；need_design=1 完全跳过处方，只有 need_design=0 才询问处方。"

    def check_tool(self, tool_name: str, facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
        if tool_name == "case_order_add":
            return order_create_allowed(facts, arguments)
        return True, ""


class ImageUpdateWorkflow(Workflow):
    """订单/病例创建后的影像更新流程。"""

    intent = "update_image"

    def next_step(self, facts: dict[str, Any]) -> str | None:
        return None if facts.get("image_processed") else "image_process"

    def instructions(self) -> str:
        return "影像更新：先完成 image_process，再允许保存或更新影像。"

    def check_tool(self, tool_name: str, facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
        if tool_name == "save_case_face":
            return image_update_allowed(facts, arguments)
        return True, ""


def build_default_workflow_registry():
    """创建产品默认 Workflow 集合；新增流程时只需在这里注册。"""
    from .registry import WorkflowRegistry

    return WorkflowRegistry([
        CaseCreationWorkflow(),
        OrderCreationWorkflow(),
        ImageUpdateWorkflow(),
    ])
