# MCP Agents Client v2

这是一个面向学习和生产演进的 Agent 客户端。

**目标不是把代码写得“高级”，而是让你能顺着源码读懂一次 Agent 请求到底发生了什么。**

## 目录结构

```text
mcp-clients-v2/
├── agent/                 # LangGraph Agent 核心：状态、循环、Workflow
├── mcp/                   # MCP Transport + Tool Adapter
├── api/                   # HTTP /query + SSE 薄适配层
├── config/servers_config.json # 本地 STDIO MCP Server 启动配置
├── tests/                 # Workflow 与 MCP 本地配置测试
├── config.py              # LLM / MCP / checkpoint 配置
└── main.py                # 最小 CLI 启动入口
```

## 核心架构

```text
前端 /query
   │  text + image_list + authorization
   ▼
AgentService
   ▼
LangGraph
   ├── LLM：理解自然语言、选择工具
   ├── Workflow Rules：确定业务流程约束
   ├── State / Checkpoint：保存多轮执行状态
   └── MCP Client：通过 STDIO 动态发现真实 Tool Schema
            │
            │ stdin / stdout
            ▼
       MCP Server 子进程
            │
            ▼
         业务 API
```

**重要：本项目沿用原客户端的 STDIO MCP 通信方式。** Client 启动后读取 `config/servers_config.json`，自动拉起 `mcp-servers/app.py` 子进程，然后通过 stdin/stdout 建立 MCP Session。`graph.py` 不负责 Transport，只负责 Agent 状态和 LLM/Tool 循环。

因此本地开发时**不需要手工再启动一个 MCP Server 终端**。

## MCP Server 配置

默认配置：

```text
mcp-clients-v2/config/servers_config.json
```

当前默认 Server：

```text
command: python3.11
args:    ../mcp-servers/app.py
transport: STDIO
```

这里没有 `MCP_SERVER_URL` 一类的 HTTP 地址，因为 Client 与 MCP Server 使用 STDIO；Server 内部调用企业业务 API 所需要的地址/鉴权仍通过 Server 自己的环境变量提供。

`MCPToolClient` 会合并父进程环境变量，并解析配置中的本地 `PYTHONPATH` / 脚本相对路径，所以从仓库根目录或 `mcp-clients-v2` 目录启动都可以。

## 病例创建流程

```text
患者基本信息
      ↓
主诉
      ↓
查询患者
      ↓
找到？
 ┌────┴────┐
 是        否
 ↓         ↓
明确选择   明确选择新建
 ↓
创建病例
```

不会因为 LLM 自己猜测患者不存在就跳过查询；患者查询结果必须来自真实 MCP Tool。

## 订单创建流程

```text
订单检查
  ↓
产品
  ↓
设计相关决策
  ↓
诊断：必须询问，可跳过
  ↓
影像：必须询问，可跳过
  ↓
模型：必须询问，可跳过
  ↓
需要设计？ ── 是 ──→ 完全跳过处方
  │
  否
  ↓
处方：必须询问，可跳过
  ↓
创建订单
```

特别规则：**需要设计时完全跳过处方；不需要设计时才进入处方流程。**

## 图片流程

前端原来的图片入口仍然保留：

```text
/query
  └── image_list
        ↓
AgentState.attachments
        ↓
image_process
        ↓
影像识别结果
```

订单创建过程中可以提供影像；订单创建完成后也可以独立执行影像补充/更新。影像更新工具执行前必须先有影像处理成功结果。

## 本地运行

### 1. 准备 Python

建议 Python 3.11：

```bash
cd mcpagents/mcp-clients-v2
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 LLM

至少需要：

```bash
export BASE_URL="你的 OpenAI-compatible Base URL"
export API_KEY="你的 API Key"
export MODEL_NAME="你的模型名"
```

如需覆盖 MCP 配置：

```bash
export MCP_CONFIG="config/servers_config.json"
```

### 3. 先跑测试

```bash
pytest -q tests
```

### 4. 启动 Agent CLI

```bash
python main.py
```

启动链路：

```text
python main.py
   ↓
Settings
   ↓
MCPToolClient.connect()
   ↓
读取 config/servers_config.json
   ↓
自动启动 ../mcp-servers/app.py
   ↓
STDIO ClientSession
   ↓
list_tools()
   ↓
MCP inputSchema → LangChain StructuredTool
   ↓
AgentService
   ↓
LangGraph
```

退出输入：

```text
quit
```

### 5. HTTP /query

HTTP 层仍保留 `/query` 兼容入口，支持原客户端的 `query + image_list + authorization`，同时支持新版 `message + attachments`。

## 测试

```bash
pytest -q tests
```

重点覆盖：病例创建前置条件、患者查询与决策门禁、订单分支规则、图片处理前置条件、MCP Result envelope、STDIO MCP 配置和本地 Server 路径。

## 重要设计原则

1. **MCP Server = 能力**：只执行明确的业务动作，不负责多轮 Agent 流程。
2. **LLM = 理解**：负责自然语言理解、参数提取和工具选择，但不能凭猜测制造业务事实。
3. **LangGraph = 状态与循环**：负责 Agent 执行过程、checkpoint、interrupt 和工具循环。
4. **Workflow Rules = 确定性业务约束**：决定什么时候允许进入下一阶段。
5. **MCP Client = Transport + Tool Adapter**：负责 STDIO 生命周期、Tool discovery 和 Schema 适配。
6. **Tool Result 才能产生业务事实**：失败结果不能推进流程。
7. **代码优先可读性**：关键逻辑都有中文注释，不为了“高级”引入不必要抽象。
