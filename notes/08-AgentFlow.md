# Agent 执行流程 — 从 CLI 到响应的完整链路

> 文件路径: `nanobot/cli/commands.py` → `nanobot/agent/loop.py` → `nanobot/agent/runner.py`
> 核心流程: 消息入口 → 主循环消费 → 会话处理 → 上下文构建 → LLM 调用 → 工具执行 → 响应返回

## 流程概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            用户输入 (CLI / Channel)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. commands.py: agent()                                                     │
│     ├─ 创建 AgentLoop 实例                                                   │
│     ├─ 交互模式: run_interactive()                                           │
│     │   ├─ asyncio.create_task(agent_loop.run())                            │
│     │   └─ bus.publish_inbound(InboundMessage)                              │
│     └─ 单次模式: run_once() → agent_loop.process_direct()                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. loop.py: run() [主循环]                                                   │
│     while self._running:                                                     │
│         msg = await self.bus.consume_inbound()    # 消费消息                 │
│         task = asyncio.create_task(self._dispatch(msg))  # 分发为异步任务   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. loop.py: _dispatch() [分发]                                              │
│     ├─ async with lock, gate:     # 会话锁 + 并发控制                        │
│     ├─ self._pending_queues[session_key] = pending  # 消息注入队列          │
│     └─ await self._process_message(msg)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
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
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
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
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  6. loop.py: _run_agent_loop() [执行Agent]                                   │
│     result = await self.runner.run(AgentRunSpec(...))                        │
│     return (final_content, tools_used, messages, stop_reason)                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
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
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                          bus.publish_outbound(OutboundMessage)               │
│                            → 用户收到响应                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 详细步骤解析

### 1. CLI 入口 (commands.py)

```python
# commands.py:870-992
@app.command()
def agent(message, session_id, workspace, config, ...):
    # 加载配置
    config = _load_runtime_config(config, workspace)

    # 创建组件
    bus = MessageBus()
    provider = _make_provider(config)
    cron = CronService(...)
    agent_loop = AgentLoop(bus, provider, workspace, ...)

    if message:
        # 单次模式 — 直接调用
        async def run_once():
            response = await agent_loop.process_direct(message, session_id)
            _print_agent_response(response.content)
        asyncio.run(run_once())
    else:
        # 交互模式 — 通过消息总线
        async def run_interactive():
            asyncio.create_task(agent_loop.run())          # 启动主循环
            while True:
                user_input = await _read_interactive_input_async()
                await bus.publish_inbound(InboundMessage(...))
```

**两种模式对比：**

| 模式 | 入口 | 数据流 | 适用场景 |
|------|------|--------|---------|
| 单次模式 | `process_direct()` | 直接 `_process_message()` | CLI `-m` 参数 |
| 交互模式 | `run()` → `_dispatch()` | MessageBus 中转 | CLI 交互、Channel |

### 2. 主循环 (loop.py: run())

```python
# loop.py:450-514
async def run(self):
    self._running = True
    await self._connect_mcp()  # 连接 MCP 服务器

    while self._running:
        try:
            # 消费消息，最多等待 1 秒（防止阻塞）
            msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
        except asyncio.TimeoutError:
            self.auto_compact.check_expired(...)  # 检查超时会话
            continue

        # 优先命令处理 (/stop 等)
        if self.commands.is_priority(msg.content):
            result = await self.commands.dispatch_priority(ctx)
            await self.bus.publish_outbound(result)
            continue

        # 分发为独立任务
        effective_key = self._effective_session_key(msg)
        task = asyncio.create_task(self._dispatch(msg))
        self._active_tasks[effective_key].append(task)
```

**设计要点：**

- **超时消费**: 1秒超时避免无限阻塞，顺便检查超时会话
- **任务分发**: 每条消息独立任务，支持 `/stop` 命令取消
- **统一会话**: `_unified_session` 模式下所有消息共享同一 session

### 3. 消息分发 (loop.py: _dispatch())

