"""Workflow 抽象接口。

Graph 不应该知道“病例”“订单”这些业务名称。
每个业务 Workflow 只负责描述自己的确定性规则，Graph 只依赖这个接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Workflow(ABC):
    """一个可插拔的业务 Workflow。

    Workflow 是业务规则层，不负责调用 LLM，也不负责调用 MCP Server。
    """

    @property
    @abstractmethod
    def intent(self) -> str:
        """返回该 Workflow 对应的稳定意图标识。"""
        raise NotImplementedError

    @abstractmethod
    def next_step(self, facts: dict[str, Any]) -> str | None:
        """返回当前流程最小缺口；返回 None 表示没有缺口。"""
        raise NotImplementedError

    def instructions(self) -> str:
        """返回当前 Workflow 给模型的最小业务说明。"""
        return "遵守当前 Workflow 的确定性前置条件；不要猜测业务事实。"

    def check_tool(self, tool_name: str, facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
        """检查某个业务 Tool 是否满足当前 Workflow 的前置条件。"""
        return True, ""

    def update_facts(self, facts: dict[str, Any], tool_name: str, result: Any) -> dict[str, Any]:
        """根据成功的业务 Tool 结果更新事实。默认不更新。"""
        return facts
