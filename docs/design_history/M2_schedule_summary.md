# M2 Schedule Summary

## Goal
- 让 agent 先具备最基础、最可靠的 schedule summary 能力。

## Main Design
- 引入 calendar connector，支持 mock calendar fixture。
- 先做 rule-based intent routing。
- 使用 `schedule_read -> schedule_summarize -> final` 的固定 workflow。

## Key Decisions
- 优先 deterministic path，而不是一开始就让 LLM 决定全部流程。
- 先把 structured state 跑通，再考虑更复杂的 agent 行为。

## Why This Matters
- 这是第一个完整闭环：
  - intent
  - tool execution
  - state write-back
  - final response

## Output
- `/chat` 支持 schedule query
- 返回 human-readable summary 和结构化 state

## Known Limits
- 时间窗口主要依赖规则。
- 对自然语言表达的鲁棒性还有限。

## Next Step
- 扩展天气和通勤能力，开始做跨工具组合。
