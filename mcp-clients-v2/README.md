# MCP Agents Client v2

这是一个面向学习和生产演进的 Agent 客户端。

**目标不是把代码写得“高级”，而是让你能顺着源码读懂一次 Agent 请求到底发生了什么。**

## 目录结构

```text
mcp-clients-v2/
├── agent/
│   ├── state.py                    # 唯一运行状态；business_facts 是业务事实来源
│   ├── graph.py                    # LLM -> Tool -> LLM 核心循环
│   ├── workflows/
│   │   ├── facts.py                # 记录用户明确决定的内部工具
│   │   ├── case_creation.py         # 病例创建阶段顺序
│   │   ├── order_creation.py        # 订单创建阶段顺序
│   │   └── rules.py                # Tool 前置条件和结果转事实规则
│   ├── service.py                   # Agent 应用层入口
│   └── ...                          # checkpoint / approval / observability
├── mcp/
│   └── client.py                    # MCP 连接、动态 Tool 发现、真实 inputSchema
├── api/
│   ├── schemas.py                  # /query 兼容参数、附件、Authorization
│   └── app.py                      # FastAPI + SSE 薄适配层
├── tests/
│   └── test_workflow_rules.py       # 核心业务不变量测试
├── config.py
└── main.py
```

## 核心架构

```text
前端 /query
   │  text + image_list + authorization
   ▼
AgentService
   │
   ▼
LangGraph
   │
   ├── LLM：理解自然语言、选择工具
   │
   ├── Workflow Rules：确定当前最小缺口
   │
   ├── business_facts：唯一业务事实来源
   │
   └── MCP Client：动态发现真实 Tool Schema
   │
   ▼
MCP Server
   │
   ▼
业务 API
```

## 病例创建流程

```text
患者基本信息
      ↓
主诉
      ↓
get_patients_by_name_and_phone
      ↓
找到？
 ┌────┴────┐
 是        否
 ↓         ↓
明确选择   明确选择新建
 ↓
case_add
```

**不会因为 LLM 觉得“应该不存在患者”就跳过查询。** `patient_checked` 必须由真实 Tool 成功结果产生。

## 订单创建流程

```text
订单检查
  ↓
产品
  ↓
need_design
  ↓
诊断：必须询问，可跳过
  ↓
影像：必须询问，可跳过
  ↓
模型：必须询问，可跳过
  ↓
need_design == 1 ? ── 是 ──→ 跳过处方
  │
  否
  ↓
处方：必须询问，可跳过
  ↓
case_order_add
```

特别规则：**`need_design=1` 完全跳过处方；只有 `need_design=0` 才进入处方流程。**

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

订单创建过程中可以提供影像；订单创建完成后也可以独立执行影像补充/更新。`save_case_face` 在执行前必须先有 `image_process` 成功事实。

`image_process` 的真实 MCP `inputSchema` 会动态传给 LangChain，Client 不再用 `**kwargs` 丢失工具参数定义。

## 运行

```bash
cd mcp-clients-v2
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 配置 .env 中的 LLM 和 MCP 配置后
python main.py
```

HTTP 服务使用项目现有 API 启动方式；`main.py` 是最简单的 CLI 入口，方便先理解 Agent Core。

## 测试

```bash
cd mcp-clients-v2
pytest -q tests/test_workflow_rules.py
```

这些测试不连接真实 LLM/MCP Server，重点验证流程门禁、need_design 分支、患者决策和 MCP Result envelope。

## 重要设计原则

1. **MCP Server = 能力**：只执行明确的业务动作，不负责多轮 Agent 流程。
2. **LLM = 理解**：负责自然语言理解、参数提取和工具选择，但不能凭猜测制造业务事实。
3. **LangGraph = 状态与循环**：负责 Agent 执行过程、checkpoint、interrupt 和工具循环。
4. **Workflow Rules = 确定性业务约束**：决定什么时候允许进入下一阶段。
5. **business_facts = 唯一业务事实来源**：避免 State 与 Facts 双份状态产生冲突。
6. **Tool Result 才能产生 Tool Fact**：失败结果不能推进流程。
7. **代码优先可读性**：关键逻辑都有中文注释，不为了“高级”引入不必要抽象。
