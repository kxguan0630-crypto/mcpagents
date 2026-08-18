# app.py - 应用工厂模式版本
import asyncio
# from venv import logger

from utils.log import setup_logger
from typing import Optional
from mcp.server.fastmcp import FastMCP


class OrthodonticServer:
    """正畸AI助手服务器类"""
    def __init__(self, name: str = "orthodontic_ai_assistant"):
        self.name = name
        self.mcp: Optional[FastMCP] = None
        self.logger = setup_logger()

    def create_app(self) -> FastMCP:
        """创建并配置MCP应用"""
        # 创建FastMCP实例
        self.mcp = FastMCP(self.name)

        # 注册工具
        self._register_tools()

        return self.mcp
    def _register_tools(self):
        """注册所有工具模块"""
        try:
            # 从各个工具模块导入并注册工具函数
            # from tools.appliance_management import (
            #     save_appliance_info,
            #     get_appliance_list,
            #     get_appliance_info
            # )
            # self.mcp.add_tool(save_appliance_info)
            # self.mcp.add_tool(get_appliance_list)
            # self.mcp.add_tool(get_appliance_info)
            import pkgutil
            import importlib
            import tools

            # 自动扫描并加载 tools 包下的所有模块
            for importer, modname, ispkg in pkgutil.iter_modules(tools.__path__, tools.__name__ + "."):
                try:
                    module = importlib.import_module(modname)
                    # 检查模块是否有 mcp 实例
                    if hasattr(module, 'mcp'):
                        self.logger.info(f'Found mcp instance in module: {modname}')

                        registered_count = 0
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            # 查找可能的工具函数
                            if (callable(attr) and
                                    hasattr(attr, '__module__') and
                                    attr.__module__ == modname and
                                    not attr_name.startswith('_') and
                                    attr_name != 'mcp'):

                                try:
                                    self.mcp.add_tool(attr)
                                    self.logger.info(f"Registered tool: {attr_name}")
                                    registered_count += 1
                                except Exception as e:
                                    self.logger.warning(f"Failed to register {attr_name}: {e}")

                        if registered_count > 0:
                            self.logger.info(f"Successfully registered {registered_count} tools from {modname}")
                        else:
                            self.logger.warning(f"No tools found in module: {modname}")

                    else:
                        self.logger.warning(f"Module {modname} has no mcp instance")
                except Exception as e:
                    self.logger.error(f"Error loading module {modname}: {e}")
                    self.logger.exception(e)

                # self.logger.info("Finished registering all tools")
        except Exception as e:
            self.logger.error(f"Failed to register tools: {e}")
            raise

    async def run(self, transport: str = 'stdio'):
        """运行服务器"""
        if not self.mcp:
            self.create_app()

        self.logger.info(f"Starting {self.name} with transport: {transport}")

        try:
            await self.mcp.run(transport=transport)
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            raise


# 创建应用实例的工厂函数
# def create_app() -> OrthodonticServer:
#     """应用工厂函数"""
#     return OrthodonticServer()
#
#
# # 便捷函数用于直接运行
# async def run_server(transport: str = 'stdio'):
#     """运行服务器的便捷函数"""
#     server = OrthodonticServer()
#     await server.run(transport)


# app.py - 适用于MCP框架的启动方式
if __name__ == "__main__":
    import sys

    transport = 'stdio'
    if len(sys.argv) > 1:
        transport = sys.argv[1]

    # 创建服务器实例
    server = OrthodonticServer()

    # 按照MCP框架的要求运行
    try:
        # 创建应用
        app = server.create_app()
        # 运行应用
        asyncio.run(app.run(transport))
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)