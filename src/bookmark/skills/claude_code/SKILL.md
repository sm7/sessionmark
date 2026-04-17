# Bookmark skill

When the user says "bookmark this", "save session", "I need to stop", or similar:

Run: `bookmark save --source claude-code --transcript-stdin -m "<one-line summary of current goal>"`
Pipe the last 20 messages of the conversation as JSON-lines to stdin, format:
{"role": "user", "content": "...", "timestamp": "..."}
{"role": "assistant", "content": "...", "timestamp": "..."}

When the user says "resume", "what was I working on", or "load bookmark <name>":
Run: `bookmark resume [name or latest]`
Show the output to the user.
