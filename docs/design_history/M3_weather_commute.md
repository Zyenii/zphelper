# M3 Weather and Commute

## Goal
- 扩展到 weather + commute，形成更真实的 personal ops workflow。

## Main Design
- 接入 Open-Meteo / mock weather。
- 接入 ETA / route connector。
- 新增 `weather_read`、`weather_summarize`、`commute_plan`。
- 支持固定 rule workflow 处理 `weather_summary` 和 `eta_query` / `commute_advice`。

## Key Decisions
- 继续保持 deterministic routing。
- 将天气、通勤结果写入统一 state，供后续节点消费。

## Architecture Change
- 从单工具任务，升级到多工具组合任务。
- `commute_advice` 开始依赖：
  - schedule
  - weather
  - commute

## Known Problems
- location extraction 和复杂 phrasing 容易失败。
- mode / output / state 一致性问题开始暴露。

## Next Step
- 支持真正的任务写入与任务管理闭环。
