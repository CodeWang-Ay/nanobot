# SkillsLoader — Agent 技能加载器

> 文件路径: `nanobot/agent/skills.py`
> 代码行数: 233 行

## 概述

`SkillsLoader` 加载和管理 markdown 格式的技能文件 (SKILL.md)，用于教导 agent 使用工具或执行特定任务。支持：
- 工作目录下的用户自定义技能
- 内置技能目录
- 技能依赖检查
- 渐进式加载

## 类方法总结

```
class SkillsLoader:
    0. __init__(workspace, builtin_skills_dir, disabled_skills)    # 初始化：工作目录、内置技能目录、禁用技能列表
    1. _skill_entries_from_dir(base, source, skip_names)           # 从目录扫描技能条目（返回 name, path, source）
    2. list_skills(filter_unavailable)                             # 列出所有可用技能（可过滤不满足要求的）
    3. load_skill(name)                                             # 加载指定技能的完整内容（SKILL.md）
    4. load_skills_for_context(skill_names)                         # 加载多个技能用于注入 agent 上下文
    5. build_skills_summary()                                       # 构建 XML 格式的技能摘要（用于渐进式加载）
    6. _get_missing_requirements(skill_meta)                        # 获取缺失的要求描述（CLI 命令或环境变量）
    7. _get_skill_description(name)                                 # 从 frontmatter 获取技能描述
    8. _strip_frontmatter(content)                                  # 移除 markdown 的 YAML frontmatter
    9. _parse_nanobot_metadata(raw)                                 # 解析 frontmatter 中的 nanobot/openclaw JSON 元数据
    10. _check_requirements(skill_meta)                             # 检查技能依赖要求（bins + env）
    11. _get_skill_meta(name)                                       # 获取技能的 nanobot 元数据字典
    12. get_always_skills()                                         # 获取标记为 always=true 且满足要求的技能列表
    13. get_skill_metadata(name)                                    # 从技能 frontmatter 解析完整元数据字典
```

## 辅助函数

```
_escape_xml(text)                  # XML 转义（&, <, >）
BUILTIN_SKILLS_DIR                 # 内置技能目录路径常量
_STRIP_SKILL_FRONTMATTER           # YAML frontmatter 正则匹配模式
```

## 技能文件结构

```
workspace/skills/
├── skill-name-1/
│   └── SKILL.md              # 技能定义文件
├── skill-name-2/
│   └── SKILL.md
...

nanobot/skills/               # 内置技能目录
├── skill-creator/
│   └── SKILL.md
├── write-code/
│   └── SKILL.md
...
```

## SKILL.md 文件格式

```markdown
---
name: skill-name
description: "技能描述"
always: true/false
metadata: {"nanobot": {"requires": {"bins": ["git"], "env": ["API_KEY"]}}}
---

# 技能内容
教导 agent 如何执行特定任务...
```

## 核心流程图

### list_skills() — 扫描技能

```
list_skills(filter_unavailable=True)
    │
    ├─ _skill_entries_from_dir(workspace_skills, "workspace")
    ├─ workspace_names = {entry["name"] for entry in skills}
    │
    ├─ _skill_entries_from_dir(builtin_skills, "builtin", skip_names=workspace_names)
    │   └─ 用户技能优先，同名的内置技能跳过
    │
    ├─ 过滤 disabled_skills
    │   └─ skills = [s for s in skills if s["name"] not in self.disabled_skills]
    │
    ├─ 若 filter_unavailable=True:
    │   └─ 过滤不满足要求的技能
    │       └─ _check_requirements(_get_skill_meta(name))
    │
    ↓
返回 [{"name", "path", "source"}, ...]
```

### build_skills_summary() — 构建摘要

```
build_skills_summary()
    │
    ├─ list_skills(filter_unavailable=False)
    │
    ├─ 对每个技能:
    │   ├─ get_skill_metadata(name) → 解析 frontmatter
    │   ├─ _get_skill_description(name) → 获取描述
    │   ├─ _check_requirements(meta) → 检查可用性
    │   └─ _get_missing_requirements(meta) → 缺失依赖
    │
    ↓
返回 XML 格式摘要:
<skills>
  <skill available="true/false">
    <name>...</name>
    <description>...</description>
    <location>...</location>
    <requires>...</requires>  # 仅当不可用时
  </skill>
</skills>
```

### load_skill() — 加载技能

```
load_skill(name)
    │
    ├─ 查找路径：workspace_skills / name / "SKILL.md"
    ├─ 若不存在：builtin_skills / name / "SKILL.md"
    │
    ↓
返回 SKILL.md 文件内容
```

### load_skills_for_context() — 注入上下文

```
load_skills_for_context(skill_names)
    │
    ├─ 对每个 skill_name:
    │   ├─ load_skill(name)
    │   ├─ _strip_frontmatter(markdown)
    │
    ↓
返回格式化内容:
### Skill: skill-name
[技能内容]

---

### Skill: skill-name-2
...
```

## 技能元数据解析流程

```
get_skill_metadata(name)
    │
    ├─ load_skill(name) → 读取 SKILL.md
    ├─ _STRIP_SKILL_FRONTMATTER.match(content) → 提取 YAML
    ├─ 解析 YAML 行 → {"name": "...", "description": "...", "metadata": "..."}
    │
    ↓
返回 metadata 字典

_get_skill_meta(name)
    │
    ├─ get_skill_metadata(name)
    ├─ meta.get("metadata") → JSON 字符串
    ├─ _parse_nanobot_metadata(raw)
    │   └─ json.loads(raw) → {"nanobot": {"requires": {...}}}
    │
    ↓
返回 {"requires": {"bins": [...], "env": [...]}, "always": true/false}

_check_requirements(skill_meta)
    │
    ├─ requires.get("bins") → 检查 shutil.which(cmd)
    ├─ requires.get("env") → 检查 os.environ.get(var)
    │
    ↓
返回 True/False（技能是否可用）
```

## 与 AgentLoop 的集成点

```
AgentLoop.__init__()
    │
    ├─ ContextBuilder(workspace, disabled_skills=...)
    │   └─ SkillsLoader(workspace, disabled_skills)
    │
    ↓
ContextBuilder.build_messages()
    │
    ├─ skills_loader.build_skills_summary() → 技能摘要注入系统提示
    ├─ skills_loader.get_always_skills() → 常驻技能内容注入
    │
    ↓
Agent 可通过 read_file 工具读取完整 SKILL.md（渐进式加载）
```

## 技能优先级

1. **workspace_skills**: 用户自定义技能，优先级最高
2. **builtin_skills**: 内置技能，同名技能会被 workspace 覆盖
3. **disabled_skills**: 禁用的技能列表，从结果中过滤