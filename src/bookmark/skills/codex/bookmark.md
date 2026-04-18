# /sessionmark

When the user says "save my progress", "I need to stop", "switching machines", "hand off to [agent]", or "bookmark this":
  sessionmark save --source codex --transcript-stdin -m "<goal>"
Pipe recent messages as JSON-lines to stdin.

When the user says "resume", "pick up where I left off", "what was I working on", or "load session [name]":
  sessionmark resume [name or latest]
