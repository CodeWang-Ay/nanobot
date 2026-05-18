# MessageBus 架构

## 核心结构

```
Channel (生产者)          MessageBus              AgentLoop (消费者)
     │                       │                        │
     │  publish_inbound()    │   consume_inbound()    │
     │ ─────────────────────►│───────────────────────►│
     │                       │                        │
     │                       │   publish_outbound()   │
     │◄───────────────────── │◄────────────────────── │
     │  consume_outbound()   │                        │
```

## 实现 (`bus/queue.py`)

```python
class MessageBus:
    inbound: asyncio.Queue[InboundMessage]   # 渠道 → Agent
    outbound: asyncio.Queue[OutboundMessage] # Agent → 渠道

    async def publish_inbound(self, msg) -> None:   # Channel 调用
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:  # AgentLoop 调用
        return await self.inbound.get()

    async def publish_outbound(self, msg) -> None:  # AgentLoop 调用
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:  # Channel 调用
        return await self.outbound.get()
```

本质：两个 `asyncio.Queue`，实现**生产者-消费者模式**。

## 数据流

```
用户消息 → Channel.start() 监听
         → Channel._handle_message()
         → bus.publish_inbound(msg)

AgentLoop.run() 主循环
         → bus.consume_inbound() (wait_for timeout=1s)
         → asyncio.create_task(_dispatch(msg))  # 不阻塞
         → _process_message() → LLM + 工具执行
         → bus.publish_outbound(response)

Channel 消费 outbound
         → bus.consume_outbound()
         → Channel.send() 发送给用户
```

## 消息类型 (`bus/events.py`)

```python
@dataclass
class InboundMessage:
    channel: str        # telegram, discord, slack, cli
    sender_id: str      # 用户 ID
    chat_id: str        # 聊天 ID
    content: str        # 消息内容
    media: list[str]    # 媒体 URL
    metadata: dict      # 渠道特定数据

    @property
    def session_key(self) -> str:
        return f"{self.channel}:{self.chat_id}"  # 会话标识

@dataclass
class OutboundMessage:
    channel: str
    chat_id: str
    content: str
    reply_to: str | None
    media: list[str]
    metadata: dict
```

## 消费端并发控制 (`loop.py`)

MessageBus 本身不处理并发，**并发控制在 AgentLoop 消费端**：

```python
# loop.py:515-529
async def _dispatch(self, msg: InboundMessage) -> None:
    """Process a message: per-session serial, cross-session concurrent."""
    session_key = msg.session_key
    lock = self._session_locks.setdefault(session_key, asyncio.Lock())

    async with lock, gate:  # session 锁 + 全局并发限制
        response = await self._process_message(msg)
```

### 并发设计

```
用户A: telegram:100 → Task-1 持有 lock_100 → LLM 调用中
用户B: telegram:200 → Task-2 持有 lock_200 → LLM 调用中（并发）
用户A: telegram:100 → Task-3 等待 lock_100 → 阻塞（同会话串行）
```

| 锁/信号量 | 作用 |
|-----------|------|
| `_session_locks[key]` | 同会话串行（防止上下文混乱） |
| `_concurrency_gate` | 全局并发限制（默认 3，保护 LLM API） |

```python
# loop.py:221-224
_max = int(os.environ.get("NANOBOT_MAX_CONCURRENT_REQUESTS", "3"))
self._concurrency_gate = asyncio.Semaphore(_max) if _max > 0 else None
```

## 关键文件

| 文件 | 职责 |
|------|------|
| `nanobot/bus/queue.py` | MessageBus 实现（两个 Queue） |
| `nanobot/bus/events.py` | InboundMessage/OutboundMessage 定义 |
| `nanobot/agent/loop.py:450-514` | 消费 inbound，分发任务 |
| `nanobot/agent/loop.py:515-529` | `_dispatch` 并发控制（锁 + gate） |
| `nanobot/channels/*/channel.py` | 生产 inbound，消费 outbound |