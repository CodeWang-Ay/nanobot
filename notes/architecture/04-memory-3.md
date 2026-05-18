核心组件

1. MemoryStore（存储层）

纯文件 I/O 抽象，管理以下文件：
- memory/MEMORY.md - 长期记忆事实
- memory/history.jsonl - 仅追加的历史日志（带游标追踪）
- SOUL.md - Bot 身份/行为配置
- USER.md - 用户身份/偏好

2. Consolidator（实时压缩）

触发条件：token 预算溢出时
作用：将超出上下文窗口的消息通过 LLM 摘要后写入 history.jsonl

工作流程：
1. 计算当前 prompt token 数
2. 若超预算，选择用户对话边界进行截断
3. 调用 LLM 生成摘要
4. 追加到 history.jsonl，最多 5 轮循环

3. Dream（定时整理）

触发条件：每 2 小时（可配置）或手动 /dream
作用：深度整理记忆，更新长期记忆文件

两阶段流程：
- Phase 1 分析：读取未处理的 history 条目，生成指令（[FILE] 添加、[FILE-REMOVE] 删除、[SKILL] 创建技能）
- Phase 2 执行：通过 AgentRunner 执行文件编辑操作，自动 git commit

数据流

用户消息 → AgentLoop
               ↓
          [token超限?]
               ↓ Yes
          Consolidator → history.jsonl (摘要)
作用：深度整理记忆，更新长期记忆文件

两阶段流程：
- Phase 1 分析：读取未处理的 history 条目，生成指令（[FILE] 添加、[FILE-REMOVE] 删除、[SKILL] 创建技能）
- Phase 2 执行：通过 AgentRunner 执行文件编辑操作，自动 git commit

数据流

用户消息 → AgentLoop
               ↓
          [token超限?]
               ↓ Yes
          Consolidator → history.jsonl (摘要)
               ↓
用户消息 → AgentLoop
               ↓
          [token超限?]
               ↓ Yes
          Consolidator → history.jsonl (摘要)
               ↓
          (定时触发)
               ↓
          Dream → 分析 history.jsonl → 编辑 MEMORY.md/SOUL.md/USER.md
               ↓
          [token超限?]
               ↓ Yes
          Consolidator → history.jsonl (摘要)
               ↓
          (定时触发)
               ↓
          Dream → 分析 history.jsonl → 编辑 MEMORY.md/SOUL.md/USER.md
          (定时触发)
               ↓
          Dream → 分析 history.jsonl → 编辑 MEMORY.md/SOUL.md/USER.md
               ↓
          Dream → 分析 history.jsonl → 编辑 MEMORY.md/SOUL.md/USER.md
               ↓
               ↓
          Git 自动提交

配置示例
          Git 自动提交

配置示例

配置示例

agents:
defaults:
     dream:
               ↓ Yes
          Consolidator → history.jsonl (摘要)
               ↓
          (定时触发)
               ↓
两阶段流程：
- Phase 1 分析：读取未处理的 history 条目，生成指令（[FILE] 添加、[FILE-REMOVE] 删除、[SKILL] 创建技能）
- Phase 2 执行：通过 AgentRunner 执行文件编辑操作，自动 git commit

数据流

用户消息 → AgentLoop
               ↓
          [token超限?]
               ↓ Yes
          Consolidator → history.jsonl (摘要)
               ↓
          (定时触发)
               ↓
          Dream → 分析 history.jsonl → 编辑 MEMORY.md/SOUL.md/USER.md
               ↓
          Git 自动提交

配置示例

agents:
defaults:
     dream:
     interval_h: 2        # 每 2 小时
     max_batch_size: 20   # 每次处理最多 20 条
     max_iterations: 10   # Phase 2 最多 10 次工具调用

这套设计平衡了实时性（Consolidator 防止上下文溢出）和长期记忆演化（Dream 定期提炼有价值的信息）。