整体汇报过程

① Nanobot 源码解读 (主体，篇幅最大)
- 已经过了一遍代码，整理成笔记
- 讲架构、核心逻辑、实际怎么用的， [审计的skill版本适配]
- 遇到的问题，盘古之白 路径读取错误问题。
② 现场演示 guizang-ppt-skill
- 把刚才的笔记内容 → 直接生成 HTML 格式 PPT
- 观众能看到整个过程，很直观
- 顺带解释这个 skill 的设计思路和使用流程
③ 工具介绍
- claude-code-router 是什么、解决什么问题
- cc switch 怎么配合使用

1. Nanobot 架构
参考链接1: https://mp.weixin.qq.com/s/k_cpKKIzjFDzjqKO29-5ow
1. Agent Loop             done
2. 加载skill              done
3. 工具调用和注册          done       
4. memory机制             done
5. Subagent               done


6. Bus                   ing
7. hook                  done
8. cron
[图片]
[图片]

1.1 Agent Loop
1.1.1 什么是Agent Loop:
[图片]
 [一次llm api]: 普通的 AI 是你问一句它答一句，问答之间没有连续性。
 [一个agent 系统的API]: Agent Loop 不一样，你给它一个目标，它会自己反复思考、自己决定要不要用工具、用什么工具、看结果、再思考，一直循环到它认为任务完成为止。
ReAct 是 Agent Loop 的一种具体实现策略。ReAct = Reasoning + Acting

用户消息 → AgentLoop 分发 → Runner 执行思考 → 调用工具 → 再思考 → 结束应答
用户输入
   ↓
LLM 思考 → 需要用工具吗？
   ├── 是 → 调用工具（搜索/写代码/查数据库...）→ 拿到结果 → 再次思考
   └── 否 → 直接输出答案

# 伪代码形式
while True:
    response = llm.think(context)      # 思考
    if response.is_done:
        return response.answer          # 任务完成，退出
    tool_result = tools.call(response)  # 调用工具
    context.add(tool_result)            # 结果加入上下文，进入下一轮

1.1.2 nanobot中agent loop实现
[图片]

# 主要涉及三个类
AgentLoop, AgentRunner, ContextBuilder

loop.py: _run_agent_loop()
    └─ 创建 AgentRunner
    └─ runner.py: AgentRunner.run()
           └─ for iteration in range(spec.max_iterations):
                  └─ _request_model()   ← 调 LLM
                  └─ 有 tool_calls？
                       ├─ YES → 执行工具 → 结果 append 进 messages → continue
                       └─ NO  → break


1. commands.py: agent() --> 
    1.1. 进行交互 run_interactive() [内部方法]
        1.1. agent_loop.run()      [loop.py]
2. loop.py： run().     [主循环]   消费 inbound 消息    
3. loop.py：_dispatch() [分发]                                                                                                                                                                    
4. loop.py: _process_message() [处理消息]     
  ├─ sessions.get_or_create()                           [1. 获取或创建会话] 【核心】获取或创建会话：缓存优先 → 加载/创建 → 缓存      
  ├─ auto_compact.prepare_session() 
  ├─ commands.dispatch() (斜杠命令)  
  ├─ history = session.get_history(max_messages=0)      [2. 加载历史消息]  
  ├─ messages = self.context.build_messages()           [3. 构建上下文（系统提示 + 历史 + 当前消息 + skills元数据）]                                                                                                                                      
  ├─ final_content, ... await self._run_agent_loop()    [4. 运行 Agent 循环（LLM ↔ 工具调用）]
                                                                                                                                                                                                                                                                                             
  ├─ consolidator.maybe_consolidate()   
  ├─ OutboundMessage消息返回
  
# context 构建上下文中
4.3. context.py: build_messages() -->  
    build_system_prompt [构建上下文。这里回加载system_prompt skills] 
        系统提示： agents.md, hearbeat.md, soul.md, tools.md, user.md, momory 信息， skill 原数据, 都加载进来
    历史消息
    当前消息

# AgentLoop: _run_agent_loop                                                                                                                     
6. loops.py: _run_agent_loop()        [执行Agent]   
   
# AgentRunner._run_agent_loop()                                                                                                                                                         
7. runner.py: run()                   执行runner的run方法、
    
    # spec.max_iterations 默认是200， AgentLoop的核心设计 利用for循环代替while 循环
    7.1 for iteration in range(spec.max_iterations):     # AgentLoop的核心设计 利用for循环代替while 循环 
        是否有工具调用[continue/ break]
        7.1. await self._request_model(spec, messages_for_model, hook, context)    [调用大模型]
        # 判断有没有tool_calls

        
loop.py
context.py




1.1.3 流程图
1. 入口：commands.py → agent_loop.run()

2. 主循环：loop.py → run() 消费 inbound 消息
 ├─ loop.py：_dispatch() [分发]                                                                                                                                                                    
     ├─ loop.py: _process_message() [处理消息]

3. 消息处理：_process_message()
    ├─ sessions.get_or_create()                           [1. 获取或创建会话] 【核心】获取或创建会话：缓存优先 → 加载/创建 → 缓存      
    ├─ history = session.get_history(max_messages=0)      [2. 加载历史消息]  
    ├─ messages = self.context.build_messages()           [3. 构建上下文（系统提示 + 历史 + 当前消息 + skills元数据）]                                                                                                                                      
    ├─ await self._run_agent_loop()                       [4. 运行 Agent 循环（LLM ↔ 工具调用）]                                                                                                                                                                                                                                                                                          
    ├─ consolidator.maybe_consolidate()                   [5. token压缩]
    └─ OutboundMessage消息返回

