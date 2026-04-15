# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

nanobot 是一个轻量级个人 AI 助手框架，支持多渠道消息平台（Telegram、Discord、Slack、飞书、微信等）和多种 LLM 后端（Anthropic、OpenAI-compat、Azure 等）。

## 常用命令

```bash
# 安装开发依赖
uv sync --all-extras

# 运行测试
uv run pytest tests/

# 运行单个测试文件
uv run pytest tests/agent/test_runner.py

# 运行单个测试（使用 -k 过滤）
uv run pytest tests/ -k "test_name"

# 代码检查
uv run ruff check nanobot/

# 代码格式化
uv run ruff format nanobot/

# 运行 CLI
uv run nanobot --help
```

## 分支策略

- `main` 分支：稳定版本，生产就绪
- `nightly` 分支：实验性功能，可能有 bug 或 breaking changes

**PR 目标分支选择：**
- 新功能、重构 → `nightly`
- Bug 修复、文档改进 → `main`
- 不确定时 → `nightly`

## 核心架构

### 数据流

```
用户消息 → MessageBus → AgentLoop → AgentRunner → LLM + 工具执行 → 响应 → Channel.send()
```

### 模块职责

| 模块 | 职责 |
|------|------|
| `nanobot.channels` | 消息平台集成，继承 `BaseChannel`，实现 `start()`/`stop()`/`send()` |
| `nanobot.providers` | LLM 后端抽象，继承 `LLMProvider`，实现 `chat()`/`chat_stream()` |
| `nanobot.agent.loop` | `AgentLoop`：消息总线消费、会话管理、Agent 执行协调 |
| `nanobot.agent.context` | `ContextBuilder`：构建 system prompt + messages |
| `nanobot.agent.subagent` | `SubagentManager`：后台子 Agent 任务执行 |
| `nanobot.agent.memory` | `MemoryStore`/`Consolidator`/`Dream`：三层记忆系统 |
| `nanobot.agent.skills` | `SkillsLoader`：加载 SKILL.md 技能文件 |
| `nanobot.bus` | `MessageBus`：异步消息队列，`InboundMessage`/`OutboundMessage` |
| `nanobot.session` | `SessionManager`：会话历史管理 |
| `nanobot.cron` | 定时任务服务 |
| `nanobot.config` | 配置加载和 schema（Pydantic 模型） |

### Channel 开发

渠道插件通过 Python entry points (`nanobot.channels` 组) 注册。继承 `BaseChannel`：

```python
class MyChannel(BaseChannel):
    name = "mychannel"  # config section key

    async def start(self) -> None:  # 必须阻塞，持续监听
        while self._running:
            # 接收消息，调用 _handle_message()
            await self._handle_message(sender_id, chat_id, content, media)

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        # 发送响应到平台
```

详见 `docs/CHANNEL_PLUGIN_GUIDE.md`。

### Provider 开发

继承 `LLMProvider`，实现 `chat()` 方法。Provider 通过 `nanobot/providers/registry.py` 注册。

### Skills 系统

技能是 `SKILL.md` 文件，位于 `nanobot/skills/`（内置）或 workspace 的 `skills/` 目录。格式：

```markdown
---
name: skill-name
description: What this skill does
---

技能指令内容...
```

### 记忆系统

三层架构：
1. **MemoryStore**：每次对话写入 `history.jsonl`
2. **Consolidator**：token 超限时触发 LLM 摘要合并
3. **Dream**：定时任务，编辑长期记忆文件（`MEMORY.md`、`SOUL.md`、`USER.md`）

### Python SDK 使用

```python
from nanobot import Nanobot

bot = Nanobot.from_config()
result = await bot.run("Hello")
```

详见 `docs/PYTHON_SDK.md`。

## 代码风格

- Python 3.11+，行长度 100 字符
- ruff 规则：E, F, I, N, W（忽略 E501）
- pytest asyncio_mode = "auto"
- 异步代码使用 `asyncio`
- 配置使用 Pydantic 模型（继承 `nanobot.config.schema.Base`）