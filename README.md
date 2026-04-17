# Bookmark your sessions 

**Git, but for your AI coding sessions.**

You're deep in a debugging thread. A meeting pops up. Or you close the laptop. Or you switch from Claude Code to Cursor. 90 minutes later, the thread is gone.

```bash
sessionmark save -m "focal loss regression — gamma=3 breaks minority class"
# ...tomorrow, different machine, different agent...
sessionmark resume
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

> **Cross-agent fidelity caveat:** sessionmark recovers the thread of thought, not live runtime state. Goal, files, TODOs, and recent exchange carry over. Open DB connections, running dev servers, and the original agent's native tool reasoning do not.

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
sessionmark save wip -m "fixing the login race condition"

# 2. See all your sessions
sessionmark list

# 3. Pick up where you left off
sessionmark resume wip

# 4. Drop it into any agent
sessionmark export wip --format paste --target cursor | pbcopy
# paste as your first message in a new Cursor chat
```

---

## All commands

```
sessionmark save [NAME] [-m MSG] [--tag TAG] [--source AGENT] [--transcript-stdin]
sessionmark resume [NAME|latest] [--apply] [--json]
sessionmark show [NAME|latest] [--full] [--no-transcript] [--json]
sessionmark list [--repo REPO] [--tag TAG] [--source AGENT] [-n N] [--all] [--json]
sessionmark search QUERY [-n N] [--json]
sessionmark diff NAME1 [NAME2]
sessionmark delete NAME [-f]
sessionmark export NAME [--format paste|md|json] [--target AGENT] [-o FILE]
sessionmark import FILE

sessionmark install --for AGENT|all       # install skill/command files for an agent
sessionmark install --list                 # show installed agents
sessionmark install --hooks                # Claude Code PreCompact + SessionEnd hooks

sessionmark sync init --git URL            # set up git-backed sync
sessionmark sync push                      # push to remote
sessionmark sync pull                      # pull from remote
sessionmark sync clone URL                 # clone onto a new machine

sessionmark config get KEY                 # e.g. briefing.provider
sessionmark config set KEY VALUE

sessionmark doctor                         # health check: DB, blobs, agents, MCP
sessionmark doctor --check-redaction       # verify secrets corpus is caught
```

**Short alias:** `sm` = `sessionmark`

**Name resolution** for `show`, `resume`, `diff`, `delete`, `export`:
1. `latest` → most recently saved
2. Exact slug
3. Exact name (case-insensitive)
4. Unique prefix (e.g. `focal` → `debug-focal-loss` if unambiguous)
5. Ambiguous → lists candidates, exits 1

**Exit codes:** 0 success · 1 user error · 2 not found · 3 integrity error · 4 git sync conflict

---

## Shipping as a Claude Code skill

A **skill** is a markdown file that tells Claude Code when and how to invoke `sessionmark`. One command writes it:

```bash
sessionmark install --for claude-code
```

This drops `.claude/skills/sessionmark/SKILL.md` into your current directory. Claude Code picks it up automatically on the next session.

**What the skill does:**

| You say | Claude Code runs |
|---|---|
| "sessionmark this" / "save session" / "I need to stop" | `sessionmark save --source claude-code --transcript-stdin -m "<goal>"` piping recent messages |
| "resume" / "what was I working on" / "load sessionmark auth-fix" | `sessionmark resume [name or latest]` |

**Install for every agent at once:**

```bash
sessionmark install --for all
```

This drops skill/command files for Claude Code, Cursor, Codex CLI, Gemini CLI, and Aider in one shot. Re-running is a no-op if the files are already current.

**Install locations per agent:**

| Agent | File written |
|---|---|
| Claude Code | `.claude/skills/sessionmark/SKILL.md` |
| Cursor | `.cursor/rules/sessionmark.mdc` |
| Codex CLI | `.codex/commands/sessionmark.md` |
| Gemini CLI | `.gemini/commands/sessionmark.md` |
| Aider | `CONVENTIONS.md` (sessionmark section appended) |

**Dry-run to preview:**

```bash
sessionmark install --for all --dry-run
```

**Opt-in Claude Code hooks** — auto-sessionmark on compaction and session end:

```bash
sessionmark install --hooks
```

Adds `PreCompact` and `SessionEnd` entries to `.claude/settings.json`. These run `sessionmark save --auto` silently in the background. Auto-sessionmarks are hidden in `sessionmark list` by default; use `--all` to see them.

**Manual skill content** (if you prefer to copy-paste instead of running `install`):

For Claude Code, create `.claude/skills/sessionmark/SKILL.md`:

```markdown
# sessionmark skill

When the user says "sessionmark this", "save session", "I need to stop", or similar:

Run: `sessionmark save --source claude-code --transcript-stdin -m "<one-line summary of current goal>"`
Pipe the last 20 messages of the conversation as JSON-lines to stdin:
{"role": "user", "content": "...", "timestamp": "..."}
{"role": "assistant", "content": "...", "timestamp": "..."}

When the user says "resume", "what was I working on", or "load sessionmark <name>":
Run: `sessionmark resume [name or latest]`
Show the output to the user.
```

