# Skills 加载机制

## 目录结构

```
nanobot/skills/*/SKILL.md      # 内置 skills
workspace/skills/*/SKILL.md    # 用户 skills（优先级高，同名覆盖 builtin）
```

## SKILL.md 格式

```markdown
---
name: audit_cw08
description: "[强制触发] CW08 流程审计..."
metadata: {"nanobot":{"always": true, "requires":{"bins":["python"],"env":["API_KEY"]}}}
---

# Skill 内容（Markdown）
```

## 两种加载模式

| 类型 | 加载位置 | 触发条件 |
|------|----------|----------|
| **Always Skills** | system_prompt 完整内容 | `metadata.always=true` 且依赖满足 |
| **普通 Skills** | XML 摘要（元数据） | Agent 通过 `read_file` 按需加载完整内容 |

> Token 优化：只把核心 skills 放入 system_prompt，其他按需加载。

## 加载流程 (context.py)

```python
def build_system_prompt(self) -> str:
    parts = []

    # 1-2. Bootstrap files + Memory
    parts.append(self._load_bootstrap_files())
    parts.append(self.memory.get_memory_context())

    # 3. Always Skills - 完整加载
    always_skills = self.skills.get_always_skills()           # → ['audit_cw08']
    if always_skills:
        content = self.skills.load_skills_for_context(always_skills)  # 去除 frontmatter
        parts.append(f"# Active Skills\n\n{content}")

    # 4. Skills Summary - XML 摘要
    summary = self.skills.build_skills_summary()
    parts.append(summary)  # <skills><skill name="..."/></skills>

    return "\n\n---\n\n".join(parts)
```

## SkillsLoader 核心方法

| 方法 | 作用 |
|------|------|
| `get_always_skills()` | 返回 always=true 且依赖满足的 skill 名称列表 |
| `load_skills_for_context(names)` | 加载完整内容，去除 frontmatter，格式化输出 |
| `build_skills_summary()` | 生成所有 skills 的 XML 元数据摘要 |
| `get_skill_metadata(name)` | 解析 YAML frontmatter |

## 依赖检查

```python
# requires.bins: 检查 CLI 是否存在
all(shutil.which(cmd) for cmd in required_bins)

# requires.env: 检查环境变量是否设置
all(os.environ.get(var) for var in required_env_vars)
```

依赖不满足 → `available="false"`，不加载到 system_prompt。

## 禁用配置

```yaml
agents:
  defaults:
    disabled_skills: ["summarize", "skill-creator"]
```

## 关键文件

| 文件 | 职责 |
|------|------|
| `nanobot/agent/skills.py` | SkillsLoader 实现 |
| `nanobot/agent/context.py` | build_system_prompt 调用 |
| `nanobot/skills/*/SKILL.md` | 内置 skills |