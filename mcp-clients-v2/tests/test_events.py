"""AgentEvent 的格式测试。"""

import json

from agent.events import AgentEvent


def test_event_can_be_encoded_as_sse():
    """事件应该能转换成标准 SSE data 行。"""
    text = AgentEvent(
        type="tool_end",
        content="success",
        tool_name="query_case",
    ).to_sse()

    assert text.startswith("data: ")
    payload = json.loads(text[len("data: ") :].strip())
    assert payload["type"] == "tool_end"
    assert payload["tool_name"] == "query_case"
