"""FastAPI application factory."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import audit, compose, diff, graph, prompts, render, validate


def create_app(workspace_root: Path | None = None, dev: bool = False) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        workspace_root: Root directory for prompt-vc workspace.
        dev: Enable dev mode (CORS for all origins).
    """
    app = FastAPI(
        title="prompt-vc",
        description="Web UI API for prompt version control",
        version="0.1.0",
    )

    app.state.workspace_root = (workspace_root or Path.cwd()).resolve()

    if dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(prompts.router, prefix="/api")
    app.include_router(validate.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")
    app.include_router(render.router, prefix="/api")
    app.include_router(compose.router, prefix="/api")
    app.include_router(diff.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _app_from_env() -> FastAPI:
    """Create app from environment variables (used by uvicorn import string)."""
    workspace = os.environ.get("PROMPT_VC_WORKSPACE")
    root = Path(workspace) if workspace else None
    dev = bool(os.environ.get("PROMPT_VC_DEV"))
    return create_app(workspace_root=root, dev=dev)
