"""Bookmark resume and show orchestration for bookmark-cli.

Implements:
- resume_bookmark: Load a bookmark, render a briefing, optionally apply git state
- show_bookmark: Load a bookmark, render a briefing (no NEXT STEP / actions)

Name resolution follows design doc §8:
  exact slug → exact name (case-insensitive) → unique prefix → error exit 2

See design doc §6 for the resume pipeline description.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from bookmark.config import Config, load_config
from bookmark.core.models import Bookmark, FileEntry
from bookmark.storage.db import get_todos, list_bookmarks, open_db, resolve_name


def _load_config_and_conn(config: Config | None = None):
    """Return (config, conn) for the current bookmark home."""
    if config is None:
        config = load_config()
    db_path = config.home / "bookmarks.db"
    conn = open_db(db_path)
    return config, conn


def _resolve_or_exit(conn, name: str) -> Bookmark:
    """Resolve bookmark name or exit with code 2 if not found."""
    import typer

    if name == "latest":
        rows = list_bookmarks(conn, n=1, include_auto=False)
        if not rows:
            print("No bookmarks found.", file=sys.stderr)
            raise typer.Exit(2)
        return rows[0]

    try:
        bm = resolve_name(conn, name)
    except ValueError as exc:
        # Ambiguous prefix — user error (exit 1), not "not found" (exit 2)
        print(str(exc), file=sys.stderr)
        raise typer.Exit(1) from exc

    if bm is None:
        print(f"Bookmark '{name}' not found.", file=sys.stderr)
        raise typer.Exit(2)

    return bm


def _load_transcript(config: Config, bm: Bookmark) -> list[dict]:
    """Load transcript messages from the transcript blob path."""
    if not bm.transcript_blob:
        return []

    # transcript_blob is a relative path like blobs/tr/<id>/transcript.jsonl
    blob_path = config.home / bm.transcript_blob
    if not blob_path.exists():
        return []

    messages: list[dict] = []
    for line in blob_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return messages


def _load_open_files(config: Config, bm: Bookmark) -> list[FileEntry]:
    """Load open files from the files blob."""
    if not bm.files_blob:
        return []

    from bookmark.storage.blobs import BlobStore
    store = BlobStore(config.home, compress=config.blob_compress)
    raw = store.read(bm.files_blob)
    if not raw:
        return []

    try:
        data = json.loads(raw)
        return [FileEntry(**item) for item in data]
    except Exception:
        return []


def resume_bookmark(
    name: str = "latest",
    apply: bool = False,
    as_json: bool = False,
    config: Config | None = None,
) -> Bookmark:
    """Load a bookmark and render its briefing.

    Parameters
    ----------
    name:
        Bookmark name or "latest". Resolved via §8 resolution order.
    apply:
        If True, run `cd <repo_root> && git checkout <branch>` via subprocess.
    as_json:
        If True, print the full bookmark record as JSON instead of briefing.
    config:
        Pre-loaded Config (loads fresh if None).
    """
    from bookmark.briefing.template import render_briefing

    cfg, conn = _load_config_and_conn(config)
    bm = _resolve_or_exit(conn, name)
    todos = get_todos(conn, bm.id)
    conn.close()

    transcript = _load_transcript(cfg, bm)
    open_files = _load_open_files(cfg, bm)

    if as_json:
        data = bm.model_dump()
        data["todos"] = [t.model_dump() for t in todos]
        data["transcript_messages"] = bm.transcript_messages
        print(json.dumps(data, indent=2))
        return bm

    # Try LLM briefing provider if configured
    llm_summary = None
    provider_uri = cfg.briefing_provider or cfg.llm_provider or "template"
    if provider_uri and provider_uri != "template":
        try:
            from bookmark.briefing.providers import get_provider
            provider = get_provider(provider_uri)
            if provider:
                context = {
                    "goal": bm.goal,
                    "transcript": transcript,
                    "todos": todos,
                    "open_files": open_files,
                    "repo_root": bm.repo_root,
                    "git_branch": bm.git_branch,
                }
                llm_summary = provider.generate(context)
        except Exception as e:
            print(f"[bookmark] briefing provider failed, using template: {e}", file=sys.stderr)

    briefing = render_briefing(
        bookmark=bm,
        todos=todos,
        transcript=transcript,
        open_files=open_files,
        include_next_step=True,
        llm_summary=llm_summary,
    )
    print(briefing)

    if apply:
        cmd = f"cd {bm.repo_root}"
        if bm.git_branch:
            cmd += f" && git checkout {bm.git_branch}"
        result = subprocess.run(cmd, shell=True)
        if result.returncode == 0:
            print(f"Applied: {cmd}")
        else:
            print(f"Command failed (exit {result.returncode}): {cmd}", file=sys.stderr)

    # Inject context into installed agent config files (best-effort)
    try:
        from bookmark.install.context_writer import update_all_installed

        session_data = bm.model_dump()
        session_data["todos"] = [t.model_dump() for t in todos]
        update_all_installed(Path(os.getcwd()), session_data)
    except Exception:
        pass

    return bm


def show_bookmark(
    name: str = "latest",
    full: bool = False,
    no_transcript: bool = False,
    as_json: bool = False,
    config: Config | None = None,
) -> Bookmark:
    """Load a bookmark and render its briefing (no NEXT STEP section).

    Parameters
    ----------
    name:
        Bookmark name or "latest". Resolved via §8 resolution order.
    full:
        If True, include full transcript dump instead of last exchange.
    no_transcript:
        If True, omit transcript section entirely.
    as_json:
        If True, print the full bookmark record as JSON.
    config:
        Pre-loaded Config (loads fresh if None).
    """
    from bookmark.briefing.template import render_briefing

    cfg, conn = _load_config_and_conn(config)
    bm = _resolve_or_exit(conn, name)
    todos = get_todos(conn, bm.id)
    conn.close()

    transcript = [] if no_transcript else _load_transcript(cfg, bm)
    open_files = _load_open_files(cfg, bm)

    if as_json:
        data = bm.model_dump()
        data["todos"] = [t.model_dump() for t in todos]
        data["transcript_messages"] = bm.transcript_messages
        print(json.dumps(data, indent=2))
        return bm

    # Try LLM briefing provider if configured
    llm_summary = None
    provider_uri = cfg.briefing_provider or cfg.llm_provider or "template"
    if provider_uri and provider_uri != "template":
        try:
            from bookmark.briefing.providers import get_provider
            provider = get_provider(provider_uri)
            if provider:
                context = {
                    "goal": bm.goal,
                    "transcript": transcript,
                    "todos": todos,
                    "open_files": open_files,
                    "repo_root": bm.repo_root,
                    "git_branch": bm.git_branch,
                }
                llm_summary = provider.generate(context)
        except Exception as e:
            print(f"[bookmark] briefing provider failed, using template: {e}", file=sys.stderr)

    briefing = render_briefing(
        bookmark=bm,
        todos=todos,
        transcript=transcript,
        open_files=open_files,
        include_next_step=False,
        full_transcript=full,
        llm_summary=llm_summary,
    )
    print(briefing)
    return bm