4. Agent 执行：loop.py: _run_agent_loop()
    └─ 创建 AgentRunner
    └─ runner.py: AgentRunner.run()
           └─ for iteration in range(spec.max_iterations):
                  └─ _request_model()   ← 调 LLM
                  └─ 有 tool_calls？
                       ├─ YES → 执行工具 → 结果 append 进 messages → continue
                       └─ NO  → break

6. OutboundMessage消息返回
```
┌───────────────────────────────────────────────┐
│                            用户输入 (CLI / Channel)                            │
└───────────────────────────────────────────────┘
                                    ↓
┌───────────────────────────────────────────────┐
│  1. commands.py: agent()                                                     │
│     ├─ 创建 AgentLoop 实例                                                   │
│     ├─ 交互模式: run_interactive()                                           │
│     │   ├─ asyncio.create_task(agent_loop.run())                           │
│     │   └─ bus.publish_inbound(InboundMessage)                             │
│     └─ 单次模式: run_once() → agent_loop.process_direct()                   │
└───────────────────────────────────────────────┘
                                    ↓
┌───────────────────────────────────────────────┐
│  2. loop.py: run() [主循环]                                                   │
│     while self._running:                                                     │
│         msg = await self.bus.consume_inbound()    # 消费消息                  ｜
│         task = asyncio.create_task(self._dispatch(msg))  # 分发为异步任务   │
└───────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────┐
│  3. loop.py: _dispatch() [分发]                                              │
│     ├─ async with lock, gate:     # 会话锁 + 并发控制                        │
│     ├─ self._pending_queues[session_key] = pending  # 消息注入队列          │
│     └─ await self._process_message(msg)                                      │
└──────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────┐
│  4. loop.py: _process_message() [处理消息]                                   │
│     ├─ sessions.get_or_create(key)               [1. 获取或创建会话]        │
│     ├─ auto_compact.prepare_session(session)     [2. 准备会话(归档状态)]    │
│     ├─ commands.dispatch(ctx)                    [3. 斜杠命令处理]          │
│     ├─ consolidator.maybe_consolidate_by_tokens  [4. token超限合并]         │
│     ├─ history = session.get_history()           [5. 加载历史消息]          │
│     ├─ messages = context.build_messages()       [6. 构建上下文, skill, memory]  │
│     ├─ await self._run_agent_loop()              [7. 执行Agent Loop循环 ]         │
│     ├─ self._save_turn(session, all_msgs)        [8. 保存本轮对话]                │
│     ├─ self.sessions.save(session)               [9. 持久化会话]            │
│     └─ return OutboundMessage(...)               [10. 返回响应]             │
└──────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────┐
│  5. context.py: build_messages() [构建上下文]                                │
│     messages = [                                                              │
│         {"role": "system", "content": build_system_prompt()},  # 系统提示   │
│         *history,                                              # 历史消息   │
│         {"role": "user", "content": merged}                    # 当前消息   │
│     ]                                                                          │
│                                                                                │
│     build_system_prompt() 加载:                                               │
│     ├─ AGENTS.md, SOUL.md, USER.md, TOOLS.md (bootstrap files)              │
│     ├─ Memory 信息 (MEMORY.md)                                               │
│     ├─ Skills 元数据 (always_skills 全量, 其他只摘要)                        │
│     └─ Recent History (最近对话历史)                                          │
└───────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────┐
│  6. loop.py: _run_agent_loop() [执行Agent]                                   │
│     result = await self.runner.run(AgentRunSpec(...))                        │
│     return (final_content, tools_used, messages, stop_reason)                │
└───────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────┐
│  7. runner.py: run() [LLM + 工具执行循环]                                    │
│     for iteration in range(spec.max_iterations):  # 核心设计: for循环       │
│         ├─ messages_for_model = self._apply_tool_result_budget(...)         │
│         ├─ response = await self._request_model(...)    # 调用LLM           │
│         │                                                                       │
│         │   if response.has_tool_calls:             # 有工具调用            │
│         │       ├─ results = await self._execute_tools(...)                  │
│         │       ├─ messages.append(tool_message)    # 工具结果               │
│         │       └─ continue                         # 继续下一轮             │
│         │                                                                       │
│         │   # 无工具调用 → 结束                                               │
│         │   final_content = clean                                              │
│         │   break                                                              │
│         │                                                                       │
│     return AgentRunResult(...)                                                │
└───────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────┐
│                          bus.publish_outbound(OutboundMessage)               │
│                            → 用户收到响应                                     │
└───────────────────────────────────────────────┘
```

1.2 Skill 何时加载，配置策略
[图片]
1.2.1 什么是skill
anthrpoic官网文档: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
Anthropic将Agent Skills定义为基于大模型的智能体模块化能力单元，核心是通过“能力解耦-按需组合-安全校验”闭环，将大模型的感知、推理、行动等基础能力封装为可复用组件。其原理依托大模型的上下文理解与工具调用优势，使智能体在目标驱动下动态编排技能，实现从简单操作到复杂任务的自主涌现，同时通过对齐机制确保行为符合人类意图。
级别
加载时机
Token 成本
内容
第一级：元数据
始终（启动时）
每个 Skill 约 100 个 token
YAML 前置元数据中的 name 和 description
第二级：指令
触发 Skill 时
不超过 5k token
包含指令和指导的 SKILL.md 主体
第三级及以上：资源
按需
实际上无限制
通过 bash 执行的捆绑文件，不将内容加载到上下文中
1.2.2 nanobot中skills的实现和配置方式
# Skills 加载机制

