"""STDIO MCP 本地启动配置测试。

这些测试不启动真实 MCP Server，只验证配置和路径解析逻辑，
避免单元测试依赖用户本机的 Python/业务环境。
"""

from pathlib import Path

from mcp.client import MCPToolClient


def test_local_stdio_config_exists_and_has_default_server():
    config = Path(__file__).parents[1] / "config" / "servers_config.json"
    assert config.exists()

    client = MCPToolClient(str(config))
    import json

    data = json.loads(config.read_text(encoding="utf-8"))
    server = data["mcpServers"]["default"]

    assert server["command"] == "python3.11"
    args = client._resolve_server_args(server["args"])
    assert args
    assert Path(args[0]).name == "app.py"
    assert Path(args[0]).exists()


def test_stdio_pythonpath_is_resolved_relative_to_config():
    config = Path(__file__).parents[1] / "config" / "servers_config.json"
    client = MCPToolClient(str(config))

    env = client._merge_server_env({"PYTHONPATH": "../mcp-servers"})
    paths = env["PYTHONPATH"].split(":")

    assert str((config.parent / "../mcp-servers").resolve()) in paths
