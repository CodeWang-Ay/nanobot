# 工具注册与调用流程

> 核心类: `ToolRegistry` / `Tool` / `Schema`
> 文件路径: `nanobot/agent/tools/registry.py` → `base.py` → `schema.py`

## 1. 工具注册时机 (AgentLoop 启动时)

```
┌────────────────────────────────────────────────────────────────────┐
│  AgentLoop.__init__()                                              │
│     self.tools = ToolRegistry()         # 创建注册表                 │
│     self._register_default_tools()      # 注册内置工具               │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│  _register_default_tools()                                         │
│     self.tools.register(ReadFileTool(...))                         │
│     self.tools.register(WriteFileTool(...))                        │
│     self.tools.register(ExecTool(...))                             │
│     self.tools.register(PriceHistoryTool(...))                     │
│     ...                                                            │
│                                                                    │
│  ToolRegistry._tools = {                                           │
│     "read_file": ReadFileTool 实例,                                │
│     "write_file": WriteFileTool 实例,                              │
│     "shell_exec": ExecTool 实例,                                   │
│     "price_history": PriceHistoryTool 实例,                        │
│  }                                                                 │
└────────────────────────────────────────────────────────────────────┘
```

## 2. 工具定义加载时机 (LLM 请求前)

```
┌────────────────────────────────────────────────────────────────────┐
│  AgentRunner.run()                                                 │
│     await self._request_model()                                    │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│  _request_model()                                                  │
│     tools = self.tools.get_definitions()                           │
│     await provider.chat(messages, tools=tools)                     │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│  ToolRegistry.get_definitions()                                    │
│     definitions = [tool.to_schema() for tool in self._tools]       │
│     return definitions                                             │
│                                                                    │
│  返回格式 (OpenAI Function Calling 兼容):                          │
│  [                                                                 │
│    {"type": "function",                                            │
│     "function": {                                                  │
│       "name": "price_history",                                     │
│       "description": "查询物料历史价格...",                         │
│       "parameters": {                                              │
│         "type": "object",                                          │
│         "properties": {"material_id": {...}},                      │
│         "required": ["material_id"]                                │
│       }                                                            │
│    }}                                                              │
│  ]                                                                 │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│  Tool.to_schema()                                                  │
│     return {                                                       │
│       "type": "function",                                          │
│       "function": {                                                │
│         "name": self.name,                                         │
│         "description": self.description,                           │
│         "parameters": self.parameters,  # 来自装饰器注入           │
│       }                                                            │
│     }                                                              │
└────────────────────────────────────────────────────────────────────┘
```

## 3. 工具调用流程 (LLM 返回 tool_call)

