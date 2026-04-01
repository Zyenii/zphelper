# U2 Agent Evaluation

## Goal
- 把评估从“回答看起来对不对”升级成 agent pipeline 分层评估。

## Main Design
- 增加 agent evaluation harness。
- 按 query 检查：
  - intent correctness
  - planned tool-chain correctness
  - execution fidelity
  - final response consistency with state
  - required fields coverage
  - runtime metrics

## A/B Setup
- workflow baseline
- planner variant

## Why This Matters
- 可以明确比较 deterministic workflow 和 planner 的 tradeoff。
- 不只是知道系统有没有错，还能知道错在 routing、planning、execution 还是 response。

## Key Findings
- baseline 更便宜、更稳定
- planner 在更复杂自然语言表达上更鲁棒
- 引入 planner 后，必须重点关注 plan-execution consistency 和 latency

## Next Step
- 扩展 eval set
- 加 memory-aware evaluation
- 做更长期的 regression tracking