## 目录结构

```
nanobot/skills/*/SKILL.md      # 内置 skills
workspace/skills/*/SKILL.md    # 用户 skills（优先级高，同名覆盖 builtin）
```

## SKILL.md 格式

```markdown
---
name: audit_cw08
description: "[强制触发] CW08 流程审计..."
metadata: {"nanobot":{"always": true, "requires":{"bins":["python"],"env":["API_KEY"]}}}
---

# Skill 内容（Markdown）
```

## 两种加载模式

| 类型 | 加载位置 | 触发条件 |
|------|----------|----------|
| **Always Skills** | system_prompt 完整内容 | `metadata.always=true` 且依赖满足 |
| **普通 Skills** | XML 摘要（元数据） | Agent 通过 `read_file` 按需加载完整内容 |

> Token 优化：只把核心 skills 放入 system_prompt，其他按需加载。

## 加载流程 (context.py)

```python
def build_system_prompt(self) -> str:
    parts = []

    # 1-2. Bootstrap files + Memory
    parts.append(self._load_bootstrap_files())
    parts.append(self.memory.get_memory_context())

    # 3. Always Skills - 完整加载
    always_skills = self.skills.get_always_skills()           # → ['audit_cw08']
    if always_skills:
        content = self.skills.load_skills_for_context(always_skills)  # 去除 frontmatter
        parts.append(f"# Active Skills\n\n{content}")

    # 4. Skills Summary - XML 摘要
    summary = self.skills.build_skills_summary()
    parts.append(summary)  # <skills><skill name="..."/></skills>

    return "\n\n---\n\n".join(parts)
```

## SkillsLoader 核心方法

| 方法 | 作用 |
|------|------|
| `get_always_skills()` | 返回 always=true 且依赖满足的 skill 名称列表 |
| `load_skills_for_context(names)` | 加载完整内容，去除 frontmatter，格式化输出 |
| `build_skills_summary()` | 生成所有 skills 的 XML 元数据摘要 |
| `get_skill_metadata(name)` | 解析 YAML frontmatter |

## 依赖检查

```python
# requires.bins: 检查 CLI 是否存在
all(shutil.which(cmd) for cmd in required_bins)

# requires.env: 检查环境变量是否设置
all(os.environ.get(var) for var in required_env_vars)
```

依赖不满足 → `available="false"`，不加载到 system_prompt。

## 禁用配置

```yaml
agents:
  defaults:
    disabled_skills: ["summarize", "skill-creator"]
```

## 关键文件

| 文件 | 职责 |
|------|------|
| `nanobot/agent/skills.py` | SkillsLoader 实现 |
| `nanobot/agent/context.py` | build_system_prompt 调用 |
| `nanobot/skills/*/SKILL.md` | 内置 skills |

1.3 工具的使用注册和方法相关

[图片]
[图片]

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
1. ToolRegistry  # 是专门管理工具注册的核心类。它的主要职责：
    self._tools [key:value] --> [工具名称：工具Tool对象]
2. Tool          # 工具的基类

继承Tool的工具有哪些
cron.py, filesystem.py, mcp.py, message.py, notebook.py, 
price_internet.py, search.py, shell.py, spawn.py,  web.py


[图片]
[图片]

1.3.1 工具注册和调用的时机
# AgentLoop， 工具注册时机 nanobot启动时
__init__()
    _register_default_tools()
        self.tools.register()    # 依次注册自己想要调用的工具


# 调用时机，大模型回复的时候会加载所有的工具定义
1. AgentRunner: run()                    # Agent loop的核心这里
2. AgentRunner: _request_model
    2.1. spec.tools.get_definitions()
        # ToolRegistry: get_definitions
        # 就是把 Tool 对象转换为 OpenAI Function Calling API 兼容的 JSON 格式：
        # 这个格式可以直接传给 OpenAI API 的 tools 参数，让 LLM 知道有哪些工具可用以及如何调用它们。
        definitions = [tool.to_schema() for tool in self._tools.values()]               
    

1.3.2 如何添加一个自己的工具
@tool_parameters(
    tool_parameters_schema(
        material_id=StringSchema("要查询历史价格的物料编号", min_length=1),
        required=["material_id"],              # 标记必填参数
    )
)
class MyTool(Tool): 
    @property
    def name(self) -> str:
        return "工具名称"
    @property
    def description(self) -> str:
        return ("工具的具体描述")
    # 参数名必须和 tool_parameters_schema 中的 properties key 一致
    async def execute(self, material_id: str) -> str:        
        return "函数调用结果"
        
# 添加后在AgentLoop，中注册
__init__()
    _register_default_tools()
        self.tools.register()    # 依次注册自己想要调用的工具
        

这样定义后，ToolRegistry 会：
1. 用 get_definitions() 把 schema 发给 LLM
2. LLM 调用时，prepare_call() 会校验参数
3. execute() 被调用时，参数已经完成类型转换

StringSchema 是用来描述字符串参数的约束条件
1. to_json_schema()        # 就是把 Python 对象转成 dict：

