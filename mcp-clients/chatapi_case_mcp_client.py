# mcp_client_workflow.py
import json
from contextlib import AsyncExitStack
from openai import AsyncClient
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import os
from dotenv import load_dotenv
import argparse
from functools import wraps
import time
from quart import Quart, request, jsonify, render_template_string
from quart_cors import cors
import logging
import asyncio
from tenacity import retry, stop_after_attempt, wait_fixed
import traceback
import uuid
from system_prompt import PROMPT_MEDICAL_ASSISTANT,PROMPT_MEDICAL_ASSISTANT_EN
import requests
from typing import AsyncGenerator
from tenacity import RetryError
import redis
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
import sys
import subprocess
from typing import Dict, Optional
import copy

# 禁用 watchdog 的调试日志
logging.getLogger('watchdog.observers.inotify_buffer').setLevel(logging.WARNING)
logging.getLogger('watchdog').setLevel(logging.WARNING)

# 日志配置
from utils.log import setup_logging # 导入日志实例
logger = setup_logging()


class MCPFileChangeHandler(FileSystemEventHandler):
    def __init__(self, watched_dir, restart_callback, config_file=None):
        self.watched_dir = os.path.abspath(watched_dir) if watched_dir else None
        self.restart_callback = restart_callback
        self.last_modified_time = 0  # 上次修改时间戳
        self.debounce_seconds = 1  # 防抖间隔（秒）
        self.config_file = config_file and os.path.abspath(config_file)

    def on_modified(self, event: FileModifiedEvent):
        if event.is_directory:
            return
        file_path = os.path.abspath(event.src_path)

        if self.config_file and file_path == self.config_file:
            print(f"[热加载] 检测到配置文件已修改: {file_path}")
            self.restart_callback()
            return

        # 只监听 .py 文件（可按需扩展）
        if not file_path.endswith(".py"):
            return
        # 判断是否在目标目录下
        if self.watched_dir and not file_path.startswith(self.watched_dir):
            return

        current_time = time.time()
        if current_time - self.last_modified_time < self.debounce_seconds:
            return  # 防抖，避免重复触发

        self.last_modified_time = current_time
        print(f"[热加载] 检测到文件已修改: {file_path}")
        self.restart_callback()


def start_watching_mcp_file(watched_dir, callback, config_path="servers_config.json"):
    observer = Observer()
    if watched_dir:
        observer.schedule(MCPFileChangeHandler(watched_dir, callback), path=watched_dir, recursive=True)
    config_dir = os.path.dirname(os.path.abspath(config_path)) if os.path.isabs(config_path) else "."
    config_file = os.path.abspath(config_path)
    observer.schedule(MCPFileChangeHandler(None, callback, config_file), path=config_dir, recursive=False)

    observer.start()
    if watched_dir:
        print(f"[热加载] 正在监控目录: {watched_dir} 中的 .py 文件")
    print(f"[热加载] 正在监控配置文件: {config_file}")
    return observer


def restart_program():
    """重启程序 - 仅用于热加载场景"""
    logger.info("Restarting program...")
    print("[热加载] 正在准备重启服务...")

    # 【重要】不要尝试在任何新的事件循环中清理资源！
    # 直接终止进程，让 OS 回收子进程。
    # 任何异步清理在跨 Loop 时都会导致 anyio 报错。

    try:
        import psutil
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                print(f"[热加载] 终止子进程 PID: {child.pid}")
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        gone, still_alive = psutil.wait_procs(children, timeout=3)
        for p in still_alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        print(f"Error terminating processes: {e}")

    restart_cmd = [sys.executable, "-u"] + sys.argv
    print(f"🔄 执行重启命令：{' '.join(restart_cmd)}")
    subprocess.Popen(restart_cmd, start_new_session=True)

    # 强制退出，跳过所有 Python 层面的清理
    os._exit(0)

# 加载环境变量
# 根据环境变量加载相应的 .env 文件
environment = os.getenv('MCP_ENV', 'development').lower()
env_file = f".env.{environment}"
logger.info(f"Loading environment file: {env_file}")
# 检查文件是否存在
if os.path.isfile(env_file):
    logger.info(f"Loading environment file: {env_file}")
    try:
        load_dotenv(env_file)
    except Exception as e:
        logger.error(f"Failed to load environment file {env_file}: {e}")
else:
    logger.warning(f"Environment file {env_file} does not exist.")

