# Session 会话系统

## Session Key 构成

```python
@property
def session_key(self) -> str:
    return f"{self.channel}:{self.chat_id}"
```

| Channel | Chat ID | Session Key | 含义 |
|---------|---------|-------------|------|
| `telegram` | `123456` | `telegram:123456` | Telegram 私聊 |
| `telegram` | `-100123` | `telegram:-100123` | Telegram 群组 |
| `discord` | `channel_xyz` | `discord:channel_xyz` | Discord 频道 |
| `cli` | `direct` | `cli:direct` | CLI 默认会话 |
| `cli` | `project1` | `cli:project1` | CLI 项目会话 |

## Session 隔离机制

| 机制 | 数据结构 | 作用 |
|------|----------|------|
| **上下文隔离** | `sessions/{key}.jsonl` | 各会话独立历史文件 |
| **执行隔离** | `_session_locks[key]` | 同会话串行，跨会话并发 |
| **任务隔离** | `_active_tasks[key]` | `/stop` 只取消自己的任务 |
| **注入隔离** | `_pending_queues[key]` | follow-up 只注入当前会话 |

## 并发模型

```python
# loop.py:516-529
async def _dispatch(self, msg) -> None:
    """Process a message: per-session serial, cross-session concurrent."""
    session_key = self._effective_session_key(msg)
    lock = self._session_locks.setdefault(session_key, asyncio.Lock())

    async with lock, gate:  # session 锁 + 全局并发限制
        response = await self._process_message(msg)
```

**并发示意**：

```
用户A: telegram:100 → Task-1 持有 lock_A → LLM调用中
用户B: telegram:200 → Task-2 持有 lock_B → LLM调用中（并发）
用户A: telegram:100 → Task-3 等待 lock_A → 阻塞（串行）
```

**全局并发限制**：

```python
# loop.py:221-224
_max = int(os.environ.get("NANOBOT_MAX_CONCURRENT_REQUESTS", "3"))
self._concurrency_gate = asyncio.Semaphore(_max) if _max > 0 else None
```

## 会话模式

| 配置 | 模式 | Session Key | 适用场景 |
|------|------|-------------|----------|
| `unified_session=False` | 多会话 | `{channel}:{chat_id}` | 多用户 Bot |
| `unified_session=True` | 统一会话 | `unified:default` | 单用户多设备同步 |

```python
# loop.py
UNIFIED_SESSION_KEY = "unified:default"

def _effective_session_key(self, msg) -> str:
    if self._unified_session and not msg.session_key_override:
        return UNIFIED_SESSION_KEY
    return msg.session_key
```

## SessionManager 核心方法

| 方法 | 作用 |
|------|------|
| `get_or_create(key)` | 获取或创建 Session（缓存优先） |
| `save(session)` | 持久化到 `sessions/{key}.jsonl` |
| `list_sessions()` | 列出所有会话 |
| `get_history(max_messages)` | 获取历史消息 |

## CLI Session

```bash
# 默认单一会话
nanobot agent                      # session_key: "cli:direct"

# 多项目隔离
nanobot agent -s "project1"        # session_key: "cli:project1"
nanobot agent -s "project2"        # session_key: "cli:project2"

# 复用渠道会话
nanobot agent -s "telegram:123"    # session_key: "telegram:123"
```

## 关键文件

| 文件 | 职责 |
|------|------|
| `nanobot/session/manager.py` | SessionManager 实现 |
| `nanobot/bus/events.py:22-24` | session_key 属性定义 |
| `nanobot/agent/loop.py:515-601` | _dispatch 隔离逻辑 |
| `nanobot/cli/commands.py:872` | CLI --session 参数 |