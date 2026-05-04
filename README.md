# sessionmark

**Save and resume AI coding sessions across agents and machines.**

You're deep in a debugging thread with Claude Code. A meeting pops up. Or you switch to Cursor. Or you start fresh the next morning. The thread is gone.

```bash
sessionmark save focal-debug -m "gamma=3 breaks minority class"
# later, in any agent, in the same directory...
sessionmark resume focal-debug
```

```
📍 focal-debug  saved 8h ago
~/code/transformerhttp  on  exp/focal-gamma @ a3f91c2

GOAL
  gamma=3 breaks minority class

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

Local-first. No cloud. No auth. Works with Claude Code, Cursor, Codex CLI, Gemini CLI, GitHub Copilot, and Windsurf — and any MCP client.

> **Cross-agent fidelity:** sessionmark recovers goal, files, TODOs, git state, and full exchange. Open DB connections and running dev servers don't carry over.

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

# 4. Export for pasting into any agent or web chat
sessionmark export wip --format paste --target cursor | pbcopy
```

---

## Automatic context injection

The most seamless workflow: `sessionmark install` writes a compressed session
block directly into each agent's startup config file. The next time you open
Claude Code, Cursor, Codex CLI, or any other installed agent in that directory,
it reads the session context automatically — no resume command needed.

```bash
# One-time setup per project
cd ~/code/myproject
sessionmark install --for all
```

This writes a `<!-- sessionmark:start ... sessionmark:end -->` block into each
agent's project-local config file. After that, every `sessionmark save` or
`sessionmark resume` updates the block silently in the background.

**Config files written per agent:**

| Agent | File |
|---|---|
| Claude Code | `CLAUDE.md` |
| Codex CLI | `AGENTS.md` |
| Cursor | `.cursor/rules/sessionmark.mdc` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Windsurf | `.windsurf/rules/sessionmark.md` |
| Gemini CLI | `.gemini/system.md` (full system prompt) |

**Context is project-scoped.** Session A never bleeds into project B because
each project has its own config files.

**Installing onto an existing file is safe.** sessionmark appends the block
without touching your existing content. Re-running `install` is a no-op if
the block is already present.

```bash
# Install for one agent
sessionmark install --for claude-code

# Install for all agents at once
sessionmark install --for all

# Preview without writing
sessionmark install --for all --dry-run

# Check what's installed in the current project
sessionmark install --list
```

### How the encoding works

The injected block uses LPIC+CSV encoding to keep the context under ~40 tokens
(down from ~500 for verbose markdown). A dictionary of repeated substrings is
built from the session data, then the fields are written as a single CSV line
with substitutions applied:

```
<!-- sessionmark-schema: fields sep=, lists sep=| bool=0/1
     keys:n=name,g=goal,b=branch,... -->

<!-- sessionmark:start
dict:A=src/bookmark/,B=bookmark-cli,C=v0.1.0
-->
n:B-build,g:Built B C all 5 weeks of work,b:master,h:a3f91c2,...
<!-- sessionmark:end -->
```

This was validated against OpenAI o3 in both explicit decode mode and agentic
mode ("what are we working on?") — 100% lossless at ~92% token reduction.

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

sessionmark install --for AGENT|all       # inject context sections into agent config files
sessionmark install --list                 # show which agents have sections installed
sessionmark install --hooks                # Claude Code PreCompact + SessionEnd hooks

sessionmark sync init --git URL            # set up git-backed sync
sessionmark sync push                      # push to remote
sessionmark sync pull                      # pull from remote
sessionmark sync clone URL                 # clone onto a new machine

sessionmark config get KEY                 # e.g. briefing.provider
sessionmark config set KEY VALUE

sessionmark doctor                         # health check: DB, blobs, agents, install status
sessionmark doctor --check-redaction       # verify secrets corpus is caught
```

**Short alias:** `sm` = `sessionmark`

**Name resolution** for `show`, `resume`, `diff`, `delete`, `export`:
1. `latest` → most recently saved
2. Exact slug
3. Exact name (case-insensitive)
4. Unique prefix (e.g. `focal` → `focal-debug` if unambiguous)
5. Ambiguous → lists candidates, exits 1

**Exit codes:** 0 success · 1 user error · 2 not found · 3 integrity error · 4 git sync conflict

---

## Opt-in Claude Code hooks

Auto-save on compaction and session end:

```bash
sessionmark install --hooks
```

Adds `PreCompact` and `SessionEnd` entries to `.claude/settings.json`. These
run `sessionmark save --auto` silently in the background. Auto-saves are hidden
in `sessionmark list` by default; use `--all` to see them.

---

## MCP server

The MCP server lets any MCP-compatible agent call sessionmark tools directly.

```bash
sessionmark-mcp
```

**Tools exposed:**

| Tool | Arguments | Returns |
|---|---|---|
| `sessionmark_save` | `name`, `message`, `tags` | `{id, name, summary}` |
| `sessionmark_resume` | `name` (default `"latest"`) | `{briefing, goal, open_files, todos, next_step, source, saved_at}` |
| `sessionmark_list` | `repo`, `tag`, `limit` | `[{name, when, goal}]` |
| `sessionmark_search` | `query`, `limit` | `[{name, snippet, score}]` |
| `sessionmark_show` | `name` | full sessionmark record |

**Wiring into Claude Code** (`~/.claude/claude_desktop_config.json`):

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

---

## Multi-agent workflow

All sessionmarks land in one SQLite database regardless of which agent captured them.

```bash
# Monday: deep in Claude Code
sessionmark save focal-debug -m "gamma=3 breaks minority class"

# Tuesday: open Cursor in the same directory
# → Cursor reads the injected context block from .cursor/rules/sessionmark.mdc automatically

# Or resume explicitly in any agent
sessionmark resume focal-debug
```

Filter by capturing agent:

```bash
sessionmark list --source claude-code
sessionmark list --source cursor
sessionmark list --source codex
sessionmark list --source github-copilot
```

---

## LLM briefing providers (optional)

By default, `sessionmark resume` renders a deterministic template briefing — no
network, no API key. Optionally configure a local or remote LLM to summarize
the transcript:

```bash
# Local Ollama
sessionmark config set briefing.provider "ollama:qwen2.5-coder:7b"

# Anthropic (needs ANTHROPIC_API_KEY)
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

API keys come from environment variables only — never written to config:
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`

On any failure (unreachable, missing key, timeout), falls back to template mode silently.

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

Sync is a git repo you own. sessionmark never talks to a proprietary server.

---

## Secret redaction

Every piece of captured text (transcript, todos, env vars, goal) passes through
the redaction layer before hitting disk.

| Pattern | Replaced with |
|---|---|
| `AKIA[0-9A-Z]{16}` | `[REDACTED:aws]` |
| `sk-[a-zA-Z0-9]{20,}` | `[REDACTED:openai]` |
| `ghp_…`, `gho_…`, `ghs_…` | `[REDACTED:github]` |
| `xox[baprs]-…` | `[REDACTED:slack]` |
| High-entropy base64 after `token=`, `password=`, `secret=`, `api_key=`, `Authorization:` | `[REDACTED:generic]` |

`.env` and `.env.*` files are never read.

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
sessionmark config get briefing.provider
sessionmark config set briefing.provider "ollama:qwen2.5-coder:7b"
```

Full config reference (`~/.sessionmark/config.toml`):

```toml
[general]
default_source = "terminal"
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
git clone https://github.com/sm7/sessionmark
cd sessionmark
pip install -e ".[dev]"
pytest
```

```bash
ruff check src/
ruff format src/
```

---

## License

MIT