1.3.3 Schema 目的
优势
说明
语法简洁
StringSchema("物料编号", min_length=1) 比手写字典形式更简短
IDE 支持
自带类型提示与参数联想，无需死记 JSON Schema 字段名
避免错误
规避 minLength / min_length 这类命名格式混用写错问题
可复用
Schema 实例支持多处复用、灵活组合拼装
内置验证
提供 validate_value() 方法，直接校验参数是否符合约束规则

# 用于工具注册和执行
# DSL = Domain Specific Language（领域特定语言）
 本质就是用 Python DSL 替代手写 JSON Schema，开发体验更好。
StringSchema("物料编号", min_length=1)
# 等价于直接写领域原始格式（JSON Schema dict）
{"type": "string", "description": "物料编号", "minLength": 1}
每种 Schema 类对应一种基本类型的约束：

这样 LLM 就能知道：
- 参数类型是什么
- 有什么限制（长度、范围、枚举）
- 哪些是必填的

约束越精确，LLM 调用工具就越准确，减少传参错误。
1.3.4 tool_parameters, tool_parameters_schema()
# 接受一个schema[tool_parameters_schema 返回值 大的object_schema] --> 
tool_parameters()

# 多个 Schema → ObjectSchema → to_json_schema() → 一个大 dict
tool_parameters_schema 把多个 Schema 合并成一个大的 object dict：


# 自动注入 类属性 parameters
@tool_parameters(
    tool_parameters_schema(
        material_id=StringSchema("要查询历史价格的物料编号", min_length=1),
         required=["material_id"],
    )
)

# 等价于 实现这个方法
class MyTool(Tool):
  @property
  def parameters(self) -> dict[str, Any]:
      return {
          "type": "object",
          "properties": {
              "material_id": {"type": "string",  "description": "要查询历史价格的物料编号", "minLength": 1}
          },
          "required": ["material_id"]
      }
      
# 
get_definitions()
    to_schema()
    self.parameters. 注解调用

{"type": "object", "properties": {"material_id": {"type": "string", "description": "要查询历史价格的物料编号", "minLength": 1}, "start_date": {"type": "string", "description": "查询开始日期，格式 YYYY-MM-DD，默认为最早记录"}, "end_date": {"type": "string", "description": "查询结束日期，格式 YYYY-MM-DD，默认为最新记录"}, "limit": {"type": "integer", "description": "返回记录数量上限，默认 100，最大 1000", "minimum": 1, "maximum": 1000}}, "required": ["material_id"]}


1.4 Memory  机制
memory store
consolidator
Dream

[图片]
[图片]

Session history + auto-compact 是被动防御，由 token 压力驱动，目标是让 prompt 永远装得进上下文窗口。它只做压缩，不做筛选——旧消息原样摘要追加进 history.jsonl，不判断哪些"重要"。
Dream consolidation 是主动提炼，由时间（cron）驱动，目标是把对话里有价值的信息升华为长期认知。它有两个 LLM 调用：第一个负责"想清楚该改什么"，第二个负责"真正动手改文件"。改完之后推进 .dream_cursor，下次只处理新增的部分，不会重复。

memory.py
    1. MemoryStore（存储层）
    2. Consolidator（实时压缩）                #  (token超限时触发)
    3. Dream（定时整理）

# Consolidator
maybe_consolidate_by_tokens()             # 循环：将旧消息存档，直到提示符合安全预算。
   self.estimate_session_prompt_tokens(session)   
   
# 超过上线就压缩到一半以内，50%
consolidator_archive.md                   # 进行摘要的提示

1.4.1 Consolidator 压缩
memory.py: Consolidator 类

maybe_consolidate_by_tokens(session)                        # 【核心】循环合并直到符合 token 预算   
    ├── estimate_session_prompt_tokens(session)                     # 估算会话提示词 token 数量                                                                                     
    ├── pick_consolidation_boundary(session, tokens_to_remove)      # 选择合并边界（user-turn 分界点）                                                                                 
    ├── _cap_consolidation_boundary(session, end_idx)               # 限制块大小（不超过 MAX_CHUNK_MESSAGES）                                                                          
    ├── archive(messages)                                           # 【核心】通过 LLM 摘要消息并写入 history.jsonl     
    

1.4.1.1 Consolidator 方法之间的关系
[图片]

# Consolidator 方法之间的关系
maybe_consolidate_by_tokens(session)                     # 【核心】循环压缩直到符合 token 预算
    │
    ├─ 1. 计算预算
    │      budget = context_window - max_completion - SAFETY_BUFFER
    │      target = budget // 2  # 目标：降到预算的一半
    │
    ├─ 2. 估算当前 token
    │      estimate_session_prompt_tokens(session) → (estimated, source)
    │
    ├─ 3. 判断是否超限
    │      if estimated < budget: return  # 不超限，跳过
    │
    └─ 4. 循环压缩（最多 5 轮）
            ├─ pick_consolidation_boundary(session, need_remove)
            │     → 返回 (end_idx, removed_tokens)
            │     约束：用户消息边界（保证完整性）
            │
            ├─ _cap_consolidation_boundary(session, end_idx)
            │     → 限制块大小 ≤ MAX_CHUNK_MESSAGES (60)
            │
            ├─ archive(chunk)  # LLM 摘要
            │     → 成功：写入 history.jsonl
            │     → 失败：raw_archive 原始 dump
            │
            ├─ session.last_consolidated = end_idx  # 更新游标
            │
            └─ 重新估算 token，继续下一轮

关键补充：