---

## Shipping as an MCP server

The MCP server lets **any MCP-compatible agent** call sessionmark tools directly — no skill file needed.

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
| `sessionmark_save` | `name`, `message`, `tags` | `{id, name, summary}` |
| `sessionmark_resume` | `name` (default `"latest"`) | `{briefing, goal, open_files, todos, next_step, source, saved_at}` |
| `sessionmark_list` | `repo`, `tag`, `limit` | `[{name, when, goal}]` |
| `sessionmark_search` | `query`, `limit` | `[{name, snippet, score}]` |
| `sessionmark_show` | `name` | full sessionmark record |

All results are structured JSON — the agent formats for the user.

### Wiring into Claude Code (MCP config)

Add to your Claude Code MCP config (`~/.claude/claude_desktop_config.json` or the project-level equivalent):

```json
{
  "mcpServers": {
    "sessionmark": {
      "command": "sessionmark-mcp",
      "args": []
    }
  }
}
```

Restart Claude Code. The tools appear automatically. You can then say:

> "Save this session as auth-refactor"  
> "What was I working on yesterday?"  
> "Resume my last sessionmark"

and Claude Code calls `sessionmark_save` / `sessionmark_list` / `sessionmark_resume` directly.

### Wiring into Cursor

In Cursor's MCP settings (Settings → MCP):

```json
{
  "sessionmark": {
    "command": "sessionmark-mcp",
    "args": [],
    "type": "stdio"
  }
}
```

### Wiring into any MCP client

Any client that supports stdio MCP servers works. The server binary is `sessionmark-mcp` (installed alongside `sessionmark` when you `pip install sessionmark`).

**Verify the server starts:**

```bash
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}},"id":1}' | sessionmark-mcp
```

**Verify with `sessionmark doctor`:**

```bash
sessionmark doctor
```

Look for `✓ MCP server` in the output.

---

## Multi-agent workflow

Sessionmark is built for users who float between agents. All sessionmarks land in one SQLite database regardless of which agent captured them.

```bash
# Monday: deep in Claude Code
sessionmark save focal-debug -m "gamma=3 breaks minority class"

# Tuesday: switch to Cursor
sessionmark resume focal-debug
# → prints full briefing, past exchange, open files, TODOs

# Export for paste into any agent or web chat
sessionmark export focal-debug --format paste --target cursor | pbcopy
```

Filter by capturing agent:

```bash
sessionmark list --source claude-code
sessionmark list --source cursor
sessionmark list --source codex
```

---

## LLM briefing providers (optional)

By default, `sessionmark resume` renders a deterministic template briefing — no network, no API key. Optionally configure a local or remote LLM to summarize the transcript:

```bash
# Local Ollama
sessionmark config set briefing.provider "ollama:qwen2.5-coder:7b"

# Anthropic (needs ANTHROPIC_API_KEY env var)
sessionmark config set briefing.provider "anthropic:claude-haiku-4-5"

# OpenAI
sessionmark config set briefing.provider "openai:gpt-4o-mini"

# Google
sessionmark config set briefing.provider "google:gemini-2.5-flash"

# Groq
sessionmark config set briefing.provider "groq:llama-3.3-70b"

# Any OpenAI-compatible endpoint
sessionmark config set briefing.provider "openai-compat:http://localhost:8080:mymodel"

# Back to default
sessionmark config set briefing.provider "template"
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
sessionmark sync init --git git@github.com:you/my-sessionmarks.git
sessionmark sync push

# Machine B
sessionmark sync clone git@github.com:you/my-sessionmarks.git
sessionmark resume focal-debug
```

Sync is a git repo you own. Sessionmark never talks to a proprietary server.

> **v0.1.0 limitation:** `sync pull` overwrites the local `sessionmarks.db`. Back up first if you have unsynchronized local sessionmarks. Merge-on-pull is planned for v0.2.

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
sessionmark doctor --check-redaction
# PASS: 10/10 lines redacted correctly
```

---

## Storage

Everything lives under `~/.sessionmark/` (override with `$SESSIONMARK_HOME`):

```
~/.sessionmark/
├── config.toml
├── sessionmarks.db          # SQLite — all agents, one DB
├── blobs/
│   ├── tr/<id>/          # transcripts (JSONL)
│   └── <sha256>/         # files + diffs (gzip, content-addressed)
└── sync/                 # optional git-backed sync working dir
    └── .git/
```

---

## Configuration

```bash
sessionmark config get briefing.provider
sessionmark config set briefing.provider "ollama:qwen2.5-coder:7b"
```

Full config reference (`~/.sessionmark/config.toml`):

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
