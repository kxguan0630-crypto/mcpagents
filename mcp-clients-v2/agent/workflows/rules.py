"""确定性的业务流程规则。

LangGraph 负责“怎么跑”，本文件负责“什么情况下允许继续”。

重要原则：
- LLM 可以理解用户表达，但不能凭猜测制造业务事实。
- MCP Tool 成功返回才可以产生工具事实。
- 用户的“提供/不提供/选择新患者”等决策必须进入 AgentState 后，才能作为流程事实。
- 本文件不执行 MCP Tool，也不创建第二套 Workflow Engine。
"""

from __future__ import annotations

import json
from typing import Any


# 用户在交互阶段明确表达后，Workflow 应保存