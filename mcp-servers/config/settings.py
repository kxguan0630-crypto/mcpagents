# config/settings.py
import os
from dotenv import load_dotenv


# 根据环境加载不同的.env文件
environment = os.getenv('MCP_ENV', 'development').lower()
env_file = f".env.{environment}"

if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    load_dotenv()  # 加载默认.env文件


class Settings:
    # API配置
    API_BASE_URL: str = os.getenv('API_BASE_URL', 'http://localhost/orth')
    REQUEST_TIMEOUT: int = int(os.getenv('REQUEST_TIMEOUT', '300'))

    # 日志配置
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'DEBUG')
    LOG_FILE_PATH: str = os.getenv('MCP_SERVER_LOG_PATH', '')

    # 其他配置
    IMAGE_PROCESS_URL: str = os.getenv('IMAGE_PROCESS_URL', 'https://pbmaintenancetool.utcnc.cn:50012/process')


settings = Settings()
