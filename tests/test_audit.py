"""Tests for prompt_vc.audit."""

from pathlib import Path

import pytest

from prompt_vc.audit import (
    AuditReport,
    ComplianceIssue,
    PromptAuditResult,
    check_production_requirements,
    run_audit,
)
from prompt_vc.models import (
    Anchor,
    Annotation,
    Evaluation,
    Metric,
    ProductionRequirements,
    PromptMeta,
)


class TestCheckProductionRequirements:
    """Tests for check_production_requirements function."""

    def test_compliant_prompt(self) -> None:
        meta = PromptMeta(
            id="test-prompt",
            intent="Handle customer refunds",
            evaluation=Evaluation(
                metrics=[Metric(name="accuracy", target=">= 90%", measured_by="eval.py")],
                test_cases_ref="tests/eval.yaml",
            ),
            annotations=[
                Annotation(
                    id="ann_01",
                    anchor=Anchor(hash="sha256:abc", preview="test"),
                    rationale="Safety",
                    tags=["reviewed"],
                )
            ],
        )
        requirements = ProductionRequirements(
            must_have_intent=True,
            must_have_evaluation=True,
            min_annotations=1,
            required_tags=["reviewed"],
        )

        issues = check_production_requirements(meta, requirements)

        assert issues == []

    def test_missing_intent(self) -> None:
        meta = PromptMeta(id="test-prompt")  # No intent
        requirements = ProductionRequirements(must_have_intent=True)

        issues = check_production_requirements(meta, requirements)

        assert len(issues) == 1
        assert "intent" in issues[0].message.lower()

    def test_missing_evaluation(self) -> None:
        meta = PromptMeta(id="test-prompt", intent="Test")
        requirements = ProductionRequirements(
            must_have_intent=True,
            must_have_evaluation=True,
        )

        issues = check_production_requirements(meta, requirements)

        assert len(issues) == 1
        assert "evaluation" in issues[0].message.lower()

    def test_insufficient_annotations(self) -> None:
        meta = PromptMeta(
            id="test-prompt",
            intent="Test",
            annotations=[
                Annotation(
                    id="ann_01",
                    anchor=Anchor(hash="sha256:abc", preview="test"),
                    rationale="One",
                )
            ],
        )
        requirements = ProductionRequirements(
            must_have_intent=True,
            min_annotations=3,
        )

        issues = check_production_requirements(meta, requirements)

        assert len(issues) == 1
        assert "annotation" in issues[0].message.lower()

    def test_missing_required_tags(self) -> None:
        meta = PromptMeta(
            id="test-prompt",
            intent="Test",
            annotations=[
                Annotation(
                    id="ann_01",
                    anchor=Anchor(hash="sha256:abc", preview="test"),
                    rationale="Test",
                    tags=["safety"],  # Missing "reviewed" tag
                )
            ],
        )
        requirements = ProductionRequirements(
            must_have_intent=True,
            required_tags=["reviewed", "safety"],
        )

        issues = check_production_requirements(meta, requirements)

        assert len(issues) == 1
        assert "reviewed" in issues[0].message

    def test_multiple_issues(self) -> None:
        meta = PromptMeta(id="test-prompt")  # No intent, no evaluation, no annotations
        requirements = ProductionRequirements(
            must_have_intent=True,
            must_have_evaluation=True,
            min_annotations=1,
        )

        issues = check_production_requirements(meta, requirements)

        assert len(issues) >= 2  # At least missing intent and evaluation


class TestPromptAuditResult:
    """Tests for PromptAuditResult dataclass."""

    def test_compliant_result(self) -> None:
        result = PromptAuditResult(
            prompt_id="test-prompt",
            domain="support",
            path="prompts/test.prompt.md",
            status="production",
            compliant=True,
            issues=[],
        )
        assert result.compliant is True
        assert result.issues == []

    def test_non_compliant_result(self) -> None:
        result = PromptAuditResult(
            prompt_id="test-prompt",
            domain="support",
            path="prompts/test.prompt.md",
            status="production",
            compliant=False,
            issues=[
                ComplianceIssue(
                    requirement="must_have_intent",
                    message="Missing intent",
                )
            ],
        )
        assert result.compliant is False
        assert len(result.issues) == 1


class TestComplianceIssue:
    """Tests for ComplianceIssue dataclass."""

    def test_compliance_issue_creation(self) -> None:
        issue = ComplianceIssue(
            requirement="must_have_intent",
            message="Prompt is missing an intent statement",
        )
        assert issue.requirement == "must_have_intent"
        assert "intent" in issue.message


class TestAuditReport:
    """Tests for AuditReport dataclass."""

    def test_empty_report(self) -> None:
        report = AuditReport(
            manifest_path="/path/to/manifest.yaml",
            requirements=None,
            results=[],
        )
        assert report.results == []

    def test_report_with_results(self) -> None:
        report = AuditReport(
            manifest_path="/path/to/manifest.yaml",
            requirements=ProductionRequirements(must_have_intent=True),
            results=[
                PromptAuditResult(
                    prompt_id="test",
                    domain="support",
                    path="p.md",
                    status="production",
                    compliant=True,
                    issues=[],
                )
            ],
        )
        assert len(report.results) == 1
        assert report.requirements is not None

    def test_report_with_error(self) -> None:
        report = AuditReport(
            manifest_path=None,
            requirements=None,
            results=[],
            error="No manifest found",
        )
        assert report.error == "No manifest found"


class TestRunAudit:
    """Tests for run_audit function."""

    def test_run_audit_no_manifest(self, tmp_path: Path) -> None:
        # No manifest in the directory
        report = run_audit(search_path=tmp_path)

        # When no manifest found, manifest_path is None and results are empty
        assert report.manifest_path is None
        assert report.results == []

    def test_run_audit_with_manifest(self, tmp_path: Path) -> None:
        # Create a minimal manifest
        manifest_content = """
schema_version: "1.0"
domains:
  support:
    prompts:
      - id: test-prompt
        path: support/test.prompt.md
        status: production
governance:
  production_requirements:
    must_have_intent: true
"""
        manifest_file = tmp_path / "prompts.manifest.yaml"
        manifest_file.write_text(manifest_content)

        # Create the prompt directory and files
        support_dir = tmp_path / "support"
        support_dir.mkdir()

        prompt_file = support_dir / "test.prompt.md"
        prompt_file.write_text("# Test Prompt\nContent here")

        meta_file = support_dir / "test.prompt.meta.yaml"
        meta_file.write_text("""
schema_version: "1.0"
id: test-prompt
intent: Test intent
""")

        report = run_audit(search_path=tmp_path)

        assert report.error is None
        assert len(report.results) == 1
        assert report.results[0].prompt_id == "test-prompt"