```python
# loop.py:515-601
async def _dispatch(self, msg):
    session_key = self._effective_session_key(msg)
    lock = self._session_locks.setdefault(session_key, asyncio.Lock())
    gate = self._concurrency_gate or nullcontext()

    # 创建消息注入队列
    pending = asyncio.Queue(maxsize=20)
    self._pending_queues[session_key] = pending

    try:
        async with lock, gate:  # 会话锁 + 并发控制
            response = await self._process_message(msg, pending_queue=pending)
            await self.bus.publish_outbound(response)
    finally:
        # 清理队列，未处理消息重新发布到 bus
        self._pending_queues.pop(session_key)
```

**设计要点：**

- **会话锁**: 同一 session 的消息串行处理
- **并发门**: `NANOBOT_MAX_CONCURRENT_REQUESTS` 限制全局并发
- **消息注入**: `pending_queue` 支持中途注入后续消息

### 4. 消息处理 (loop.py: _process_message())

```python
# loop.py:626-767
async def _process_message(self, msg, ...):
    # System 消息特殊处理
    if msg.channel == "system":
        channel, chat_id = msg.chat_id.split(":")
        session = self.sessions.get_or_create(key)
        messages = self.context.build_messages(...)
        final_content, ... = await self._run_agent_loop(...)
        self._save_turn(session, all_msgs)
        return OutboundMessage(...)

    # 正常消息处理流程
    session = self.sessions.get_or_create(key)                 # [1]

    session, pending = self.auto_compact.prepare_session(...)  # [2]

    # 斜杠命令
    ctx = CommandContext(msg=msg, session=session, ...)
    if result := await self.commands.dispatch(ctx):            # [3]
        return result

    await self.consolidator.maybe_consolidate_by_tokens(...)   # [4]

    history = session.get_history(max_messages=0)              # [5]

    messages = self.context.build_messages(                    # [6]
        history=history,
        current_message=msg.content,
        media=msg.media,
        channel=msg.channel,
        chat_id=msg.chat_id,
    )

    # [7] 执行 Agent
    final_content, ... = await self._run_agent_loop(
        messages, session=session, channel=msg.channel, ...
    )

    self._save_turn(session, all_msgs, 1 + len(history))       # [8]
    self._clear_runtime_checkpoint(session)
    self.sessions.save(session)                                # [9]

    # [10] 返回响应
    return OutboundMessage(channel=msg.channel, content=final_content)
```

**步骤详解：**

| 步骤 | 方法 | 职责 |
|------|------|------|
| 1 | `sessions.get_or_create()` | 获取或创建会话（缓存优先 → 加载/创建 → 缓存） |
| 2 | `auto_compact.prepare_session()` | 处理归档状态，返回摘要（如有） |
| 3 | `commands.dispatch()` | 斜杠命令处理，直接返回结果 |
| 4 | `consolidator.maybe_consolidate_by_tokens()` | token 超限触发合并 |
| 5 | `session.get_history()` | 加载历史消息 |
| 6 | `context.build_messages()` | 构建完整上下文 |
| 7 | `_run_agent_loop()` | 执行 AgentRunner |
| 8 | `_save_turn()` | 保存本轮消息到 session |
| 9 | `sessions.save()` | 持久化会话到文件 |
| 10 | `OutboundMessage` | 构建响应消息 |

### 5. 上下文构建 (context.py)

