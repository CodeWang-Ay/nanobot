SpawnTool.execute()
└─→ SubagentManager.spawn()          # 创建后台 asyncio.Task
        └─→ asyncio.create_task(_run_subagent())  # 异步执行
            ├─→ ToolRegistry 注册工具（不含 spawn/messag 工具）❌
            ├─→ _build_subagent_prompt()  # 构建 system prompt
            ├─→ AgentRunner.run()        # LLM + 工具执行循环
            └─→ _announce_result()       # 通过 MessageBus 通知主 agent

关键点：
1. spawn() 是非阻塞的 —— 使用 asyncio.create_task() 创建后台任务后立即返回，主 agent 可以继续工作
2. _run_subagent() 在后台独立运行，完成后通过 MessageBus.publish_inbound() 发送 InboundMessage 通知主 agent
3. 结果以 system message 形式注入，触发主 agent 的下一轮处理

限制：单层派生（不可嵌套）
- Subagent 工具列表不注册 SpawnTool（见 subagent.py:119 注释）
- 设计考量：避免任务树爆炸、简化管理、资源控制