1. target 是预算的一半：target = budget // 2，不是刚好降到 budget
2. 循环最多 5 轮：防止无限压缩
3. _cap 是对 end_idx 的二次限制：先选边界，再限制大小

1.4.1.2 Consolidator 压缩过程
[图片]

# 65536 - 8192 - 1024
budget                     # 输入消息的安全上限，表示 prompt 可以使用的最大 token 数。
self.context_window_tokens # LLM 模型的最大上下文容量（输入+输出）
self.max_completion_tokens # 为 LLM 响应输出预留的 token 空间
self._SAFETY_BUFFER        # tokenizer 估算误差的缓冲 容错
budget = self.context_window_tokens - self.max_completion_tokens - self._SAFETY_BUFFER 
estimated, source = self.estimate_session_prompt_tokens(session)     # 已经用了多少token
estimated 是"用了多少"，budget 是"能用多少"。用了 < 能用 → 安全，继续。

# 压缩 样例
63964[当前token] - 28160[目标token]    # 需要移除的量
1. 需要移除的 token 数         [尽量达到]
2. 用户消息边界（保证完整性）
3. 最多 60 条消息上限
# Token 预算计算

budget = context_window_tokens - max_completion_tokens - SAFETY_BUFFER
# 示例：65536 - 8192 - 1024 = 56320

estimated = 当前 session 已用 token

# 触发条件
if estimated > budget:
    target = budget * 0.5  # 目标：降到预算的 50%
    need_remove = estimated - target  # 需移除的量

# 边界选择
boundary = pick_consolidation_boundary(session, need_remove)
# 返回：(end_idx, removed_tokens) -> (截断的消息索引位置, 该位置累计移除的 token 数)
# 约束：用户消息完整性 + 最多 60 条上限

# 执行压缩
archive(chunk)  # 若返回 nothing → 无价值内容，跳过

# 存储结果
摘要写入 history.jsonl，格式：
{"role": "assistant", "content": "[摘要内容]", "type": "consolidation", ...}

图示简化：

|<---------- context_window (65536) ----------|
|                                              |
|-- 输入 (≤budget) --|-- 输出预留 (8192) --|-- 缓冲[容错] (1024) --|
|    ≤ 56320         |      8192           |      1024       |

2026-05-18 01:21:28.343 | INFO     | nanobot.agent.memory:maybe_consolidate_by_tokens:529 - Token consolidation round 1 for cli:direct: 59409/65536 via tiktoken, chunk=59 msgs
2026-05-18 01:23:59.922 | INFO     | nanobot.agent.memory:maybe_consolidate_by_tokens:529 - Token consolidation round 2 for cli:direct: 37982/65536 via tiktoken, chunk=40 msgs

1.4.1 history.jsonl 的写入时机和来源
[图片]

[Consolidator 压缩] history.jsonl 的写入时机和来源
1. Consolidator 自动压缩（主要来源）   【append_history 通过这个方法实现】
2. 用户手动归档（次要来源）
    触发条件：用户输入 /new 命令清空会话
    /new 调用的 archive() 与 Consolidator 自动压缩调用的 archive() 是同一个方法  【append_history 通过这个方法实现】

  
用户对话
  ↓
Session.messages 增长
  ↓ (每次对话后)
AgentLoop._process_message()
  ↓
AgentLoop._schedule_background(consolidator.maybe_consolidate_by_tokens(session))
  ↓ (异步检查)
estimated > budget?
  ├─ No → 直接返回（不写入 history.jsonl）
  └─ Yes → 循环压缩
      ↓
      截取 chunk = session.messages[last_consolidated:end_idx]
      ↓
      Consolidator.archive(chunk)
      ├─ 格式化 messages → MemoryStore._format_messages()
      ├─ LLM 摘要 → provider.chat_with_retry()
      ├─ 写入 history.jsonl → MemoryStore.append_history(summary)  ⭐⭐⭐
      └─ 失败降级 → MemoryStore.raw_archive(messages)

/new 手动归档

用户输入 /new
  ↓
CommandRouter.dispatch(ctx)
  ↓
cmd_new(ctx)
  ├─ snapshot = session.messages[last_consolidated:]  ⭐ 提取未压缩部分
  ├─ session.clear()                                 ⭐ 清空会话
  └─ loop._schedule_background(consolidator.archive(snapshot))  ⭐ 后台归档
      ↓
      Consolidator.archive(snapshot)
      ↓
      MemoryStore.append_history(summary)  ⭐ 写入 history.jsonl

1.4.2 Dream
history.jsonl 的写入时机和来源
1. Consolidator 自动压缩（主要来源）   【append_history 通过这个方法实现】
2. 用户手动归档（次要来源）
    触发条件：用户输入 /new 命令清空会话
    /new 调用的 archive() 与 Consolidator 自动压缩调用的 archive() 是同一个方法  【append_history 通过这个方法实现】


"Dream 是中期记忆到长期记忆的关键步骤"
  - 自动触发：作为系统后台服务，定期维护长期记忆          定时记录 [默认两小时]
  - 手动触发：给用户控制权，可以随时检查或加速处理        /dream 命令

dream 是通过workspace/memory/history.jsonl 
文件去更新user.md, memory.md, skills 这几个文件的内容

这样设计的好处是：
长期记忆文件（USER/MEMORY/SOUL）会持续进化，既能记住用户偏好，又能清理过时信息，还能发现可复用的技能模式。

