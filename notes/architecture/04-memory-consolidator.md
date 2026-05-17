# Consolidator 记忆压缩机制

## 核心职责

Consolidator 是**实时对话压缩器**，当上下文超限时，将旧消息压缩成摘要写入 `history.jsonl`，释放 token 空间。

## 代码位置

`nanobot/agent/memory.py:345-548`

## 核心参数

### 1. context_window_tokens（上下文窗口）

来源：`config/schema.py:71`

```python
context_window_tokens: int = 65_536  # 默认值
```

含义：LLM 模型的最大上下文容量（输入+输出）

| 模型 | 典型值 |
|------|--------|
| Claude Opus/Sonnet | 200,000 |
| GPT-4 | 128,000 |
| 默认配置 | 65,536 |

配置：
```yaml
agents:
  defaults:
    context_window_tokens: 200000
```

### 2. max_completion_tokens（响应预留）

来源：`config/schema.py:70` → 传入 Consolidator

```python
max_tokens: int = 8192  # 配置默认值
max_completion_tokens = provider.generation.max_tokens  # loop.py 传入
```

含义：为 LLM **响应输出**预留的 token 空间，防止输入占满窗口导致无法生成响应。

### 3. SAFETY_BUFFER（安全缓冲）

来源：`memory.py:351` 硬编码常量

```python
_SAFETY_BUFFER = 1024
```

含义：tokenizer 估算误差的缓冲，防止估算偏低导致实际请求超限。

## Token 判断逻辑

### 计算安全预算

```python
# memory.py:478
budget = context_window_tokens - max_completion_tokens - SAFETY_BUFFER

# 例如：
budget = 200000 - 8192 - 1024 = 190,784
```

```
|<------------- context_window_tokens (200K) -------------|
|                                                          |
|  |-- 输入可用空间 --|  |-- 响应预留 --|  |-- 缓冲 --|
|     budget         |     8192        |    1024     |
|     190,784        |                 |             |
```

### 估算当前用量

```python
# memory.py:418-433
estimated, source = estimate_session_prompt_tokens(session)

# 估算包含：
# - system prompt
# - memory context (MEMORY.md/SOUL.md/USER.md)
# - session history（当前会话所有历史消息）
# - tool definitions
```

### 触发条件

```python
# memory.py:487-497
if estimated < budget:
    return  # 未超限，不压缩

# 超限 → 进入压缩循环
```

## 压缩流程

### 整体流程

```
estimated ≥ budget
    ↓
触发压缩循环（最多 5 轮）
    ↓
每轮：
  1. 找截断边界（用户消息开头）
  2. 截取旧消息块（不超过 60 条）
  3. LLM 生成摘要
  4. 写入 history.jsonl
  5. 更新 session.last_consolidated
  6. 重新估算 estimated
    ↓
estimated ≤ target (budget/2) → 停止
```

### 压缩目标

```python
# memory.py:479
target = budget // 2  # 压缩到预算的一半，留足空间
```

### 截断边界选择

**三个条件按优先级执行：**

```
条件 2（用户消息边界） → 硬性要求，必须满足
条件 3（60 条上限）    → 硬性上限，不能超过
条件 1（移除 token 数） → 目标，尽量达到
```

#### 1. 找用户消息边界

```python
# memory.py:380-400
def pick_consolidation_boundary(session, tokens_to_remove):
    removed_tokens = 0
    for idx in range(start, len(session.messages)):
        message = session.messages[idx]
        # 只在用户消息处截断（保证对话完整性）
        if idx > start and message.get("role") == "user":
            last_boundary = (idx, removed_tokens)
            if removed_tokens >= tokens_to_remove:
                return last_boundary
        removed_tokens += estimate_message_tokens(message)
```

返回：`boundary = (end_idx, removed_tokens)` 元组

#### 2. 60 条消息上限

```python
# memory.py:349
_MAX_CHUNK_MESSAGES = 60  # 常量

# memory.py:402-416
def _cap_consolidation_boundary(session, end_idx):
    if end_idx - start <= 60:
        return end_idx  # 未超过，直接返回
    
    # 超过 60，强制截断并回退到用户边界
    capped_end = start + 60
    for idx in range(capped_end, start, -1):
        if session.messages[idx].get("role") == "user":
            return idx
```

### LLM 摘要生成

```python
# memory.py:435-465
async def archive(messages):
    formatted = MemoryStore._format_messages(messages)
    response = await self.provider.chat_with_retry(
        model=self.model,
        messages=[
            {"role": "system", "content": render_template("agent/consolidator_archive.md")},
            {"role": "user", "content": formatted},
        ],
    )
    summary = response.content or "[no summary]"
    self.store.append_history(summary)  # 写入 history.jsonl
    return summary
```

#### 摘要模板规则

`templates/agent/consolidator_archive.md`:

```
提取关键信息：
- 用户事实：个人信息、偏好、观点、习惯
- 决策：做出的选择、得出的结论
- 解决方案：成功的方法、非显而易见的方法
- 事件：计划、截止日期、重要事件
- 偏好：沟通风格、工具偏好

优先级：用户纠正 > 解决方案 > 决策 > 事件
跳过：代码模式、git 历史、已有记忆

输出格式：简洁要点，每行一条
无内容时输出：(nothing)
```

#### (nothing) 含义

LLM 判断该段对话无价值信息，但仍然写入 history.jsonl 作为处理标记，用于：
- 标记已处理，避免重复处理
- cursor 推进追踪

## 关键常量

```python
_MAX_CONSOLIDATION_ROUNDS = 5      # 最多压缩轮数
_MAX_CHUNK_MESSAGES = 60          # 每轮最多截取消息数
_SAFETY_BUFFER = 1024             # token 估算缓冲
```

## 数据流

```
用户消息 → AgentLoop._process_message()
              ↓
         Consolidator.maybe_consolidate_by_tokens()
              ↓
         [estimated ≥ budget?]
              ↓ Yes
         循环压缩（最多 5 轮）
              ↓
         每轮：
           - pick_consolidation_boundary() → 找截断位置
           - _cap_consolidation_boundary() → 检查 60 条上限
           - archive() → LLM 摘要
           - append_history() → 写入 history.jsonl
           - 更新 session.last_consolidated
              ↓
         [estimated ≤ target?]
              ↓ Yes
         停止压缩，继续正常对话
```

## 与 Dream 的区别

| 组件 | Consolidator | Dream |
|------|-------------|-------|
| 触发方式 | 实时（token 超限） | 定时（每 2 小时） |
| 输入来源 | 当前 session 消息 | history.jsonl 条目 |
| 输出目标 | history.jsonl | MEMORY.md / SOUL.md / USER.md |
| 处理深度 | 轻量摘要 | 深度分析 + 文件编辑 |

## 配置

```yaml
agents:
  defaults:
    context_window_tokens: 200000  # 根据实际模型调整
    max_tokens: 8192               # 响应预留
```

---

**核心思想**：逐步从旧消息开始压缩，用 LLM 摘要代替原始消息，直到 prompt 瘦身到安全范围（budget/2），保证对话可以正常继续。