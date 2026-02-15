"""Render endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...render import render_prompt

router = APIRouter(tags=["render"])


class RenderRequest(BaseModel):
    context: dict[str, Any] = {}


class RenderResponse(BaseModel):
    prompt_id: str
    rendered_content: str
    template_engine: str
    variables_used: list[str]


@router.post("/prompts/{prompt_id}/render", response_model=RenderResponse)
async def render(prompt_id: str, body: RenderRequest) -> RenderResponse:
    result = render_prompt(prompt_id, context=body.context if body.context else None)

    if result.error:
        raise HTTPException(status_code=400, detail=result.error)

    return RenderResponse(
        prompt_id=result.prompt_id,
        rendered_content=result.rendered_content,
        template_engine=result.template_engine,
        variables_used=result.variables_used,
    )
