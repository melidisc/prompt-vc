"""Shared dependencies for the server."""

from pathlib import Path

from pydantic import BaseModel


class WorkspaceSettings(BaseModel):
    """Resolved workspace root for all file operations."""

    root: Path = Path.cwd()


_settings: WorkspaceSettings | None = None


def get_settings() -> WorkspaceSettings:
    global _settings
    if _settings is None:
        _settings = WorkspaceSettings()
    return _settings


def set_workspace_root(path: Path) -> None:
    global _settings
    _settings = WorkspaceSettings(root=path.resolve())
