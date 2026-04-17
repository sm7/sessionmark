## Bookmark

When the user says "bookmark this" or "save session":
Run: `bookmark save --source aider --transcript-stdin -m "<current goal>"`
Pipe recent conversation as JSON-lines to stdin.

When the user says "resume" or "what was I working on":
Run: `bookmark resume [name or latest]`
Show the output to the user.
