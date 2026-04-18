"""Doctor health check tests."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_doctor_runs_without_error(tmp_path, monkeypatch, capsys):
    """sessionmark doctor runs all checks without crashing."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config

    config = load_config()  # create config + home dir

    from bookmark.core.doctor import run_doctor
    run_doctor(config=config)
    out = capsys.readouterr().out
    assert "bookmark" in out.lower() or "home" in out.lower() or "✓" in out


def test_doctor_check_redaction_passes():
    """All lines in the redaction corpus should be redacted."""
    from bookmark.redact import redact

    corpus = Path("tests/fixtures/redaction_corpus/secrets.txt")
    if not corpus.exists():
        pytest.skip("Redaction corpus fixture not found")

    lines = [l for l in corpus.read_text().splitlines() if l.strip()]
    for line in lines:
        assert redact(line) != line, f"Line not redacted: {line[:50]}"


def test_doctor_checks_db_status(tmp_path, monkeypatch, capsys):
    """Doctor reports DB schema version after a bookmark is saved."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.doctor import run_doctor

    config = load_config()
    repo = tmp_path / "repo"
    repo.mkdir()
    save_bookmark(name="test", goal="test goal", config=config, cwd=str(repo))

    run_doctor(config=config)
    out = capsys.readouterr().out
    # Should mention SQLite DB
    assert "SQLite" in out or "db" in out.lower() or "schema" in out.lower()


def test_doctor_checks_blob_store(tmp_path, monkeypatch, capsys):
    """Doctor checks blob store existence."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.doctor import run_doctor

    config = load_config()
    run_doctor(config=config)
    out = capsys.readouterr().out
    assert "blob" in out.lower()


def test_doctor_shows_sync_disabled(tmp_path, monkeypatch, capsys):
    """Doctor shows sync as disabled by default."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.doctor import run_doctor

    config = load_config()
    assert not config.sync_enabled  # default is disabled
    run_doctor(config=config)
    out = capsys.readouterr().out
    assert "sync" in out.lower()
    assert "disabled" in out.lower()
