"""防止 Agent Graph 重新长回业务 if/else 的回归测试。"""

from pathlib import Path


def test_graph_does_not_encode_business_workflow_branches():
    graph_source = Path(__file__).parents[1].joinpath("agent", "graph.py").read_text(encoding="utf-8")

    # 这些业务标识应该由 Workflow Registry / 业务规则层持有，而不是 Graph 持有。
    forbidden = (
        "if intent == \"case_creation\"",
        "if intent == \"order_creation\"",
        "if tool_name == \"case_add\"",
        "if tool_name == \"case_order_add\"",
        "if tool_name == \"save_case_face\"",
        "if tool_name == \"record_workflow_intent\"",
        "if tool_name == \"record_case_information\"",
    )

    assert all(item not in graph_source for item in forbidden)
