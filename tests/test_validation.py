"""Tests for prompt_vc.validation."""

import tempfile
from pathlib import Path

import pytest

from prompt_vc.models import Anchor, Annotation, PromptMeta
from prompt_vc.validation import (
    ValidationIssue,
    check_annotation_hashes,
    find_prompt_file,
    parse_meta_file,
)


class TestParseMetaFile:
    """Tests for parse_meta_file function."""

    def test_parse_valid_meta_file(self, tmp_path: Path) -> None:
        meta_content = """
schema_version: "1.0"
id: test-prompt
intent: Test intent
"""
        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text(meta_content)

        meta, issues = parse_meta_file(meta_file)

        assert meta is not None
        assert meta.id == "test-prompt"
        assert meta.intent == "Test intent"
        assert issues == []

    def test_parse_meta_file_with_annotations(self, tmp_path: Path) -> None:
        meta_content = """
schema_version: "1.0"
id: test-prompt
annotations:
  - id: ann_01
    anchor:
      hash: "sha256:abc123"
      preview: "Test text"
      line_hint: 5
    rationale: "Safety requirement"
"""
        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text(meta_content)

        meta, issues = parse_meta_file(meta_file)

        assert meta is not None
        assert len(meta.annotations) == 1
        assert meta.annotations[0].id == "ann_01"

    def test_parse_invalid_yaml(self, tmp_path: Path) -> None:
        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text("invalid: yaml: content: [")

        meta, issues = parse_meta_file(meta_file)

        assert meta is None
        assert len(issues) > 0
        assert issues[0].level == "error"

    def test_parse_missing_required_field(self, tmp_path: Path) -> None:
        meta_content = """
schema_version: "1.0"
# Missing id field
intent: Test
"""
        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text(meta_content)

        meta, issues = parse_meta_file(meta_file)

        assert meta is None
        assert len(issues) > 0

    def test_parse_nonexistent_file(self, tmp_path: Path) -> None:
        meta_file = tmp_path / "nonexistent.prompt.meta.yaml"

        meta, issues = parse_meta_file(meta_file)

        assert meta is None
        assert len(issues) > 0
        assert "Cannot read" in issues[0].message or "not found" in issues[0].message.lower()


class TestFindPromptFile:
    """Tests for find_prompt_file function."""

    def test_find_md_prompt(self, tmp_path: Path) -> None:
        meta_file = tmp_path / "test.prompt.meta.yaml"
        prompt_file = tmp_path / "test.prompt.md"
        meta_file.write_text("id: test")
        prompt_file.write_text("# Prompt content")

        result = find_prompt_file(meta_file)

        assert result is not None
        assert result == prompt_file

    def test_find_jinja_prompt(self, tmp_path: Path) -> None:
        meta_file = tmp_path / "test.prompt.meta.yaml"
        prompt_file = tmp_path / "test.prompt.jinja"
        meta_file.write_text("id: test")
        prompt_file.write_text("{{ variable }}")

        result = find_prompt_file(meta_file)

        assert result is not None
        assert result == prompt_file

    def test_find_txt_prompt(self, tmp_path: Path) -> None:
        meta_file = tmp_path / "test.prompt.meta.yaml"
        prompt_file = tmp_path / "test.prompt.txt"
        meta_file.write_text("id: test")
        prompt_file.write_text("Plain text prompt")

        result = find_prompt_file(meta_file)

        assert result is not None
        assert result == prompt_file

    def test_no_prompt_file_found(self, tmp_path: Path) -> None:
        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text("id: test")

        result = find_prompt_file(meta_file)

        assert result is None


class TestCheckAnnotationHashes:
    """Tests for check_annotation_hashes function."""

    def test_valid_annotation_hash(self, tmp_path: Path) -> None:
        # Create prompt file with known content
        prompt_file = tmp_path / "test.prompt.md"
        prompt_file.write_text("Line 1\nYou MUST NOT promise refunds\nLine 3")

        # Create meta with matching hash
        from prompt_vc.hashing import hash_content

        content_hash = hash_content("You MUST NOT promise refunds")
        meta = PromptMeta(
            id="test",
            annotations=[
                Annotation(
                    id="ann_01",
                    anchor=Anchor(
                        hash=content_hash,
                        preview="You MUST NOT promise refunds",
                        line_hint=2,
                    ),
                    rationale="Safety",
                )
            ],
        )

        results = check_annotation_hashes(meta, prompt_file)

        assert len(results) == 1
        assert results[0].status == "valid"

    def test_stale_annotation_hash(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "test.prompt.md"
        prompt_file.write_text("Line 1\nDifferent content now\nLine 3")

        meta = PromptMeta(
            id="test",
            annotations=[
                Annotation(
                    id="ann_01",
                    anchor=Anchor(
                        hash="sha256:wronghash",
                        preview="Original text that no longer exists",
                        line_hint=2,
                    ),
                    rationale="Safety",
                )
            ],
        )

        results = check_annotation_hashes(meta, prompt_file)

        assert len(results) == 1
        assert results[0].status in ("stale", "orphaned")

    def test_moved_annotation(self, tmp_path: Path) -> None:
        # Content moved to different line
        prompt_file = tmp_path / "test.prompt.md"
        prompt_file.write_text("New line\nAnother line\nYou MUST NOT promise refunds\nLine 4")

        from prompt_vc.hashing import hash_content

        content_hash = hash_content("You MUST NOT promise refunds")
        meta = PromptMeta(
            id="test",
            annotations=[
                Annotation(
                    id="ann_01",
                    anchor=Anchor(
                        hash=content_hash,
                        preview="You MUST NOT promise refunds",
                        line_hint=1,  # Original line
                    ),
                    rationale="Safety",
                )
            ],
        )

        results = check_annotation_hashes(meta, prompt_file)

        assert len(results) == 1
        # Should find the content at a different line
        assert results[0].status in ("valid", "moved")

    def test_no_annotations(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "test.prompt.md"
        prompt_file.write_text("Some content")

        meta = PromptMeta(id="test", annotations=[])

        results = check_annotation_hashes(meta, prompt_file)

        assert results == []


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_validation_issue_creation(self) -> None:
        issue = ValidationIssue(
            level="error",
            file="/test/path.yaml",
            message="Test error message",
        )
        assert issue.file == "/test/path.yaml"
        assert issue.message == "Test error message"
        assert issue.level == "error"

    def test_validation_issue_warning(self) -> None:
        issue = ValidationIssue(
            level="warning",
            file="/test/path.yaml",
            message="Test warning",
        )
        assert issue.level == "warning"
