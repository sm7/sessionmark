"""Git-backed sync for bookmark-cli — §3 Flow C and §8 of design doc."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from bookmark.config import Config


def _default_sync_dir(config: Optional[Config] = None) -> Path:
    """Return the default sync directory."""
    if config is not None:
        return config.home / "sync"
    from bookmark.config import load_config
    cfg = load_config()
    return cfg.home / "sync"


def _bookmark_home(config: Optional[Config] = None) -> Path:
    """Return the bookmark home directory."""
    if config is not None:
        return config.home
    from bookmark.config import load_config
    return load_config().home


def _run_git(args: list[str], cwd: Optional[Path] = None) -> None:
    """Run a git command with check=True. Raises RuntimeError on failure."""
    cmd = ["git"] + args
    try:
        subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
        raise RuntimeError(f"git {args[0]} failed: {stderr}") from e


def sync_init(
    git_remote: str,
    sync_dir: Optional[Path] = None,
    config: Optional[Config] = None,
) -> None:
    """Initialize a local git-backed sync repo.

    Creates sync_dir, initializes a git repo, adds the remote, copies
    bookmarks.db, and makes an initial commit.
    """
    if sync_dir is None:
        sync_dir = _default_sync_dir(config)

    home = _bookmark_home(config)
    sync_dir = Path(sync_dir)
    sync_dir.mkdir(parents=True, exist_ok=True)

    # Initialize git repo
    _run_git(["init", str(sync_dir)])

    # Add remote
    _run_git(["-C", str(sync_dir), "remote", "add", "origin", git_remote])

    # Copy bookmarks.db if it exists
    db_src = home / "bookmarks.db"
    db_dst = sync_dir / "bookmarks.db"
    if db_src.exists():
        shutil.copy2(db_src, db_dst)
    else:
        # Create an empty placeholder so git has something to commit
        db_dst.touch()

    # Stage and commit
    _run_git(["-C", str(sync_dir), "add", "."])
    try:
        _run_git(["-C", str(sync_dir), "commit", "-m", "init"])
    except RuntimeError:
        # Nothing to commit is OK on fresh init
        pass


def sync_push(
    sync_dir: Optional[Path] = None,
    message: str = "bookmark sync",
    config: Optional[Config] = None,
) -> None:
    """Copy bookmarks.db + blobs to sync dir, commit, push.

    Note: v0.1.0 does a simple file copy — no merge logic.
    """
    if sync_dir is None:
        sync_dir = _default_sync_dir(config)

    home = _bookmark_home(config)
    sync_dir = Path(sync_dir)

    if not (sync_dir / ".git").exists():
        raise RuntimeError(
            f"Sync dir {sync_dir} is not a git repo. Run 'bookmark sync init' first."
        )

    # Copy bookmarks.db to sync dir
    db_src = home / "bookmarks.db"
    db_dst = sync_dir / "bookmarks.db"
    if db_src.exists():
        shutil.copy2(db_src, db_dst)

    # Stage all changes
    _run_git(["-C", str(sync_dir), "add", "."])

    # Commit (may be nothing to commit — that's OK)
    try:
        _run_git(["-C", str(sync_dir), "commit", "-m", message])
    except RuntimeError:
        pass  # nothing to commit

    # Push
    _run_git(["-C", str(sync_dir), "push", "origin", "HEAD"])


def sync_pull(
    sync_dir: Optional[Path] = None,
    config: Optional[Config] = None,
) -> None:
    """Pull from remote, merge bookmarks.db.

    v0.1.0 limitation: simple overwrite — last-write-wins, no merge.
    The pulled bookmarks.db replaces the local one.
    """
    if sync_dir is None:
        sync_dir = _default_sync_dir(config)

    home = _bookmark_home(config)
    sync_dir = Path(sync_dir)

    if not (sync_dir / ".git").exists():
        raise RuntimeError(
            f"Sync dir {sync_dir} is not a git repo. Run 'bookmark sync init' first."
        )

    # Pull from remote
    _run_git(["-C", str(sync_dir), "pull"])

    # Copy pulled bookmarks.db over local one
    db_src = sync_dir / "bookmarks.db"
    db_dst = home / "bookmarks.db"
    if db_src.exists():
        home.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_src, db_dst)


def sync_clone(
    git_remote: str,
    sync_dir: Optional[Path] = None,
    config: Optional[Config] = None,
) -> None:
    """Clone a remote sync repo and import its bookmarks.db.

    v0.1.0 limitation: simple overwrite — no merge.
    """
    if sync_dir is None:
        sync_dir = _default_sync_dir(config)

    home = _bookmark_home(config)
    sync_dir = Path(sync_dir)

    # Clone the remote repo into sync_dir
    _run_git(["clone", git_remote, str(sync_dir)])

    # Copy bookmarks.db to bookmark home
    db_src = sync_dir / "bookmarks.db"
    db_dst = home / "bookmarks.db"
    if db_src.exists():
        home.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_src, db_dst)
