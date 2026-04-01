# M5 Leaving Checklist

## Goal
- 让 agent 具备基于多个信息源生成准备建议的能力。

## Main Design
- 新增 `checklist_generate`。
- checklist 依赖：
  - next event
  - weather
  - commute
- 先用 deterministic rules，必要时可叠加 LLM enrichment。

## Key Decisions
- 把 checklist 做成一个聚合节点，而不是让 final response 临时拼接。
- checklist 结果写入结构化 state，保证可检查、可测试。

## Why This Matters
- 这是第一个明显的 multi-source synthesis 能力。
- 系统开始从查询型 agent 走向建议型 agent。

## Known Limits
- 个性化能力较弱，更多依赖默认规则。
- 行为习惯和偏好还没有长期记忆支持。

## Next Step
- 让系统在解析与决策阶段更灵活，不只依赖规则。
