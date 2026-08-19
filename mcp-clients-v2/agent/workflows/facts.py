"""把用户已经明确做出的流程决定记录到 AgentState。

这些不是 MCP 业务工具，而是 Agent 内部的小工具。
它们不访问后端，只负责把“用户说了什么决定”变成结构化状态。

为什么需要它？

LLM 的自然语言消息不能直接作为可靠的业务状态。订单创建要求每次明确询问
诊断、影像、模型，以及根据 need_design 决定是否询问处方，所以这些决定都必须
进入 business_facts，而不能只存在于一次 LLM 的 tool call 参数里。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Decision =