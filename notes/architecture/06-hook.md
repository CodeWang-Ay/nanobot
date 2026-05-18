# nanobot Hook 机制

## 概述

nanobot 的 Hook 是一个**Agent 内部生命周期钩子系统**，用于在 Agent 执行循环的各个关键节点注入自定义行为。

与 Claude Code 的 Hook 不同：
- Claude Code Hook：用户工作流自动化，由 CLI harness 在外部拦截
- nanobot Hook：Agent 内部行为扩展，由 AgentRunner 在执行循环中调用

## 核心架构

### 1. AgentHook 基类

定义 6 个可覆盖的钩子方法：

```python
class AgentHook:
    def wants_streaming(self) -> bool:
        # 是否启用流式输出
        return False
    
    async def before_iteration(self, context: AgentHookContext) -> None:
        # 每次迭代开始前
        pass
    
    async def on_stream(self, context: AgentHookContext, delta: str) -> None:
        # 流式输出增量文本
        pass
    
    async def on_stream_end(self, context: AgentHookContext, *, resuming: bool) -> None:
        # 流式输出结束
        pass
    
    async def before_execute_tools(self, context: AgentHookContext) -> None:
        # 执行工具前
        pass
    
    async def after_iteration(self, context: AgentHookContext) -> None:
        # 每次迭代结束后
        pass
    
    def finalize_content(self, context: AgentHookContext, content: str | None) -> str | None:
        # 最终内容处理（管道式）
        return content
```

### 2. AgentHookContext 状态

每次迭代的上下文数据：

```python
@dataclass(slots=True)
class AgentHookContext:
    iteration: int              # 当前迭代次数
    messages: list[dict]        # 消息历史
    response: LLMResponse       # LLM 响应
    usage: dict[str, int]       # token 使用统计
    tool_calls: list            # 工具调用请求
    tool_results: list          # 工具执行结果
    tool_events: list           # 工具事件记录
    final_content: str          # 最终输出内容
    stop_reason: str            # 结束原因
    error: str                  # 错误信息
```

### 3. CompositeHook 组合模式

组合多个 hook，实现**扇出 + 错误隔离**：

```python
class CompositeHook(AgentHook):
    def __init__(self, hooks: list[AgentHook]):
        self._hooks = list(hooks)
    
    # 特性：
    # 1. 所有 hook 按顺序执行
    # 2. 单个 hook 抛错不会影响其他 hook（除非 reraise=True）
    # 3. finalize_content 是管道式处理（无隔离）
```

## 执行流程

在 `AgentRunner.run()` 中的调用时序：

```
for iteration in range(max_iterations):
    │
    ├── before_iteration(context)         # 迭代开始
    │
    ├── 调用 LLM
    │   │
    │   └── on_stream(delta)              # 流式输出（可选）
    │
    ├── 判断是否有工具调用
    │   │
    │   ├── [有工具调用]
    │   │   ├── on_stream_end(resuming=True)  # 流式暂停
    │   │   ├── before_execute_tools(context) # 执行工具前
    │   │   ├── 执行工具
    │   │   └── after_iteration(context)      # 迭代结束，继续循环
    │   │
    │   └── [无工具调用，最终响应]
    │       ├── finalize_content(content)     # 内容处理
    │       ├── on_stream_end(resuming=False) # 流式结束
    │       └── after_iteration(context)      # 迭代结束，退出循环
```

## 使用方式

### 方式一：SDK 使用

```python
from nanobot import Nanobot
from nanobot.agent.hook import AgentHook, AgentHookContext

class MyHook(AgentHook):
    async def before_iteration(self, context: AgentHookContext) -> None:
        print(f"开始第 {context.iteration} 次迭代")
    
    async def after_iteration(self, context: AgentHookContext) -> None:
        print(f"使用了 {context.usage.get('prompt_tokens', 0)} tokens")
    
    async def before_execute_tools(self, context: AgentHookContext) -> None:
        print(f"即将执行: {[tc.name for tc in context.tool_calls]}")

bot = Nanobot.from_config()
result = await bot.run("Hello", hooks=[MyHook()])
```

### 方式二：AgentLoop 构造函数

