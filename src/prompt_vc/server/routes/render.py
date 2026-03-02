"""Render endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...render import render_prompt
from ..deps import get_workspace_root

router = APIRouter(tags=["render"])


class RenderRequest(BaseModel):
    context: dict[str, Any] = {}


class RenderResponse(BaseModel):
    prompt_id: str
    rendered_content: str
    template_engine: str
    variables_used: list[str]


@router.post("/prompts/{prompt_id}/render", response_model=RenderResponse)
def render(
    prompt_id: str,
    body: RenderRequest,
    root: Path = Depends(get_workspace_root),
) -> RenderResponse:
    result = render_prompt(
        prompt_id,
        context=body.context if body.context else None,
        search_path=root,
    )

    if result.error:
        status = 404 if "not found" in result.error.lower() else 400
        raise HTTPException(status_code=status, detail=result.error)

    return RenderResponse(
        prompt_id=result.prompt_id,
        rendered_content=result.rendered_content,
        template_engine=result.template_engine,
        variables_used=result.variables_used,
    )
