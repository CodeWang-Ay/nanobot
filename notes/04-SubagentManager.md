# SubagentManager — 子 Agent 管理器

> 文件路径: `nanobot/agent/subagent.py`
> 代码行数: 264 行

## 概述

`SubagentManager` 管理后台子 Agent 的执行，用于：
- 派生独立的后台任务
- 执行完成后通过消息总线通知主 Agent
- 支持会话绑定和取消

## 类方法总结

```
class SubagentManager:
    0. __init__(provider, workspace, bus, max_tool_result_chars, ...)   # 初始化：LLM提供商、工作目录、消息总线、工具结果截断长度
    1. spawn(task, label, origin_channel, origin_chat_id, session_key)  # 【核心】派生子 Agent 执行后台任务，返回任务 ID
    2. _run_subagent(task_id, task, label, origin)                      # 执行子 Agent 任务：构建工具→调用 runner→处理结果
    3. _announce_result(task_id, label, task, result, origin, status)   # 通过消息总线向主 Agent 宣告任务完成结果
    4. _format_partial_progress(result)                                 # 格式化部分执行进度（成功步骤 + 失败步骤）
    5. _build_subagent_prompt()                                         # 构建子 Agent 的系统提示（时间上下文 + 技能摘要）
    6. cancel_by_session(session_key)                                   # 取消指定会话的所有子 Agent，返回取消数量
    7. get_running_count()                                              # 返回当前运行的子 Agent 数量
```

## 内部类 _SubagentHook

```
class _SubagentHook(AgentHook):
    0. __init__(task_id)                                                # 初始化：关联的任务 ID
    1. before_execute_tools(context)                                   # 工具执行前日志记录（DEBUG 级别）
```

## 核心流程图

### spawn() — 派生入口

```
spawn(task, label, origin_channel, origin_chat_id, session_key)
    │
    ├─ task_id = uuid[:8]
    ├─ display_label = label or task[:30]
    │
    ↓
asyncio.create_task(_run_subagent(...))  [创建后台任务]
    │
    ├─ 注册到 _running_tasks[task_id]
    ├─ 注册到 _session_tasks[session_key]（可选）
    ├─ 添加 _cleanup 回调（任务完成后自动清理）
    │
    ↓
返回: "Subagent [label] started (id: task_id)"
```

### _run_subagent() — 执行后台任务

```
_run_subagent(task_id, task, label, origin)
    │
    ├─ 构建工具集（不含 message, spawn 工具）
    │   ├─ ReadFileTool, WriteFileTool, EditFileTool
    │   ├─ ListDirTool, GlobTool, GrepTool
    │   ├─ ExecTool（可选）
    │   └─ WebSearchTool, WebFetchTool（可选）
    │
    ├─ _build_subagent_prompt() → 系统提示
    │   ├─ ContextBuilder._build_runtime_context()
    │   └─ SkillsLoader.build_skills_summary()
    │
    ├─ 构建 messages: [system, user]
    │
    ↓
runner.run(AgentRunSpec)  [调用 AgentRunner]
    │
    ├─ max_iterations=15
    ├─ fail_on_tool_error=True（遇错即停）
    ├─ hook=_SubagentHook(task_id)
    │
    ├─ stop_reason == "tool_error" → 部分进度
    ├─ stop_reason == "error" → 错误消息
    ├─ 正常完成 → final_content
    │
    ↓
_announce_result(task_id, label, task, result, origin, status)
    │
    ├─ render_template("agent/subagent_announce.md")
    │   ├─ label, status_text, task, result
    │
    ├─ InboundMessage(channel="system", sender_id="subagent", ...)
    │
    ↓
bus.publish_inbound(msg)  [注入到主 Agent 消息总线]
    │
    ↓
主 Agent 收到 system 消息 → 触发 _process_message()
```

### _announce_result() — 宣告结果

```
_announce_result(task_id, label, task, result, origin, status)
    │
    ├─ status_text = "completed successfully" if status == "ok" else "failed"
    │
    ├─ render_template("agent/subagent_announce.md")
    │   ├─ label
    │   ├─ status_text
    │   ├─ task
    │   ├─ result
    │
    ├─ InboundMessage:
    │   ├─ channel="system"
    │   ├─ sender_id="subagent"
    │   ├─ chat_id=f"{origin['channel']}:{origin['chat_id']}"
    │   ├─ content=announce_content
    │
    ↓
bus.publish_inbound(msg)
```

## 子 Agent 与主 Agent 的区别

| 特性 | 主 Agent (AgentLoop) | 子 Agent (SubagentManager) |
|------|---------------------|-------------------------|
| **工具集** | 全部工具（含 message, spawn, cron 等） | 精简工具（文件、搜索、Shell、Web） |
| **消息发送** | 通过 message 工具主动发送 | 完成后注入 system 消息 |
| **会话管理** | 持久化会话历史 | 无会话，单次执行 |
| **上下文** | 包含历史消息 + 记忆 + skills | 仅 system + user 消息 |
| **错误处理** | 继续/重试/恢复 | fail_on_tool_error=True |
| **迭代限制** | 可配置 max_iterations | 固定 15 次迭代 |
| **派生能力** | 可 spawn 子 Agent | 不含 spawn 工具（不可再派生） |

## 消息宣告格式

```
# subagent_announce.md 模板

Subagent [label] status_text.

Task: task

Result:
result
```

## 会话绑定与清理

```
spawn(..., session_key="cli:direct")
    │
    ├─ _session_tasks["cli:direct"].add(task_id)
    │
    ↓
主 Agent 执行 /stop 命令
    │
    ↓
cancel_by_session("cli:direct")
    │
    ├─ 查找 _session_tasks["cli:direct"] → {task_id_1, task_id_2}
    ├─ 对每个 task: task.cancel()
    ├─ await asyncio.gather(*tasks)
    │
    ↓
返回取消数量

_cleanup 回调（任务完成后）
    │
    ├─ _running_tasks.pop(task_id)
    ├─ _session_tasks[session_key].discard(task_id)
    ├─ 若集合为空 → del _session_tasks[session_key]
```

## 与 AgentLoop 的集成点

```
AgentLoop.__init__()
    │
    ├─ SubagentManager(provider, workspace, bus, ...)
    │
    ↓
AgentLoop._register_default_tools()
    │
    ├─ SpawnTool(subagent_manager=self.subagents)
    │
    ↓
用户调用 spawn 工具
    │
    ├─ subagent_manager.spawn(task, ...)
    │
    ↓
子 Agent 完成后 → bus.publish_inbound(InboundMessage(channel="system", sender_id="subagent", ...))
    │
    ↓
AgentLoop.run() 收到 system 消息
    │
    ├─ _process_message() 处理
    │   ├─ channel == "system" → 解析 origin
    │   ├─ sender_id == "subagent" → current_role="assistant"
    │
    ↓
主 Agent 继续对话，将子 Agent 结果纳入上下文
```