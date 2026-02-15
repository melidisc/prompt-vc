"""Validation endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...validation import validate_all, validate_prompt
from ...view import find_meta_file_by_id
from ..deps import get_workspace_root

router = APIRouter(tags=["validate"])


class ValidationIssueResponse(BaseModel):
    level: str
    file: str
    message: str
    line: int | None = None
    annotation_id: str | None = None


class ValidationResultResponse(BaseModel):
    meta_file: str
    prompt_file: str | None
    valid: bool
    error_count: int
    warning_count: int
    issues: list[ValidationIssueResponse]


class ValidateAllResponse(BaseModel):
    results: list[ValidationResultResponse]
    total_errors: int
    total_warnings: int


def _to_result_response(r: object) -> ValidationResultResponse:
    """Convert a ValidationResult to its response model."""
    from ...validation import ValidationResult

    assert isinstance(r, ValidationResult)
    return ValidationResultResponse(
        meta_file=r.meta_file,
        prompt_file=r.prompt_file,
        valid=r.valid,
        error_count=r.error_count,
        warning_count=r.warning_count,
        issues=[
            ValidationIssueResponse(
                level=i.level,
                file=i.file,
                message=i.message,
                line=i.line,
                annotation_id=i.annotation_id,
            )
            for i in r.issues
        ],
    )


@router.get("/validate", response_model=ValidateAllResponse)
def validate_all_prompts(
    root: Path = Depends(get_workspace_root),
) -> ValidateAllResponse:
    results = validate_all(root)
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)

    return ValidateAllResponse(
        results=[_to_result_response(r) for r in results],
        total_errors=total_errors,
        total_warnings=total_warnings,
    )


@router.get("/validate/{prompt_id}", response_model=ValidationResultResponse)
def validate_single(
    prompt_id: str,
    root: Path = Depends(get_workspace_root),
) -> ValidationResultResponse:
    meta_path = find_meta_file_by_id(prompt_id, root)
    if not meta_path:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")

    result = validate_prompt(meta_path)
    return _to_result_response(result)
