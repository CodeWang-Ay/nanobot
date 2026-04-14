# AutoCompact — 自动压缩器

> 文件路径: `nanobot/agent/autocompact.py`
> 代码行数: 115 行

## 概述

`AutoCompact` 主动压缩空闲会话，减少 token 成本和延迟：
- 定期检查超时会话
- 异步归档旧消息
- 生成对话摘要供下次恢复使用

## 类方法总结

```
class AutoCompact:
    0. __init__(sessions, consolidator, session_ttl_minutes)       # 初始化：会话管理器、合并器、会话超时分钟数
    1. _is_expired(ts)                                             # 判断会话是否超时（根据 updated_at 时间）
    2. _format_summary(text, last_active)                          # 【静态】格式化摘要文本（显示空闲时间）
    3. _split_unconsolidated(session)                              # 分割会话：可归档的前缀 + 保留的最近后缀
    4. check_expired(schedule_background)                          # 【核心】检查所有会话，调度超时会话的归档
    5. _archive(key)                                               # 【核心】异步归档指定会话：合并旧消息 + 生成摘要
    6. prepare_session(session, key)                               # 【核心】准备会话：处理归档状态 + 返回摘要
```

## 常量定义

```
_RECENT_SUFFIX_MESSAGES = 8   # 保留的最近消息数量（后缀）
```

## 核心流程图

### check_expired() — 定期检查超时会话

```
check_expired(schedule_background)
    │
    ├─ sessions.list_sessions() → 所有会话信息列表
    │
    ├─ 对每个会话 info:
    │   │
    │   ├─ key not in _archiving (未在归档中)
    │   ├─ _is_expired(info["updated_at"]) → 判断超时
    │   │   └─ (datetime.now() - ts).total_seconds() >= _ttl * 60
    │   │
    │   ├─ 条件满足:
    │   │   ├─ _archiving.add(key) → 标记为正在归档
    │   │   └─ schedule_background(_archive(key)) → 调度后台归档任务
    │   │
    │   └─ logger.debug("Auto-compact: scheduling archival for {}...")
    │
    ↓
返回 None（后台任务异步执行）
```

### _archive() — 异步归档会话

```
_archive(key)
    │
    ├─ sessions.invalidate(key) → 清除缓存，强制重新加载
    ├─ sessions.get_or_create(key) → 获取会话实例
    │
    ├─ _split_unconsolidated(session)
    │   │
    │   ├─ tail = session.messages[last_consolidated:] → 未合并部分
    │   │
    │   ├─ 创建 probe Session:
    │   │   ├─ messages = tail.copy()
    │   │   ├─ last_consolidated = 0
    │   │   └─ retain_recent_legal_suffix(8) → 保留最近 8 条合法后缀
    │   │
    │   ├─ kept = probe.messages → 保留的消息
    │   ├─ cut = len(tail) - len(kept) → 归档的消息数量
    │   │
    │   └─ 返回 (tail[:cut], kept)
    │   │
    │   ├─ archive_msgs → 可归档的旧消息
    │   └─ kept_msgs → 保留的最近消息
    │
    ├─ 若 archive_msgs 存在:
    │   │
    │   ├─ consolidator.archive(archive_msgs)
    │   │   ├─ _format_messages(messages) → 格式化
    │   │   ├─ provider.chat_with_retry() → LLM 摘要
    │   │   └─ store.append_history(summary) → 写入 history.jsonl
    │   │
    │   ├─ summary = response.content or ""
    │   │
    │   └─ 若 summary 有效:
    │       ├─ _summaries[key] = (summary, last_active) → 内存缓存
    │       ├─ session.metadata["_last_summary"] = {...} → 元数据持久化
    │
    ├─ session.messages = kept_msgs → 替换为保留的消息
    ├─ session.last_consolidated = 0 → 重置合并标记
    ├─ session.updated_at = datetime.now() → 更新时间
    │
    ├─ sessions.save(session) → 持久化会话
    │
    ├─ logger.info("Auto-compact: archived {} (archived={}, kept={}, summary={})")
    │
    ├─ finally: _archiving.discard(key) → 移除归档标记
    │
    ↓
归档完成
```

### prepare_session() — 准备会话 + 返回摘要

