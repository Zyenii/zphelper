# M4 Todo Automation

## Goal
- 增加 todo 创建与读取，让系统具备 task management 能力。

## Main Design
- 接入 Todoist API。
- 增加 `todo_parse`、`todo_write`、`todo_read`。
- 通过严格 schema 验证 todo draft。

## Key Decisions
- `todo_parse` 允许使用 LLM，但写入前必须经过结构化校验。
- 引入 confidence gate，低置信度时不直接写入。

## Why This Matters
- 从只读信息助手，升级成具备 side effect 的 agent。
- 系统开始真正涉及 write action。

## Known Problems
- 早期更偏重 create path，read path 后面才补齐。
- 需要更强的 clarification / approval 机制。

## Next Step
- 把 schedule、weather、commute 和 todo 串起来，支持出门清单。
