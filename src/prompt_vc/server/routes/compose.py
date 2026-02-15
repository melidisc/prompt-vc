"""Compose endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...compose import compose_prompt

router = APIRouter(tags=["compose"])


class DependencyResponse(BaseModel):
    from_id: str
    to_id: str
    include_type: str


class ComposeResponse(BaseModel):
    prompt_id: str
    composed_content: str
    dependencies: list[DependencyResponse]
    resolved_prompts: list[str]


@router.get("/prompts/{prompt_id}/compose", response_model=ComposeResponse)
async def compose(prompt_id: str) -> ComposeResponse:
    result = compose_prompt(prompt_id)

    if result.error:
        raise HTTPException(status_code=400, detail=result.error)

    return ComposeResponse(
        prompt_id=result.prompt_id,
        composed_content=result.composed_content,
        dependencies=[
            DependencyResponse(
                from_id=d.from_id,
                to_id=d.to_id,
                include_type=d.include_type,
            )
            for d in result.dependencies
        ],
        resolved_prompts=result.resolved_prompts,
    )
