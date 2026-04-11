Extract key facts from this conversation. Only output items matching these categories, skip everything else:
- User facts: personal info, preferences, stated opinions, habits, emotional states
- Decisions: choices made, conclusions reached
- Solutions: working approaches discovered through trial and error, especially non-obvious methods that succeeded after failed attempts
- Events: plans, deadlines, notable occurrences
- Preferences: communication style, tool preferences
- Emotional moments: shared feelings, moments of connection or tension, things that made either person laugh or worry

Priority: emotional moments and user corrections > preferences > solutions > decisions > events > environment facts. The most valuable memory prevents the user from having to repeat themselves. Emotional context is equally valuable — knowing someone was stressed when they said something is as important as what they said.

Skip: code patterns derivable from source, git history, or anything already captured in existing memory.

Output as concise bullet points, one fact per line. No preamble, no commentary.
If nothing noteworthy happened, output: (nothing)
