# AgentRunner — Agent 执行引擎

> 文件路径: `nanobot/agent/runner.py`
> 代码行数: 915 行

## 概述

`AgentRunner` 是纯粹的 LLM + 工具执行引擎，不涉及消息总线/会话等外部依赖。核心职责：
- 调用 LLM（流式/非流式）
- 执行工具调用（并发/串行）
- 管理上下文窗口
- 处理重试和异常恢复

## 配置数据类

```
@dataclass AgentRunSpec:
    initial_messages    # 初始消息列表
    tools               # ToolRegistry 工具注册表
    model               # 模型名称
    max_iterations      # 最大迭代次数
    max_tool_result_chars  # 工具结果截断长度
    hook                # AgentHook 钩子实例
    error_message       # 错误消息模板
    concurrent_tools    # 是否并发执行工具
    fail_on_tool_error  # 工具错误是否终止
    context_window_tokens  # 上下文窗口 token 数
    checkpoint_callback    # 检查点回调
    injection_callback     # 消息注入回调
```

## 结果数据类

```
@dataclass AgentRunResult:
    final_content    # 最终响应内容
    messages         # 完整消息历史
    tools_used       # 使用过的工具列表
    usage            # token 使用量统计
    stop_reason      # 停止原因 (completed/error/max_iterations/empty_final_response)
    error            # 错误信息
    tool_events      # 工具执行事件列表
    had_injections   # 是否有中途注入的消息
```

## 类方法总结

```
class AgentRunner:
    0. __init__(provider)                                  # 初始化 LLM 提供商
    1. _merge_message_content(left, right)                 # 合并两个消息内容块（字符串或列表）
    2. _append_injected_messages(messages, injections)     # 将注入的用户消息追加到消息列表（保持角色交替）
    3. _drain_injections(spec)                             # 通过回调获取待注入的用户消息（限制最大数量）
    4. run(spec)                                           # 【核心方法】执行完整的 Agent 迭代循环
    5. _build_request_kwargs(spec, messages, tools)        # 构建发给 LLM 的请求参数字典
    6. _request_model(spec, messages, hook, context)       # 调用 LLM（支持流式和非流式）
    7. _request_finalization_retry(spec, messages)         # 空响应重试：追加提示消息后重新请求
    8. _usage_dict(usage)                                  # 将 usage 字典转换为整数值字典
    9. _accumulate_usage(target, addition)                 # 累加 token 使用量到目标字典
    10. _merge_usage(left, right)                          # 合并两个 usage 字典
    11. _execute_tools(spec, tool_calls, lookup_counts)    # 执行所有工具调用（支持并发）
    12. _run_tool(spec, tool_call, lookup_counts)          # 执行单个工具调用，返回结果+事件+错误
    13. _emit_checkpoint(spec, payload)                    # 发送检查点回调（保存中断恢复状态）
    14. _append_final_message(messages, content)           # 追加最终响应消息到消息列表
    15. _append_model_error_placeholder(messages)          # 追加模型错误占位消息
    16. _normalize_tool_result(spec, id, name, result)     # 规范化工具结果（确保非空、截断过长）
    17. _drop_orphan_tool_results(messages)                # 删除无匹配 tool_call_id 的孤立工具结果
    18. _backfill_missing_tool_results(messages)           # 为未响应的 tool_use 块插入合成错误结果
    19. _microcompact(messages)                            # 微压缩：将旧的 compactable 工具结果替换为摘要
    20. _apply_tool_result_budget(spec, messages)          # 应用工具结果截断预算
    21. _snip_history(spec, messages)                      # 根据上下文窗口裁剪历史消息
    22. _partition_tool_batches(spec, tool_calls)          # 将工具调用分区为可并发执行的批次
```

## 核心流程图 (run 方法)

