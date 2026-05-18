  Layer 3: Dream (深度处理)

  核心逻辑： nanobot/agent/memory.py:557-768

  两阶段处理

  ┌─────────────────────────────────────────────────────────────────┐
  │  Dream.run()                                                     │
  ├─────────────────────────────────────────────────────────────────┤
  │  读取未处理的 history.jsonl 条目 (cursor > dream_cursor)         │
  │                                                                  │
  │  Phase 1: 分析 (dream_phase1.md)                                │
  │  ├─ [FILE] 添加原子事实到 MEMORY/SOUL/USER                        │
  │  ├─ [FILE-REMOVE] 删除过时内容                                   │
  │  └─ [SKILL] 发现可复用的技能模式                                  │
  │                                                                  │
  │  Phase 2: 执行 (dream_phase2.md)                                │
  │  ├─ 使用 AgentRunner + edit_file 工具精确编辑                    │
  │  ├─ 创建新技能: skills/<name>/SKILL.md                          │
  │  └─ 使用 write_file 工具                                         │
  │                                                                  │
  │  后处理:                                                         │
  │  ├─ 更新 dream_cursor                                            │
  │  ├─ compact_history() 清理旧条目                                  │
  │  └─ Git 自动提交变更                                              │
  └─────────────────────────────────────────────────────────────────┘

  Phase 1 分析规则 (dream_phase1.md)

  | 标记            | 用途                               |
  |---------------|----------------------------------|
  | [FILE]        | 添加原子事实（如 "has a cat named Luna"） |
  | [FILE-REMOVE] | 删除过时内容（>14天的临时信息、已完成任务）          |
  | [SKILL]       | 发现重复出现的可复用工作流                    |

  Phase 2 编辑规则 (dream_phase2.md)

  - 使用 edit_file 精确编辑，不重写整个文件
  - 批量合并同一文件的修改
  - 创建技能时检查去重