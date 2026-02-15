"""Audit functionality for prompt-vc governance compliance."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .listing import find_manifest, list_from_manifest, parse_manifest
from .models import ProductionRequirements, PromptMeta
from .validation import parse_meta_file

# Pattern to match any .prompt.* extension and convert to .prompt.meta.yaml
PROMPT_EXT_PATTERN = re.compile(r"\.prompt\.[^.]+$")


def _get_meta_path_from_prompt_path(prompt_path: str) -> str:
    """Convert a prompt file path to its corresponding meta file path.

    Handles all prompt extensions: .prompt.md, .prompt.jinja, .prompt.txt, etc.
    """
    return PROMPT_EXT_PATTERN.sub(".prompt.meta.yaml", prompt_path)


@dataclass
class ComplianceIssue:
    """A single compliance issue."""

    requirement: str
    message: str
    severity: str = "error"  # "error" or "warning"


@dataclass
class PromptAuditResult:
    """Audit result for a single prompt."""

    prompt_id: str
    domain: str | None
    status: str
    path: str
    compliant: bool
    issues: list[ComplianceIssue] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


@dataclass
class AuditReport:
    """Complete audit report."""

    manifest_path: str | None
    requirements: ProductionRequirements | None
    results: list[PromptAuditResult] = field(default_factory=list)
    error: str | None = None

    @property
    def total_prompts(self) -> int:
        """Total number of prompts audited."""
        return len([r for r in self.results if not r.skipped])

    @property
    def compliant_count(self) -> int:
        """Number of compliant prompts."""
        return sum(1 for r in self.results if r.compliant and not r.skipped)

    @property
    def non_compliant_count(self) -> int:
        """Number of non-compliant prompts."""
        return sum(1 for r in self.results if not r.compliant and not r.skipped)

    @property
    def skipped_count(self) -> int:
        """Number of skipped prompts."""
        return sum(1 for r in self.results if r.skipped)


def check_production_requirements(
    meta: PromptMeta,
    requirements: ProductionRequirements,
) -> list[ComplianceIssue]:
    """Check a prompt against production requirements.

    Args:
        meta: Parsed prompt metadata
        requirements: Production requirements from governance

    Returns:
        List of compliance issues found
    """
    issues: list[ComplianceIssue] = []

    # Check must_have_intent
    if requirements.must_have_intent:
        if not meta.intent or not meta.intent.strip():
            issues.append(ComplianceIssue(
                requirement="must_have_intent",
                message="Prompt must have an intent field",
            ))

    # Check must_have_evaluation
    if requirements.must_have_evaluation:
        if not meta.evaluation:
            issues.append(ComplianceIssue(
                requirement="must_have_evaluation",
                message="Prompt must have an evaluation section",
            ))
        elif not meta.evaluation.metrics:
            issues.append(ComplianceIssue(
                requirement="must_have_evaluation",
                message="Prompt evaluation must define at least one metric",
            ))

    # Check min_annotations
    if requirements.min_annotations > 0:
        annotation_count = len(meta.annotations) if meta.annotations else 0
        if annotation_count < requirements.min_annotations:
            issues.append(ComplianceIssue(
                requirement="min_annotations",
                message=(
                    f"Prompt must have at least {requirements.min_annotations} "
                    f"annotations (has {annotation_count})"
                ),
            ))

    # Check required_tags
    if requirements.required_tags:
        all_tags: set[str] = set()
        if meta.annotations:
            for annotation in meta.annotations:
                all_tags.update(annotation.tags)

        missing_tags = set(requirements.required_tags) - all_tags
        if missing_tags:
            issues.append(ComplianceIssue(
                requirement="required_tags",
                message=f"Missing required tags: {', '.join(sorted(missing_tags))}",
            ))

    return issues


def audit_prompt(
    prompt_id: str,
    meta_path: Path,
    requirements: ProductionRequirements,
    domain: str | None = None,
    status: str = "unknown",
    path: str = "",
) -> PromptAuditResult:
    """Audit a single prompt against requirements.

    Args:
        prompt_id: Prompt identifier
        meta_path: Path to the meta file
        requirements: Production requirements to check against
        domain: Domain name
        status: Prompt status
        path: Path to prompt file

    Returns:
        Audit result for this prompt
    """
    # Parse the meta file
    meta, parse_issues = parse_meta_file(meta_path)

    if meta is None:
        return PromptAuditResult(
            prompt_id=prompt_id,
            domain=domain,
            status=status,
            path=path,
            compliant=False,
            skipped=True,
            skip_reason=(
                f"Could not parse meta file: "
                f"{parse_issues[0].message if parse_issues else 'unknown error'}"
            ),
        )

    # Check against requirements
    issues = check_production_requirements(meta, requirements)

    return PromptAuditResult(
        prompt_id=prompt_id,
        domain=domain,
        status=status,
        path=path,
        compliant=len(issues) == 0,
        issues=issues,
    )


def run_audit(
    search_path: Path | None = None,
    status_filter: str | None = "production",
) -> AuditReport:
    """Run governance audit on all prompts.

    Args:
        search_path: Directory to search for manifest
        status_filter: Only audit prompts with this status (default: "production")

    Returns:
        Complete audit report
    """
    manifest_path = find_manifest(search_path)

    if not manifest_path:
        return AuditReport(
            manifest_path=None,
            requirements=None,
            results=[],
        )

    manifest, parse_error = parse_manifest(manifest_path)
    if manifest is None:
        return AuditReport(
            manifest_path=str(manifest_path),
            requirements=None,
            results=[],
            error=parse_error,
        )

    # Get production requirements
    requirements = None
    if manifest.governance and manifest.governance.production_requirements:
        requirements = manifest.governance.production_requirements
    else:
        # Use defaults if no governance defined
        requirements = ProductionRequirements()

    # Get prompts to audit
    prompts = list_from_manifest(
        manifest,
        manifest_path,
        status_filter=status_filter,
    )

    results: list[PromptAuditResult] = []
    manifest_dir = manifest_path.parent

    for prompt_info in prompts:
        # Find the meta file
        meta_path = manifest_dir / _get_meta_path_from_prompt_path(prompt_info.path)

        if not meta_path.exists():
            results.append(PromptAuditResult(
                prompt_id=prompt_info.id,
                domain=prompt_info.domain,
                status=prompt_info.status,
                path=prompt_info.path,
                compliant=False,
                skipped=True,
                skip_reason="Meta file not found",
            ))
            continue

        result = audit_prompt(
            prompt_id=prompt_info.id,
            meta_path=meta_path,
            requirements=requirements,
            domain=prompt_info.domain,
            status=prompt_info.status,
            path=prompt_info.path,
        )
        results.append(result)

    return AuditReport(
        manifest_path=str(manifest_path),
        requirements=requirements,
        results=results,
    )
