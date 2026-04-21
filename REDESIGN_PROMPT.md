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

When `sessionmark save` is called from inside a project directory it should do two things:

1. Save the session to the SQLite DB as before. All existing DB features are preserved.
2. Write a compressed context section directly into each installed agent config file inside a clearly marked block.

When the user opens any agent in the same project directory, that agent reads its own config file at startup and sees the context section automatically. No trigger phrase needed. No resume command needed on the receiving end. Context injection is invisible to the user.

When `sessionmark resume NAME` is called it should:

1. Print the full formatted briefing as before.
2. Update the compressed section in all installed config files found in cwd to that session, so the next agent opened in this directory gets that session's context.

Important: context injection is project-scoped. The user must be in the project directory when running save or resume for the config files to be updated. Context from project A never appears in project B because each project has its own config files.

---

## Section 5: Verified Agent Config Files

These are the verified project-local config files each agent reads unconditionally at startup. All files live inside the repo directory.

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
<!-- sessionmark-schema: fields sep=, lists sep=| bool=0/1 keys:n=name,g=goal,b=branch,h=head,r=repo,s=source,f=files(type:path),t=todos(done:text),c=commands,x=context,nxt=next_step. When you see a sessionmark block expand all single-letter tokens using the dict before reading the session context. -->
```

### 6.2 Data Section Format

Updated on every save or resume. The full block must follow this exact format:

```
<!-- sessionmark:start
dict:A=src/bookmark/,B=bookmark-cli,C=v0.1.0
-->
n:B-build,g:Built B C — all 5 weeks of work,b:master,h:a3f91c2,r:bookmark,s:claude-code,f:M:Acore/save.py|M:Astorage/db.py|M:Acli.py,t:0:publish to PyPI|0:write README|1:initial release,c:pytest tests/|ruff check src/|git tag C,x:completed initial release of B C covering full feature set,nxt:cd ~/code/bookmark && git checkout master
<!-- sessionmark:end -->
```

Field reference:
- `n` = session name
- `g` = goal
- `b` = git branch
- `h` = git head short hash (7 chars)
- `r` = repo name
- `s` = source agent
- `f` = modified files as type:path pairs where type is M for modified, A for added, D for deleted
- `t` = todos as done:text pairs where done is 0 for pending and 1 for complete
- `c` = commands run during session (deduplicated, most recent first)
- `x` = one or two sentence context summary of what was found or decided
- `nxt` = next step command to resume work (cd path and git checkout branch)

Fields are separated by `,`. List items within a field are separated by `|`. The data is always a single line.

### 6.3 Transcript Context Extraction

The `x` (context) field and `c` (commands) field are extracted from the transcript blob stored in `~/.bookmark/blobs/tr/<id>/`. The transcript is a JSONL file. Each line is a JSON object.

To extract commands: find all lines where the type is tool_use and the tool name is Bash or bash. Extract the command field. Deduplicate. Take the 5 most recent unique commands.

To extract context: take the last 2 assistant messages. Strip tool call content. Concatenate into a 1-2 sentence summary. If no transcript is available, use the goal field as the context.

To extract MCP tools used: find all lines where type is tool_use and the tool name starts with mcp__ or contains a dot suggesting a namespaced tool. List unique tool names only.

### 6.4 Gemini Special Case

`.gemini/system.md` is a full system prompt override. sessionmark must own and manage the entire file. Structure it as a valid standalone system prompt with the compressed session section at the end. Do not use append_section mode for Gemini.

### 6.5 Dict Building Algorithm

Implement in `src/bookmark/install/context_writer.py`:

- Collect all string values from the session fields into one string
- Find substrings that appear 2 or more times and are longer than 4 characters
- Rank by `(occurrences - 1) * len(substring)` to get net character saving
- Assign single uppercase letters A, B, C... to top candidates in order of saving
- Only include entries where net saving exceeds `len(key) + 1 + len(value) + 1` which is the dict overhead
- Apply substitutions to the full data string before writing

### 6.6 Section Regex

Use this exact regex to find and replace the section in any config file:

```python
import re
SECTION_RE = re.compile(
    r"<!-- sessionmark:start.*?<!-- sessionmark:end -->",
    re.DOTALL,
)
```

---

## Section 7: install Command Changes

`sessionmark install --for AGENT` should:

- Create the config file if it does not exist, writing the schema line and empty markers
- If the file exists with no sessionmark section, append the schema line and empty markers
- If the file exists with a sessionmark section already, leave it unchanged (idempotent)
- Return `{"action": "installed" | "already_installed" | "dry_run"}`

`sessionmark install --for all` installs for all 6 agents in Section 5.

`list_installs(cwd)` in `src/bookmark/install/installer.py` must be updated. It currently checks for old skill file paths. It must now check whether the agent config file exists in cwd AND contains a sessionmark section. Return `{"agent": ..., "dest": ..., "installed": bool}` for each agent.

Remove `src/bookmark/skills/` and all per-agent skill template files. The installer no longer copies static skill files.

---

## Section 8: save Command Changes

After the existing DB save logic in `src/bookmark/core/save.py`, call `context_writer.update_all_installed(cwd, session)` which:

- Detects which config files from Section 5 are present in cwd
- Extracts commands and context summary from the transcript blob (see Section 6.3)
- Builds the LPIC dict from all session field values
- Encodes the session as a single CSV line with dict substitutions applied
- Updates the sessionmark section in each present config file using the regex from Section 6.6
- Skips silently if no config files are present (user has not run install yet)

---

## Section 9: resume Command Changes

After generating the briefing in `src/bookmark/core/resume.py`, call `context_writer.update_all_installed(cwd, session)` to update all installed config files to the resumed session. Opening any agent after `sessionmark resume NAME` will automatically have that session's context.

---

## Section 10: doctor Command Changes

Update `src/bookmark/core/doctor.py` to check which agents have sessionmark sections installed in the current project. For each agent in Section 5, report whether the config file exists and contains the sessionmark section. Output lines should follow the existing doctor format using checkmark for installed and dash for not installed.

---

## Section 11: New Module

Create `src/bookmark/install/context_writer.py` with this exact interface:

```python
from pathlib import Path
from typing import Literal
import re

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
    "keys:n=name,g=goal,b=branch,h=head,r=repo,s=source,f=files(type:path),"
    "t=todos(done:text),c=commands,x=context,nxt=next_step. "
    "When you see a sessionmark block expand all single-letter tokens "
    "using the dict before reading the session context. -->"
)

