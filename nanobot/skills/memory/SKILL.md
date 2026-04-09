---
name: memory
description: Memory system with Dream-managed profile files and ReMe vector storage.
always: true
---

# Memory

## Structure

- `SOUL.md` — Bot personality and communication style. **Managed by Dream.** Do NOT edit.
- `USER.md` — User profile and preferences. **Managed by Dream.** Do NOT edit.
- `memory/history.jsonl` — append-only JSONL, not loaded into context. Prefer the built-in `grep` tool to search it.

## ReMe Vector Memory (Long-term Storage)

Use the memory tools for semantic retrieval and storage:

| Tool | Purpose |
|------|---------|
| `retrieve_memory` | Semantic search for past conversations and facts |
| `add_memory` | Store important information to long-term memory |
| `list_memories` | List recent memories |
| `delete_memory` | Delete specific memory |
| `get_memory_status` | Check memory system health |

## Search Past Events

`memory/history.jsonl` is JSONL format — each line is a JSON object with `cursor`, `timestamp`, `content`.

- For broad searches, start with `grep(..., path="memory", glob="*.jsonl", output_mode="count")` or the default `files_with_matches` mode before expanding to full content
- Use `output_mode="content"` plus `context_before` / `context_after` when you need the exact matching lines
- Use `fixed_strings=true` for literal timestamps or JSON fragments
- Use `head_limit` / `offset` to page through long histories
- Use `exec` only as a last-resort fallback when the built-in search cannot express what you need

Examples (replace `keyword`):
- `grep(pattern="keyword", path="memory/history.jsonl", case_insensitive=true)`
- `grep(pattern="2026-04-02 10:00", path="memory/history.jsonl", fixed_strings=true)`
- `grep(pattern="keyword", path="memory", glob="*.jsonl", output_mode="count", case_insensitive=true)`
- `grep(pattern="oauth|token", path="memory", glob="*.jsonl", output_mode="content", case_insensitive=true)`

## Important

- **Do NOT edit SOUL.md or USER.md.** They are automatically managed by Dream.
- If you notice outdated information, it will be corrected when Dream runs next.
- Users can view Dream's activity with the `/dream-log` command.
