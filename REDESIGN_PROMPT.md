# sessionmark Redesign Implementation Prompt

Hand this document to an AI coding agent to implement the new working principle. Read it top to bottom and implement all sections.

---

## Section 1: First Task

Create the branch before making any changes:

```bash
git checkout master && git pull && git checkout -b feature/update-working-principle
```

---

## Section 2: What sessionmark Is

sessionmark is a Python CLI tool that saves and resumes AI coding sessions. It captures git state, open files, diffs, todos, shell history, and conversation transcripts, storing everything in a local SQLite DB at `~/.bookmark/`. The CLI entry point is `sessionmark`. The internal Python package is `bookmark`.

- Current version: 0.2.0
- Python 3.11+
- Build system: hatch
- Linter: ruff, line-length=100, rules E/F/I/UP

---

## Section 3: Problem with the Current Design

The current design installs agent-specific skill files into project directories such as `.claude/skills/bookmark/SKILL.md` and `.codex/commands/bookmark.md`. These files contain trigger phrases that prompt the agent to run `sessionmark save`.

This only works for the save side. On the resume side the user must manually type a trigger phrase in the new agent session. There is no automatic context injection into the receiving agent. The handoff is not seamless.

---

## Section 4: The New Working Principle

When `sessionmark save` is called it should do two things:

1. Save the session to the SQLite DB as before. All existing DB features are preserved.
2. Write a compressed context section directly into each installed agent config file inside a clearly marked block.

When the user opens any agent in the same project directory, that agent reads its own config file at startup and sees the context section automatically. No trigger phrase needed. No resume command needed on the receiving end. Context injection is invisible to the user.

When `sessionmark resume NAME` is called it should:

1. Print the full formatted briefing as before.
2. Update the compressed section in all installed config files to that session, so the next agent opened in this directory gets that session's context.

---

## Section 5: Verified Agent Config Files

These are the verified project-local config files each agent reads unconditionally at startup. All files live inside the repo directory so context from project A never appears when opening an agent in project B.

| Agent | File | Notes |
|---|---|---|
| Claude Code | `CLAUDE.md` | Also reads global `~/.claude/CLAUDE.md` which merges with project file |
| Codex CLI | `AGENTS.md` | Project root. First match wins. 32 KiB limit. |
| Cursor | `.cursor/rules/sessionmark.mdc` | `.cursorrules` is deprecated — do NOT use it |
| GitHub Copilot | `.github/copilot-instructions.md` | Works for VS Code extension and JetBrains plugin |
| Windsurf | `.windsurf/rules/sessionmark.md` | Ignore global `~/.windsurf/rules/` |
| Gemini CLI | `.gemini/system.md` | FULL OVERRIDE — sessionmark must own entire file contents |

Aider has no auto-loaded instructions file. Skip it for context injection.

---

## Section 6: Encoding — LPIC + CSV

Context sections must be token-efficient. Use LPIC (Lossless Prompt Compression via Dictionary-Encoding and In-Context Learning, arxiv 2604.13066) combined with CSV-style field encoding.

This has been manually validated against OpenAI o3 in both explicit decode mode and agentic mode ("what are we working on?"). Both returned 100% lossless output. Token savings: ~500 tokens verbose markdown → ~40 tokens LPIC+CSV (~92% reduction).

### 6.1 Schema Line

Written once at install. Never modified by save or resume. Write this exact string into every config file:

```
<!-- sessionmark-schema: fields sep=, lists sep=| bool=0/1 keys:n=name,g=goal,b=branch,r=repo,s=source,f=files,t=todos(done:text),c=commands. When you see a sessionmark block expand all single-letter tokens using the dict before reading the session context. -->
```

### 6.2 Data Section Format

Updated on every save or resume. The full block must follow this exact format:

