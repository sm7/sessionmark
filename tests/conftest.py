"""Shared pytest fixtures for bookmark-cli tests.

See design doc §19 for Week 1 test requirements.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_bookmark_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary BOOKMARK_HOME and set the env var."""
    home = tmp_path / "bookmark_home"
    home.mkdir()
    monkeypatch.setenv("BOOKMARK_HOME", str(home))
    return home


@pytest.fixture()
def fake_git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo in a temp directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, check=True, capture_output=True,
    )
    # Initial commit so HEAD exists
    (repo / "README.md").write_text("# Test repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo, check=True, capture_output=True,
    )
    return repo
