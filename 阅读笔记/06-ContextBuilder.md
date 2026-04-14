# ContextBuilder — Agent 上下文构建器

> 文件路径: `nanobot/agent/context.py`
> 代码行数: 200 行

## 概述

`ContextBuilder` 组装完整的 LLM 调用上下文，包括：
- 系统提示（身份、启动文件、记忆、技能）
- 历史消息
- 运行时元数据（时间、通道、会话摘要）
- 用户消息内容（文本 + 图片）

## 类方法总结

```
class ContextBuilder:
    0. __init__(workspace, timezone, disabled_skills)             # 初始化：工作目录、时区、禁用技能列表
    1. build_system_prompt(skill_names, channel)                  # 【核心】构建完整系统提示
    2. _get_identity(channel)                                     # 获取核心身份定义（模板 + 运行时信息）
    3. _build_runtime_context(channel, chat_id, timezone, ...)   # 【静态】构建运行时元数据块（时间+通道+会话摘要）
    4. _merge_message_content(left, right)                        # 【静态】合并两个消息内容（字符串或块列表）
    5. _load_bootstrap_files()                                    # 加载工作目录下的启动文件（AGENTS.md 等）
    6. build_messages(history, current_message, ...)              # 【核心】构建完整的消息列表供 LLM 调用
    7. _build_user_content(text, media)                           # 构建用户消息内容（文本 + 可选 base64 图片）
    8. add_tool_result(messages, tool_call_id, tool_name, result) # 追加工具结果消息
    9. add_assistant_message(messages, content, ...)              # 追加 assistant 消息（含 tool_calls/reasoning）
```

## 常量定义

```
BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]  # 启动文件列表
_RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"  # 运行时块起始标记
_RUNTIME_CONTEXT_END = "[/Runtime Context]"                        # 运行时块结束标记
_MAX_RECENT_HISTORY = 50                                           # 最近历史条目上限
```

## 系统提示组成结构

```
build_system_prompt() 返回的系统提示：

---
# Identity (identity.md 模板)
  ├─ workspace_path
  ├─ runtime (macOS/Windows/Linux + Python 版本)
  ├─ platform_policy.md (平台特定行为)
  └─ channel (当前通道信息)

---

# Bootstrap Files
  ├─ AGENTS.md (用户自定义 Agent 行为)
  ├─ SOUL.md (Agent 核心 identity)
  ├─ USER.md (用户偏好信息)
  └─ TOOLS.md (工具使用说明)

---

# Memory
  ├─ ## Long-term Memory
  └─ MEMORY.md 内容

---

# Active Skills (always=true 的技能)
  ├─ ### Skill: skill-name
  ├─ 技能内容（SKILL.md）
  └─ (多个技能用 --- 分隔)

---

# Available Skills (skills_section.md 模板)
<skills>
  <skill available="true/false">
    <name>...</name>
    <description>...</description>
    <location>...</location>
  </skill>
</skills>

---

# Recent History
  ├─ 从 history.jsonl 读取未处理条目
  ├─ 限制最近 50 条
  └─ 格式: "- [timestamp] content"
```

## 核心流程图

### build_system_prompt()

```
build_system_prompt(skill_names, channel)
    │
    ├─ _get_identity(channel)
    │   └─ render_template("agent/identity.md", ...)
    │       ├─ workspace_path
    │       ├─ runtime (平台 + Python)
    │       ├─ platform_policy.md (平台特定)
    │       └─ channel
    │
    ├─ _load_bootstrap_files()
    │   └─ 遍历 BOOTSTRAP_FILES
    │       ├─ AGENTS.md → "## AGENTS.md\n\n{content}"
    │       ├─ SOUL.md
    │       ├─ USER.md
    │       └─ TOOLS.md
    │   └─ 合并用 "\n\n" 分隔
    │
    ├─ memory.get_memory_context()
    │   └─ read_memory() → MEMORY.md
    │   └─ 返回 "# Memory\n\n## Long-term Memory\n{content}"
    │
    ├─ skills.get_always_skills()
    │   └─ load_skills_for_context(always_skills)
    │       ├─ 对每个 skill: load_skill(name)
    │       ├─ _strip_frontmatter(markdown)
    │       └─ "### Skill: {name}\n\n{content}"
    │   └─ 返回 "# Active Skills\n\n{content}"
    │
    ├─ skills.build_skills_summary()
    │   └─ XML 格式的技能摘要
    │   └─ render_template("agent/skills_section.md", ...)
    │
    ├─ memory.read_unprocessed_history(since_cursor)
    │   └─ 从 history.jsonl 读取未处理条目
    │   └─ 限制最近 _MAX_RECENT_HISTORY 条
    │   └─ "# Recent History\n\n- [ts] content"
    │
    ↓
用 "\n\n---\n\n" 合并所有部分
返回完整系统提示
```