SECTION_RE = re.compile(
    r"<!-- sessionmark:start.*?<!-- sessionmark:end -->",
    re.DOTALL,
)

def build_dict(session_str: str) -> dict[str, str]: ...
def encode_session(session: dict, sub_dict: dict[str, str]) -> str: ...
def extract_transcript_context(transcript_path: Path) -> tuple[str, list[str]]: ...
    # returns (context_summary, commands_list)
def update_context_section(
    config_file: Path,
    compressed: str,
    mode: Literal["append_section", "full_override"],
) -> bool: ...
def install_section(config_file: Path) -> Literal["installed", "already_installed"]: ...
def update_all_installed(cwd: Path, session: dict) -> list[Path]: ...
def clear_section(config_file: Path) -> bool: ...
def has_section(config_file: Path) -> bool: ...
```

---

## Section 12: What to Keep Unchanged

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

## Section 13: Tests Required

All existing tests must pass or be updated to match new behaviour.

`tests/test_install.py` must be updated. It currently checks for old skill file paths such as `.claude/skills/bookmark/SKILL.md`. Update all path assertions to use the new config file locations from Section 5. The `test_install_all` test currently asserts `len(results) == 6`. This should remain 6 but the agents are now the 6 from Section 5.

New tests for `context_writer.py` must cover:

- `install_section` on a new file: creates file with schema line and empty markers
- `install_section` on existing file without section: appends schema line and empty markers
- `install_section` is idempotent: second call returns already_installed and makes no changes
- `has_section` returns True when section is present and False when absent
- `build_dict` finds correct repeated substrings and assigns A, B, C in order
- `build_dict` skips entries where dict overhead exceeds savings
- `build_dict` returns empty dict when no substring saves tokens
- `encode_session` produces correct single CSV line with all fields present
- `encode_session` applies dict substitutions correctly
- `extract_transcript_context` returns context summary and deduplicated command list from JSONL
- `extract_transcript_context` returns empty strings when no transcript exists
- `update_context_section` in append_section mode replaces existing section content
- `update_context_section` in append_section mode adds section when none exists
- `update_context_section` in full_override mode replaces entire file contents
- `clear_section` removes the section entirely and returns True
- `clear_section` returns False when no section is present
- `update_all_installed` updates only config files that already exist in cwd
- `update_all_installed` skips silently when no config files are present
- `update_all_installed` returns list of paths that were actually modified
- `save()` call triggers context update in all present config files
- `resume()` call triggers context update in all present config files
- `list_installs()` returns installed True for agents with section present, False otherwise
- Decoded output from encoded session matches all original field values exactly (lossless validation)

---

## Section 14: Constraints

- All ruff checks must pass: `ruff check src/` with line-length=100 and rules E/F/I/UP
- No new dependencies unless strictly necessary
- The `<!-- sessionmark:start -->` and `<!-- sessionmark:end -->` markers must be identical across all file formats. Use SECTION_RE from Section 11 to find and replace.
- For `.mdc` files (Cursor), HTML comment markers work — Cursor ignores them in rendering
- Dict keys must be single uppercase letters A–Z only, maximum 26 entries per session
- The schema line must never be modified after install — only the data section between markers changes on each save or resume
- The `nxt` key in the schema is two characters. All other keys are single characters. The regex and CSV parser must handle multi-character keys.
- Commit incrementally with clear messages
- Push to `origin feature/update-working-principle` when done

---

## Section 15: Validation Proof

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