dream_phase1.md， dream_phase2.md  这两个文件的区别和作用
第一个负责"想清楚该改什么"，第二个负责"真正动手改文件"
[图片]

"Dream 是中期记忆到长期记忆的关键步骤"
  - 自动触发：作为系统后台服务，定期维护长期记忆          定时记录 [默认两小时]
  - 手动触发：给用户控制权，可以随时检查或加速处理        /dream 命令

dream 是通过workspace/memory/history.jsonl 
文件去更新user.md, memory.md, skills 这几个文件的内容

两阶段处理

┌───────────────────────────────────────┐
│                        Dream.run()                              │
├───────────────────────────────────────┤
│  1. 读取未处理 history.jsonl 条目（cursor > dream_cursor）         │
│                                                                 │
│  2. 阶段一：分析阶段（dream_phase1.md）                            │
│     ├─ [文件操作] 向 MEMORY/SOUL/USER 写入原子事实                │
│     ├─ [文件清理] 移除过期无效内容                                │
│     └─ [技能挖掘] 提炼可复用通用技能模式                           │
│                                                                 │
│  3. 阶段二：执行阶段（dream_phase2.md）                            │
│     ├─ 调用 AgentRunner + edit_file 精准修改文件                 │
│     ├─ 新建技能文件：skills/自定义名称/SKILL.md                   │
│     └─ 调用 write_file 完成内容写入                              │
│                                                                 │
│  4. 后置处理流程                                                  │
│     ├─ 更新游标字段 dream_cursor                                │
│     ├─ 执行 compact_history() 压缩清理历史会话                   │
│     └─ 自动 Git 提交所有变更内容                                 │
└──────────────────────────────────────┘

Phase 1 分析规则 (dream_phase1.md)

| 标记            | 用途                               |
|---------------|----------------------------------|
| [FILE]        | 添加原子事实（如 "has a cat named Luna"） |
| [FILE-REMOVE] | 删除过时内容（>14天的临时信息、已完成任务）          |
| [SKILL]       | 发现重复出现的可复用工作流                    |

Phase 2 编辑规则 (dream_phase2.md)

- 使用 edit_file 精确编辑，不重写整个文件
- 批量合并同一文件的修改
- 创建技能时检查去重

dream_phase1.md， dream_phase2.md  这两个文件的区别和作用
第一个负责"想清楚该改什么"，第二个负责"真正动手改文件"

1.4.2.1 dream_phase1.md
# 全文精准中文翻译
将对话历史与当前记忆文件进行比对，同时扫描记忆文件中**过期无效内容**（即便对话历史里未提及也要排查）。

每条发现结果单独占一行输出：
[文件类型] 新增原子事实（此前未存入记忆）
[文件-移除] 移除该内容的原因
[通用技能] 短横线命名格式：可复用流程模式的单行说明

**文件分类**
USER 用户档案（身份信息、个人偏好）
SOUL 人设行为库（机器人言行风格、语气设定）
MEMORY 业务知识库（技术知识、项目相关背景）

## 执行规则
1. 原子事实要求：写明确事实短句，例“养了一只名叫露娜的猫”，禁止笼统描述如“聊过宠物养护”
2. 信息修正格式示例：[USER] 常住地为东京，非大阪
3. 必须收录用户**确认认可**的实操方案

## 过期内容判定（标记 [文件-移除] 删除）
1. 时效类数据：距今超过14天的天气、日常状态、单次会面、已结束活动
2. 一次性完结任务：问题分诊、单次评审、已完成调研、已解决故障事件
3. 已办结追踪内容：已合并/关闭代码推送、已修复问题、完成的环境迁移
4. 超14天详细故障记录：精简为单行总结，删除冗余详情
5. 被替代内容：已有新版方案取代的旧流程、已废弃依赖组件

## 通用技能提取判定（标记 [通用技能]）
需同时满足全部条件才收录：
1. 该固定可复用工作流程，在对话记录中**出现2次及以上**
2. 流程有清晰执行步骤，而非“喜欢简洁回答”这类模糊偏好
3. 内容具备实用价值，值得整理成独立执行规范，排除读取文件这类简单操作
4. 无需排查重复技能，后续流程会自动去重

## 禁止录入内容
实时天气、临时状态、临时报错信息、闲聊无关话术
无任何内容需要更新时，直接标注：[跳过]

1.4.2.2 .dream_phase2.md
# 中文完整翻译
根据下方分析内容更新记忆文件
- [文件新增] 条目：将对应内容添加至匹配的目标文件中
- [文件移除] 条目：从记忆文件里删除对应内容
- [通用技能] 条目：使用**写入文件**功能，在 `skills/技能名/` 目录下新建 `SKILL.md` 技能文档

## 工作区相对文件路径
- 人设配置：SOUL.md
- 用户档案：USER.md
- 知识库：memory/MEMORY.md
- 技能文档：skills/<技能名>/SKILL.md（仅用于通用技能条目）

**严禁自行猜测自定义文件路径**

## 编辑规范
1. 直接编辑文件，已提供文件原文，无需读取文件
2. 匹配旧内容时使用**完整原文**，连带前后空行保证精准唯一匹配
3. 同一文件的所有修改合并为一次编辑操作
4. 删除内容规则：把对应板块标题+全部列表内容设为旧文本，新文本置空
5. 仅做精准局部修改，**禁止全文重写**
6. 无任何更新需求则直接终止流程，不调用任何工具

