# server 项目的 utils/log.py 或直接在 main.py 入口
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

environment = os.getenv('MCP_ENV', 'development').lower()
env_file = f".env.{environment}"
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '..', "{env_file}")
load_dotenv(dotenv_path=env_path)
RUNTIME_PATH = os.getenv('RUNTIME_PATH')


class DailyLogHandler(logging.Handler):
    """
    一个自定义的日志处理器，能够根据日期动态切换日志文件。
    即使程序长时间运行不重启，也能在跨天时自动创建新文件。
    """

    def __init__(self, base_runtime_path):
        super().__init__()
        self.base_runtime_path = base_runtime_path
        self.current_date_str = None
        self.current_file_handler = None

    def emit(self, record):
        try:
            # 1. 获取当前日期字符串，例如 '2026-04-22'
            date_str = datetime.now().strftime('%Y-%m-%d')

            # 2. 检查日期是否变化（首次运行或跨天）
            if self.current_date_str != date_str:
                # 日期变了，需要关闭旧的文件处理器
                if self.current_file_handler:
                    self.current_file_handler.close()
                    # 从当前 logger 中移除旧的 handler，避免重复
                    # 注意：这里不需要显式移除，因为我们每次都只通过 self.current_file_handler 写入

                # 3. 构建新的目录和文件路径
                # 将 '2026-04-22' 分割成年、月、日
                year, month, day = date_str.split('-')
                date_dir = os.path.join(self.base_runtime_path, year, month, day)

                # 确保新目录存在
                os.makedirs(date_dir, exist_ok=True)

                log_file_path = os.path.join(date_dir, "client.log")

                # 4. 创建新的文件处理器
                self.current_file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
                # 将之前设置好的 formatter 赋给新的 handler
                self.current_file_handler.setFormatter(self.formatter)

                # 更新当前日期标记
                self.current_date_str = date_str

                print(f"✅ 日志已切换到: {log_file_path}")

            # 5. 使用正确的文件处理器来写入日志
            if self.current_file_handler:
                self.current_file_handler.emit(record)
        except Exception as e:
            # 4. 异常处理：防止日志系统崩溃影响主程序
            self.handleError(record)
            print(f"❌ 日志写入错误: {e}")

def setup_logging():
    # ✅ 1. 清除 root logger 的所有 handlers
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # ✅ 2. 设置 root logger level 为 NOTSET，避免干扰
    root_logger.setLevel(logging.NOTSET)

    # ✅ 3. 创建一个独立的 logger（不要用 root 或 __name__）
    logger = logging.getLogger("SERVER_LOGGER")
    logger.setLevel(logging.DEBUG)

    # ✅ 4. 确保没有重复 handlers
    if logger.handlers:
        logger.handlers.clear()

    # ✅ 5. 设置 propagate = False，防止日志“泄露”到 root logger
    logger.propagate = False
    # 1. 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 路径设置
    runtime_dir = RUNTIME_PATH or os.path.join(project_root, "runtime")
    print(f"最终使用的 RUNTIME_PATH: {RUNTIME_PATH}")


    # 4. 【核心修改】使用我们自定义的 DailyLogHandler
    handler = DailyLogHandler(runtime_dir)
    # 2. 获取当前日期，构建年/月/日目录
    # now = datetime.now()
    # date_dir = os.path.join(
    #     runtime_dir,
    #     now.strftime("%Y"),  # 年：2025
    #     now.strftime("%m"),  # 月：08
    #     now.strftime("%d")  # 日：06
    # )
    # # 3. 确保多级目录存在
    # os.makedirs(date_dir, exist_ok=True)
    # # 4. 日志文件路径
    # log_file = os.path.join(date_dir, "client.log")
    #
    # # ✅ 7. 手动添加 FileHandler
    # handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger