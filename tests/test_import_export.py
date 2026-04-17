"""Import/export round-trip tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_export_json_format(tmp_path, monkeypatch):
    """export_json returns valid JSON with the bookmark name and goal."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark

    repo = tmp_path / "repo"
    repo.mkdir()
    config = load_config()
    save_bookmark(name="export-me", goal="exportable goal", config=config, cwd=str(repo))

    from bookmark.export.markdown import export_json
    result = export_json("export-me", config=config)
    data = json.loads(result)
    assert data["name"] == "export-me"
    assert data["goal"] == "exportable goal"


def test_export_json_includes_todos(tmp_path, monkeypatch):
    """export_json includes todos list."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark

    repo = tmp_path / "repo"
    repo.mkdir()
    config = load_config()
    save_bookmark(name="with-todos", goal="has todos", config=config, cwd=str(repo))

    from bookmark.export.markdown import export_json
    result = export_json("with-todos", config=config)
    data = json.loads(result)
    assert "todos" in data
    assert isinstance(data["todos"], list)


def test_import_from_exported_json(tmp_path, monkeypatch):
    """import_bookmarks imports a bookmark from a JSON file."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.import_ import import_bookmarks
    from bookmark.storage.db import list_bookmarks, open_db

    config = load_config()
    repo = tmp_path / "repo"
    repo.mkdir()
    save_bookmark(name="importable", goal="to be imported", config=config, cwd=str(repo))

    # Export to file
    from bookmark.export.markdown import export_json
    json_str = export_json("importable", config=config)
    export_file = tmp_path / "export.json"
    export_file.write_text(json_str)

    # New home, import
    home2 = tmp_path / "home2"
    home2.mkdir()
    monkeypatch.setenv("BOOKMARK_HOME", str(home2))
    config2 = load_config()
    count = import_bookmarks(str(export_file), config=config2)
    assert count >= 1

    conn = open_db(home2 / "bookmarks.db")
    bms = list_bookmarks(conn, include_auto=True)
    conn.close()
    assert any(bm.name == "importable" for bm in bms)


def test_import_skips_duplicate_slug(tmp_path, monkeypatch):
    """import_bookmarks skips bookmarks with already-existing slugs."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.import_ import import_bookmarks
    from bookmark.export.markdown import export_json

    config = load_config()
    repo = tmp_path / "repo"
    repo.mkdir()
    save_bookmark(name="dup-test", goal="duplicate test", config=config, cwd=str(repo))

    json_str = export_json("dup-test", config=config)
    export_file = tmp_path / "export.json"
    export_file.write_text(json_str)

    # First import succeeds
    count1 = import_bookmarks(str(export_file), config=config)
    assert count1 == 0  # slug already exists — skipped

    # Import to fresh home succeeds
    home2 = tmp_path / "home2"
    home2.mkdir()
    monkeypatch.setenv("BOOKMARK_HOME", str(home2))
    config2 = load_config()
    count2 = import_bookmarks(str(export_file), config=config2)
    assert count2 >= 1


def test_import_list_of_bookmarks(tmp_path, monkeypatch):
    """import_bookmarks handles a JSON array of bookmarks."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.import_ import import_bookmarks
    from bookmark.export.markdown import export_json

    config = load_config()
    repo = tmp_path / "repo"
    repo.mkdir()
    save_bookmark(name="bm-one", goal="first", config=config, cwd=str(repo))
    save_bookmark(name="bm-two", goal="second", config=config, cwd=str(repo))

    # Build a list export
    json1 = json.loads(export_json("bm-one", config=config))
    json2 = json.loads(export_json("bm-two", config=config))

    # New home
    home2 = tmp_path / "home2"
    home2.mkdir()
    monkeypatch.setenv("BOOKMARK_HOME", str(home2))
    config2 = load_config()

    export_file = home2 / "bulk.json"
    export_file.write_text(json.dumps([json1, json2]))

    count = import_bookmarks(str(export_file), config=config2)
    assert count == 2


def test_import_file_not_found(tmp_path, monkeypatch):
    """import_bookmarks raises FileNotFoundError for missing file."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.import_ import import_bookmarks

    config = load_config()
    with pytest.raises(FileNotFoundError):
        import_bookmarks(str(tmp_path / "nonexistent.json"), config=config)