```
prepare_session(session, key)
    │
    ├─ 检查会话状态:
    │   ├─ key in _archiving → 正在归档中
    │   ├─ _is_expired(session.updated_at) → 会话已超时
    │   │
    │   ├─ 条件满足:
    │   │   ├─ logger.info("Auto-compact: reloading session {}...")
    │   │   └─ sessions.get_or_create(key) → 强制重新加载
    │
    ├─ 获取摘要:
    │   │
    │   ├─ _summaries.pop(key, None) → 优先从内存缓存获取
    │   │   ├─ 若存在:
    │   │   │   ├─ session.metadata.pop("_last_summary") → 清理元数据
    │   │   │   └─ 返回 _format_summary(entry[0], entry[1])
    │   │   │
    │   │   ├─ 若不存在，检查 session.metadata["_last_summary"]
    │   │   │   ├─ meta = session.metadata.pop("_last_summary")
    │   │   │   ├─ sessions.save(session) → 清理后保存
    │   │   │   └─ 返回 _format_summary(meta["text"], meta["last_active"])
    │   │   │
    │   │   └─ 无摘要 → 返回 None
    │
    ↓
返回 (session, summary | None)
    │
    ├─ session: 处理后的会话实例
    └─ summary: 格式化的摘要文本（若存在）
        "Inactive for {idle_min} minutes.\nPrevious conversation summary: {text}"
```

## 会话分割示意图

```
原始会话 messages:
[0] [1] [2] [3] [4] [5] [6] [7] [8] [9] [10] [11] [12] [13] [14]
    ↑                       ↑
    last_consolidated       分割点

分割后:
archive_msgs: [4] [5] [6] [7] [8] [9] [10] → 归档 + LLM 摘要
kept_msgs:    [11] [12] [13] [14]          → 保留（最近 8 条后缀）

归档后会话:
[11] [12] [13] [14]
last_consolidated = 0
```

## 会话生命周期状态

```
[活跃会话]
    │
    ├─ updated_at 不断更新
    ├─ 消息累积
    │
    ↓ 超过 TTL 分钟无活动
[超时会话]
    │
    ├─ _is_expired() → True
    ├─ check_expired() → 调度 _archive()
    ├─ _archiving.add(key) → 标记归档中
    │
    ↓
[归档中]
    │
    ├─ sessions.invalidate() → 清缓存
    ├─ _split_unconsolidated() → 分割消息
    ├─ consolidator.archive() → LLM 摘要
    ├─ session.messages = kept_msgs → 替换
    ├─ _summaries[key] = (summary, last_active) → 内存缓存
    │
    ↓
[归档完成]
    │
    ├─ _archiving.discard(key)
    ├─ 会话只保留最近 8 条消息
    │
    ↓ 用户再次发送消息
[会话恢复]
    │
    ├─ prepare_session() → 获取摘要
    ├─ _summaries.pop(key) → 获取并清除缓存
    ├─ 摘要注入到上下文
    │
    ↓
[正常对话继续]
    │
    ├─ Agent 理解之前的对话摘要
    ├─ 新消息正常处理
```

## 配置参数影响

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `session_ttl_minutes` | 0 (禁用) | 会话超时分钟数，≤0 表示不自动归档 |
| `_RECENT_SUFFIX_MESSAGES` | 8 | 归档时保留的最近消息数量 |

## 内存缓存结构

```
_auto_compact._summaries: dict[str, tuple[str, datetime]]
    │
    ├─ key: "cli:direct"
    ├─ value: ("用户之前讨论了 Python 编程...", datetime(2024-01-15 10:00))
    │
    └─ 用途：快速获取摘要（进程未重启时）

session.metadata["_last_summary"]: dict
    │
    ├─ "text": "用户之前讨论了 Python 编程..."
    ├─ "last_active": "2024-01-15T10:00:00"
    │
    └─ 用途：持久化摘要（进程重启后可恢复）
```

## 与 AgentLoop 的集成点

```
AgentLoop.__init__()
    │
    ├─ AutoCompact(sessions, consolidator, session_ttl_minutes)
    │   ├─ sessions = SessionManager
    │   ├─ consolidator = Consolidator
    │   └─ _ttl = session_ttl_minutes (配置的超时时间)
    │
    ↓
AgentLoop.run() [主循环]
    │
    ├─ while _running:
    │   ├─ msg = await bus.consume_inbound(timeout=1.0)
    │   │
    │   ├─ except asyncio.TimeoutError:
    │   │   └─ auto_compact.check_expired(self._schedule_background)
    │   │       └─ 每秒检查一次超时会话
    │   │       └─ 调度后台归档任务
    │   │
    ↓
AgentLoop._process_message()
    │
    ├─ session, pending = auto_compact.prepare_session(session, key)
    │   │
    │   ├─ 若会话正在归档或超时 → 重新加载
    │   ├─ 若有摘要 → 返回格式化摘要
    │   │
    │   └─ pending = "Inactive for X min.\nPrevious conversation summary: ..."
    │
    ├─ context.build_messages(..., session_summary=pending)
    │   └─ 摘要注入到运行时上下文
    │   └─ "[Resumed Session]\n{session_summary}"
    │
    ↓
_run_agent_loop(...)
    │
    ↓
LLM 收到摘要上下文，理解之前的对话内容
```