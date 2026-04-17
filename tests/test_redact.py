"""Tests for the secret redaction module (bookmark.redact).

Verifies that each pattern fires correctly and that clean text passes
through unchanged.

See design doc §9 for redaction requirements.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from bookmark.redact import is_env_file, redact

_CORPUS_PATH = Path(__file__).parent / "fixtures" / "redaction_corpus" / "secrets.txt"


# ---------------------------------------------------------------------------
# Pattern tests
# ---------------------------------------------------------------------------


def test_redact_aws_key() -> None:
    text = "export AWS_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE123"
    result = redact(text)
    assert "[REDACTED:aws]" in result
    assert "AKIAIOSFODNN7" not in result


def test_redact_openai_key() -> None:
    text = "key = sk-abcdefghijklmnopqrstuvwxyz12345"
    result = redact(text)
    assert "[REDACTED:openai]" in result
    assert "sk-abcdefghijklmnopqrstuvwxyz12345" not in result


def test_redact_github_pat() -> None:
    text = "token: ghp_" + "A" * 36
    result = redact(text)
    assert "[REDACTED:github]" in result


def test_redact_github_oauth() -> None:
    text = "gho_" + "B" * 36
    result = redact(text)
    assert "[REDACTED:github]" in result


def test_redact_github_server() -> None:
    text = "ghs_" + "C" * 36
    result = redact(text)
    assert "[REDACTED:github]" in result


def test_redact_slack_token() -> None:
    text = "xoxb-12345-abcdef-ghijklmnop"
    result = redact(text)
    assert "[REDACTED:slack]" in result


def test_redact_generic_password() -> None:
    text = "password=SuperSecretPasswordThatIsLongEnoughToBeRedacted1234"
    result = redact(text)
    assert "[REDACTED:generic]" in result


def test_redact_generic_api_key() -> None:
    text = "api_key=abcdefghijklmnopqrstuvwxyz1234567890ABCDEF"
    result = redact(text)
    assert "[REDACTED:generic]" in result


def test_redact_generic_secret() -> None:
    text = "secret=ThisIsMySecretValue1234567890abcdefghijklmn"
    result = redact(text)
    assert "[REDACTED:generic]" in result


# ---------------------------------------------------------------------------
# Clean text passes through unchanged
# ---------------------------------------------------------------------------


def test_clean_text_unchanged() -> None:
    text = "Hello world! This is a normal commit message."
    assert redact(text) == text


def test_clean_code_unchanged() -> None:
    text = "x = foo(bar=42, baz='hello')"
    assert redact(text) == text


def test_empty_string() -> None:
    assert redact("") == ""


# ---------------------------------------------------------------------------
# .env file detection
# ---------------------------------------------------------------------------


def test_is_env_file_dotenv() -> None:
    assert is_env_file(".env") is True


def test_is_env_file_dotenv_local() -> None:
    assert is_env_file(".env.local") is True


def test_is_env_file_dotenv_production() -> None:
    assert is_env_file("/some/path/.env.production") is True


def test_is_not_env_file() -> None:
    assert is_env_file("main.py") is False
    assert is_env_file("environment.py") is False
    assert is_env_file(".envrc") is False  # direnv, not .env.*


# ---------------------------------------------------------------------------
# Redaction corpus test (§19 Week 2)
# ---------------------------------------------------------------------------


def test_redaction_corpus() -> None:
    """Each line in the corpus should be redacted; count [REDACTED:...] tokens."""
    assert _CORPUS_PATH.exists(), f"Corpus file not found: {_CORPUS_PATH}"

    lines = [l for l in _CORPUS_PATH.read_text().splitlines() if l.strip()]
    assert len(lines) >= 10, "Corpus should have at least 10 lines"

    redacted_pattern = re.compile(r"\[REDACTED:[^\]]+\]")

    for i, line in enumerate(lines):
        result = redact(line)
        # Assert the original line was changed (secret was redacted)
        assert result != line, (
            f"Line {i + 1} was NOT redacted: {line!r}"
        )
        # Assert at least one [REDACTED:...] token appears
        tokens = redacted_pattern.findall(result)
        assert len(tokens) >= 1, (
            f"Line {i + 1} has no [REDACTED:...] token after redaction. "
            f"Result: {result!r}"
        )
