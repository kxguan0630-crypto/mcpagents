"""HTTP 请求模型的首次会话兼容测试。

前端第一次调用 /query 时 session_id 可能还是空字符串。
服务端负责生成会话 ID，后续 Agent 层只接收有效 ID。
"""

from api.schemas import ChatRequest


def test_empty_session_id_is_replaced_with_uuid():
    request = ChatRequest(session_id="", query="创建患者")

    assert request.session_id
    assert request.session_id != ""
    assert len(request.session_id) == 36


def test_existing_session_id_is_preserved():
    request = ChatRequest(session_id="frontend-session-001", query="你好")

    assert request.session_id == "frontend-session-001"


def test_session_id_can_be_omitted_on_first_request():
    request = ChatRequest(query="你好")

    assert request.session_id
