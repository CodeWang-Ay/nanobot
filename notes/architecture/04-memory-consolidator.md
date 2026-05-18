# Consolidator 记忆压缩机制

## 核心职责

实时对话压缩器，当上下文超限时，将旧消息压缩成摘要写入 history.jsonl。

## 关键参数

| 参数 | 含义 | 示例值 |
|------|------|--------|
| context_window_tokens | 模型总容量（天花板） | 200,000 |
| max_completion_tokens | 响应输出预留空间 | 8,192 |
| SAFETY_BUFFER | tokenizer 估算误差缓冲 | 1,024 |
| budget | 输入安全上限 = 总容量 - 响应预留 - 缓冲 | 190,784 |
| estimated | 当前 prompt 实际 token 数 | 动态计算 |
| target | 压缩目标 = budget/2 | 95,392 |

## 触发条件

```
estimated ≥ budget → 触发压缩
```

## 压缩流程

```
[超限检测]
estimated ≥ budget
    ↓
[循环压缩] 最多 5 轮
    ↓
每轮三步：
    1. 找截断边界 → 用户消息处 + 达到移除目标
    2. 检查上限 → 不超过 60 条消息
    3. LLM 摘要 → 写入 history.jsonl
    ↓
[目标判断]
estimated ≤ target → 停止
```

## 截断规则（优先级）

```
优先级 1：用户消息边界（必须满足，保证对话完整）
优先级 2：60 条上限（不能超过）
优先级 3：移除 token 目标（尽量达到）
```

## 摘要输出

```
提取：用户事实 / 决策 / 解决方案 / 事件 / 偏好
跳过：代码模式 / git 历史 / 已有记忆
格式：简洁要点，每行一条
无内容：(nothing)
```

## 数据流

```
AgentLoop → Consolidator.maybe_consolidate_by_tokens()
                ↓
           [estimated ≥ budget?]
                ↓ Yes
           循环压缩 → LLM 摘要 → history.jsonl
                ↓
           [estimated ≤ target?]
                ↓ Yes
           继续对话
```

## 关键常量

```
_MAX_CONSOLIDATION_ROUNDS = 5   # 最多压缩轮数
_MAX_CHUNK_MESSAGES = 60       # 每轮最多截取消息数
_SAFETY_BUFFER = 1024          # token 估算缓冲
```

## 与 Dream 对比

| Consolidator | Dream |
|--------------|-------|
| 实时触发（token 超限） | 定时触发（每 2h） |
| 输入：session 消息 | 输入：history.jsonl |
| 输出：history.jsonl | 输出：MEMORY.md/SOUL.md/USER.md |
| 轻量摘要 | 深度分析 + 文件编辑 |