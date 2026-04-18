## Bookmark

Saves session context so work can be resumed on another machine or continued in a different agent (Claude Code, Cursor, JetBrains, etc.).

When the user says "save my progress", "I need to stop", "switching machines", "hand off to [agent]", or "bookmark this":
Run: `sessionmark save --source aider --transcript-stdin -m "<current goal>"`
Pipe recent conversation as JSON-lines to stdin.

When the user says "resume", "pick up where I left off", "what was I working on", or "load session [name]":
Run: `sessionmark resume [name or latest]`
Show the output to the user.
