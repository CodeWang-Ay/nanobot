# nanobot agent/ 模块阅读笔记索引

> 项目: nanobot
> 核心代码目录: `nanobot/agent/`
> 核心代码量: 约 3,533 行

## 文件索引

| 序号 | 文件 | 类名 | 代码行数 | 职责 |
|------|------|------|----------|------|
| 01 | [AgentLoop.md](./01-AgentLoop.md) | AgentLoop, _LoopHook | 917 | Agent 核心处理引擎 |
| 02 | [AgentRunner.md](./02-AgentRunner.md) | AgentRunner, AgentRunSpec, AgentRunResult | 915 | LLM + 工具执行引擎 |
| 03 | [SkillsLoader.md](./03-SkillsLoader.md) | SkillsLoader | 233 | 技能加载管理器 |
| 04 | [SubagentManager.md](./04-SubagentManager.md) | SubagentManager, _SubagentHook | 264 | 子 Agent 管理器 |
| 05 | [MemorySystem.md](./05-MemorySystem.md) | MemoryStore, Consolidator, Dream | 766 | 三层记忆系统 |
| 06 | [ContextBuilder.md](./06-ContextBuilder.md) | ContextBuilder | 200 | 上下文构建器 |
| 07 | [AutoCompact.md](./07-AutoCompact.md) | AutoCompact | 115 | 自动压缩器 |
| 08 | [AgentFlow.md](./08-AgentFlow.md) | - | - | Agent 执行流程完整链路 |

## 核心架构关系

```
AgentLoop (产品层)
    │
    ├─ ContextBuilder → 构建 system prompt + messages
    │   ├─ MemoryStore → 读取长期记忆
    │   ├─ SkillsLoader → 加载技能
    │   └─ MemoryStore → 读取历史
    │
    ├─ SessionManager → 会话管理
    │
    ├─ Consolidator → token-budget 触发合并
    │   └─ MemoryStore → 写入 history.jsonl
    │
    ├─ AutoCompact → 超时会话自动归档
    │   └─ Consolidator → LLM 摘要
    │
    ├─ SubagentManager → 后台任务执行
    │   └─ AgentRunner → 执行子 Agent
    │
    ├─ AgentRunner (引擎层)
    │   ├─ LLM 调用 (流式/非流式)
    │   ├─ 工具执行 (并发)
    │   ├─ 上下文治理
    │   └─ 异常恢复
    │
    └─ Dream (定时任务)
        └─ AgentRunner → 编辑长期记忆文件
```

## 数据流向

```
用户消息
    ↓
MessageBus (消息总线)
    ↓
AgentLoop.run() → 消费 inbound
    ↓
AgentLoop._process_message()
    ├─ SessionManager.get_or_create()
    ├─ AutoCompact.prepare_session() → 摘要
    ├─ Consolidator.maybe_consolidate_by_tokens() → 合并
    ├─ ContextBuilder.build_messages() → 构建
    │   ├─ build_system_prompt()
    │   │   ├─ identity + bootstrap + memory + skills + history
    │   └─ build user message + runtime context
    ↓
AgentLoop._run_agent_loop()
    ↓
AgentRunner.run()
    ├─ LLM 调用 + 工具执行
    ├─ 上下文治理 (snip/microcompact)
    └─ 消息注入
    ↓
AgentLoop._save_turn() → 持久化
    ↓
SessionManager.save()
    ↓
MemoryStore.append_history() → history.jsonl
    ↓
Dream.run() (定时)
    ├─ 处理 history.jsonl
    └─ 编辑 MEMORY.md / SOUL.md / USER.md
    ↓
下次对话时，ContextBuilder 加载更新的记忆
```

## 三层记忆架构

| 层级 | 类 | 触发条件 | 输出 |
|------|-----|---------|------|
| 存储层 | MemoryStore | 每次对话结束 | history.jsonl |
| 轻量合并 | Consolidator | token 超限 | LLM 摘要 → history.jsonl |
| 重量处理 | Dream | cron 定时 | 编辑 MEMORY.md 等 |

## 核心类职责速查

| 类 | 核心方法 | 主要职责 |
|-----|---------|---------|
| **AgentLoop** | `run()`, `_process_message()` | 消息总线 → 会话管理 → Agent 执行 → 响应发送 |
| **AgentRunner** | `run()` | LLM 调用 + 工具执行 + 上下文治理 + 异常恢复 |
| **ContextBuilder** | `build_system_prompt()`, `build_messages()` | 组装系统提示 + 历史消息 + 运行时元数据 |
| **MemoryStore** | `append_history()`, `read_memory()` | 纯文件 I/O（MEMORY.md, history.jsonl 等） |
| **Consolidator** | `archive()`, `maybe_consolidate_by_tokens()` | token-budget 触发的消息摘要合并 |
| **Dream** | `run()` | 两阶段处理：分析 → 编辑长期记忆文件 |
| **SkillsLoader** | `load_skill()`, `build_skills_summary()` | 加载 SKILL.md 技能文件 |
| **SubagentManager** | `spawn()`, `_run_subagent()` | 派生后台子 Agent 执行任务 |
| **AutoCompact** | `check_expired()`, `_archive()` | 超时会话自动归档 + 摘要生成 |

## 钩子系统

| 钩子类 | 使用场景 | 关键回调 |
|-------|---------|---------|
| `_LoopHook` | AgentLoop → AgentRunner | `on_stream`, `before_execute_tools`, `finalize_content` |
| `_SubagentHook` | SubagentManager → AgentRunner | `before_execute_tools` (日志) |
| `AgentHook` | 基类接口 | `before_iteration`, `on_stream_end`, `after_iteration` 等 |

## 配置参数参考

| 参数 | 默认值 | 影响组件 |
|------|--------|---------|
| `max_iterations` | 可配置 | AgentRunner 工具调用迭代上限 |
| `context_window_tokens` | 可配置 | Consolidator 合并触发阈值 |
| `session_ttl_minutes` | 0 (禁用) | AutoCompact 超时归档 |
| `max_tool_result_chars` | 可配置 | 工具结果截断长度 |
| `max_batch_size` | 20 | Dream 每批处理条目数 |

---

*阅读笔记生成时间: 2024-01*