```
run(spec) [执行入口]
    │
    ├─ 构建初始 messages 列表
    │
    ↓
for iteration in range(max_iterations):
    │
    ├─ _drop_orphan_tool_results()     # 清理孤立工具结果
    ├─ _backfill_missing_tool_results()# 补充缺失的工具结果
    ├─ _microcompact()                 # 微压缩旧工具结果
    ├─ _apply_tool_result_budget()     # 应用结果截断预算
    ├─ _snip_history()                 # 裁剪超出上下文窗口的历史
    │
    ↓
    hook.before_iteration(context)     # 钩子：迭代开始
    │
    ↓
    _request_model()                   # 调用 LLM（流式/非流式）
    │
    ├─ 有 tool_calls？
    │   ├─ hook.on_stream_end(resuming=True)  # 流式结束（继续）
    │   ├─ append assistant message
    │   ├─ _emit_checkpoint()          # 保存检查点
    │   ├─ hook.before_execute_tools() # 钩子：工具执行前
    │   ├─ _execute_tools()            # 执行所有工具
    │   │   └─ _partition_tool_batches() → _run_tool() (并发/串行)
    │   ├─ append tool results
    │   ├─ _drain_injections()         # 检查待注入消息
    │   ├─ hook.after_iteration()      # 钩子：迭代结束
    │   └─ continue (下一轮迭代)
    │
    ├─ 空响应？
    │   ├─ 重试计数 < MAX_EMPTY_RETRIES → continue
    │   ├─ _request_finalization_retry() → 再次尝试
    │   └─ 最终失败 → stop_reason="empty_final_response"
    │
    ├─ length 截断？
    │   ├─ append assistant + length_recovery 消息
    │   └─ continue (继续生成)
    │
    ├─ 检查 mid-turn injections
    │   ├─ 有注入消息 → append → continue
    │
    ├─ error？
    │   └─ stop_reason="error"
    │
    ↓
hook.finalize_content()                # 过滤最终内容
hook.on_stream_end(resuming=False)     # 流式结束（完成）
hook.after_iteration()                 # 钩子：迭代结束
break                                  # 正常退出循环
    │
    ↓
return AgentRunResult                  # 返回执行结果
```

## 上下文治理阶段

| 处理阶段 | 方法 | 说明 |
|---------|------|------|
| **上下文治理** | `_drop_orphan_tool_results`, `_backfill_missing_tool_results`, `_microcompact`, `_apply_tool_result_budget`, `_snip_history` | 管理消息历史，适配上下文窗口 |
| **LLM 调用** | `_request_model` | 流式/非流式请求，支持重试 |
| **工具执行** | `_execute_tools`, `_run_tool`, `_partition_tool_batches` | 并发执行工具，处理错误 |
| **状态保存** | `_emit_checkpoint` | 保存中断恢复点 |
| **消息注入** | `_drain_injections`, `_append_injected_messages` | mid-turn 用户消息注入 |
| **异常处理** | `_request_finalization_retry`, 空响应/截断恢复 | 多种错误恢复策略 |

## 与 AgentLoop 的关系

```
AgentLoop (产品层)
    │  调用
    ↓
AgentRunner.run() (引擎层)
    │  调用
    ↓
LLMProvider.chat() (提供商层)
```

- **AgentLoop**: 处理消息总线、会话管理、命令路由、响应发送等产品层逻辑
- **AgentRunner**: 纯粹的 LLM + 工具执行引擎，不涉及消息总线/会话等外部依赖

## 工具并发执行策略

```
_partition_tool_batches(tool_calls)
    │
    ├─ 遍历 tool_calls
    │   ├─ get_tool(name) → 获取工具实例
    │   ├─ tool.concurrency_safe → 判断是否可并发
    │   │
    │   ├─ 可并发 → 加入 current batch
    │   ├─ 不可并发 → 先提交 current batch，再单独批次
    │
    ↓
返回 batches: [[tool_call], [tool_call, tool_call], ...]

_execute_tools(batches)
    │
    ├─ 对每个 batch:
    │   ├─ len(batch) > 1 且 concurrent_tools=True
    │   │   └─ asyncio.gather(*(_run_tool(tc) for tc in batch))  # 并发
    │   ├─ 否则
    │   │   └─ 顺序执行 _run_tool(tc)  # 串行
    │
    ↓
返回 (results, events, fatal_error)
```