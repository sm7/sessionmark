# bookmark

**Git, but for your AI coding sessions.**

You're deep in a debugging thread. A meeting pops up. Or you close the laptop. Or you switch from Claude Code to Cursor. 90 minutes later, the thread is gone.

```bash
bookmark save -m "focal loss regression — gamma=3 breaks minority class"
# ...tomorrow, different machine, different agent...
bookmark resume
```

```
📍 debug-focal-loss  saved 8h ago
~/code/transformerhttp  on  exp/focal-gamma @ a3f91c2

GOAL
  focal loss regression — gamma=3 breaks minority class

LAST AGENT EXCHANGE
  you   → run the eval with the new gamma
  agent → miss_rate went from 20.9 to 31.4. something's off in how
          the minority class is weighted.

TODOS (3)
  [ ] check BPE merge table for attack tokens
  [ ] rerun with gamma=2 as baseline
  [x] verify focal loss implementation matches paper

OPEN FILES (3)
  M  src/loss/focal.py          +12 -4
  M  scripts/eval.py            +3 -1
  ?  notes/gamma-tuning.md      new

NEXT STEP
  cd ~/code/transformerhttp && git checkout exp/focal-gamma
```

Local-first. No cloud. No auth. Works with Claude Code, Cursor, Codex CLI, Gemini CLI, Aider — and any MCP client.

> **Cross-agent fidelity caveat:** bookmark recovers the thread of thought, not live runtime state. Goal, files, TODOs, and recent exchange carry over. Open DB connections, running dev servers, and the original agent's native tool reasoning do not.

---

## Install

```bash
pipx install sessionmark
```

Or with pip:

```bash
pip install sessionmark
```

Requires Python 3.11+. Works on macOS and Linux.

**Optional — LLM briefing providers** (ollama, Anthropic, OpenAI, etc.):

```bash
pip install "sessionmark[llm]"
```

---

## 30 seconds to value

```bash
# 1. Save where you are
bookmark save wip -m "fixing the login race condition"

# 2. See all your sessions
bookmark list

# 3. Pick up where you left off
bookmark resume wip

# 4. Drop it into any agent
bookmark export wip --format paste --target cursor | pbcopy
# paste as your first message in a new Cursor chat
```

---

## All commands

```
bookmark save [NAME] [-m MSG] [--tag TAG] [--source AGENT] [--transcript-stdin]
bookmark resume [NAME|latest] [--apply] [--json]
bookmark show [NAME|latest] [--full] [--no-transcript] [--json]
bookmark list [--repo REPO] [--tag TAG] [--source AGENT] [-n N] [--all] [--json]
bookmark search QUERY [-n N] [--json]
bookmark diff NAME1 [NAME2]
bookmark delete NAME [-f]
bookmark export NAME [--format paste|md|json] [--target AGENT] [-o FILE]
bookmark import FILE

bookmark install --for AGENT|all       # install skill/command files for an agent
bookmark install --list                 # show installed agents
bookmark install --hooks                # Claude Code PreCompact + SessionEnd hooks

bookmark sync init --git URL            # set up git-backed sync
bookmark sync push                      # push to remote
bookmark sync pull                      # pull from remote
bookmark sync clone URL                 # clone onto a new machine

bookmark config get KEY                 # e.g. briefing.provider
bookmark config set KEY VALUE

bookmark doctor                         # health check: DB, blobs, agents, MCP
bookmark doctor --check-redaction       # verify secrets corpus is caught
```

**Short alias:** `bm` = `bookmark`

**Name resolution** for `show`, `resume`, `diff`, `delete`, `export`:
1. `latest` → most recently saved
2. Exact slug
3. Exact name (case-insensitive)
4. Unique prefix (e.g. `focal` → `debug-focal-loss` if unambiguous)
5. Ambiguous → lists candidates, exits 1

**Exit codes:** 0 success · 1 user error · 2 not found · 3 integrity error · 4 git sync conflict

---

## Shipping as a Claude Code skill

A **skill** is a markdown file that tells Claude Code when and how to invoke `bookmark`. One command writes it:

```bash
bookmark install --for claude-code
```

This drops `.claude/skills/bookmark/SKILL.md` into your current directory. Claude Code picks it up automatically on the next session.

**What the skill does:**

