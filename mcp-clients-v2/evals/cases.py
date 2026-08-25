"""离线 Agent 行为场景。

这些场景刻意只描述“必须发生什么”，不规定 LLM 的自然语言措辞。
因此不会因为模型换了表达方式就让回归测试失效。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalCase:
    name: str
    tool_sequence: tuple[str, ...]
    forbidden_tools: tuple[str, ...] = ()
    answer_contains: tuple[str, ...] = ()


CASES = (
    EvalCase(
        name="case_creation_must_check_patient_after_information",
        tool_sequence=("get_patients_by_name_and_phone",),
        forbidden_tools=("case_add",),
    ),
    EvalCase(
        name="new_patient_can_create_case_after_decision",
        tool_sequence=("get_patients_by_name_and_phone", "case_add"),
    ),
    EvalCase(
        name="order_with_design_skips_recipe_collection",
        tool_sequence=("get_product_list", "record_design_decision"),
        forbidden_tools=("record_order_decisions.recipe_decision",),
    ),
    EvalCase(
        name="image_can_be_updated_after_order",
        tool_sequence=("image_process",),
    ),
)