## 技能创建规范（仅通用技能条目使用）
1. 调用写入文件命令创建 `skills/<技能名>/SKILL.md`
2. 写入前读取**技能模板参考路径**，对齐前置元数据格式、命名规则与内容标准
3. **去重校验**：核对已有技能列表，确认无功能重复；已有同类流程则跳过新建
4. 文档开头必须加入YAML前置元数据，包含名称、描述字段
5. 技能文档字数控制在2000字以内，内容精简、可直接执行
6. 文档必备内容：使用场景、操作步骤、输出格式、至少一条实操示例
7. 禁止覆盖已有技能，技能文件夹已存在则跳过创建
8. 写明可调用的专属工具（读取文件、写入文件、终端执行、网页搜索等）
9. 技能只写操作指令流程，**禁止写入实际业务代码**

## 内容质量要求
1. 每一行内容都要有独立实用价值
2. 清晰分栏，用简洁列表梳理内容
3. 内容精简压缩（非删除）：保留核心事实，剔除冗余赘述
4. 无法确定是否过期的内容：予以保留，并标注「需核验时效性」

1.5 Subagent 的用法
[图片]

类关系
SpawnTool(Tool)， SubagentManager， AgentRunner

SpawnTool 和 SubagentManager 组合关系
    SubAgentManager 为 SpawnTool 类的成员属性
    
SubagentManager，AgentRunner 组合关系
    AgentRunner 为 SubAgentManager类的成员属性
    

[图片]

关键部分
SpawnTool.execute()
└─→ SubagentManager.spawn()          # 创建后台 asyncio.Task
        └─→ asyncio.create_task(_run_subagent())  # 异步执行
            ├─→ ToolRegistry 注册工具（不含 spawn/messag 工具）❌
            ├─→ _build_subagent_prompt()  # 构建 system prompt
            ├─→ AgentRunner.run()        # LLM + 工具执行循环
            └─→ _announce_result()       # 通过 MessageBus 通知主 agent

关键点：
1. spawn() 是非阻塞的 —— 使用 asyncio.create_task() 创建后台任务后立即返回，主 agent 可以继续工作
2. _run_subagent() 在后台独立运行，完成后通过 MessageBus.publish_inbound() 发送 InboundMessage 通知主 agent
3. 结果以 system message 形式注入，触发主 agent 的下一轮处理

限制：单层派生（不可嵌套）
- Subagent 工具列表不注册 SpawnTool（见 subagent.py:119 注释）
- 设计考量：避免任务树爆炸、简化管理、资源控制

用户: "帮我分析这个项目的架构，需要10分钟"                                                                                                
    ↓                                                                                                                                   
LLM: tool_calls: spawn(task="分析项目架构...")                                                                                            
    ↓                                                                                                                                   
SpawnTool.execute()                                                                                                                       
└─ self._manager.spawn(task, label)  ← 调用 SubagentManager                                                                             
    ↓                                                                                                                                   
SubagentManager.spawn()                                                                                                                   
├─ asyncio.create_task(_run_subagent)  ← 创建后台任务                                                                                   
├─ 返回: "Subagent [分析项目架构] started (id: abc123)"                                                                                 
└─ 主 Agent 继续响应用户                                                                                                                
    ↓                                                                                                                                   
LLM: "已启动后台任务，完成后会通知您"                                                                                                     
                                                                                                                                        
--- 后台运行 ---                                                                                                                          
_run_subagent()                                                                                                                           
├─ 创建独立 ToolRegistry（无 spawn、message）                                                                                           
├─ AgentRunner.run() 执行任务                                                                                                           
└─ 完成后 _announce_result() 通过 MessageBus 通知                                                                                       
    ↓                                                                                                                                   
主 Agent 收到通知 → 告知用户任务完成  

1.5.1 Spawn [tool]
spawn的工具描述
**后台创建子代理来处理任务**
适用于可独立运行、流程复杂或耗时较长的任务。
子代理完成任务后会主动上报执行结果。
若涉及成果交付或已有项目，优先先检查工作区环境，
必要时单独新建专属子目录进行处理。

1.6 Bus的用法
[图片]
bus负责处理信息队列和事件。 events定义事件，nanobot/bus/events.py，即从聊天渠道获得的信息和要返回到聊天界面的信息，就是个结构体。
里面的MessageBus就是维护信息流的，解耦聊天渠道与Agent核心，代码非常简单。
# 相关的类
# events.py: 
    InboundMessage
    OutboundMessage

# queue.py
    MessageBus


1.6.1 普通消息流程
[图片]
- nanobot/agent/loop.py内的AgentLoop调用run，持续消费inbound中的内容。
  - 一个细节，如果content是"/stop"，则会停止，走_handle_stop。
- 如果content是"/stop"，则会停止，走_handle_stop。
- 而如果不是stop，则走_dispatch，此处是会拿到在async with self._processing_lock，调用 self._process_message(msg)。
- 返回响应。渠道管理器或其他消费者通过 bus.consume_outbound() 获取响应，然后调用对应渠道的 send() 方法将消息发送到外部平台。继续以nanobot/cli/commands.py为例。
- 这块内容对python的协程asyncio有非常深入的应用，这块的调度基本就实现了Agent里面的异步、队列、随时打断、刷新的调度处理。
# 生产消息。nanobot/cli/commands.py
# agent()
    ├─  run_interactive()
            ├─  await bus.publish_inbound(InboundMessage(
                channel=cli_channel,
                sender_id="user",
                chat_id=cli_chat_id,
                content=user_input,
                metadata={"_wants_stream": True},
            ))
            
            
