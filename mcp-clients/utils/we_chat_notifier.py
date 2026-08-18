# utils/we_chat_notifier.py

import requests
import logging
from typing import Optional, List
import os
import json
from datetime import datetime

logger = logging.getLogger("SERVER_LOGGER")


class WeChatNotifier:
    """企业微信消息通知器"""

    def __init__(self):
        # 从环境变量读取配置
        self.token = os.getenv('WECHAT_TOKEN')
        self.platform = os.getenv('WECHAT_PLATFORM', '未指定平台')
        self.enabled_config = os.getenv('WECHAT_ENABLED', 'false').lower() == 'true'

        # 根据 token 自动生成 webhook URL（如果提供了 token）
        if self.token:
            self.webhook_url = f'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={self.token}'
            self.enabled = self.enabled_config
            logger.info(f"企业微信通知器已初始化 - 平台：{self.platform}, Token: {self.token[:8]}...***")
        else:
            self.webhook_url = None
            self.enabled = False
            logger.warning("企业微信 Webhook 未配置，通知功能已禁用")

    def send_text_message(self, content: str, mentioned_list: Optional[List[str]] = None):
        """
        发送文本消息

        Args:
            content: 消息内容
            mentioned_list: 需要@的成员列表，["all"] 表示所有人
        """
        if not self.enabled:
            return False

        try:
            data = {
                "msgtype": "text",
                "text": {
                    "content": content,
                    "mentioned_list": mentioned_list or []
                }
            }

            response = requests.post(
                self.webhook_url,
                json=data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )

            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"企业微信消息发送成功")
                return True
            else:
                logger.error(f"企业微信消息发送失败：{result}")
                return False

        except Exception as e:
            logger.error(f"发送企业微信消息时出错：{e}")
            return False

    def send_markdown_message(self, content: str, mentioned_list: Optional[List[str]] = None):
        """
        发送 Markdown 消息

        Args:
            content: Markdown 格式的消息内容
            mentioned_list: 需要@的成员列表，["all"] 表示所有人
        """
        if not self.enabled:
            return False

        try:
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }

            if mentioned_list:
                data["markdown"]["mentioned_list"] = mentioned_list

            response = requests.post(
                self.webhook_url,
                json=data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )

            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"企业微信 Markdown 消息发送成功")
                return True
            else:
                logger.error(f"企业微信 Markdown 消息发送失败：{result}")
                return False

        except Exception as e:
            logger.error(f"发送企业微信 Markdown 消息时出错：{e}")
            return False

    def send_error_notification(
            self,
            error_type: str,
            error_message: str,
            traceback_info: Optional[str] = None,
            context: Optional[dict] = None,
            level: str = "error"
    ):
        """
        发送错误通知消息（Markdown 格式）

        Args:
            error_type: 错误类型
            error_message: 错误消息
            traceback_info: 堆栈信息
            context: 上下文信息（如 session_id, user_info 等）
            level: 错误级别 (error/warning/critical)
        """
        if not self.enabled:
            return False

        # 构建 Markdown 消息
        emoji_map = {
            "error": "❌",
            "warning": "⚠️",
            "critical": "🔥"
        }
        emoji = emoji_map.get(level, "❌")

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        markdown_content = f"""{emoji} **系统异常通知**

> **错误类型**: {error_type}
> **错误级别**: {level.upper()}
> **发生时间**: {timestamp}
> **平台**: {self.platform}

**错误详情**:
"""

        # 添加错误消息
        markdown_content += f"\n"

        # 添加上下文信息
        if context:
            markdown_content += "\n**上下文信息**:\n"
            for key, value in context.items():
                if isinstance(value, dict):
                    value = json.dumps(value, ensure_ascii=False, indent=2)
                markdown_content += f"> - **{key}**: `{value}`\n"

        # 添加堆栈信息（如果有）
        if traceback_info:
            # 截取前 1000 个字符，避免消息过长
            stack_trace = traceback_info[:1000] + "..." if len(traceback_info) > 1000 else traceback_info
            markdown_content += f"\n**堆栈跟踪**:\n"

        # 根据级别决定是否@所有人
        mentioned_list = ["all"] if level == "critical" else []

        return self.send_markdown_message(markdown_content, mentioned_list)


# 创建全局单例
wechat_notifier = WeChatNotifier()
