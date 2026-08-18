# models/validators.py
"""
通用验证装饰器和语言支持模块
Common Validation Decorators and Language Support Module

提供用于 MCP 工具参数验证的通用装饰器和多语言支持
Provides common decorators and multilingual support for MCP tool parameter validation
"""
from functools import wraps
import json
import logging
from typing import Type, Callable
from pydantic import BaseModel
from contextvars import ContextVar

# ==================== 语言支持 ====================
# ==================== Language Support ====================

# 语言上下文变量 | Language context variable
_current_language: ContextVar[str] = ContextVar('current_language', default='zh-CN')


def set_current_language(lang: str = "zh-CN"):
    """
    设置当前语言上下文
    Set current language context

    Args:
        lang: 语言代码 | Language code (e.g., 'zh-CN', 'en-US')
    """
    _current_language.set(lang)


def get_current_language() -> str:
    """获取当前语言 | Get current language"""
    return _current_language.get()


def _(zh: str, en: str) -> str:
    """
    国际化翻译函数 | Internationalization function
    根据当前语言返回对应的文本 | Return text based on current language

    Args:
        zh: 中文文本 | Chinese text
        en: 英文文本 | English text

    Returns:
        对应语言的文本 | Text in current language
    """
    return zh if get_current_language() == "zh-CN" else en


# ==================== 验证装饰器 ====================
# ==================== Validation Decorators ====================

def with_model_validation(model_class: Type[BaseModel], param_name: str) -> Callable:
    """
    通用的模型验证装饰器 | Common model validation decorator

    用于自动验证和转换 MCP 工具参数为 Pydantic 模型
    Automatically validate and convert MCP tool parameters to Pydantic models

    功能 | Features:
    - 自动将 dict 参数转换为指定的 Pydantic 模型实例
      Automatically convert dict parameters to specified Pydantic model instances
    - 处理语言设置 | Handle language settings
    - 统一的错误响应格式 | Unified error response format

    Args:
        model_class: 要验证的 Pydantic 模型类 | Pydantic model class to validate
        param_name: 需要验证的参数名 | Parameter name to validate

    Returns:
        装饰器函数 | Decorator function

    Example:
        @with_model_validation(CheckInfoTemplate, 'check_info')
        async def save_check_info(check_info: dict, ...):
            # check_info 已自动转换为 CheckInfoTemplate 实例
            # check_info is automatically converted to CheckInfoTemplate instance
            pass

    Note:
        该装饰器会：
        The decorator will:
        1. 从 kwargs 获取 we_lang 参数并设置语言上下文
           Get we_lang parameter from kwargs and set language context
        2. 将 param_name 对应的参数转换为 model_class 实例
           Convert parameter to model_class instance
        3. 验证失败时返回统一的 JSON 错误响应
           Return unified JSON error response on validation failure
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            we_lang = kwargs.get('we_lang', 'zh-CN')
            set_current_language(we_lang)

            if param_name in kwargs:
                data = kwargs[param_name]
                if data:
                    try:
                        kwargs[param_name] = model_class(**data)
                    except Exception as e:
                        return json.dumps({
                            "message": _(
                                f"{model_class.__name__} 验证失败",
                                f"{model_class.__name__} validation failed"
                            ),
                            "details": str(e),
                            "code": 30000
                        })
                else:
                    kwargs[param_name] = None
            return await func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    'with_model_validation',
    'set_current_language',
    'get_current_language',
    '_'
]
