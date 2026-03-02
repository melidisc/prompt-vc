"""Compose endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...compose import compose_prompt
from ..deps import get_workspace_root

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
def compose(
    prompt_id: str,
    root: Path = Depends(get_workspace_root),
) -> ComposeResponse:
    result = compose_prompt(prompt_id, search_path=root)

    if result.error:
        status = 404 if "not found" in result.error.lower() else 400
        raise HTTPException(status_code=status, detail=result.error)

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
