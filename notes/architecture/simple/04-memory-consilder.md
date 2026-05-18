# Token 预算计算

budget = context_window_tokens - max_completion_tokens - SAFETY_BUFFER
# 示例：65536 - 8192 - 1024 = 56320

estimated = 当前 session 已用 token

# 触发条件
if estimated > budget:
    target = budget * 0.5  # 目标：降到预算的 50%
    need_remove = estimated - target  # 需移除的量

# 边界选择
boundary = pick_consolidation_boundary(session, need_remove)
# 返回：(end_idx, removed_tokens) -> (截断的消息索引位置, 该位置累计移除的 token 数)
# 约束：用户消息完整性 + 最多 60 条上限

# 执行压缩
archive(chunk)  # 若返回 nothing → 无价值内容，跳过

# 存储结果
摘要写入 history.jsonl，格式：
{"role": "assistant", "content": "[摘要内容]", "type": "consolidation", ...}

图示简化：

|<---------- context_window (65536) ----------|
|                                              |
|-- 输入 (≤budget) --|-- 输出预留 (8192) --|-- 缓冲[容错] (1024) --|
|    ≤ 56320         |      8192           |      1024       |


  
# Consolidator 方法之间的关系
maybe_consolidate_by_tokens(session)                     # 【核心】循环压缩直到符合 token 预算
    │
    ├─ 1. 计算预算
    │      budget = context_window - max_completion - SAFETY_BUFFER
    │      target = budget // 2  # 目标：降到预算的一半
    │
    ├─ 2. 估算当前 token
    │      estimate_session_prompt_tokens(session) → (estimated, source)
    │
    ├─ 3. 判断是否超限
    │      if estimated < budget: return  # 不超限，跳过
    │
    └─ 4. 循环压缩（最多 5 轮）
            ├─ pick_consolidation_boundary(session, need_remove)
            │     → 返回 (end_idx, removed_tokens)
            │     约束：用户消息边界（保证完整性）
            │
            ├─ _cap_consolidation_boundary(session, end_idx)
            │     → 限制块大小 ≤ MAX_CHUNK_MESSAGES (60)
            │
            ├─ archive(chunk)  # LLM 摘要
            │     → 成功：写入 history.jsonl
            │     → 失败：raw_archive 原始 dump
            │
            ├─ session.last_consolidated = end_idx  # 更新游标
            │
            └─ 重新估算 token，继续下一轮

关键补充：

1. target 是预算的一半：target = budget // 2，不是刚好降到 budget
2. 循环最多 5 轮：防止无限压缩
3. _cap 是对 end_idx 的二次限制：先选边界，再限制大小