# 配置 OpenAI 兼容模式客户端
BASE_URL = os.getenv('BASE_URL')
API_KEY = os.getenv('API_KEY')
MODEL_NAME = os.getenv('MODEL_NAME')
MCP_SERVER_PATH = os.getenv('MCP_SERVER_PATH')
MCP_SERVER_DIR = os.getenv('MCP_SERVER_DIR')
CONTEXT_URL = os.getenv('CONTEXT_URL')
RESTART_HOT = os.getenv('RESTART_HOT','false').lower() == 'true'

client = AsyncClient(
    base_url=BASE_URL,
    api_key=API_KEY,
    timeout=600
)

# 引入微信通知器 而且必须放在环境变量引入之后
from utils.we_chat_notifier import  wechat_notifier

def jwt_required(func):
    """
    自定义 JWT 验证装饰器
    通过调用外部 CSN 服务验证 JWT token 的有效性
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 获取请求头中的 Authorization 字段
        authorization = request.headers.get("Authorization")
        language = request.headers.get("We-Lang")

        if not authorization:
            return ("Missing Authorization header", 401)

        try:
            # 从环境变量读取 CSN URL
            csn_url = os.getenv('CSN_URL')
            if not csn_url:
                logger.error("CSN_URL not configured in environment variables")
                return ("服务器配置错误，请联系管理员", 500)

            # 调用外部 CSN 服务验证 token
            headers = {'Authorization': authorization}
            response = requests.post(
                f'{csn_url}/v2/user-clinic-doctor/validate-doctor-token',
                json={},
                headers=headers,
                timeout=30
            )
            result = response.json()

            if result.get('code') != 10000:
                logger.error(f"CSN validation failed: {result.get('msg')}")
                return (result.get('msg', 'Token validation failed'), 401)

            # 验证成功，获取返回的用户信息
            user_info = result.get('resultObject', {})
            kwargs["user_info"] = user_info
            kwargs["authorization"] = authorization
            kwargs["we_lang"] = language
        except requests.exceptions.Timeout:
            logger.error("CSN service timeout")
            return ("用户系统繁忙，请稍后重试", 401)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to CSN service: {e}")
            return ("用户系统繁忙，请稍后重试", 401)
        except Exception as e:
            logger.error(f"JWT validation failed: {e}")
            return ("Invalid token", 401)

        # 调用原始函数
        return await func(*args, **kwargs)

    return wrapper


# 修改 MCPClient 类，添加新的连接方法
class MCPClient:
    def __init__(self, name: str = "default"):
        # 初始化会话和客户端对象
        self.exit_stack = AsyncExitStack()
        self.session = None
        self.stdio = None
        self.write = None
        self.messages = []
        self.available_tools = []
        self.system_prompt = PROMPT_MEDICAL_ASSISTANT
        self.session_messages = {}

        # 【新增】初始化关闭事件和任务引用
        self.name = name
        self.shutdown_event = asyncio.Event()
        self.connection_task = None
        self.is_connected = False

        # 初始化 Redis 连接，添加 username 和 password 参数
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST'),
            port=int(os.getenv('REDIS_PORT')),
            db=int(os.getenv('REDIS_DB')),
            username=os.getenv('REDIS_USERNAME'),
            password=os.getenv('REDIS_PASSWORD')
        )
        self.session_expiration = int(os.getenv('SESSION_EXPIRATION', 2592000))

    async def connect_to_server_with_config(self, server_config: dict):
        """根据配置连接到服务端并初始化工具"""
        mcp_server_app_path = os.path.join(MCP_SERVER_DIR, 'app.py')
        command = server_config.get("command")
        args = server_config.get("args") or [mcp_server_app_path]
        logger.info(f"mcp_server项目路径: {mcp_server_app_path}")
        env = server_config.get("env") or [MCP_SERVER_DIR]
        # 合并环境变量
        merged_env = dict(os.environ)
        merged_env.update(env)
        merged_env['MCP_ENV'] = os.getenv('MCP_ENV', 'development').lower()
        print(f"启动服务端: {command} {' '.join(args)}")

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=merged_env
        )

        try:
            # 关键点：整个连接生命周期必须在这个 async with 块内
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session
                    self.stdio = None
                    self.write = write

                    await session.initialize()
                    self.is_connected = True

                    # 列出工具（可选，如果需要立即获取工具列表）
                    try:
                        response = await session.list_tools()
                        tools = response.tools
                        print("\n已连接到服务器，支持以下工具:",
                              [tool.name for tool in tools])
                        self.available_tools = [{
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "input_schema": tool.inputSchema
                            }
                        } for tool in tools]
                        logger.info(f"已加载 {len(tools)} 个工具 for {self.name}")
                    except Exception as e:
                        logger.warning(f"Failed to list tools for {self.name}: {e}")

                    logger.info(f"MCP Client {self.name} connected and waiting for shutdown signal...")

                    # 【核心修复】无限等待，直到收到关闭信号或被任务取消
                    try:
                        while not self.shutdown_event.is_set():
                            try:
                                # 每秒检查一次，以便快速响应取消
                                await asyncio.wait_for(self.shutdown_event.wait(), timeout=1.0)
                            except asyncio.TimeoutError:
                                continue
                    except asyncio.CancelledError:
                        logger.info(f"MCP Client {self.name} received cancellation signal.")
                        raise  # 重新抛出，让 anyio 在同一个 Task 中执行 __aexit__

                    logger.info(f"Shutdown event set for {self.name}, closing connection...")

        except Exception as e:
            self.is_connected = False
            logger.error(f"Connection error for {self.name}: {e}")
            raise
        finally:
            self.is_connected = False
            logger.info(f"Connection fully closed for {self.name}")

    async def connect_to_server(self, server_script_path: str):
        """连接到服务端并初始化工具（兼容旧方法）"""
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("服务端脚本必须是 .py 或 .js 文件")

        command = "python" if is_python else "node"
        print(f"启动服务端脚本: {command} {server_script_path}")

        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env={
                'MCP_ENV': os.getenv('MCP_ENV', 'development').lower()
            }
        )
        try:
            # 启动 MCP 服务器并建立通信
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.stdio, self.write))

            await self.session.initialize()

            # 列出 MCP 服务器上的工具
            response = await self.session.list_tools()
            tools = response.tools
            print("\n已连接到服务器，支持以下工具:",
                  [tool.name for tool in tools])
            self.available_tools = [{
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
            } for tool in tools]
        except Exception as e:
            print(f"连接到服务器失败: {str(e)}")
            await self.cleanup()

    def context_to_str(self, context_info):
        if context_info is None:
            return ""
        if isinstance(context_info, list):
            return "\n".join(str(item) for item in context_info)
        return str(context_info)

    def _get_workflow_for_tool(self, tool_name: str) -> Optional[str]:
        """根据工具名获取对应的工作流"""
        workflow_mapping = {
            "check_order_by_case_code": "order_check",
            # "get_patients_by_name_and_phone": "patient_check"
            # 可以添加更多映射
        }
        return workflow_mapping.get(tool_name)

    async def process_query(self, query: str, session_id: str, authorization=None, we_lang="zh-CN") -> AsyncGenerator[
        str, None]:
        """
        使用大模型处理查询并调用可用的 MCP 工具 (Function Calling)
        支持多轮工具链调用：LLM -> Tool1 -> LLM -> Tool2 -> LLM -> Final Response
        """
        # 从 redis 中获取会话信息
        session_messages_str = self.redis_client.hget('session_messages', session_id)
        if session_messages_str is not None:
            try:
                session_messages = json.loads(session_messages_str)
            except json.JSONDecodeError as e:
                print(f"Failed to decode session messages from Redis: {str(e)}")
                session_messages = []
        else:
            session_messages = []

        messages = []
        if we_lang == "en-US":
            self.system_prompt = PROMPT_MEDICAL_ASSISTANT_EN
        else:
            self.system_prompt = PROMPT_MEDICAL_ASSISTANT
        messages.append({"role": "system", "content": self.system_prompt + "\n\n"})

        if session_messages:
            messages.extend(session_messages)

        # 在用户消息中明确语言偏好
        language_context = ""
        if we_lang and we_lang.lower().startswith('en'):
            language_context = "Please respond in English. "
        elif we_lang:
            language_context = "请用中文回复。"

        messages.append({"role": "user", "content": language_context + query})

        # 将新消息添加到会话消息列表
        session_messages.extend([
            {"role": "user", "content": query}
        ])
        self.redis_client.hset('session_messages', session_id, json.dumps(session_messages))
        # 过期时间一个月
        self.redis_client.expire('session_messages', self.session_expiration)  # 设置过期时间为 1 个月
        print(f'messages={messages}')

        # 最大工具调用轮次，防止无限循环
        max_tool_call_rounds = 6
        current_round = 0

        try:
            while current_round < max_tool_call_rounds:
                current_round += 1
                logger.info(f"=== Round {current_round} of tool calling ===")

                payload = {
                    "model": MODEL_NAME,
                    "messages": messages,
                    "tools": self.available_tools,
                    # "extra_body" : {"enable_thinking": False},
                    "extra_headers": {
                        "We-Lang": we_lang
                    } if we_lang else None,
                    "stream": False
                }

                @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
                async def call_with_retry():
                    return await client.chat.completions.create(**payload)

                try:
                    response = await call_with_retry()
                except RetryError as e:
                    original_error = e.last_attempt.exception()
                    print("原始错误:", original_error)
                    # 【新增】发送企业微信通知
                    try:
                        wechat_notifier.send_error_notification(
                            error_type="LLM API 调用失败",
                            error_message=str(original_error),
                            traceback_info=traceback.format_exc(),
                            context={
                                "session_id": session_id,
                                "query": query,  # 只取前 200 个字符
                                "we_lang": we_lang,
                                "round": current_round
                            },
                            level="error"
                        )
                    except Exception as notify_error:
                        logger.error(f"发送企业微信通知失败：{notify_error}")
                    raise

                content = response.choices[0]
                print(f'response choice={content}')


                # 如果没有工具调用，说明可以返回最终答案了
                if content.finish_reason != "tool_calls":
                    logger.info("No more tool calls needed, generating final response")
                    # 使用流式输出最终答案
                    assistant_response = content.message.content

                    try:
                        for char in assistant_response:
                            yield char
                        # 保存到会话历史
                        messages.append({"role": "assistant", "content": assistant_response})
                        session_messages.extend([
                            {"role": "assistant", "content": assistant_response}
                        ])
                        self.redis_client.hset('session_messages', session_id, json.dumps(session_messages))
                        self.redis_client.expire('session_messages', self.session_expiration)

                    except Exception as e:
                        logger.error(f"Error generating final response: {e}")
                        # 如果流式失败，降级到非流式
                        final_content = content.message.content
                        if final_content:
                            yield final_content

                        # 仍然保存会话历史
                        messages.append(content.message.model_dump())
                        session_messages.extend([
                            content.message.model_dump()
                        ])
                        self.redis_client.hset('session_messages', session_id, json.dumps(session_messages))
                        self.redis_client.expire('session_messages', self.session_expiration)

                    return  # 结束整个流程

                # 有工具调用，继续处理
                logger.info(f"Detected {len(content.message.tool_calls)} tool call(s)")

                # 获取所有工具调用
                tool_calls = content.message.tool_calls

                # 添加原始助手消息（包含工具调用）到消息列表
                messages.append({
                    "role": "assistant",
                    "content": content.message.content,
                    "tool_calls": [tc.model_dump() for tc in tool_calls]  # 确保包含工具调用信息
                })

                session_messages.append({
                    "role": "assistant",
                    "content": content.message.content,
                    "tool_calls": [tc.model_dump() for tc in tool_calls]  # 确保包含工具调用信息
                })

                # 处理所有工具调用
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    logger.info(f"正在处理工具调用：{tool_name}")
                    print(f"使用直接工具调用方式：{tool_name}")

                    from utils import common_functions
                    display_name = common_functions._get_friendly_name(tool_name, we_lang)
                    progress_msg = f"{display_name}..."
                    logger.info(f"[进度] {progress_msg}")
                    if we_lang == "zh-CN":
                        yield f"\n【处理中】{progress_msg}\n\n"
                    else:
                        yield f"\n【Processing】{progress_msg}\n\n"

                    tool_args_str = tool_call.function.arguments
                    try:
                        tool_args = json.loads(tool_args_str)
                    except json.JSONDecodeError as e:
                        print(f"Failed to decode tool arguments: {str(e)}")
                        print(f"Original arguments: {tool_args_str}")
                        messages.append({
                            "role": "assistant",
                            "content": f"解析工具参数时出错：{str(e)}"
                        })
                        yield f"解析工具参数时出错 / An error occurred while parsing the tool parameters.：{str(e)}"
                        return
                    # tool_args = json.loads(tool_call.function.arguments)

                    if authorization:
                        tool_args["authorization"] = authorization

                    if we_lang:
                        tool_args["we_lang"] = we_lang

                    try:
                        result = await self.session.call_tool(tool_name, tool_args)
                        print(
                            f"\n\n[Calling tool {tool_name} with args {tool_args}]\n\n with result {result}")
                        if result.isError:
                            error_message = result.content[0].text if result.content else "Unknown error"
                            print(f"Error calling tool {tool_name}: {error_message}")
                            # 提取对用户友好的错误信息，去掉技术细节
                            from utils import common_errors
                            user_friendly_error = common_errors._extract_user_friendly_error(self, error_message,we_lang)
                            # 【新增】发送工具调用错误通知
                            try:
                                print(f"=========================[进度] 发送工具调用错误通知")
                                wechat_notifier.send_error_notification(
                                    error_type=f"MCP 工具调用错误 - {tool_name}",
                                    error_message=error_message,
                                    context={
                                        "session_id": session_id,
                                        "tool_name": tool_name,
                                        "tool_args": json.dumps(tool_args, ensure_ascii=False),
                                        "msg": user_friendly_error
                                    },
                                    level="warning"
                                )
                            except Exception as notify_error:
                                logger.error(f"发送企业微信通知失败：{notify_error}")

                            # 在这种情况下，仍然需要添加工具响应消息
                            messages.append({
                                "role": "tool",
                                "content": f"Error calling tool {tool_name}: {error_message}",
                                "tool_call_id": tool_call.id
                            })
                            yield user_friendly_error
                            return
                    except Exception as e:
                        print(f"调用工具 {tool_name} 时出错：{str(e)}")
                        # 【新增】发送工具调用异常通知
                        try:
                            wechat_notifier.send_error_notification(
                                error_type=f"MCP 工具调用异常 - {tool_name}",
                                error_message=str(e),
                                traceback_info=traceback.format_exc(),
                                context={
                                    "session_id": session_id,
                                    "tool_name": tool_name,
                                    "query": query[:200]
                                },
                                level="error"
                            )
                        except Exception as notify_error:
                            logger.error(f"发送企业微信通知失败：{notify_error}")
                        messages.append({
                            "role": "tool",
                            "content": f"调用工具 {tool_name} 时出错：{str(e)}",
                            "tool_call_id": tool_call.id
                        })
                        yield f"系统异常，请稍后再试 / A system exception occurred. Please try again later."
                        return

                    # 处理工具调用结果，确保格式正确
                    tool_response_text = result.content[0].text if result.content else ""

                    # 确保添加到 messages 中的内容格式正确
                    messages.append({
                        "role": "tool",
                        "content": tool_response_text,
                        "tool_call_id": tool_call.id,
                    })

                    # 将新消息添加到会话消息列表
                    session_messages.append({
                        "role": "tool",
                        "content": tool_response_text,
                        "tool_call_id": tool_call.id,
                    })
                    self.redis_client.hset('session_messages', session_id, json.dumps(session_messages))
                    # 过期时间一个月
                    self.redis_client.expire('session_messages', self.session_expiration)  # 设置过期时间为 1 个月

                    # 实时反馈工具执行结果
                    from utils import common_functions
                    result_summary = common_functions._summarize_tool_result(tool_response_text, tool_name, we_lang)
                    if result_summary:
                        logger.info(f"[结果] {result_summary}")
                        if we_lang == "zh-CN":
                            yield f"\n【完成】{result_summary}\n\n"
                        else:
                            yield f"\n【Completed】{result_summary}\n\n"

                # 完成这一轮工具调用后，继续下一轮循环
                # 此时 messages 已经包含了所有工具调用的结果
                # LLM 会根据这些结果决定是否需要继续调用其他工具
                logger.info(f"Round {current_round} completed, preparing for next round...")


            # 如果达到最大轮次，说明可能存在循环依赖或其他问题
            if current_round >= max_tool_call_rounds:
                logger.warning(f"Reached maximum tool call rounds ({max_tool_call_rounds}), stopping...")
                yield "抱歉，处理您的请求时遇到了问题，工具调用次数过多，请稍后重试或联系管理员。/ Apologies, there was a problem processing your request due to excessive tool calls. Please retry later or contact the administrator. "

        except GeneratorExit:
            # 处理生成器提前退出的情况（热加载时会触发）
            logger.info("Generator exited early, cleaning up resources...")
            try:
                # 清理 Redis 连接
                if hasattr(self, 'redis_client') and self.redis_client:
                    self.redis_client.close()
            except Exception as cleanup_error:
                logger.warning(f"Cleanup error: {cleanup_error}")
            raise  # 重新抛出 GeneratorExit
        except Exception as e:
            logger.error(traceback.format_exc())
            # 【新增】发送未捕获异常通知
            try:
                wechat_notifier.send_error_notification(
                    error_type="process_query 未捕获异常",
                    error_message=str(e),
                    traceback_info=traceback.format_exc(),
                    context={
                        "session_id": session_id,
                        "query": query[:200],
                        "we_lang": we_lang
                    },
                    level="critical"
                )
            except Exception as notify_error:
                logger.error(f"发送企业微信通知失败：{notify_error}")
            yield f"Error: {str(e)}"


async def cleanup(self):
    """清理资源 - 通过触发事件和取消任务来优雅关闭"""
    logger.info(f"Triggering cleanup for MCP Client: {self.name}")

    # 1. 设置关闭事件，通知主循环退出
    self.shutdown_event.set()

    # 2. 如果任务还在运行，取消它
    # 这将导致 connect_to_server_with_config 中的 CancelledError 被触发
    # 进而触发 async with 块的 __aexit__，在正确的 Task 上下文中关闭资源
    if self.connection_task and not self.connection_task.done():
        logger.info(f"Cancelling connection task for {self.name}")
        self.connection_task.cancel()
        try:
            await self.connection_task
        except asyncio.CancelledError:
            pass  # 预期中的取消，忽略
        except Exception as e:
            logger.error(f"Error awaiting cancelled task for {self.name}: {e}")

    # 3. 重置状态
    self.is_connected = False
    self.session = None
    self.stdio = None
    self.write = None

    # 4. 关闭 Redis 连接
    try:
        if self.redis_client:
            self.redis_client.close()
    except Exception as e:
        logger.warning(f"Error closing Redis connection: {e}")

    logger.info(f"Cleanup completed for MCP Client: {self.name}")

class MCPClientManager:
    """管理多个MCP客户端实例"""

    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        self.server_configs: Dict[str, dict] = {}

    async def initialize_from_config(self, config_path: str = "servers_config.json"):
        """根据配置文件初始化所有启用的服务"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            mcp_servers = config.get("mcpServers", {})

            for service_name, service_config in mcp_servers.items():
                if service_config.get("enabled", False):
                    try:
                        await self.add_client(service_name, service_config)
                        logger.info(f"Successfully initialized service: {service_name}")
                    except Exception as e:
                        logger.error(f"Failed to initialize service {service_name}: {str(e)}")
                else:
                    logger.info(f"Service {service_name} is disabled, skipping...")
        except Exception as e:
            logger.error(f"Failed to load server config: {str(e)}")

    async def add_client(self, service_name: str, service_config: dict):
        """根据配置添加一个新的 MCP 客户端"""
        if service_name in self.clients:
            logger.info(f"Removing existing client {service_name} before adding new one")
            await self.remove_client(service_name)

        client = MCPClient(name=service_name)
        try:
            # 【关键修改】创建任务并保存引用
            task = asyncio.create_task(client.connect_to_server_with_config(service_config))
            client.connection_task = task

            # 不要在这里 await task，否则程序会卡住
            # 任务会在后台运行，直到被取消

            self.clients[service_name] = client
            self.server_configs[service_name] = copy.deepcopy(service_config)

            # 可选：等待一小段时间确认连接成功（非阻塞太久）
            # await asyncio.sleep(0.5)

            return True
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {service_name}: {str(e)}")
            # 如果启动失败，确保清理
            if client.connection_task and not client.connection_task.done():
                client.connection_task.cancel()
            await client.cleanup()
            return False

    def get_client(self, service_name: str) -> Optional[MCPClient]:
        """获取指定服务的客户端"""
        return self.clients.get(service_name)

    async def remove_client(self, service_name: str):
        """移除并清理指定的客户端"""
        if service_name in self.clients:
            await self.clients[service_name].cleanup()
            del self.clients[service_name]
        if service_name in self.server_configs:
            del self.server_configs[service_name]

    async def cleanup_all(self):
        """清理所有客户端"""
        # 先收集所有服务名称，避免在迭代时修改字典
        service_names = list(self.clients.keys())

        # 逐个清理客户端
        tasks = [self.remove_client(name) for name in service_names]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 确保清空所有数据结构
        self.clients.clear()
        self.server_configs.clear()


