"""bookmark.capture — workspace context capture modules.

Each sub-module captures a different aspect of the current workspace:
- git.py   : git branch, HEAD, diff summary, changed files
- files.py : recently modified files
- todos.py : TODO items from various sources
- env.py   : runtime environment info
- shell.py : recent shell history

See design doc §5 for the capture pipeline overview.
"""
