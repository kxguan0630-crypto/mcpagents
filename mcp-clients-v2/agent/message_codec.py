"""LangChain Message 的序列化工具。

Redis 只能保存字符串/bytes，所以不能直接 json.dumps(HumanMessage)。
这个文件只解决一个问题：

    Message 对象 <-> JSON 可保存的数据

把序列化细节集中起来，RedisCheckpoint 就能保持非常简单。
"""

from typing import Any

from langchain_core.messages import messages_from_dict, messages_to_dict


def messages_to_json_data(messages: list[Any]) -> list[dict[str, Any]]:
    """把 LangChain Message 转成普通 dict 列表。"""
    return messages_to_dict(messages)


def messages_from_json_data(data: list[dict[str, Any]]) -> list[Any]:
    """把 dict 列表恢复成 LangChain Message 对象。"""
    return messages_from_dict(data)
