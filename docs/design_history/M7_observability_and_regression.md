# M7 Observability and Regression

## Goal
- 让系统不仅能跑，而且可观测、可诊断、可回归测试。

## Main Design
- 增加统一 structured logging。
- 在 runtime state 中记录 telemetry：
  - llm_calls
  - tokens
  - latency
  - retry_count
  - llm_error_count
- 增加 regression runner。

## Key Decisions
- telemetry 不只服务 debug，也服务 evaluation 和 A/B analysis。
- request、router、planner、tool execution 都要可追踪。

## Why This Matters
- agent 系统的主要问题通常不是“完全不能跑”，而是慢、不稳、成本高或中间链路不一致。
- observability 是后续做 harness engineering 的基础。

## Next Step
- 引入更系统的 agent evaluation，而不是只看 final answer。