async def process_query_with_all_services(available_services: dict, query: str, session_id: str,
                                          authorization=None, we_lang="zh-CN") -> AsyncGenerator[
    str, None]:
    """
    使用所有可用服务处理查询
    """
    if not available_services:
        yield "错误: 没有可用的服务"
        return

    # 尝试每个服务，直到有一个成功或全部失败
    last_error = None
    for service_name, client_instance in available_services.items():
        try:
            has_content = False
            async for chunk in client_instance.process_query(query, session_id, authorization, we_lang):
                has_content = True
                yield chunk

            # 如果有内容输出，说明服务处理成功
            if has_content:
                return
        except Exception as e:
            last_error = f"Service {service_name} failed: {str(e)}"
            logger.error(last_error)
            # 继续尝试下一个服务
            continue

    # 如果所有服务都失败了
    error_msg = last_error or "错误: 所有服务都无法处理请求"
    yield error_msg


app = Quart(__name__)
app.config['RESPONSE_TIMEOUT'] = 1200  # 设置响应超时时间为 600 秒
app = cors(app, allow_origin="*")  # Enable CORS for all origins

# 使用管理器替代单个实例
mcp_client_manager = MCPClientManager()


@app.route('/')
async def index():
    return await render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Chat</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #chatbox { width: 400px; height: 300px; border: 1px solid #ccc; overflow-y: scroll; padding: 10px; margin-bottom: 10px; }
        #userInput { width: calc(400px - 22px); padding: 10px; }
        button { padding: 10px 15px; }
    </style>
