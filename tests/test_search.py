"""FTS5 search tests."""


def test_search_finds_by_goal(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.search import search_cmd

    config = load_config()
    repo = tmp_path / "repo"
    repo.mkdir()
    save_bookmark(name="focal-test", goal="gamma regression focal loss", config=config, cwd=str(repo))

    results = search_cmd("focal", config=config)
    assert len(results) >= 1
    assert any("focal" in r["name"] or "focal" in (r.get("snippet") or "") for r in results)


def test_search_no_results(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.search import search_cmd
    config = load_config()
    results = search_cmd("zzznomatch", config=config)
    assert results == []


def test_search_json_output(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.search import search_cmd
    config = load_config()
    repo = tmp_path / "repo"
    repo.mkdir()
    save_bookmark(name="auth-refactor", goal="refactor the auth module", config=config, cwd=str(repo))
    results = search_cmd("auth", config=config, as_json=True)
    assert isinstance(results, list)
