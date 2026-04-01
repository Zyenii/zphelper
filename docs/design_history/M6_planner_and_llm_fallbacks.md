# M6 Planner and LLM Fallbacks

## Goal
- 解决纯规则路由与固定 workflow 的灵活性不足问题。

## Main Design
- 加入 LLM fallback，用于时间窗口、地点等更复杂的语义解析。
- 引入 bounded planner，让系统从“先判 intent 再走固定流程”升级为“先产出结构化 plan 再执行”。
- planner 输出 `ExecutionPlan`，包含：
  - intent
  - actions
  - reason
  - confidence

## Key Decisions
- planner 不是 fully open agent，而是 bounded planner。
- action space 使用白名单工具集合。
- tool execution 仍由程序控制，而不是让模型直接执行函数。

## Major Problem Encountered
- planner 能产出 plan，但执行层最开始没有完全尊重 plan。
- 出现 plan / execution / state / output 不一致。

## Fix
- 让 executor 真正传递 `action args`
- 让 node respect planner semantics
- 让 final output 从 state 渲染

## Why This Matters
- planner 从“看起来高级的 trace”变成真正驱动 execution 的机制。

## Next Step
- 加强系统级 observability 和 regression。
