# Bookmark skill for Gemini

When the user says "bookmark this", "save session", or "I need to stop":

Run: `bookmark save --source gemini --transcript-stdin -m "<one-line goal>"`
Pipe recent conversation messages as JSON-lines to stdin.

When the user says "resume", "load bookmark <name>", or "what was I working on":
Run: `bookmark resume [name or latest]`
Show the output to the user.
