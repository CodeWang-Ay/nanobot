5. context.py: build_messages() [构建上下文]                                
   messages = [                                                              
       {"role": "system", "content": build_system_prompt()},  # 系统提示   
       *history,                                              # 历史消息   
       {"role": "user", "content": merged}                    # 当前消息   
   ]                                                                          
                                                                              
   build_system_prompt() 加载:                                               
   ├─ AGENTS.md, SOUL.md, USER.md, TOOLS.md (bootstrap files)              
   ├─ Memory 信息 (MEMORY.md)                                               
   ├─ Skills 元数据 (always_skills 全量, 其他只摘要)            # 这里加载skills                       
   └─ Recent History (最近对话历史)     

Skills 加载机制总结
元数据处理
# 扫描skill目录的路径
# 配置模式
1. always_skills   skills的所有数据加载进去，不只是元数据，
2. skills_summary. skills的元数据    
所有 skills 的元数据都会被解析（用于生成摘要），但完整内容是按需加载的。
具体流程 (context.py:30-63)：
build_system_prompt()
    │
    ├── 1. always_skills = skills.get_always_skills()            # ['audit_cw08']
    │       └── 解析所有 skills 的元数据，找出 always=true 的
    │
    ├── 2. 加载 always_skills 的完整内容
    │       └── skills.load_skills_for_context(always_skills)
    │
    └── 3. 其他 skills 只生成摘要
            └── skills.build_skills_summary(exclude=always_skills)

三种情况：
结论
元数据：所有 skills 的元数据都会被解析（用于生成摘要列表）
完整内容：
- always=true 的 skills → 完整内容加载到 system_prompt
- 其他 skills → 只显示摘要，agent 需要用 read_file 按需读取完整内容

这种设计是为了控制 token 使用量——只把必须的 skill 内容放入 system_prompt，其他 skill 让 agent 按需加载。