```python
from nanobot.agent.loop import AgentLoop

loop = AgentLoop(
    bus=bus,
    provider=provider,
    workspace=workspace,
    hooks=[MyHook()],  # 内置 hook
)
```

### 方式三：Channel 通过回调间接使用

```python
# Channel 调用方式（内部会包装成 _LoopHook）
await agent_loop.process_direct(
    message,
    session_key="telegram:123",
    on_progress=self._send_progress,    # 进度回调
    on_stream=self._send_streaming,     # 流式回调
    on_stream_end=self._finalize,       # 结束回调
)
```

## 内置实现：_LoopHook

`AgentLoop` 内部的核心 hook 实现：

```python
class _LoopHook(AgentHook):
    """Core hook for the main loop."""
    
    def __init__(
        self,
        agent_loop: AgentLoop,
        on_progress: Callable | None = None,
        on_stream: Callable | None = None,
        on_stream_end: Callable | None = None,
        channel: str = "cli",
        chat_id: str = "direct",
    ):
        super().__init__(reraise=True)  # 错误直接抛出
        self._loop = agent_loop
        self._on_progress = on_progress
        self._on_stream = on_stream
        self._on_stream_end = on_stream_end
    
    # 功能：
    # 1. on_stream: 过滤 <think> 标签，增量输出
    # 2. before_execute_tools: 显示进度、设置工具上下文
    # 3. after_iteration: 记录 token 使用日志
    # 4. finalize_content: 过滤 <think> 标签
```

## 钩子方法详解

| 方法 | 调用时机 | 用途 | 是否可覆盖 |
|------|----------|------|------------|
| `wants_streaming()` | 创建 hook 时 | 判断是否启用流式 | ✓ |
| `before_iteration()` | 每次迭代开始 | 记录日志、初始化状态 | ✓ |
| `on_stream()` | 流式输出增量 | 实时显示响应 | ✓ |
| `on_stream_end()` | 流式结束 | 关闭渲染器 | ✓ |
| `before_execute_tools()` | 工具执行前 | 显示进度、设置上下文 | ✓ |
| `after_iteration()` | 每次迭代结束 | 统计 token、清理状态 | ✓ |
| `finalize_content()` | 内容最终处理 | 过滤/转换输出 | ✓ |

## 设计特点

1. **错误隔离**：单个 hook 失败不会崩溃 Agent 循环（`CompositeHook._for_each_hook_safe`）
2. **流式支持**：`wants_streaming()` + `on_stream()` 实现实时输出
3. **组合模式**：`CompositeHook` 支持多 hook 并行执行
4. **状态透明**：`AgentHookContext` 暴露完整迭代状态
5. **内容管道**：`finalize_content` 可链式处理输出

## 与 Claude Code Hook 对比

| 特性 | Claude Code Hook | nanobot Hook |
|------|------------------|--------------|
| 配置方式 | `~/.claude/settings.json` | Python 代码传入 |
| 执行主体 | CLI harness（外部进程） | AgentLoop 内部（Python 类） |
| 触发时机 | 用户操作层面 | Agent 执行层面 |
| 用途 | 自动化工作流、拦截操作 | 扩展 Agent 内部行为 |
| Hook 类型 | PreToolUse, PostToolUse, Stop, Notification | before_iteration, on_stream, before_execute_tools 等 |

```
Claude Code Hook 流程:
  用户 → CLI → [Hook] → 工具执行 → [Hook] → 结果
         ↑ harness 在外部拦截

nanobot Hook 流程:
  AgentLoop → before_iteration → LLM → on_stream → before_execute_tools → 工具 → after_iteration
              ↑ Agent 内部生命周期节点
```

## 相关文件

- `nanobot/agent/hook.py` - AgentHook、AgentHookContext、CompositeHook 定义
- `nanobot/agent/runner.py` - AgentRunner.run() 中调用 hook
- `nanobot/agent/loop.py` - _LoopHook 内置实现、AgentLoop._extra_hooks
- `nanobot/nanobot.py` - Nanobot.run() hooks 参数
- `tests/agent/test_hook_composite.py` - hook 单元测试