| You say | Claude Code runs |
|---|---|
| "bookmark this" / "save session" / "I need to stop" | `bookmark save --source claude-code --transcript-stdin -m "<goal>"` piping recent messages |
| "resume" / "what was I working on" / "load bookmark auth-fix" | `bookmark resume [name or latest]` |

**Install for every agent at once:**

```bash
bookmark install --for all
```

This drops skill/command files for Claude Code, Cursor, Codex CLI, Gemini CLI, and Aider in one shot. Re-running is a no-op if the files are already current.

**Install locations per agent:**

| Agent | File written |
|---|---|
| Claude Code | `.claude/skills/bookmark/SKILL.md` |
| Cursor | `.cursor/rules/bookmark.mdc` |
| Codex CLI | `.codex/commands/bookmark.md` |
| Gemini CLI | `.gemini/commands/bookmark.md` |
| Aider | `CONVENTIONS.md` (bookmark section appended) |

**Dry-run to preview:**

```bash
bookmark install --for all --dry-run
```

**Opt-in Claude Code hooks** — auto-bookmark on compaction and session end:

```bash
bookmark install --hooks
```

Adds `PreCompact` and `SessionEnd` entries to `.claude/settings.json`. These run `bookmark save --auto` silently in the background. Auto-bookmarks are hidden in `bookmark list` by default; use `--all` to see them.

**Manual skill content** (if you prefer to copy-paste instead of running `install`):

For Claude Code, create `.claude/skills/bookmark/SKILL.md`:

```markdown
# Bookmark skill

When the user says "bookmark this", "save session", "I need to stop", or similar:

Run: `bookmark save --source claude-code --transcript-stdin -m "<one-line summary of current goal>"`
Pipe the last 20 messages of the conversation as JSON-lines to stdin:
{"role": "user", "content": "...", "timestamp": "..."}
{"role": "assistant", "content": "...", "timestamp": "..."}

When the user says "resume", "what was I working on", or "load bookmark <name>":
Run: `bookmark resume [name or latest]`
Show the output to the user.
```

---

## Shipping as an MCP server

The MCP server lets **any MCP-compatible agent** call bookmark tools directly — no skill file needed.

### Start the server

```bash
sessionmark-mcp
```

Runs over stdio (the MCP default). For persistent HTTP mode:

```bash
sessionmark-mcp --http --port 7337   # coming in v0.2
```

### Tools exposed

| Tool | Arguments | Returns |
|---|---|---|
| `bookmark_save` | `name`, `message`, `tags` | `{id, name, summary}` |
| `bookmark_resume` | `name` (default `"latest"`) | `{briefing, goal, open_files, todos, next_step, source, saved_at}` |
| `bookmark_list` | `repo`, `tag`, `limit` | `[{name, when, goal}]` |
| `bookmark_search` | `query`, `limit` | `[{name, snippet, score}]` |
| `bookmark_show` | `name` | full bookmark record |

All results are structured JSON — the agent formats for the user.

### Wiring into Claude Code (MCP config)

Add to your Claude Code MCP config (`~/.claude/claude_desktop_config.json` or the project-level equivalent):

```json
{
  "mcpServers": {
    "bookmark": {
      "command": "sessionmark-mcp",
      "args": []
    }
  }
}
```

Restart Claude Code. The tools appear automatically. You can then say:

> "Save this session as auth-refactor"  
> "What was I working on yesterday?"  
> "Resume my last bookmark"

and Claude Code calls `bookmark_save` / `bookmark_list` / `bookmark_resume` directly.

### Wiring into Cursor

In Cursor's MCP settings (Settings → MCP):

```json
{
  "bookmark": {
    "command": "sessionmark-mcp",
    "args": [],
    "type": "stdio"
  }
}
```

### Wiring into any MCP client

Any client that supports stdio MCP servers works. The server binary is `sessionmark-mcp` (installed alongside `bookmark` when you `pip install sessionmark`).

**Verify the server starts:**

```bash
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}},"id":1}' | sessionmark-mcp
```

**Verify with `bookmark doctor`:**

```bash
bookmark doctor
```

Look for `✓ MCP server` in the output.

---

## Multi-agent workflow

Bookmark is built for users who float between agents. All bookmarks land in one SQLite database regardless of which agent captured them.