```
<!-- sessionmark:start
dict:A=src/bookmark/,B=bookmark-cli,C=v0.1.0
-->
n:B-build,g:Built B C — all 5 weeks of work,b:master,r:bookmark,s:claude-code,f:Acore/save.py|Astorage/db.py|Acli.py,t:0:publish to PyPI|0:write README|1:initial release,c:pytest tests/|ruff check src/|git tag C
<!-- sessionmark:end -->
```

In this example `A` expands to `src/bookmark/`, `B` expands to `bookmark-cli`, `C` expands to `v0.1.0`. The data is a single CSV line. Fields are separated by `,`. List items within a field are separated by `|`. Bool values are `0` for not done and `1` for done.

### 6.3 Gemini Special Case

`.gemini/system.md` is a full system prompt override. sessionmark must own and manage the entire file, structured as a valid standalone system prompt with the compressed session section at the end.

### 6.4 Dict Building Algorithm

Implement in `src/bookmark/install/context_writer.py`:

- Collect all string values from the session: goal, branch, repo, file paths, commands, todos
- Find substrings that appear 2 or more times and are longer than 4 characters
- Rank by `(occurrences - 1) * len(substring)` to get net character saving
- Assign single uppercase letters A, B, C... to top candidates
- Only include entries where net saving exceeds `len(key) + 1 + len(value) + 1` (dict overhead)
- Apply substitutions to the data string before writing

---

## Section 7: install Command Changes

`sessionmark install --for AGENT` should:

- Create the config file if it does not exist, writing the schema line and empty markers
- If the file exists with no sessionmark section, append the schema line and empty markers
- If the file exists with a sessionmark section already, leave it unchanged (idempotent)
- Return `{"action": "installed" | "already_installed" | "dry_run"}`

`sessionmark install --for all` installs for all 6 agents in Section 5.

Remove `src/bookmark/skills/` and all per-agent skill template files. The installer no longer copies static skill files.

---

## Section 8: save Command Changes

After the existing DB save logic in `src/bookmark/core/save.py`, call `context_writer.update_all_installed(cwd, session)` which:

- Detects which config files from Section 5 are present in cwd
- Builds the LPIC dict from the session data
- Encodes the session as a single CSV line with dict substitutions applied
- Updates the sessionmark section in each present file
- Skips silently if no config files are present (user has not run install yet)

---

## Section 9: resume Command Changes

After generating the briefing in `src/bookmark/core/resume.py`, call `context_writer.update_all_installed(cwd, session)` to update all installed config files to the resumed session. Opening any agent after `sessionmark resume NAME` will automatically have that session's context.

---

## Section 10: New Module

Create `src/bookmark/install/context_writer.py` with this exact interface:

```python
from pathlib import Path
from typing import Literal

CONFIG_FILES: dict[str, dict] = {
    "claude-code":    {"path": "CLAUDE.md",                       "mode": "append_section"},
    "codex":          {"path": "AGENTS.md",                       "mode": "append_section"},
    "cursor":         {"path": ".cursor/rules/sessionmark.mdc",   "mode": "append_section"},
    "github-copilot": {"path": ".github/copilot-instructions.md", "mode": "append_section"},
    "windsurf":       {"path": ".windsurf/rules/sessionmark.md",  "mode": "append_section"},
    "gemini":         {"path": ".gemini/system.md",               "mode": "full_override"},
}

SCHEMA_LINE = (
    "<!-- sessionmark-schema: fields sep=, lists sep=| bool=0/1 "
    "keys:n=name,g=goal,b=branch,r=repo,s=source,f=files,"
    "t=todos(done:text),c=commands. "
    "When you see a sessionmark block expand all single-letter tokens "
    "using the dict before reading the session context. -->"
)

def build_dict(session_str: str) -> dict[str, str]: ...
def encode_session(session: dict, sub_dict: dict[str, str]) -> str: ...
def update_context_section(
    config_file: Path,
    compressed: str,
    mode: Literal["append_section", "full_override"],
) -> bool: ...
def install_section(config_file: Path) -> Literal["installed", "already_installed"]: ...
def update_all_installed(cwd: Path, session: dict) -> list[Path]: ...
def clear_section(config_file: Path) -> bool: ...
```

