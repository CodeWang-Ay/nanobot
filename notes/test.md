  nanobot/
  ├── __init__.py          # 模块初始化
  ├── __main__.py          # 入口点
  ├── nanobot.py           # 程序接口门面类
  │
  ├── agent/               # Agent 核心模块
  │   ├── tools.py
  │         ├── cron.py          # 定时任务
  │         ├── filesystem.py    # 文件读写、目录列表
  │         ├── mcp.py           # MCP 协议工具
  │         ├── message.py       # 消息发送
  │         ├── notebook.py      # Jupyter notebook 编辑
  │         ├── price_history.py # 价格历史查询
  │         ├── price_internet.py# 互联网价格查询
  │         ├── search.py        # Glob/Grep 文件搜索
  │         ├── shell.py         # Shell 命令执行
  │         ├── spawn.py         # 子 Agent 任务
  │         ├── web.py           # WebFetch/WebSearch
  │         └── base.py          # Tool 基类 + 装饰器
  │         └── registry.py      # ToolRegistry
  │         └── schema.py        # Schema DSL
  │   ├── autocompact.py   # 自动压缩会话
  │   ├── context.py       # 上下文构建器
  │   ├── hook.py          # Agent 钩子
  │   ├── loop.py          # Agent 循环引擎
  │   ├── memory.py        # 记忆/
  │   ├── runner.py        # Agent 执行器
  │   ├── skills.py        # 技能管理
  │   ├── subagent.py      # 子 Agent 管理
  │   └── tools/           # 工具集（见之前的输出）
  │
  ├── api/                 # API 服务
  │   ├── __init__.py
  │   └── server.py        # API 服务器
  │
  ├── bus/                 # 消息总线
  │   ├── __init__.py
  │   ├── events.py        # 消息事件定义
  │   └── queue.py         # 消息队列
  │
  ├── channels/            # 多渠道集成
  │   ├── __init__.py
  │   ├── feishu.py        # 飞书
  │   ├── qq.py            # QQ
  │   ├── wecom.py         # 企业微信
  │   ├── weixin.py        # 微信
  │   └── whatsapp.py      # WhatsApp
  │
  ├── cli/                 # CLI 命令行
  │   ├── __init__.py
  │   ├── commands.py      # CLI 命令
  │   ├── models.py        # CLI 模型
  │   ├── onboard.py       # 新用户引导
  │   └── stream.py        # 流式输出
  │
  ├── command/             # 命令路由
  │   ├── __init__.py
  │   ├── builtin.py       # 内置命令
  │   └── router.py        # 命令路由器
  │
  ├── config/              # 配置管理
  │   ├── __init__.py
  │   ├── llm_config.py    # LLM 配置
  │   ├── loader.py        # 配置加载器
  │   ├── paths.py         # 路径配置
  │   ├── project_config.py# 项目配置
  │   └── schema.py        # 配置 Schema
  │
  ├── cron/                # 定时任务
  │   ├── __init__.py
  │   ├── service.py       # Cron 服务
  │   └── types.py         # Cron 类型定义
  │
  ├── data/                # 数据存储
  │
  ├── heartbeat/           # 心跳服务
  │   ├── __init__.py
  │   └── service.py       # 心跳检测
  │
  ├── minio_data/          # MinIO 数据
  │
  ├── providers/           # LLM 提供商
  │   ├── __init__.py
  │   ├── anthropic_provider.py      # Anthropic
  │   ├── openai_compat_provider.py   # OpenAI 兼容
  │   ├── registry.py                 # 提供商注册表
  │   └── transcription.py            # 语音转录
  │
  ├── security/            # 安全模块
  │   ├── __init__.py
  │   └ network.py         # 网络安全
  │
  ├── session/             # 会话管理
  │   ├── __init__.py
  │   └ manager.py         # 会话管理器
  │
  ├── skills/              # 技能目录（16个审计技能）
  │   ├── README.md
  │   ├── audit-*/         # 各类审计技能
  │   └── audit_gyl*/      # GYL系列审计技能
  │
  ├── templates/           # 模板文件
  │   ├── __init__.py
  │
  └── utils/               # 工具函数
      ├── __init__.py
      ├── document.py      # 文档处理
      ├── evaluator.py     # 评估器
      ├── file_processor.py# 文件处理器
      ├── gitstore.py      # Git 存储
      ├── helpers.py       # 辅助函数
      ├── onebound_server.py# OneBound 服务
      ├── oracle_db_service.py# Oracle DB 服务
      ├── path.py          # 路径工具
      ├── prompt_templates.py# 提示模板
      ├── restart.py       # 重启工具
      ├── runtime.py       # 运行时工具
      ├── searchusage.py   # 搜索使用
      └── tool_hints.py    # 工具提示