```bash
# Monday: deep in Claude Code
bookmark save focal-debug -m "gamma=3 breaks minority class"

# Tuesday: switch to Cursor
bookmark resume focal-debug
# → prints full briefing, past exchange, open files, TODOs

# Export for paste into any agent or web chat
bookmark export focal-debug --format paste --target cursor | pbcopy
```

Filter by capturing agent:

```bash
bookmark list --source claude-code
bookmark list --source cursor
bookmark list --source codex
```

---

## LLM briefing providers (optional)

By default, `bookmark resume` renders a deterministic template briefing — no network, no API key. Optionally configure a local or remote LLM to summarize the transcript:

```bash
# Local Ollama
bookmark config set briefing.provider "ollama:qwen2.5-coder:7b"

# Anthropic (needs ANTHROPIC_API_KEY env var)
bookmark config set briefing.provider "anthropic:claude-haiku-4-5"

# OpenAI
bookmark config set briefing.provider "openai:gpt-4o-mini"

# Google
bookmark config set briefing.provider "google:gemini-2.5-flash"

# Groq
bookmark config set briefing.provider "groq:llama-3.3-70b"

# Any OpenAI-compatible endpoint
bookmark config set briefing.provider "openai-compat:http://localhost:8080:mymodel"

# Back to default
bookmark config set briefing.provider "template"
```

API keys come from **environment variables only** — never written to config:
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`

On any failure (unreachable, missing key, timeout), falls back to template mode silently.

Install the optional `httpx` dep:

```bash
pip install "sessionmark[llm]"
```

---

## Git-backed sync

```bash
# Machine A
bookmark sync init --git git@github.com:you/my-bookmarks.git
bookmark sync push

# Machine B
bookmark sync clone git@github.com:you/my-bookmarks.git
bookmark resume focal-debug
```

Sync is a git repo you own. Bookmark never talks to a proprietary server.

> **v0.1.0 limitation:** `sync pull` overwrites the local `bookmarks.db`. Back up first if you have unsynchronized local bookmarks. Merge-on-pull is planned for v0.2.

---

## Secret redaction

Every piece of captured text (transcript, todos, env vars, goal) passes through the redaction layer before hitting disk. Patterns caught:

| Pattern | Replaced with |
|---|---|
| `AKIA[0-9A-Z]{16}` | `[REDACTED:aws]` |
| `sk-[a-zA-Z0-9]{20,}` | `[REDACTED:openai]` |
| `ghp_…`, `gho_…`, `ghs_…` | `[REDACTED:github]` |
| `xox[baprs]-…` | `[REDACTED:slack]` |
| High-entropy base64 after `token=`, `password=`, `secret=`, `api_key=`, `Authorization:` | `[REDACTED:generic]` |

`.env` and `.env.*` files are never read.

Verify your installation catches all patterns:

```bash
bookmark doctor --check-redaction
# PASS: 10/10 lines redacted correctly
```

---

## Storage

Everything lives under `~/.bookmark/` (override with `$BOOKMARK_HOME`):

```
~/.bookmark/
├── config.toml
├── bookmarks.db          # SQLite — all agents, one DB
├── blobs/
│   ├── tr/<id>/          # transcripts (JSONL)
│   └── <sha256>/         # files + diffs (gzip, content-addressed)
└── sync/                 # optional git-backed sync working dir
    └── .git/
```

---

## Configuration

```bash
bookmark config get briefing.provider
bookmark config set briefing.provider "ollama:qwen2.5-coder:7b"
```

Full config reference (`~/.bookmark/config.toml`):

```toml
[general]
default_source = "terminal"
max_transcript_messages = 20
recent_file_window_seconds = 7200   # capture files modified in last 2h

[capture]
include_shell_history = true
include_env = true
include_git_diff = true
max_diff_bytes = 262144

[redaction]
enabled = true

[briefing]
provider = "template"               # see LLM providers section
max_summary_sentences = 4
timeout_seconds = 10

[sync]
enabled = false
git_remote = ""

[ui]
show_source_column = true
color = "auto"                      # auto | always | never
```

---

## Developing / contributing

```bash
git clone https://github.com/smukhopa/sessionmark
cd sessionmark
pip install -e ".[dev]"
pytest
```

```bash
ruff check src/
ruff format src/
```

Tests: 134 passing, covering core save/resume, redaction, storage, MCP server, per-agent install, briefing providers, sync, search, export, and CLI integration.

---

## License

MIT