# 消费消息
# 拿消息进行消费，最多1s，无消息则continue 防止阻塞
AgentLoop: run()
msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)   

1.6.2 bus并发控制
[图片]

1.7 /hooks
[图片]



2. 工具分享
1. guizang-ppt-skill
2. cc switch 
3. claude-code-router 
2.1 guizang-ppt-skill 介绍
它解决的核心问题是：用 AI 做出来的 PPT 通常又丑又平庸。这个 skill 把一位真实演讲者踩坑后的审美标准、布局规范、质量检查清单全部编码进去，让 Claude Code 生成的 HTML 演示文稿直接达到"编辑级"视觉水准，而不是默认的"商务模板"风格。
这是一个适配 Claude Code、Codex 等 Agent 环境的 Skill，用于将提示词生成单文件 HTML 横向翻页演示文稿，视觉风格是"编辑杂志 × 电子墨水"，就像 Monocle 杂志缝上了代码。 GitHub
两套视觉系统（最新版）：
- Style A 是电子杂志 × 电子墨水风格，适合叙事、观点、分享、个人风格表达；
- Style B 是瑞士国际主义风格，网格至上、单一高饱和锚点色、直角、丝线、极致字号对比，适合事实、产品、分析、方法论表达。
# 同类产品
1. guizang-ppt-skill
2. frontend-slides-editable
3. Beautiful HTML templates 

2.2 CC switch
GitHub 地址：https://github.com/farion1231/cc-switch
参考资料1: cc-switch设置在Claude code中使用GPT系列 - 小红书
参考资料2: 【CC-Switch】:Claude Code 兼容 OpenAI 格式 API, Claude code 接入本地部署模型_ccswitch的路由开关在哪-CSDN博客

2.2.1 cc switch 是什么
CC Switch 是一个跨平台桌面端的 All-in-One 工具，支持管理 Claude Code、Codex、OpenCode、OpenClaw、Gemini CLI 和 Hermes Agent 等多个 AI 编程 CLI 工具。
[图片]

2.2.2 核心功能
功能特性
说明
一个应用, 六个 CLI 工具
在单一界面中管理 Claude Code、Codex、Gemini CLI、OpenCode 和 OpenClaw， Hermes agent
告别手动编辑
50+ 供应商预设，包括 AWS Bedrock、NVIDIA NIM 和社区中转服务
一键切换
可视化界面，一键在不同供应商之间切换
统一 MCP/Skills 管理
一个面板管理四个应用的 MCP、Skills，支持双向同步
系统托盘快速切换
从托盘菜单即时切换供应商，无需打开完整应用
路由模式（核心亮点）
让 Claude Code 直接使用 OpenAI 兼容格式 API，解锁 DeepSeek、硅基流动等更多模型
跨平台支持
Windows、macOS、Linux 全平台覆盖
1. CC-Switch 的路由模式可以让 Claude Code 直接使用 OpenAI兼容格式的 API，解锁 DeepSeek、硅基流动、Gemini 等更多模型选择！, 也可以兼容部署的vllm模型。
2. 切换配置热更新，切换之后立即生效，无需退出cc

2.2.3 注意点
他是界面端的，如果是linux 无界面的，可能切换相对没那么友好

注意点：
Anthropic 格式： https://coding.dashscope.aliyuncs.com/apps/anthropic
OpenAI 格式[不要写全路径]: https://coding.dashscope.aliyuncs.com/v1

2.3 Claude code Router
Claude Code Router GitHub: https://github.com/musistudio/claude-code-router
参考博客1: https://rosetears.cn/archives/61/
参考博客2: https://blog.csdn.net/qq_45056135/article/details/160717854?spm=1001.2014.3001.5502

2.3.1 Claude Code Router 是什么
Claude Code 是 Anthropic 官方推出的 AI 编程助手 CLI 工具，默认使用 Claude 模型。Claude Code Router 是一个开源的路由工具，允许我们将 Claude Code 的请求转发到其他兼容 OpenAI API 格式的模型服务，实现灵活的模型切换和统一管理。
主要是针对claude code用户

2.3.2 核心功能 
Claude Code Router 主要提供以下能力：
功能
说明
多模型路由
支持配置多个模型提供商，按需切换使用不同模型
请求转发
将 Claude Code 的请求转换为 OpenAI 兼容格式，转发到目标模型服务
统一认证
支持设置统一的 API Key，简化认证管理
Web 管理界面
提供可视化配置界面，方便管理 Providers 和路由规则
日志记录
完整的请求日志，便于调试和问题排查

2.3.3 典型使用场景
- 使用本地部署的 LLM 模型（如 vLLM、Ollama）
- 接入国内大模型服务（如通义千问、智谱 AI、字节跳动）
- 多模型负载均衡和切换测试
- claude code router 配置不是热更新，每次完成之后需要利用ccr restart 重启才会生效

2.3.4 快速使用
1. 安装claude code router
npm install -g @musistudio/claude-code-router
2. 启动ccr
ccr code
3. 其他命令
# 更新配置文件之后重启
ccr restart

# 启动ui界面
ccr ui
# 点击
http://127.0.0.1:3456/ui/
配置文件位于 ~/.claude-code-router/config.json

4. 注意
# 这样启动clade coe不会触发ccr的默认 默认用之前claude code的配置
claude
# 这样才会启动ccr 的配置
ccr code

