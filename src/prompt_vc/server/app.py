"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .deps import set_workspace_root
from .routes import audit, compose, diff, graph, prompts, render, validate


def create_app(workspace_root: Path | None = None, dev: bool = False) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        workspace_root: Root directory for prompt-vc workspace.
        dev: Enable dev mode (CORS for all origins).
    """
    if workspace_root:
        set_workspace_root(workspace_root)

    app = FastAPI(
        title="prompt-vc",
        description="Web UI API for prompt version control",
        version="0.1.0",
    )

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
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
