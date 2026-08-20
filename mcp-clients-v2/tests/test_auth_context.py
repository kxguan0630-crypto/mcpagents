"""认证上下文和 MCP Tool 认证边界测试。"""

from auth.context import AuthContext, get_auth_context, reset_auth_context, set_auth_context
from mcp_intergration.client import MCPToolClient


def test_auth_context_is_request_scoped():
    context = AuthContext("Bearer real-token", {"userId": 123})
    token = set_auth_context(context)
    try:
        assert get_auth_context() is context
        assert get_auth_context().authorization == "Bearer real-token"
    finally:
        reset_auth_context(token)


def test_tool_schema_hides_authorization():
    schema = {
        "type": "object",
        "properties": {
            "patient_name": {"type": "string"},
            "authorization": {"type": "string"},
        },
        "required": ["patient_name", "authorization"],
    }

    public_schema = MCPToolClient._public_tool_schema(schema)

    assert "authorization" not in public_schema["properties"]
    assert "authorization" not in public_schema["required"]
    assert "authorization" in schema["properties"]
    assert "authorization" in schema["required"]
