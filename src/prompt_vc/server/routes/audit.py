"""Audit endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...audit import run_audit
from ...models import ProductionRequirements
from ..deps import get_workspace_root

router = APIRouter(tags=["audit"])


class ComplianceIssueResponse(BaseModel):
    requirement: str
    message: str
    severity: str


class PromptAuditResultResponse(BaseModel):
    prompt_id: str
    domain: str | None
    status: str
    path: str
    compliant: bool
    issues: list[ComplianceIssueResponse]
    skipped: bool
    skip_reason: str | None


class AuditReportResponse(BaseModel):
    manifest_path: str | None
    requirements: ProductionRequirements | None
    results: list[PromptAuditResultResponse]
    total_prompts: int
    compliant_count: int
    non_compliant_count: int
    skipped_count: int
    error: str | None


@router.get("/audit", response_model=AuditReportResponse)
def audit_prompts(
    status: str = "production",
    all: bool = False,
    root: Path = Depends(get_workspace_root),
) -> AuditReportResponse:
    status_filter = None if all else status
    report = run_audit(search_path=root, status_filter=status_filter)

    if not report.manifest_path:
        raise HTTPException(status_code=404, detail="No manifest found")

    if report.error:
        raise HTTPException(status_code=400, detail=report.error)

    return AuditReportResponse(
        manifest_path=report.manifest_path,
        requirements=report.requirements,
        results=[
            PromptAuditResultResponse(
                prompt_id=r.prompt_id,
                domain=r.domain,
                status=r.status,
                path=r.path,
                compliant=r.compliant,
                issues=[
                    ComplianceIssueResponse(
                        requirement=i.requirement,
                        message=i.message,
                        severity=i.severity,
                    )
                    for i in r.issues
                ],
                skipped=r.skipped,
                skip_reason=r.skip_reason,
            )
            for r in report.results
        ],
        total_prompts=report.total_prompts,
        compliant_count=report.compliant_count,
        non_compliant_count=report.non_compliant_count,
        skipped_count=report.skipped_count,
        error=report.error,
    )
