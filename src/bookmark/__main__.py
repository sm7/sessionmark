"""Entry point for `python -m bookmark`.

See design doc §17 for CLI invocation details.
"""

from bookmark.cli import app

if __name__ == "__main__":
    app()
