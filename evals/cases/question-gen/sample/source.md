---
type: permanent
tags: [knowledge-management, quiz]
created: "2026-05-19"
modified: "2026-05-19"
---
# 题目格式

> 每道题目为 `.md` 文件，包含 YAML frontmatter 和固定格式的 body。

## Frontmatter

```yaml
type: question
id: "{topic}-{slug}-{n}"   # 唯一标识符
topic: ""                   # 主题标签
difficulty: ""              # easy / medium / hard
sources: []                # source note slugs that contributed
deprecated: false           # 可选，标记旧题退役
created: "YYYY-MM-DD"
```

## Body 格式

```markdown
# {题干}

A. {选项A}
B. {选项B}
C. {选项C}
D. {选项D}

**答案:** {A|B|C|D}

**解析:** {解释为什么这是正确答案}
```

## 题目状态

题目状态（attempts, correct, wrong 等）存储在 `state/{id}.json` 而非题目文件中。
题目文件内容创建后不变。
