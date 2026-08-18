# tools/__init__.py
import pkgutil
import importlib
from mcp.server.fastmcp import FastMCP
import tools

# 创建统一的MCP实例
tool_mcp = FastMCP("all_tools")

def load_all_tools():
    """自动加载所有工具模块"""
    for importer, modname, ispkg in pkgutil.iter_modules(tools.__path__, tools.__name__ + "."):
        try:
            module = importlib.import_module(modname)
            if hasattr(module, 'mcp'):
                tool_mcp.merge(module.mcp)
        except Exception as e:
            print(f"Failed to load module {modname}: {e}")
            continue

# 自动加载所有工具
load_all_tools()