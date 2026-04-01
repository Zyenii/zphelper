# U3 Clarification Loop

## Goal
- 让 agent 在 planning 阶段先判断信息是否充分。
- 如果信息不足，不直接硬规划，也不乱猜，而是先向用户发起澄清。
- 用户补充后，系统继续进入 planner，直到：
  - 信息足够执行
  - 或达到停止条件

## Problem
- 当前 planner 只能在“已有信息足够”的前提下产出 plan。
- 如果用户输入缺少关键槽位，例如：
  - `我现在过去要多久`
  - `帮我安排个会`
  - `提醒我一下`
  系统要么误规划，要么 fallback，不够自然。
- 单轮 clarification 虽然能解决部分问题，但不够通用；很多任务需要多轮补信息。

## Design Summary
- 引入一个 **clarification-aware planning loop**。
- planner 不只输出 action plan，还要输出当前是否已经可以执行。
- 如果仍然缺少信息，系统记录一个短期 continuation context，并返回澄清问题。
- 下一轮用户补充后，再把 continuation context 注入 planner，继续判断。

## Core Decision
- **不把 clarification 设计成一个大的 graph state 模块。**
- **不把这类信息写入 long-term memory。**
- 采用更轻量的方案：
  - continuation context 作为 **session-scoped short-term context**
  - 只服务“当前未完成任务”的续接
  - 在下一轮 planning 时作为外部上下文注入

## Planner Output Extension
- 当前 `ExecutionPlan` 需要扩展，至少支持：

```json
{
  "status": "ready | needs_clarification | cannot_complete",
  "goal": "short goal",
  "intent": "eta_query",
  "missing_slots": ["destination"],
  "clarification_question": "你想去哪里？",
  "actions": [],
  "reason": "missing destination",
  "confidence": 0.82
}
```

### Status Meaning
- `ready`
  - 信息已经足够，可以直接执行 `actions`
- `needs_clarification`
  - 信息不足，需要继续问用户
- `cannot_complete`
  - 已无法合理继续，例如多轮澄清后仍无法补齐

## Continuation Context
- continuation context 不放在主 graph state，而放在独立 session store 中。
- planner 每次运行时，可以选择读取它并合并进 planner context。

### Minimal Shape

```json
{
  "session_id": "default",
  "continuation_context": {
    "active": true,
    "original_user_request": "我现在过去要多久",
    "intent": "eta_query",
    "known_slots": {},
    "missing_slots": ["destination"],
    "last_clarification_question": "你想去哪里？",
    "turn_count": 1
  }
}
```

## Why Not Put It In Graph State
- graph state 更适合当前请求内的 working memory：
  - message
  - intent
  - plan
  - tool outputs
  - telemetry
- clarification continuation 需要跨请求保留，但又不属于长期记忆。
- 如果直接塞进 graph state，会让 state 语义变得混杂，不利于后续扩展。

## Storage
- 最小实现先用：
  - `data/session_context.json`
- 后续可升级为：
  - SQLite
  - Postgres

## Loop Model
- 这里的“循环”不是单次 HTTP 请求内的 while loop。
- 它是一个 **跨请求的 session-level clarification loop**。

### Request 1
用户输入：

```text
我现在过去要多久
```

planner 输出：

```json
{
  "status": "needs_clarification",
  "intent": "eta_query",
  "missing_slots": ["destination"],
  "clarification_question": "你想去哪里？"
}
```

系统行为：
- 将 continuation context 写入 session store
- 返回 clarification question 给用户

### Request 2
用户回复：

```text
纽约
```

系统行为：
- 读取 continuation context
- 将其注入 planner context
- planner 判断当前回复是在补充 destination

如果信息足够，planner 输出：

```json
{
  "status": "ready",
  "intent": "eta_query",
  "actions": [
    {
      "tool": "commute_plan",
      "args": {
        "destination": "New York",
        "departure_time": "now",
        "transport_mode": "driving"
      }
    }
  ]
}
```

然后正常执行，并清空 continuation。

## Max Clarification Turns
- 第一版不加 TTL。
- 先使用：

```python
max_clarification_turns = 3
```

### Behavior
- 每次 planner 返回 `needs_clarification`：
  - continuation `turn_count += 1`
- 如果 `turn_count >= 3`：
  - 不再继续追问
  - 清掉 continuation
  - 返回结束消息，例如：
    - `当前信息仍不足以完成这个任务，请重新完整描述你的需求。`

## Scope of First Version
- 第一版不追求全任务泛化。
- 优先支持这些缺槽位最明确的 intent：

### `eta_query`
- required slot:
  - `destination`

### `calendar_create`
- required slots:
  - `title`
  - `start_time`

### `todo_create`
- required slots:
  - `task_title`
  - optionally `due_date`

## Integration Points

### 1. Planner Schema
- 扩展 `ExecutionPlan`
- 增加：
  - `status`
  - `missing_slots`
  - `clarification_question`

### 2. Planner Prompt
- 明确告诉模型：
  - 如果 continuation context 存在，要把当前 message 视为上一个未完成任务的补充
  - 如果仍缺槽位，输出 `needs_clarification`
  - 如果信息足够，输出 `ready`

### 3. Planner Node
- 读取 continuation context
- 将其合并进 planner context

### 4. API Layer
- 在 `/chat` 入口维护 continuation store
- 根据 planner 的 `status`：
  - 保存 continuation
  - 清除 continuation
  - 或进入正常执行

## Example Stop Condition

```python
if plan.status == "needs_clarification":
    turn_count = existing.turn_count + 1 if existing else 1
    if turn_count >= 3:
        clear_continuation(session_id)
        output = "当前信息仍不足以完成这个任务，请重新完整描述你的需求。"
    else:
        save_continuation(...)
        output = plan.clarification_question
```

## Why This Design
- 比“单次 clarification”更完整
- 比“把所有对话历史都塞给模型”更克制
- 比“把 clarification state 混进主 graph state”更优雅
- 为后续扩展留出路径：
  - agent loop
  - re-plan
  - reflection

## Future Extension
- TTL
- repeated-question detection
- richer conversation history
- approval continuation
- reflection after repeated failure