```python
# context.py:119-150
def build_messages(self, history, current_message, ...):
    # 运行时元数据（时间、channel、chat_id）
    runtime_ctx = self._build_runtime_context(channel, chat_id, ...)

    # 用户内容（文本 + 媒体）
    user_content = self._build_user_content(current_message, media)

    # 合并为单个 user message
    merged = f"{runtime_ctx}\n\n{user_content}"

    messages = [
        {"role": "system", "content": self.build_system_prompt()},  # 系统提示
        *history,                                                    # 历史消息
        {"role": "user", "content": merged}                          # 当前消息
    ]
    return messages


# context.py:31-64
def build_system_prompt(self, skill_names=None, channel=None):
    parts = [
        self._get_identity(channel),          # 核心身份 + 平台策略
        self._load_bootstrap_files(),         # AGENTS.md, SOUL.md, USER.md, TOOLS.md
        self.memory.get_memory_context(),     # MEMORY.md 内容
        self.skills.load_skills_for_context(always_skills),  # always skills 全量
        self.skills.build_skills_summary(),   # 其他 skills 摘要
        self.memory.read_unprocessed_history(),  # 最近历史
    ]
    return "\n\n---\n\n".join(parts)
```

**上下文组成：**

| 组成部分 | 来源 | 说明 |
|---------|------|------|
| Identity | `identity.md` 模板 | 工作目录、平台信息、channel |
| Bootstrap Files | workspace 文件 | AGENTS.md, SOUL.md, USER.md, TOOLS.md |
| Memory | MEMORY.md | 长期记忆 |
| Active Skills | SKILL.md | `always: true` 的技能全量加载 |
| Skills Summary | SKILL.md 元数据 | 其他技能只加载 name + description |
| Recent History | history.jsonl | 未处理的最近对话 |

### 6. Agent 执行 (loop.py: _run_agent_loop())

```python
# loop.py:359-448
async def _run_agent_loop(self, initial_messages, session, ...):
    # 创建钩子
    loop_hook = _LoopHook(self, on_progress, on_stream, ...)

    # 注入回调
    async def _drain_pending(limit=...):
        items = []
        while len(items) < limit:
            pending_msg = pending_queue.get_nowait()
            items.append({"role": "user", "content": merged})
        return items

    # 调用 runner
    result = await self.runner.run(AgentRunSpec(
        initial_messages=initial_messages,
        tools=self.tools,
        model=self.model,
        max_iterations=self.max_iterations,
        hook=hook,
        injection_callback=_drain_pending,
        ...
    ))

    return (result.final_content, result.tools_used, result.messages, ...)
```

### 7. Runner 循环 (runner.py)

```python
# runner.py:182-481
async def run(self, spec):
    messages = list(spec.initial_messages)

    for iteration in range(spec.max_iterations):  # 核心设计: for循环
        # 上下文治理
        messages_for_model = self._drop_orphan_tool_results(messages)
        messages_for_model = self._backfill_missing_tool_results(...)
        messages_for_model = self._microcompact(...)
        messages_for_model = self._apply_tool_result_budget(...)
        messages_for_model = self._snip_history(...)

        # 调用 LLM
        response = await self._request_model(
            spec, messages_for_model,
            tools=spec.tools.get_definitions(),  # 工具定义 → LLM
        )

        # 工具调用处理
        if response.has_tool_calls:
            # 构建 assistant message
            assistant_message = build_assistant_message(
                response.content,
                tool_calls=[tc.to_openai_tool_call() for tc in response.tool_calls],
            )
            messages.append(assistant_message)

            # 执行工具
            results = await self._execute_tools(spec, response.tool_calls)

            # 构建 tool messages
            for tool_call, result in zip(response.tool_calls, results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "content": result,
                })

            # 检查是否有注入消息
            injections = await self._drain_injections(spec)
            if injections:
                self._append_injected_messages(messages, injections)
                continue  # 继续下一轮

            continue  # 继续工具调用循环

        # 无工具调用 → 结束
        clean = hook.finalize_content(context, response.content)
        final_content = clean
        messages.append(build_assistant_message(clean))
        break

    return AgentRunResult(
        final_content=final_content,
        messages=messages,
        tools_used=tools_used,
        usage=usage,
        stop_reason=stop_reason,
    )
```

**Runner 核心设计：**

