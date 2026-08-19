"""订单创建 Workflow 的业务规则。

LLM 负责理解用户；LangGraph 负责流程；本文件负责确定性的订单阶段判断；
MCP Tool 负责真正执行业务动作。

尤其要注意：
- “必须询问”和“必须提供”不是一回事；
- 诊断、影像、模型每次都必须询问，但用户可以选择不提供；
- need_design=1 完全跳过处方；
- need_design=0 才进入处方询问。
"""

from __future__ import annotations

from typing import Any


ORDER_REQUIRED_DECISIONS = (
    ("diagnosis_decision", "诊断"),
    ("image_decision", "影像"),
    ("model_decision", "模型"),
)


def next_required_question(facts: dict[str, Any], need_design: int | None) -> str | None:
    """返回当前订单流程需要完成的阶段。

    返回的是稳定的阶段名称，不是自然语言问题；自然语言由 LLM 根据上下文生成。
    """
    if not facts.get("order_checked"):
        return "order_check"
    if not facts.get("product_list_loaded"):
        return "product_selection"
    if need_design not in (0, 1):
        return "need_design"

    for key, _label in ORDER_REQUIRED_DECISIONS:
        if facts.get(key) not in ("provide", "skip"):
            return key

    # 只有 need_design=0 才允许进入处方阶段。
    if need_design == 0 and facts.get("recipe_decision") not in ("provide", "skip"):
        return "recipe_decision"

    return None


def normalize_optional_decision(value: Any) -> str | None:
    """把用户的“提供/不提供”统一成 Workflow 使用的两个值。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return "provide" if value else "skip"

    text = str(value).strip().lower()
    if text in {"provide", "yes", "y", "是", "提供", "愿意"}:
        return "provide"
    if text in {"skip", "no", "n", "否", "不提供", "不愿意", "跳过"}:
        return "skip"
    return None


def should_collect_recipe(need_design: int | None) -> bool:
    """判断是否进入处方流程。"""
    return need_design == 0
