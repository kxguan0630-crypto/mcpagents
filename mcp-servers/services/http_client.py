# services/http_client.py
import httpx
import json
from typing import Dict, Any, Optional
# from utils.logger import logger
from config.settings import settings
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional
import logging
logger = logging.getLogger("SERVER_LOGGER")

T = TypeVar("T")

@dataclass
class APIResponse(Generic[T]):
    """统一API响应格式"""
    success: bool
    data: Optional[T] = None
    error_code: Optional[int] = None
    error_messsage: Optional[str] = None
    http_status: Optional[int] = None

class HTTPClient:
    """HTTP客户端封装"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=float(settings.REQUEST_TIMEOUT))

    async def post(
            self,
            url: str,
            json_data: Optional[Dict] = None,
            headers: Optional[Dict[str, str]] = None
    ) -> APIResponse[Dict[str, Any]]:
        """
        发送POST请求

        Args:
            url: 请求URL
            json_data: JSON数据
            headers: 请求头

        Returns:
            响应数据或None
        """
        try:
            logger.debug(f"发送请求到: {url}")
            if json_data:
                logger.debug(f"请求数据: {json.dumps(json_data, ensure_ascii=False, indent=2)}")

            response = await self.client.post(
                url,
                json=json_data,
                headers=headers
            )
            response.raise_for_status()

            result = response.json()
            logger.debug(f"响应数据: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return result
        except httpx.RequestError as e:
            logger.error(f"请求错误: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP状态错误: {e}")
            return None
        except Exception as e:
            logger.error(f"未知错误: {e}")
            return None
    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()


# 全局HTTP客户端实例
http_client = HTTPClient()
