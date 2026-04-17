"""Tests for resume_bookmark and show_bookmark — §19 Week 2.

Verifies:
- resume_bookmark("latest") works after a save
- briefing contains the goal
- --json flag returns parseable JSON with expected keys
- name resolution: partial match works, ambiguous match exits 2
- show_bookmark("latest") renders without NEXT STEP section
- show_bookmark with --full includes full transcript
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest
import typer

from bookmark.config import Config
from bookmark.core.save import save_bookmark
from bookmark.core.resume import resume_bookmark, show_bookmark


def _make_config(home: Path) -> Config:
    """Build a Config pointing at the given tmp home."""
    return Config(home=home, default_source="terminal", redact_enabled=True, blob_compress=False)


# ---------------------------------------------------------------------------
# resume_bookmark tests
# ---------------------------------------------------------------------------


def test_resume_latest_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """resume_bookmark('latest') should succeed after a save."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config = _make_config(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    save_bookmark(name="mywork", goal="test the resume flow", config=config, cwd=str(repo))

    bm = resume_bookmark(name="latest", config=config)
    assert bm.name == "mywork"


def test_resume_briefing_contains_goal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """The briefing output should contain the bookmark's goal."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config = _make_config(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    save_bookmark(name="goalcheck", goal="implement the auth module", config=config, cwd=str(repo))

    resume_bookmark(name="latest", config=config)
    captured = capsys.readouterr()
    assert "implement the auth module" in captured.out


def test_resume_json_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """--json flag should output parseable JSON with expected keys."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config = _make_config(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    bm = save_bookmark(name="jsontest", goal="json output test", config=config, cwd=str(repo))
    capsys.readouterr()  # clear save output

    resume_bookmark(name="latest", as_json=True, config=config)
    captured = capsys.readouterr()

    data = json.loads(captured.out)
    assert "id" in data
    assert "name" in data
    assert "goal" in data
    assert "source" in data
    assert "todos" in data
    assert data["id"] == bm.id
    assert data["name"] == "jsontest"
    assert data["goal"] == "json output test"


def test_resume_partial_name_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Partial name match should resolve to the unique bookmark."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config = _make_config(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    bm = save_bookmark(name="feature-auth", goal="auth work", config=config, cwd=str(repo))

    # Prefix match
    found = resume_bookmark(name="feature", config=config)
    assert found.id == bm.id


def test_resume_ambiguous_name_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ambiguous name is a user error — must exit with code 1 (not 2)."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config = _make_config(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    save_bookmark(name="feature-alpha", goal="a", config=config, cwd=str(repo))
    save_bookmark(name="feature-beta", goal="b", config=config, cwd=str(repo))

    with pytest.raises(typer.Exit) as exc_info:
        resume_bookmark(name="feature", config=config)
    assert exc_info.value.exit_code == 1


def test_resume_not_found_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-existent bookmark name should exit with code 2."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config = _make_config(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    save_bookmark(name="something", goal="x", config=config, cwd=str(repo))

    with pytest.raises(typer.Exit) as exc_info:
        resume_bookmark(name="nonexistent-bookmark-xyz", config=config)
    assert exc_info.value.exit_code == 2


# ---------------------------------------------------------------------------
# show_bookmark tests
# ---------------------------------------------------------------------------


def test_show_bookmark_latest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """show_bookmark('latest') should render without NEXT STEP section."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config = _make_config(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    save_bookmark(name="showtest", goal="test the show command", config=config, cwd=str(repo))

    show_bookmark(name="latest", config=config)
    captured = capsys.readouterr()

    assert "test the show command" in captured.out
    # show command should NOT have NEXT STEP section
    assert "NEXT STEP" not in captured.out


def test_show_bookmark_has_no_next_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """Verify show never includes NEXT STEP, but resume does."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config = _make_config(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    save_bookmark(name="steptest", goal="step check", config=config, cwd=str(repo))

    show_bookmark(name="latest", config=config)
    show_out = capsys.readouterr().out
    assert "NEXT STEP" not in show_out

    resume_bookmark(name="latest", config=config)
    resume_out = capsys.readouterr().out
    assert "NEXT STEP" in resume_out


def test_show_full_includes_transcript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """show --full should include full transcript section when messages exist."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config = _make_config(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    # Save with a mocked transcript by patching stdin
    import sys
    from io import StringIO

    transcript_data = "\n".join([
        '{"role": "user", "content": "first question"}',
        '{"role": "assistant", "content": "first answer"}',
        '{"role": "user", "content": "second question"}',
        '{"role": "assistant", "content": "second answer"}',
    ])
    monkeypatch.setattr(sys, "stdin", StringIO(transcript_data))

    bm = save_bookmark(
        name="transcripttest",
        goal="transcript test",
        config=config,
        cwd=str(repo),
        transcript_stdin=True,
    )
    assert bm.transcript_messages == 4

    # show --full should show TRANSCRIPT section
    show_bookmark(name="latest", full=True, config=config)
    captured = capsys.readouterr()
    assert "TRANSCRIPT" in captured.out
    assert "first question" in captured.out or "second answer" in captured.out