| 设计点 | 实现 | 目的 |
|--------|------|------|
| 循环结构 | `for iteration in range(max_iterations)` | 避免 while 无限循环 |
| 工具调用判断 | `response.has_tool_calls` | LLM 返回 `tool_calls` 字段 |
| 上下文治理 | `_snip_history`, `_microcompact` | 控制 token 使用 |
| 消息注入 | `injection_callback` | 支持中途注入用户消息 |
| 并发工具 | `asyncio.gather` | 安全工具可并行执行 |

## 工具调用机制

### 工具定义流程

```
Tool.description (属性)
    ↓
Tool.to_schema() → OpenAI function schema
    ↓
ToolRegistry.get_definitions() → list[dict]
    ↓
AgentRunner._request_model() → tools 参数
    ↓
LLM API 请求
```

**schema 结构：**

```json
{
  "type": "function",
  "function": {
    "name": "price_history",
    "description": "查询物料的历史价格记录...",
    "parameters": {
      "type": "object",
      "properties": {
        "material_id": {"type": "string", "description": "物料编号"},
        "limit": {"type": "integer", "default": 100}
      },
      "required": ["material_id"]
    }
  }
}
```

### LLM 工具选择原理

1. **LLM 收到 tools 参数**：包含每个工具的 name + description + parameters
2. **模型判断意图**：根据用户消息内容和工具描述匹配
3. **返回 tool_calls**：包含工具名称和参数
4. **Runner 执行工具**：`tool.execute(**params)`
5. **返回工具结果**：作为 `role: "tool"` message 给 LLM

### 工具执行流程

```python
# runner.py:561-587
async def _execute_tools(self, spec, tool_calls):
    batches = self._partition_tool_batches(spec, tool_calls)

    tool_results = []
    for batch in batches:
        if spec.concurrent_tools and len(batch) > 1:
            # 并发执行安全工具
            tool_results.extend(await asyncio.gather(*(
                self._run_tool(spec, tc) for tc in batch
            )))
        else:
            # 串行执行
            for tc in batch:
                tool_results.append(await self._run_tool(spec, tc))

    return results, events, fatal_error


# runner.py:589-659
async def _run_tool(self, spec, tool_call):
    # 准备调用
    tool, params, prep_error = spec.tools.prepare_call(
        tool_call.name, tool_call.arguments
    )
    if prep_error:
        return prep_error

    # 执行
    try:
        result = await tool.execute(**params)
    except Exception as e:
        return f"Error: {e}"

    return result
```

## 会话管理策略

```python
# session/manager.py
class SessionManager:
    def get_or_create(self, key: str) -> Session:
        # 1. 缓存优先
        if key in self._cache:
            return self._cache[key]

        # 2. 加载已有文件
        path = self._session_path(key)
        if path.exists():
            session = self._load_session(path)

        # 3. 创建新会话
        else:
            session = Session(key=key, messages=[], metadata={})

        # 4. 缓存
        self._cache[key] = session
        return session
```

**策略：缓存优先 → 加载/创建 → 缓存**

## 检查点恢复机制

```python
# loop.py:854-926
def _set_runtime_checkpoint(self, session, payload):
    # 保存运行中状态到 session.metadata
    session.metadata["runtime_checkpoint"] = {
        "assistant_message": ...,
        "completed_tool_results": [...],
        "pending_tool_calls": [...],
    }

def _restore_runtime_checkpoint(self, session):
    # 异常中断后恢复未完成的对话
    checkpoint = session.metadata.get("runtime_checkpoint")
    if not checkpoint:
        return False

    # 恢复 assistant message + tool results
    # 补充未完成的 tool calls 为错误消息
    ...
```

## 关键配置参数

| 参数 | 默认值 | 作用 |
|------|--------|------|
| `max_iterations` | 200 | Runner 工具调用循环上限 |
| `context_window_tokens` | 可配置 | 上下文 token 预算 |
| `max_tool_result_chars` | 可配置 | 工具结果截断长度 |
| `session_ttl_minutes` | 0 (禁用) | 会话超时自动归档 |
| `unified_session` | false | 所有消息共享同一 session |

---

*笔记生成时间: 2024-01*