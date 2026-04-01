# M1 Project Bootstrap

## Goal
- 建立项目基础骨架，确定这是一个 personal ops agent，而不是泛化聊天机器人。

## Main Design
- 使用 FastAPI 作为服务入口。
- 使用 LangGraph 组织后续节点式 workflow。
- 先搭建统一的 state、API 路由和基础目录结构。

## Why This Design
- 需要一个可扩展的 agent runtime，而不是只堆 prompt。
- 先把服务、状态和模块边界搭好，后续功能才能稳定叠加。

## Output
- 初始 API 服务
- 基础项目结构
- 统一 state / route 入口

## Known Limits at This Stage
- 还没有完整的 tool orchestration。
- 还没有明确的 planner / memory / evaluation。

## Next Step
- 先做最基本、最稳定的日程读取与总结能力。
