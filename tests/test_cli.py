"""CLI integration tests using typer.testing.CliRunner."""

from __future__ import annotations

import json
import os

import pytest
from typer.testing import CliRunner

from bookmark.cli import app

runner = CliRunner()


def test_cli_help():
    """--help exits 0 and lists the save command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "save" in result.output


def test_cli_save_and_list(tmp_path, monkeypatch):
    """save then list shows the bookmark."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    os.chdir(str(repo))

    result = runner.invoke(app, ["save", "cli-test", "-m", "cli integration test"])
    assert result.exit_code == 0
    assert "cli-test" in result.output

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "cli-test" in result.output


def test_cli_list_json(tmp_path, monkeypatch):
    """list --json returns valid JSON array."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    os.chdir(str(repo))

    runner.invoke(app, ["save", "json-test", "-m", "goal"])
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)


def test_cli_search(tmp_path, monkeypatch):
    """search returns matching bookmarks."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    os.chdir(str(repo))

    runner.invoke(app, ["save", "focal-loss", "-m", "gamma regression"])
    result = runner.invoke(app, ["search", "focal"])
    assert result.exit_code == 0
    assert "focal" in result.output


def test_cli_delete(tmp_path, monkeypatch):
    """delete removes the bookmark from list."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    os.chdir(str(repo))

    runner.invoke(app, ["save", "delete-me", "-m", "to be deleted"])
    result = runner.invoke(app, ["delete", "delete-me", "-f"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["list"])
    assert "delete-me" not in result.output


def test_cli_export_json(tmp_path, monkeypatch):
    """export --format json produces valid JSON with the bookmark name."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    os.chdir(str(repo))

    runner.invoke(app, ["save", "export-test", "-m", "exportable"])
    result = runner.invoke(app, ["export", "export-test", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    if isinstance(data, list):
        assert data[0]["name"] == "export-test"
    else:
        assert data.get("name") == "export-test"


def test_cli_config_set_get(tmp_path, monkeypatch):
    """config set then get round-trips correctly."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    result = runner.invoke(app, ["config", "set", "briefing.provider", "template"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["config", "get", "briefing.provider"])
    assert result.exit_code == 0
    assert "template" in result.output


def test_cli_diff_two_bookmarks(tmp_path, monkeypatch):
    """diff command works with two bookmark names."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    os.chdir(str(repo))

    runner.invoke(app, ["save", "diff-v1", "-m", "first"])
    runner.invoke(app, ["save", "diff-v2", "-m", "second"])

    result = runner.invoke(app, ["diff", "diff-v1", "diff-v2"])
    assert result.exit_code == 0


def test_cli_diff_not_found(tmp_path, monkeypatch):
    """diff exits non-zero when bookmark not found."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))

    result = runner.invoke(app, ["diff", "no-such-bookmark"])
    assert result.exit_code != 0


def test_cli_import_export_roundtrip(tmp_path, monkeypatch):
    """export JSON then import to new home round-trips correctly."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    os.chdir(str(repo))

    runner.invoke(app, ["save", "roundtrip-test", "-m", "round-trip goal"])
    result = runner.invoke(app, ["export", "roundtrip-test", "--format", "json"])
    assert result.exit_code == 0

    export_file = tmp_path / "export.json"
    export_file.write_text(result.output)

    # New home
    home2 = tmp_path / "home2"
    home2.mkdir()
    monkeypatch.setenv("BOOKMARK_HOME", str(home2))

    result2 = runner.invoke(app, ["import", str(export_file)])
    assert result2.exit_code == 0
    assert "imported" in result2.output.lower() or "roundtrip-test" in result2.output


def test_cli_doctor_runs(tmp_path, monkeypatch):
    """doctor command exits 0 and prints health info."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "bookmark" in result.output.lower() or "✓" in result.output or "home" in result.output.lower()