</head>
<body>
    <h1>MCP Chat</h1>
    <div id="chatbox"></div>
    <input type="text" id="userInput" placeholder="Type your message here...">
    <button onclick="sendMessage()">Send</button>

    <script>
        const chatbox = document.getElementById('chatbox');
        const userInput = document.getElementById('userInput');

        function appendMessage(sender, message) {
            const msgElement = document.createElement('div');
            msgElement.textContent = `${sender}: ${message}`;
            chatbox.appendChild(msgElement);
            chatbox.scrollTop = chatbox.scrollHeight;
        }

        async function sendMessage() {
            const userMessage = userInput.value;
            if (!userMessage) return;

            appendMessage('You', userMessage);
            userInput.value = '';

            try {
                const response = await fetch('/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: userMessage })
                });
                console.log('Query response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const chunk = decoder.decode(value, { stream: true });

                    // 如果返回错误消息，停止接收并显示错误
                    if (chunk.includes("Task was cancelled")) {
                        appendMessage('Assistant', 'The task was cancelled.');
                        break;
                    }
                    appendMessage('Assistant', chunk);
                }
            } catch (error) {
                console.error('Error sending message:', error);
                appendMessage('Assistant', 'An error occurred.');
            }
        }
    </script>
</body>
</html>
''')


@app.route('/query', methods=['POST'])
@jwt_required
async def query(user_info=None, authorization=None, we_lang="zh-CN"):
    global mcp_client_manager
    data = await request.get_json()
    logger.debug(f"Received data: {data}")

    # 获取所有可用的服务实例
    available_services = {}
    for name in mcp_client_manager.clients.keys():
        client_instance = mcp_client_manager.get_client(name)
        if client_instance:
            available_services[name] = client_instance

    # 检查是否有可用服务
    if not available_services:
        return jsonify({"error": "No services connected"}), 400

    print("Query:")
    print(f"data: {data}")
    print(f"Available services: {list(available_services.keys())}")

    upload_files = data.get('upload_files')
    upload_files_str = ''
    if upload_files:
        upload_files_str = "\n上传文件的参数如下" + json.dumps(upload_files)
    model_files = data.get("model_files")
    model_files_str = ''
    if model_files:
        model_files_str = "\n模型文件的参数如下" + json.dumps(model_files)
    user_query = data.get('query') + upload_files_str + model_files_str
    if not user_query:
        return jsonify({"error": "query is required"}), 400

    session_id = data.get('session_id')
    if not session_id:
        session_id = uuid.uuid4().hex
    print(f"session_id: {session_id}")

    try:
        async def task_wrapper():
            try:
                async with asyncio.timeout(300):
                    # async for chunk in mcp_client_instance.process_query(user_query, session_id,
                    async for chunk in process_query_with_all_services(available_services, user_query, session_id,
                                                                       authorization=authorization, we_lang=we_lang):
                        sse_chunk = {"output": {"text": chunk, "finish_reason": "null", "session_id": session_id}}
                        logger.debug(sse_chunk)
                        yield f"data: {json.dumps(sse_chunk)}\n\n".encode('utf-8')
                sse_end_marker = f"data: {json.dumps({'output': {'text': '', 'session_id': session_id, 'finish_reason': 'stop'}})}\n\n".encode(
                    'utf-8')
                yield sse_end_marker
            except asyncio.CancelledError as cancel_err:
                current_task = asyncio.current_task()
                task_info = f"Task ID: {id(current_task)}, Task Name: {current_task.get_name()}" if current_task else "No task information"
                logger.warning(f"Task was cancelled: {cancel_err}. {task_info}")
                error_sse_chunk = {
                    "output": {"text": "Task was cancelled", "finish_reason": "cancelled", "session_id": session_id}}
                yield f"data: {json.dumps(error_sse_chunk)}\n\n".encode('utf-8')
                raise
            except asyncio.TimeoutError:
                logger.error("Task timed out after 300 seconds.")
                # 【新增】发送超时通知
                try:
                    wechat_notifier.send_error_notification(
                        error_type="请求超时",
                        error_message="Task timed out after 300 seconds",
                        context={
                            "session_id": session_id,
                            "user_query": user_query[:200]
                        },
                        level="warning"
                    )
                except Exception as notify_error:
                    logger.error(f"发送企业微信通知失败：{notify_error}")
                error_sse_chunk = {
                    "output": {"text": "Task timed out", "finish_reason": "timeout", "session_id": session_id}}
                yield f"data: {json.dumps(error_sse_chunk)}\n\n".encode('utf-8')
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                # 【新增】发送意外错误通知
                try:
                    wechat_notifier.send_error_notification(
                        error_type="任务执行异常",
                        error_message=str(e),
                        traceback_info=traceback.format_exc(),
                        context={
                            "session_id": session_id,
                            "user_query": user_query[:200]
                        },
                        level="error"
                    )
                except Exception as notify_error:
                    logger.error(f"发送企业微信通知失败：{notify_error}")
                error_sse_chunk = {"output": {"text": f"Unexpected error: {str(e)}", "finish_reason": "error",
                                              "session_id": session_id}}
                yield f"data: {json.dumps(error_sse_chunk)}\n\n".encode('utf-8')
            finally:
                logger.info('generate end')

        return app.response_class(task_wrapper(), mimetype='text/event-stream', headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'X-DashScope-SSE': 'enable'
        })
    except Exception as e:
        logger.error(str(e))
        # 【新增】发送路由级别异常通知
        try:
            wechat_notifier.send_error_notification(
                error_type="/query 路由异常",
                error_message=str(e),
                traceback_info=traceback.format_exc(),
                context={
                    "user_info": user_info if user_info else 'anonymous',
                    "we_lang": we_lang
                },
                level="critical"
            )
        except Exception as notify_error:
            logger.error(f"发送企业微信通知失败：{notify_error}")
        return jsonify({"error": str(e)}), 500


@app.route('/services', methods=['GET'])
async def list_services():
    """列出所有可用的服务"""
    global mcp_client_manager
    services = list(mcp_client_manager.clients.keys())
    configs = {}
    for name, config in mcp_client_manager.server_configs.items():
        configs[name] = {
            "description": config.get("description", ""),
            "command": config.get("command"),
            "args": config.get("args", [])
        }
    return jsonify({"services": services, "configs": configs})


@app.route('/services/<service_name>', methods=['POST'])
async def add_service(service_name: str):
    """添加新服务"""
    global mcp_client_manager
    data = await request.get_json()
    service_config = data.get('service_config')

    if not service_config:
        return jsonify({"error": "service_config is required"}), 400

    success = await mcp_client_manager.add_client(service_name, service_config)
    if success:
        return jsonify({"status": f"Service {service_name} added successfully"}), 200
    else:
        return jsonify({"error": f"Failed to add service {service_name}"}), 500


@app.route('/services/<service_name>', methods=['DELETE'])
async def remove_service(service_name: str):
    """移除服务"""
    global mcp_client_manager
    await mcp_client_manager.remove_client(service_name)
    return jsonify({"status": f"Service {service_name} removed"}), 200


@app.route('/cleanup', methods=['POST'])
async def cleanup():
    """清理所有服务"""
    global mcp_client_manager
    if not mcp_client_manager.clients:
        return jsonify({"error": "No active connections"}), 400
    try:
        await mcp_client_manager.cleanup_all()
        return jsonify({"status": "All services cleaned up"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.before_serving
async def startup_event():
    """应用启动时根据配置文件初始化所有启用的服务"""
    global mcp_client_manager
    await mcp_client_manager.initialize_from_config()


@app.after_serving
async def cleanup_event():
    """应用关闭时清理所有资源"""
    global mcp_client_manager
    await mcp_client_manager.cleanup_all()


if __name__ == "__main__":
    # 创建 ArgumentParser 对象
    parser = argparse.ArgumentParser(description='Start the Flask application with a specified port.')

    # 添加命令行参数
    parser.add_argument('--port', type=int, default=5000, help='Port number to run the Flask application on')
    parser.add_argument('--config', type=str, default='servers_config.json',
                        help='Path to the servers configuration file')

    # 解析命令行参数
    args = parser.parse_args()

    # 获取传入的端口号
    port = args.port
    config_path = args.config
    print(f"Using port: {RESTART_HOT}")

    # 启动热加载监听器
    if MCP_SERVER_DIR and RESTART_HOT:
        mcp_watcher = start_watching_mcp_file(MCP_SERVER_DIR, restart_program, config_path)
    else:
        print("MCP_SERVER_DIR not set, file watching disabled")
        mcp_watcher = None

    try:
        # 打印启动信息
        print(f"Starting server on port {port}")
        print(f"Using config file: {config_path}")
        # 启动应用
        app.run(debug=True, use_reloader=RESTART_HOT, host='0.0.0.0', port=port)
    except KeyboardInterrupt:
        print("Shutting down...")
        if mcp_watcher:
            print("Shutting down watcher...")
            mcp_watcher.stop()
            mcp_watcher.join()