---

## Section 11: What to Keep Unchanged

Do not modify any of these:

- `src/bookmark/storage/db.py` — SQLite schema and all CRUD
- `src/bookmark/storage/blobs.py` — blob store
- `src/bookmark/core/models.py` — Bookmark, TodoItem, EnvVar models
- `src/bookmark/capture/` — all agent transcript readers
- `src/bookmark/briefing/` — briefing template and LLM providers
- `src/bookmark/mcp/server.py` — MCP server tools
- `src/bookmark/redact.py` — secret redaction
- `src/bookmark/sync.py` — git-backed sync
- `src/bookmark/cli.py` — all existing CLI commands and flags
- `src/bookmark/config.py` — config loading
- `src/bookmark/install/hooks.py` — Claude Code PreCompact and SessionEnd hooks

---

## Section 12: Tests Required

All existing tests must pass or be updated to match new behaviour. New tests for `context_writer.py` must cover:

- `install_section` on a new file: creates file with schema line and empty markers
- `install_section` on existing file: appends section at end
- `install_section` is idempotent: second call makes no changes
- `build_dict` finds correct repeated substrings and assigns A, B, C in order
- `build_dict` skips entries where dict overhead exceeds savings
- `encode_session` produces correct single CSV line with substitutions applied
- `update_context_section` replaces existing section content correctly
- `update_context_section` full_override mode replaces entire file (Gemini)
- `clear_section` removes the section entirely
- `update_all_installed` only touches config files that already exist in cwd
- `update_all_installed` skips silently when no config files are present
- `save()` triggers context update in present config files
- `resume()` triggers context update in present config files
- Decoded output matches original session data exactly (lossless validation)

---

## Section 13: Constraints

- All ruff checks must pass: `ruff check src/` with line-length=100 and rules E/F/I/UP
- No new dependencies unless strictly necessary
- The `<!-- sessionmark:start -->` and `<!-- sessionmark:end -->` markers must be identical across all file formats so a single regex can find and replace the section
- For `.mdc` files (Cursor), HTML comment markers work — Cursor ignores them in rendering
- Dict keys must be single uppercase letters A–Z only, maximum 26 entries per session
- The schema line must never be modified after install — only the data section changes
- Commit incrementally with clear messages
- Push to `origin feature/update-working-principle` when done

---

## Section 14: Validation Proof

This encoding scheme was manually validated against OpenAI o3 (thinking model) in both explicit decode mode and agentic mode. Both returned 100% lossless output.

Compressed block that was tested:

```
<!-- sessionmark-schema: fields sep=, lists sep=| bool=0/1 keys:n=name,g=goal,b=branch,r=repo,s=source,f=files,t=todos(done:text),c=commands. When you see a sessionmark block expand all single-letter tokens using the dict before reading the session context. -->

<!-- sessionmark:start
dict:A=src/bookmark/,B=bookmark-cli,C=v0.1.0
-->
n:B-build,g:Built B C — all 5 weeks of work,b:master,r:bookmark,s:claude-code,f:Acore/save.py|Astorage/db.py|Acli.py,t:0:publish to PyPI|0:write README|1:initial release,c:pytest tests/|ruff check src/|git tag C
<!-- sessionmark:end -->
```

Verified decoded output:

```
name:     bookmark-cli-build
goal:     Built bookmark-cli v0.1.0 — all 5 weeks of work
branch:   master
repo:     bookmark
source:   claude-code
files:    src/bookmark/core/save.py
          src/bookmark/storage/db.py
          src/bookmark/cli.py
todos:    [ ] publish to PyPI
          [ ] write README
          [x] initial release
commands: pytest tests/
          ruff check src/
          git tag v0.1.0
```

Token count: ~500 tokens verbose markdown → ~40 tokens LPIC+CSV. ~92% reduction. All fields preserved exactly.