```
┌────────────────────────────────────────────────────────────────────┐
│  LLM 返回: tool_call = {"name": "price_history",                   │
│                         "arguments": {"material_id": "ABC123"}}    │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│  AgentRunner.run()                                                 │
│     ├─ await self._execute_tools(tool_calls)                       │
│     │      └─ await self._run_tool(tool_call)                      │
│     │             ├─ prepare_call = spec.tools.prepare_call        │
│     │             ├─ tool, params, error = prepare_call(...)       │
│     │             │                                                 │
│     │             ├─ if tool:  # 主路径 (99%情况)                   │
│     │             │      await tool.execute(**params)              │
│     │             │                                                 │
│     │             └─ else:    # 备用路径 (tool为None时)             │
│     │                    await spec.tools.execute(name, params)    │
│     │                        └─ prepare_call() + tool.execute()    │
│     └─ 返回 tool 执行结果                                           │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│  ToolRegistry.prepare_call(name, params)  [runner.py直接调用]      │
│     ├─ tool = self._tools.get(name)        # 查找工具实例          │
│     ├─ cast_params = tool.cast_params(params)  # 类型转换          │
│     │    "123" → 123 (string → int)                                │
│     ├─ errors = tool.validate_params(cast_params)  # Schema校验   │
│     │    检查: required / minLength / minimum / enum 等            │
│     └─ return (tool, cast_params, error)                           │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│  Tool.execute(**params)                                            │
│     实际执行工具逻辑，返回 string 或 content blocks                │
│                                                                    │
│  PriceHistoryTool.execute(material_id="ABC123")                    │
│     → "物料 ABC123 历史价格记录（共 5 条）..."                      │
└────────────────────────────────────────────────────────────────────┘

注意：registry.execute() 是备用入口，主入口在 runner.py 直接调用 prepare_call
````

## 4. Schema DSL → JSON Schema 转换

```
┌────────────────────────────────────────────────────────────────────┐
│  Python DSL (开发时书写)                                           │
│                                                                    │
│  @tool_parameters(                                                 │
│      tool_parameters_schema(                                       │
│          material_id=StringSchema("物料编号", min_length=1),       │
│          limit=IntegerSchema(100, minimum=1, maximum=1000),        │
│          required=["material_id"],                                 │
│      )                                                             │
│  )                                                                 │
│  class PriceHistoryTool(Tool): ...                                 │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│  tool_parameters_schema()                                          │
│     ├─ StringSchema → {"type":"string", "minLength":1}            │
│     ├─ IntegerSchema → {"type":"integer", "minimum":1}            │
│     └─ ObjectSchema(...).to_json_schema()                          │
│     → 返回完整参数 schema dict                                      │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│  JSON Schema (发给 LLM)                                            │
│                                                                    │
│  {                                                                 │
│    "type": "object",                                               │
│    "properties": {                                                 │
│      "material_id": {                                              │
│        "type": "string",                                           │
│        "description": "物料编号",                                   │
│        "minLength": 1                                              │
│      },                                                            │
│      "limit": {                                                    │
│        "type": "integer",                                          │
│        "description": "...",                                       │
│        "minimum": 1,                                               │
│        "maximum": 1000                                             │
│      }                                                             │
│    },                                                              │
│    "required": ["material_id"]                                     │
│  }                                                                 │
└────────────────────────────────────────────────────────────────────┘
```

## 5. 如何添加自定义工具

```python
from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import StringSchema, IntegerSchema, tool_parameters_schema

@tool_parameters(
    tool_parameters_schema(
        query=StringSchema("查询关键词", min_length=1),
        limit=IntegerSchema(10, description="返回数量", minimum=1, maximum=50),
        required=["query"],
    )
)
class MyCustomTool(Tool):
    @property
    def name(self) -> str:
        return "my_custom_tool"

    @property
    def description(self) -> str:
        return "自定义工具描述"

    @property
    def read_only(self) -> bool:
        return True  # 无副作用，可并行执行

    async def execute(self, query: str, limit: int = 10) -> str:
        # 参数名必须和 tool_parameters_schema 的 properties key 一致
        # 参数已自动完成类型转换和校验
        return f"查询 {query}，返回 {limit} 条结果"
```

## 6. 核心类职责

| 类 | 文件 | 职责 |
|----|------|------|
| `ToolRegistry` | registry.py | 工具注册、定义生成、调用协调 |
| `Tool` | base.py | 工具抽象基类，定义 name/description/parameters/execute |
| `Schema` | schema.py | JSON Schema DSL，参数约束描述 |
| `tool_parameters` | base.py | 装饰器，自动注入 parameters 属性 |
| `tool_parameters_schema` | schema.py | 构建工具参数的完整 schema |

## 7. 继承 Tool 的工具文件

```
nanobot/agent/tools/
├── cron.py          # 定时任务
├── filesystem.py    # 文件读写、目录列表
├── mcp.py           # MCP 协议工具
├── message.py       # 消息发送
├── notebook.py      # Jupyter notebook 编辑
├── price_history.py # 价格历史查询
├── price_internet.py# 互联网价格查询
├── search.py        # Glob/Grep 文件搜索
├── shell.py         # Shell 命令执行
├── spawn.py         # 子 Agent 任务
├── web.py           # WebFetch/WebSearch
└── base.py          # Tool 基类 + 装饰器
└── registry.py      # ToolRegistry
└── schema.py        # Schema DSL
```