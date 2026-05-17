# MemorySystem — 记忆系统

> 文件路径: `nanobot/agent/memory.py`
> 代码行数: 766 行

## 概述

`memory.py` 包含三层记忆架构：
- **MemoryStore**: 纯文件 I/O 层，管理 MEMORY.md、history.jsonl 等
- **Consolidator**: 轻量级合并，当上下文超限时摘要旧消息
- **Dream**: 重量级处理，定时处理历史条目并编辑长期记忆文件

## 文件结构

```
workspace/
├── SOUL.md                    # Agent 核心身份/性格定义
├── USER.md                    # 用户偏好/信息
└── memory/
    ├── MEMORY.md              # 长期记忆事实
    ├── history.jsonl          # 合并后的历史摘要（JSONL 格式）
    ├── .cursor                # history.jsonl 最后写入的 cursor
    ├── .dream_cursor          # Dream 最后处理的 cursor
    └── HISTORY.md.bak         # 旧版迁移备份（可选）
```

---

## MemoryStore — 纯文件 I/O 层

### 类方法总结

```
class MemoryStore:
    0. __init__(workspace, max_history_entries)                    # 初始化：工作目录、历史条目上限
    1. git → GitStore                                              # Git 存储对象（用于自动提交）
    2. read_file(path)                                             # 通用文件读取（返回空串若不存在）
    3. _maybe_migrate_legacy_history()                             # 一次性迁移：HISTORY.md → history.jsonl
    4. _parse_legacy_history(text)                                 # 解析旧版 HISTORY.md 格式
    5. _split_legacy_history_chunks(text)                          # 按时间戳分割旧版历史块
    6. _should_start_new_legacy_chunk(line, current)              # 判断是否应开始新块（时间戳行）
    7. _is_raw_legacy_chunk(lines)                                 # 判断是否为 [RAW] 原始消息块
    8. _legacy_fallback_timestamp()                                # 获取旧版文件修改时间作为备用时间戳
    9. _next_legacy_backup_path()                                  # 生成备份文件路径（HISTORY.md.bak.N）
    10. read_memory()                                              # 读取 MEMORY.md 内容
    11. write_memory(content)                                      # 写入 MEMORY.md 内容
    12. read_soul()                                                # 读取 SOUL.md 内容
    13. write_soul(content)                                        # 写入 SOUL.md 内容
    14. read_user()                                                # 读取 USER.md 内容
    15. write_user(content)                                        # 写入 USER.md 内容
    16. get_memory_context()                                       # 构建注入上下文的记忆文本
    17. append_history(entry)                                      # 【核心】追加条目到 history.jsonl，返回 cursor
    18. _next_cursor()                                             # 计算下一个自增 cursor 值
    19. read_unprocessed_history(since_cursor)                     # 读取未处理的历史条目（cursor > since_cursor）
    20. compact_history()                                          # 压缩历史：删除超出上限的旧条目
    21. _read_entries()                                            # 读取所有 history.jsonl 条目
    22. _read_last_entry()                                         # 高效读取最后一条记录
    23. _write_entries(entries)                                    # 覆盖写入 history.jsonl
    24. get_last_dream_cursor()                                    # 获取 Dream 处理的最后 cursor
    25. set_last_dream_cursor(cursor)                              # 设置 Dream 处理的最后 cursor
    26. _format_messages(messages)                                 # 格式化消息列表为可读文本
    27. raw_archive(messages)                                      # 【降级】直接写入原始消息（无 LLM 摘要）
```

### history.jsonl 格式

```json
{"cursor": 1, "timestamp": "2024-01-15 10:30", "content": "用户询问了..."}
{"cursor": 2, "timestamp": "2024-01-15 11:00", "content": "讨论了..."}
...
```

### append_history() 流程

```
append_history(entry)
    │
    ├─ _next_cursor() → 自增 cursor
    ├─ strip_think(entry) → 过滤 <think> 思考块
    ├─ 构建 record: {"cursor", "timestamp", "content"}
    │
    ├─ 写入 history.jsonl（追加一行 JSON）
    ├─ 更新 .cursor 文件
    │
    ↓
返回 cursor 值
```

---

## Consolidator — 轻量级合并

### 类方法总结

```
class Consolidator:
    0. __init__(store, provider, model, sessions, ...)             # 初始化：存储、LLM 提供商、会话管理器
    1. get_lock(session_key)                                       # 获取会话级合并锁（防止并发）
    2. pick_consolidation_boundary(session, tokens_to_remove)      # 选择合并边界（user-turn 分界点）
    3. _cap_consolidation_boundary(session, end_idx)               # 限制块大小（不超过 MAX_CHUNK_MESSAGES）
    4. estimate_session_prompt_tokens(session)                     # 估算会话提示词 token 数量
    5. archive(messages)                                           # 【核心】通过 LLM 摘要消息并写入 history.jsonl
    6. maybe_consolidate_by_tokens(session)                        # 【核心】循环合并直到符合 token 预算
```

### maybe_consolidate_by_tokens() 流程

