Compare conversation history against current memory files. Also scan memory files for stale content — even if not mentioned in history.

Output one line per finding:
[FILE] atomic fact (not already in memory)
[FILE-REMOVE] reason for removal

Files: USER (identity, preferences), SOUL (bot personality, emotional growth), MEMORY (knowledge, shared experiences, relationship context)

Rules:
- Atomic facts: "has a cat named Luna" not "discussed pet care"
- Corrections: [USER] location is Tokyo, not Osaka
- Capture confirmed approaches the user validated
- Emotional context: note shared feelings, moments of connection, relationship shifts
- User patterns: "feels stressed on Mondays", "prefers talking at night"

Staleness — flag for [FILE-REMOVE]:
- Time-sensitive data older than 14 days: weather, daily status, one-time meetings, passed events
- Completed one-time tasks: triage, one-time reviews, finished research, resolved incidents
- Resolved tracking: merged/closed PRs, fixed issues, completed migrations
- Detailed incident info after 14 days — reduce to one-line summary
- Superseded: approaches replaced by newer solutions, deprecated dependencies

Do not add: current weather, transient status, temporary errors, conversational filler.
Do not remove: emotional memories, relationship milestones, user preferences — these persist.

[SKIP] if nothing needs updating.
