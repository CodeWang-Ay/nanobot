# AgentLoop — Agent 核心处理引擎

> 文件路径: `nanobot/agent/loop.py`
> 代码行数: 917 行

## 概述

`AgentLoop` 是 nanobot 的核心处理引擎，负责：
1. 接收消息总线 (MessageBus) 的消息
2. 构建上下文 (历史、记忆、技能)
3. 调用 LLM
4. 执行工具调用
5. 发送响应回消息总线

## 类方法总结

```
class AgentLoop:
    0. __init__(bus, provider, workspace, ...)           # 初始化：消息总线、LLM提供商、工作目录、会话管理器、工具注册、子Agent管理器等
    1. _register_default_tools()                         # 注册内置工具：文件读写、Shell执行、搜索、Web、消息、Cron等
    2. _connect_mcp()                                    # 连接 MCP (Model Context Protocol) 服务器
    3. _set_tool_context(channel, chat_id, message_id)   # 设置工具执行的上下文信息（当前通道、会话、消息ID）
    4. _strip_think(text)                                # 过滤 <think></think> 推理块内容
    5. _tool_hint(tool_calls)                            # 格式化工具调用为简洁提示文本
    6. _effective_session_key(msg)                       # 计算有效的会话键（支持统一会话模式）
    7. _run_agent_loop(messages, session, ...)           # 核心迭代循环：调用 runner.run() 执行LLM对话+工具调用
    8. run()                                             # 主事件循环：从 bus 消费 inbound 消息，分发为异步任务
    9. _dispatch(msg)                                    # 消息分发：会话级串行锁 + 并发控制 + pending队列管理
    10. _process_message(msg, ...)                       # 单条消息完整处理流程：会话获取→命令处理→上下文构建→Agent执行→响应发送
    11. _sanitize_persisted_blocks(content, ...)         # 过滤/截断多模态内容块，准备持久化到会话历史
    12. _save_turn(session, messages, skip)              # 保存本轮对话到会话历史，截断过长的工具结果
    13. _set_runtime_checkpoint(session, payload)        # 设置运行时检查点（保存中断时的状态）
    14. _clear_runtime_checkpoint(session)               # 清除运行时检查点
    15. _checkpoint_message_key(message)                 # 计算消息的唯一键（用于检查点恢复时去重）
    16. _restore_runtime_checkpoint(session)             # 从检查点恢复未完成的对话轮次（异常中断后恢复）
    17. process_direct(content, ...)                     # 直接处理消息（绕过消息总线，用于CLI/API直接调用）
    18. stop()                                           # 停止主循环，取消所有活跃任务和后台任务
    19. close_mcp()                                      # 关闭所有 MCP 服务器连接
    20. _schedule_background(coro)                       # 安排后台异步任务（如记忆合并、会话清理）
```

## 核心流程图

```
run() [主循环]
    ↓ 消费 inbound 消息
_dispatch() [分发]
    ↓ 会话锁 + pending队列
_process_message() [处理]
    ├─ sessions.get_or_create()
    ├─ auto_compact.prepare_session()
    ├─ commands.dispatch() (斜杠命令)
    ├─ consolidator.maybe_consolidate()
    ↓
context.build_messages() [构建上下文]
    ↓
_run_agent_loop() [执行Agent]
    ↓ runner.run() → LLM + 工具调用
_save_turn() + sessions.save() [持久化]
    ↓
bus.publish_outbound() [发送响应]
```

## 内部类 _LoopHook

```
class _LoopHook(AgentHook):
    0. __init__(agent_loop, on_progress, on_stream, ...) # 初始化回调函数
    1. wants_streaming()                                 # 返回是否需要流式输出
    2. on_stream(context, delta)                         # 流式增量内容回调（过滤 think 块）
    3. on_stream_end(context, resuming)                  # 流式结束回调
    4. before_execute_tools(context)                     # 工具执行前回调（发送进度提示）
    5. after_iteration(context)                          # 每轮迭代后回调（记录 token 使用量）
    6. finalize_content(context, content)                # 最终内容处理（过滤 think 块）
```

### _LoopHook 角色

`_LoopHook` 是 `AgentLoop` 与 `AgentRunner` 之间的桥梁钩子，实现了 `AgentHook` 接口：

| 钩子方法 | 触发时机 | 主要职责 |
|---------|---------|---------|
| `on_stream(delta)` | LLM 流式响应时 | 过滤 `<think>` 推理块，精确计算增量内容 |
| `on_stream_end(resuming)` | 流式结束 | `resuming=True` 表示工具调用即将开始 |
| `before_execute_tools(context)` | 工具执行前 | 发送进度提示 + 设置工具上下文 |
| `after_iteration(context)` | 每轮迭代后 | 记录 token 使用量日志 |
| `finalize_content(content)` | 最终输出前 | 再次过滤 `<think>` 推理块 |

## 关键设计点

1. **会话隔离**: 每个 session_key 有独立的 `asyncio.Lock`，同一会话串行处理
2. **并发控制**: `_concurrency_gate` 限制全局并发任务数
3. **消息注入**: `_pending_queue` 支持在 Agent 运行中途注入用户后续消息
4. **命令优先级**: `/stop` 等优先命令直接处理，不进入正常流程
5. **检查点恢复**: 异常中断后可通过 `_runtime_checkpoint` 恢复未完成的对话轮次