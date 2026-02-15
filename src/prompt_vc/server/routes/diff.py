"""Diff endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...diff import diff_prompt
from ..deps import get_workspace_root

router = APIRouter(tags=["diff"])


class LineDiffResponse(BaseModel):
    line_number: int | None
    content: str
    change_type: str


class AnnotationChangeResponse(BaseModel):
    annotation_id: str
    change_type: str
    details: str


class DiffResponse(BaseModel):
    prompt_id: str
    old_ref: str
    new_ref: str
    prompt_path: str
    meta_path: str
    line_diffs: list[LineDiffResponse]
    annotation_changes: list[AnnotationChangeResponse]


@router.get("/prompts/{prompt_id}/diff", response_model=DiffResponse)
def get_diff(
    prompt_id: str,
    old: str = "HEAD~1",
    new: str = "HEAD",
    root: Path = Depends(get_workspace_root),
) -> DiffResponse:
    result = diff_prompt(prompt_id, old_ref=old, new_ref=new, search_path=root)

    if result.error:
        status = 404 if "not found" in result.error.lower() else 400
        raise HTTPException(status_code=status, detail=result.error)

    return DiffResponse(
        prompt_id=result.prompt_id,
        old_ref=result.old_ref,
        new_ref=result.new_ref,
        prompt_path=result.prompt_path,
        meta_path=result.meta_path,
        line_diffs=[
            LineDiffResponse(
                line_number=ld.line_number,
                content=ld.content,
                change_type=ld.change_type,
            )
            for ld in result.line_diffs
        ],
        annotation_changes=[
            AnnotationChangeResponse(
                annotation_id=ac.annotation_id,
                change_type=ac.change_type,
                details=ac.details,
            )
            for ac in result.annotation_changes
        ],
    )