### build_messages()

```
build_messages(history, current_message, media, channel, chat_id, ...)
    │
    ├─ _build_runtime_context(channel, chat_id, timezone, session_summary)
    │   ├─ "Current Time: {current_time_str}"
    │   ├─ "Channel: {channel}" (可选)
    │   ├─ "Chat ID: {chat_id}" (可选)
    │   ├─ "[Resumed Session]" + session_summary (可选)
    │   └─ 用 RUNTIME_CONTEXT_TAG/END 包裹
    │
    ├─ _build_user_content(current_message, media)
    │   ├─ 无 media → 返回纯文本
    │   ├─ 有 media → base64 编码图片
    │   │   ├─ detect_image_mime(raw) → 真实 MIME 类型
    │   │   ├─ base64.b64encode(raw)
    │   │   └─ {"type": "image_url", "image_url": {"url": "data:mime;base64,..."}}
    │   └─ 返回 [images] + [{"type": "text", "text": text}]
    │
    ├─ 合并 runtime_ctx + user_content
    │   ├─ 字符串 → "{runtime_ctx}\n\n{user_content}"
    │   ├─ 列表 → [{"type": "text", "text": runtime_ctx}] + user_content
    │
    ├─ 构建消息列表
    │   ├─ {"role": "system", "content": build_system_prompt(...)}
    │   ├─ *history (历史消息)
    │   │
    │   ├─ 检查最后一条消息角色
    │   │   ├─ == current_role → 合并到最后一条
    │   │   │   └─ _merge_message_content(last["content"], merged)
    │   │   └─ != current_role → append 新消息
    │   │
    │   └─ {"role": current_role, "content": merged}
    │
    ↓
返回完整消息列表 [system, history..., user]
```

## 运行时上下文格式

```
[Runtime Context — metadata only, not instructions]
Current Time: 2024-01-15 10:30:00
Channel: telegram
Chat ID: user_12345

[Resumed Session]  (可选)
{session_summary}

[/Runtime Context]
```

## 用户消息内容格式

```
# 纯文本
"用户输入的文本内容"

# 含图片
[
  {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0..."}},
  {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AA..."}},
  {"type": "text", "text": "用户输入的文本内容"}
]
```

## Bootstrap 文件作用

| 文件 | 作用 | 内容示例 |
|------|------|---------|
| `AGENTS.md` | 用户自定义 Agent 行为规则 | "Always respond in Chinese" |
| `SOUL.md` | Agent 核心身份/性格 | "I am a helpful coding assistant" |
| `USER.md` | 用户偏好/信息 | "My name is Alice, I use Python" |
| `TOOLS.md` | 工具使用说明 | 自定义工具行为指南 |

## 与 AgentLoop 的集成点

```
AgentLoop.__init__()
    │
    ├─ ContextBuilder(workspace, timezone, disabled_skills)
    │   ├─ MemoryStore(workspace)
    │   └─ SkillsLoader(workspace, disabled_skills)
    │
    ↓
AgentLoop._process_message()
    │
    ├─ context.build_messages(history, current_message, ...)
    │   │
    │   ├─ build_system_prompt()
    │   │   ├─ identity + bootstrap + memory + skills + history
    │   │
    │   ├─ _build_runtime_context() → 运行时元数据
    │   ├─ _build_user_content() → 用户消息 + 图片
    │   │
    │   └─ 返回 [system, *history, user]
    │
    ↓
_run_agent_loop(messages, ...)
    │
    ↓
runner.run(AgentRunSpec(initial_messages=messages, ...))
```

## 工具方法用途

```
add_tool_result(messages, tool_call_id, tool_name, result)
    │
    └─ 追加 {"role": "tool", "tool_call_id": "...", "name": "...", "content": result}
    └─ 用于 runner.py 中构建工具响应消息

add_assistant_message(messages, content, tool_calls, ...)
    │
    └─ 追加 assistant 消息
    ├─ build_assistant_message(content, tool_calls=..., reasoning_content=..., thinking_blocks=...)
    └─ 用于记录 Agent 响应（含推理内容）
```