# MCP 层

这一层只解决一个问题：**如何把 MCP Server 提供的工具接进 Agent。**

不要在这里写病例、患者、订单等业务判断。

未来如果从 stdio 改成 SSE/Streamable HTTP，只改这里，不改 Agent 图。
