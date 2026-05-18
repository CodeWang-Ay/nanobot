1. 入口：commands.py → agent_loop.run()

2. 主循环：loop.py → run() 消费 inbound 消息
    └─ _dispatch() → _process_message()

3. 消息处理：_process_message()
    ├─ sessions.get_or_create()                     # [1. 获取或创建会话]
    ├─ consolidator.maybe_consolidate_by_tokens()   # [2. token压缩 执行前：压缩 "旧历史"，腾出空间给 "本轮输入"]
    ├─ session.get_history(max_messages=0)()        # [3. 加载历史消息]  
    ├─ context.build_messages()                     # [4. 构建上下文（系统提示 + 历史 + 当前消息 + skills元数据）] 
    ├─ _run_agent_loop()                            # [5. 运行 Agent 循环（LLM ↔ 工具调用）]    
    │    └─ runner.py: AgentRunner.run()
    │         └─ for iteration in range(max_iterations):
    │                └─ _request_model()     ← 调 LLM
    │                └─ 有 tool_calls？
    │                     ├─ YES → 执行 → append → continue
    │                     └─ NO  → break
    ├─ consolidator.maybe_consolidate_by_tokens()  # [6. token压缩 执行后：压缩 "本轮输入 + 输出"，为 "下一轮" 准备]
    └─ 返回 OutboundMessage