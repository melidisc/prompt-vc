"""FastAPI application factory."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routes import audit, compose, diff, graph, prompts, render, validate
from .ui import create_ui_router

_SERVER_DIR = Path(__file__).resolve().parent


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

    # Static files and templates
    app.mount("/static", StaticFiles(directory=_SERVER_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=str(_SERVER_DIR / "templates"))

    # JSON API routes
    app.include_router(prompts.router, prefix="/api")
    app.include_router(validate.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")
    app.include_router(render.router, prefix="/api")
    app.include_router(compose.router, prefix="/api")
    app.include_router(diff.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")

    # HTML UI routes
    app.include_router(create_ui_router(templates))

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/")

    return app


def _app_from_env() -> FastAPI:
    """Create app from environment variables (used by uvicorn import string)."""
    workspace = os.environ.get("PROMPT_VC_WORKSPACE")
    root = Path(workspace) if workspace else None
    dev = bool(os.environ.get("PROMPT_VC_DEV"))
    return create_app(workspace_root=root, dev=dev)
