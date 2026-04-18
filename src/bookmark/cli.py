"""CLI entry point for bookmark-cli.

Defines the `bookmark` (and `bm`) command with subcommands:
  bookmark save [NAME] [-m MSG] [--tag TAG] [--source AGENT] [--transcript-stdin]
  bookmark list [--repo REPO] [--tag TAG] [--source AGENT] [-n N] [--json]
  bookmark resume [NAME|latest] [--apply] [--json]
  bookmark show [NAME|latest] [--full] [--no-transcript] [--json]
  bookmark search QUERY [-n N] [--json]
  bookmark delete NAME [-f]
  bookmark export [NAME] [--format paste|md|json] [--target AGENT] [-o FILE]
  bookmark install [--for AGENT|all] [--list] [--hooks] [--dry-run]
  bookmark config get|set KEY [VALUE]
  bookmark diff [NAME]
  bookmark doctor [--check-redaction]

Exit codes (per design doc §16):
  0 — success
  1 — user error
  2 — not found
  3 — integrity error
  4 — git sync conflict

See design doc §17 for CLI design details.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(
    name="bookmark",
    help="Save and resume AI coding sessions with full context.",
    no_args_is_help=True,
    add_completion=False,
)

err_console = Console(stderr=True, style="bold red")


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


@app.command()
def save(
    name: Annotated[str, typer.Argument(help="Bookmark name (slug).")] = "wip",
    msg: Annotated[
        str | None, typer.Option("-m", "--msg", help="One-line goal / description.")
    ] = None,
    tag: Annotated[
        str | None, typer.Option("--tag", help="Comma-separated tags.")
    ] = None,
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            help="Agent source: claude-code, cursor, codex, gemini, aider, terminal, generic.",
        ),
    ] = None,
    transcript_stdin: Annotated[
        bool,
        typer.Option(
            "--transcript-stdin",
            help="Read JSON-lines transcript from stdin.",
            
        ),
    ] = False,
) -> None:
    """Save the current workspace as a bookmark."""
    from bookmark.core.save import save_bookmark

    try:
        save_bookmark(
            name=name,
            goal=msg,
            tags=tag,
            source=source,
            transcript_stdin=transcript_stdin,
        )
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command(name="list")
def list_cmd(
    repo: Annotated[
        str | None, typer.Option("--repo", help="Filter by repo name.")
    ] = None,
    tag: Annotated[
        str | None, typer.Option("--tag", help="Filter by tag.")
    ] = None,
    source: Annotated[
        str | None, typer.Option("--source", help="Filter by agent source.")
    ] = None,
    n: Annotated[int, typer.Option("-n", help="Number of results.")] = 20,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON."),
    ] = False,
    include_auto: Annotated[
        bool,
        typer.Option("--all", help="Include auto bookmarks."),
    ] = False,
) -> None:
    """List saved bookmarks."""
    from bookmark.core.list import list_cmd as _list

    try:
        _list(
            repo=repo,
            tag=tag,
            source=source,
            n=n,
            as_json=as_json,
            include_auto=include_auto,
        )
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# resume
# ---------------------------------------------------------------------------


@app.command()
def resume(
    name: Annotated[str, typer.Argument(help="Bookmark name or 'latest'.")] = "latest",
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Apply git state after printing briefing."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print full record as JSON."),
    ] = False,
) -> None:
    """Resume a saved bookmark — print briefing and optionally apply git state."""
    from bookmark.core.resume import resume_bookmark

    try:
        resume_bookmark(name=name, apply=apply, as_json=as_json)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


@app.command()
def show(
    name: Annotated[str, typer.Argument(help="Bookmark name or 'latest'.")] = "latest",
    full: Annotated[
        bool,
        typer.Option("--full", help="Include full transcript dump."),
    ] = False,
    no_transcript: Annotated[
        bool,
        typer.Option("--no-transcript", help="Omit transcript section."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print full record as JSON."),
    ] = False,
) -> None:
    """Show a saved bookmark briefing (no NEXT STEP suggestions)."""
    from bookmark.core.resume import show_bookmark

    try:
        show_bookmark(name=name, full=full, no_transcript=no_transcript, as_json=as_json)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


@app.command()
def doctor(
    check_redaction: Annotated[
        bool,
        typer.Option("--check-redaction", help="Run redaction corpus test."),
    ] = False,
) -> None:
    """Run health checks on the bookmark installation."""
    from pathlib import Path

    from bookmark.config import load_config
    from bookmark.core.doctor import run_doctor

    config = load_config()

    # Always run full health checks
    run_doctor(config=config)

    if check_redaction:
        from bookmark.redact import redact

        # cli.py lives at src/bookmark/cli.py → 3 parents up = project root
        corpus_path = (
            Path(__file__).parent.parent.parent
            / "tests" / "fixtures" / "redaction_corpus" / "secrets.txt"
        ).resolve()

        if not corpus_path.exists():
            print("FAIL: redaction corpus not found")
            raise typer.Exit(1)

        lines = [ln for ln in corpus_path.read_text().splitlines() if ln.strip()]
        failures: list[str] = []
        for line in lines:
            result = redact(line)
            if line == result:
                failures.append(f"  NOT REDACTED: {line[:60]}")

        if failures:
            print(f"FAIL: {len(failures)} line(s) not redacted")
            for f in failures:
                print(f)
            raise typer.Exit(1)
        else:
            redacted_count = sum(1 for ln in lines if redact(ln) != ln)
            print(f"PASS: {redacted_count}/{len(lines)} lines redacted correctly")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search terms.")],
    n: Annotated[int, typer.Option("-n", help="Max results.")] = 10,
    as_json: Annotated[
        bool, typer.Option("--json", help="JSON output.")
    ] = False,
) -> None:
    """Full-text search over bookmark names, goals, and tags."""
    from bookmark.core.search import search_cmd

    try:
        search_cmd(query=query, as_json=as_json, limit=n)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@app.command()
def delete(
    name: Annotated[str, typer.Argument(help="Bookmark name.")],
    force: Annotated[
        bool,
        typer.Option("-f", "--force", help="Skip confirmation."),
    ] = False,
) -> None:
    """Delete a bookmark."""
    from bookmark.core.delete import delete_bookmark as _delete

    try:
        _delete(name=name, force=force)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@app.command()
def export(
    name: Annotated[str, typer.Argument(help="Bookmark name or 'latest'.")] = "latest",
    format: Annotated[
        str, typer.Option("--format", help="Output format: paste, md, json.")
    ] = "paste",
    target: Annotated[
        str, typer.Option("--target", help="Target agent for paste format.")
    ] = "generic",
    output: Annotated[
        str | None, typer.Option("-o", "--output", help="Write to file.")
    ] = None,
) -> None:
    """Export a bookmark for sharing or cross-agent paste."""
    import json as _json

    from bookmark.core.resume import (
        _load_config_and_conn,
        _load_open_files,
        _load_transcript,
        _resolve_or_exit,
    )
    from bookmark.storage.db import get_todos

    try:
        cfg, conn = _load_config_and_conn()
        bm = _resolve_or_exit(conn, name)
        todos = get_todos(conn, bm.id)
        conn.close()
        transcript = _load_transcript(cfg, bm)
        open_files = _load_open_files(cfg, bm)

        if format == "json":
            data = bm.model_dump()
            data["todos"] = [t.model_dump() for t in todos]
            text = _json.dumps(data, indent=2)
        elif format == "md":
            from bookmark.export.markdown import render_markdown
            text = render_markdown(bm, todos, transcript, open_files)
        else:  # paste (default)
            from bookmark.export.paste import render_paste
            text = render_paste(bm, todos, transcript, open_files, target=target)

        if output:
            from pathlib import Path
            Path(output).write_text(text, encoding="utf-8")
            print(f"Written to {output}")
        else:
            print(text)

    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@app.command()
def install(
    for_agent: Annotated[
        str | None,
        typer.Option("--for", help="Agent name or 'all'."),
    ] = None,
    list_agents: Annotated[
        bool,
        typer.Option("--list", help="Show available/installed agents."),
    ] = False,
    hooks: Annotated[
        bool,
        typer.Option("--hooks", help="Install Claude Code hooks."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview without writing."),
    ] = False,
) -> None:
    """Install bookmark skills for coding agents."""
    from rich.console import Console

    from bookmark.install.installer import install_for_agent, install_for_all, list_installs

    console = Console()

    if for_agent is None and not list_agents and not hooks:
        err_console.print("Error: specify --for <agent>|all, --list, or --hooks")
        raise typer.Exit(1)

    if list_agents:
        listing = list_installs()
        for entry in listing:
            installed = entry["installed"]
            status = "[green]installed[/green]" if installed else "[dim]not installed[/dim]"
            console.print(f"  {entry['agent']:<15} {status}  ({entry['dest']})")
        return

    if hooks:
        from bookmark.install.hooks import install_hooks
        result = install_hooks(dry_run=dry_run)
        action = result["action"]
        path = result["path"]
        if action == "installed":
            console.print(f"  [green]installed[/green]  hooks  →  {path}")
        elif action == "already_installed":
            console.print(f"  [dim]already installed[/dim]  hooks  ({path})")
        elif action == "dry_run":
            console.print(f"  [cyan]dry-run[/cyan]  hooks  →  {path}")
        return

    if for_agent == "all":
        results = install_for_all(dry_run=dry_run)
    else:
        try:
            results = [install_for_agent(for_agent, dry_run=dry_run)]
        except ValueError as exc:
            err_console.print(f"Error: {exc}")
            raise typer.Exit(1) from exc

    for r in results:
        action = r["action"]
        agent = r["agent"]
        dest = r["dest"]
        if action == "installed":
            console.print(f"  [green]installed[/green]  {agent}  →  {dest}")
        elif action == "already_installed":
            console.print(f"  [dim]already installed[/dim]  {agent}")
        elif action == "updated":
            console.print(f"  [yellow]updated[/yellow]  {agent}  →  {dest}")
        elif action == "dry_run":
            console.print(f"  [cyan]dry-run[/cyan]  {agent}  →  {dest}")
        else:
            console.print(f"  [dim]{action}[/dim]  {agent}")


# ---------------------------------------------------------------------------
# config (stub)
# ---------------------------------------------------------------------------


config_app = typer.Typer(help="Get or set configuration values.")
app.add_typer(config_app, name="config")


@config_app.command("get")
def config_get_cmd(
    key: Annotated[str, typer.Argument(help="Config dot-path key, e.g. briefing.provider.")],
) -> None:
    """Get a configuration value."""
    from bookmark.config import config_get, load_config
    load_config()  # ensure config file exists
    try:
        value = config_get(key)
        print(value)
    except KeyError as exc:
        err_console.print(f"Unknown config key: {key}")
        raise typer.Exit(1) from exc


@config_app.command("set")
def config_set_cmd(
    key: Annotated[str, typer.Argument(help="Config dot-path key, e.g. briefing.provider.")],
    value: Annotated[str, typer.Argument(help="Value to set.")],
) -> None:
    """Set a configuration value."""
    from bookmark.config import config_set, load_config
    load_config()  # ensure config file exists
    try:
        config_set(key, value)
        print(f"Set {key} = {value}")
    except (ValueError, KeyError) as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


@app.command()
def diff(
    name1: Annotated[str, typer.Argument(help="First bookmark name.")],
    name2: Annotated[
        str | None, typer.Argument(help="Second bookmark name (default: current state).")
    ] = None,
) -> None:
    """Show diff between two bookmarks or a bookmark and current state."""
    from bookmark.core.diff import diff_bookmarks

    try:
        diff_bookmarks(name1, name2)
    except typer.Exit:
        raise
    except Exception as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


@app.command(name="import")
def import_cmd(
    file: Annotated[str, typer.Argument(help="Path to exported JSON file.")],
) -> None:
    """Import bookmarks from an exported JSON file."""
    from bookmark.core.import_ import import_bookmarks

    try:
        count = import_bookmarks(file)
        print(f"Imported {count} bookmark(s).")
    except Exception as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# sync subgroup
# ---------------------------------------------------------------------------

sync_app = typer.Typer(name="sync", help="Git-backed bookmark sync.")
app.add_typer(sync_app)


@sync_app.command(name="init")
def sync_init_cmd(
    git_url: str = typer.Argument(..., help="Git remote URL."),
) -> None:
    """Initialize a local git-backed sync repo."""
    from bookmark.sync import sync_init

    try:
        sync_init(git_url)
        print(f"Sync initialized with remote: {git_url}")
    except Exception as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


@sync_app.command(name="push")
def sync_push_cmd() -> None:
    """Copy bookmarks.db to sync dir, commit, and push."""
    from bookmark.sync import sync_push

    try:
        sync_push()
        print("Sync pushed.")
    except Exception as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


@sync_app.command(name="pull")
def sync_pull_cmd() -> None:
    """Pull from remote and update local bookmarks.db."""
    from bookmark.sync import sync_pull

    try:
        sync_pull()
        print("Sync pulled.")
    except Exception as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


@sync_app.command(name="clone")
def sync_clone_cmd(
    git_url: str = typer.Argument(..., help="Git remote URL to clone."),
) -> None:
    """Clone a remote sync repo and import its bookmarks.db."""
    from bookmark.sync import sync_clone

    try:
        sync_clone(git_url)
        print(f"Cloned from: {git_url}")
    except Exception as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc
