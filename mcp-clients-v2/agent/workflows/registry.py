"""Workflow 注册中心。

这里集中维护“意图 → Workflow”的关系。
Graph 不再写 if intent == ...；新增业务流程时只需注册新的 Workflow。
"""

from __future__ import annotations

from typing import Any

from .actions import RequiredAction
from .base import Workflow
from .rules import update_facts


class WorkflowRegistry:
    """可扩展的 Workflow 注册表。"""

    def __init__(self, workflows: list[Workflow] | None = None):
        self._workflows: dict[str, Workflow] = {}
        for workflow in workflows or []:
            self.register(workflow)

    def register(self, workflow: Workflow) -> None:
        """注册一个 Workflow；重复意图直接报错，避免配置悄悄覆盖。"""
        if workflow.intent in self._workflows:
            raise ValueError(f"Workflow intent already registered: {workflow.intent}")
        self._workflows[workflow.intent] = workflow

    def resolve(self, intent: str | None) -> Workflow | None:
        """根据意图取得 Workflow；未知意图返回 None。"""
        if not intent:
            return None
        return self._workflows.get(intent)

    def required_action(self, intent: str | None, facts: dict[str, Any]) -> RequiredAction | None:
        """返回当前 Workflow 要求 Runtime 自动执行的动作。"""
        workflow = self.resolve(intent)
        if workflow is None:
            return None
        return workflow.required_action(facts)

    def check_tool(self, intent: str | None, tool_name: str, facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
        """把 Tool 门禁交给当前 Workflow。"""
        workflow = self.resolve(intent)
        if workflow is None:
            return True, ""
        return workflow.check_tool(tool_name, facts, arguments)

    def update_facts(self, facts: dict[str, Any], tool_name: str, result: Any) -> dict[str, Any]:
        """统一更新业务事实。

        业务 Tool → business_facts 的映射属于业务规则层；Graph 不再知道具体 Tool 名称。
        """
        return update_facts(facts, tool_name, result)

    def all(self) -> tuple[Workflow, ...]:
        """返回当前注册的 Workflow，便于测试和观测。"""
        return tuple(self._workflows.values())
