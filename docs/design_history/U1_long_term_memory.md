# U1 Long-Term Memory

## Goal
- 在 current request state 之外，引入稳定的用户上下文。

## Main Design
- 增加 lightweight long-term memory store。
- 当前 memory 结构包括：
  - user profile
  - preferences
  - place aliases
  - behavioral notes

## Memory Layering
- short-term memory: graph state / working memory
- long-term memory: 持久化用户偏好和稳定上下文
- external memory: Calendar、Todoist、Weather、Routes 等外部事实来源

## Integration Points
- planner context
- commute resolution
- checklist personalization

## Key Decisions
- 先做 schema-controlled memory，而不是一上来做 vector DB。
- 先以 read path 为主，write path 后续再做显式确认。

## Known Limits
- planner context 中的 memory relevance control 还不够细。
- 目前还没有 explicit memory write policy。

## Next Step
- 加入更安全的 memory write
- 未来可能引入 retrieval / vector memory
