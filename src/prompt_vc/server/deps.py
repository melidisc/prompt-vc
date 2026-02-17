"""Shared dependencies for the server."""

from pathlib import Path

from fastapi import Request


def get_workspace_root(request: Request) -> Path:
    """Return the workspace root stored on app.state.

    This is the single source of truth for the workspace directory.
    Set by create_app() during startup.
    """
    root: Path = request.app.state.workspace_root
    return root