```
maybe_consolidate_by_tokens(session)
    │
    ├─ get_lock(session.key) → 会话锁
    │
    ├─ 计算 budget = context_window - max_completion - safety_buffer
    ├─ 计算 target = budget // 2
    │
    ├─ estimate_session_prompt_tokens(session) → 当前 token 数
    │
    ├─ estimated < budget → 无需合并，返回
    │
    ↓
for round_num in range(MAX_CONSOLIDATION_ROUNDS):  # 最多 5 轮
    │
    ├─ pick_consolidation_boundary(session, tokens_to_remove)
    │   └─ 找到 user-turn 边界点
    │
    ├─ _cap_consolidation_boundary(session, end_idx)
    │   └─ 限制块大小 ≤ 60 条消息
    │
    ├─ chunk = session.messages[last_consolidated:end_idx]
    │
    ↓
    archive(chunk)
        │
        ├─ _format_messages(messages) → 格式化文本
        ├─ provider.chat_with_retry() → LLM 摘要
        │   ├─ system: "consolidator_archive.md" 模板
        │   └─ user: formatted messages
        │
        ├─ store.append_history(summary) → 写入 history.jsonl
        │   └─ 若失败 → raw_archive(messages) 降级
        │
        ↓
    session.last_consolidated = end_idx
    sessions.save(session)
    
    ├─ 重新估算 token
    ├─ estimated <= target → 完成，返回
```

---

## Dream — 重量级处理

### 类方法总结

```
class Dream:
    0. __init__(store, provider, model, max_batch_size, ...)       # 初始化：存储、LLM 提供商、批次大小
    1. _build_tools()                                              # 构建 Dream 专用工具集（read/edit/write）
    2. _list_existing_skills()                                     # 列出已存在的技能（用于去重上下文）
    3. run()                                                       # 【核心】处理未处理的历史条目
```

### run() — 两阶段处理流程

```
run()
    │
    ├─ store.get_last_dream_cursor() → last_cursor
    ├─ store.read_unprocessed_history(since_cursor) → 未处理条目
    │
    ├─ batch = entries[:max_batch_size]（最多 20 条）
    │
    ├─ 构建历史文本："[timestamp] content"
    ├─ 构建文件上下文：MEMORY.md + SOUL.md + USER.md
    │
    ↓
Phase 1: 分析（纯 LLM 调用）
    │
    ├─ system: "dream_phase1.md" 模板
    ├─ user: history_text + file_context
    ├─ provider.chat_with_retry(tools=None)
    │
    ├─ 返回 analysis 文本
    │
    ↓
Phase 2: 执行编辑（通过 AgentRunner）
    │
    ├─ _list_existing_skills() → 已存在技能列表（去重）
    ├─ phase2_prompt = analysis + file_context + skills_section
    │
    ├─ system: "dream_phase2.md" 模板
    ├─ user: phase2_prompt
    │
    ├─ _runner.run(AgentRunSpec)
    │   ├─ tools: read_file, edit_file, write_file
    │   ├─ max_iterations: 10
    │   │
    │   └─ LLM 可通过工具：
    │       ├─ read_file → 读取 MEMORY.md / SOUL.md / USER.md
    │       ├─ edit_file → 增量编辑这些文件
    │       ├─ write_file → 创建 skills/<name>/SKILL.md
    │
    ├─ 记录 tool_events → changelog
    │
    ↓
推进 cursor & 清理
    │
    ├─ store.set_last_dream_cursor(new_cursor)
    ├─ store.compact_history()
    │
    ├─ git.auto_commit() → 自动 Git 提交（如有变更）
    │
    ↓
返回 True（工作已完成）
```

---

## 三层记忆架构对比

| 层级 | 类 | 触发条件 | 输出 | 工具能力 |
|------|-----|---------|------|---------|
| **存储层** | MemoryStore | append_history() 调用 | history.jsonl | 纯文件 I/O |
| **轻量合并** | Consolidator | token 预算超限 | LLM 摘要 → history.jsonl | 无工具，纯 LLM |
| **重量处理** | Dream | cron 定时触发 | 编辑 MEMORY.md/SOUL.md/USER.md | read/edit/write + AgentRunner |

---

## 与 AgentLoop 的集成点

```
AgentLoop.__init__()
    │
    ├─ MemoryStore(workspace) → store
    ├─ Consolidator(store, provider, ...) → consolidator
    │
    ↓
AgentLoop._process_message()
    │
    ├─ consolidator.maybe_consolidate_by_tokens(session)
    │   └─ 上下文超限时自动合并旧消息
    │
    ├─ _save_turn(session, messages, ...)
    │   └─ 保存本轮对话
    │
    ↓
CronService 定时任务
    │
    ├─ Dream.run()
    │   └─ 处理未合并的历史条目
    │   └─ 编辑长期记忆文件
    │
    ↓
ContextBuilder.build_messages()
    │
    ├─ store.get_memory_context() → 注入长期记忆
    ├─ read_soul() / read_user() → 注入身份/用户信息
```