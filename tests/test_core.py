"""Tests for prompt-vc."""


from prompt_vc.hashing import (
    extract_preview,
    hash_content,
    normalize_text,
    similarity_score,
)
from prompt_vc.models import Anchor, Annotation, PromptMeta


class TestHashing:
    """Tests for hashing utilities."""

    def test_normalize_text_strips_whitespace(self) -> None:
        assert normalize_text("  hello world  ") == "hello world"

    def test_normalize_text_collapses_internal_whitespace(self) -> None:
        assert normalize_text("hello   world") == "hello world"

    def test_normalize_text_handles_newlines(self) -> None:
        assert normalize_text("hello\nworld") == "hello world"

    def test_hash_content_is_deterministic(self) -> None:
        text = "You MUST NOT promise refunds exceeding"
        hash1 = hash_content(text)
        hash2 = hash_content(text)
        assert hash1 == hash2

    def test_hash_content_format(self) -> None:
        result = hash_content("test")
        assert result.startswith("sha256:")
        assert len(result) == 7 + 64  # "sha256:" + 64 hex chars

    def test_extract_preview_short_text(self) -> None:
        text = "Short text"
        assert extract_preview(text) == "Short text"

    def test_extract_preview_long_text(self) -> None:
        text = "This is a very long text that should be truncated"
        preview = extract_preview(text, max_length=20)
        assert len(preview) == 20
        assert preview.endswith("...")

    def test_similarity_score_identical(self) -> None:
        assert similarity_score("hello world", "hello world") == 1.0

    def test_similarity_score_different(self) -> None:
        score = similarity_score("hello world", "goodbye moon")
        assert score == 0.0

    def test_similarity_score_partial(self) -> None:
        score = similarity_score("hello world", "hello moon")
        assert 0.0 < score < 1.0


class TestModels:
    """Tests for Pydantic models."""

    def test_prompt_meta_minimal(self) -> None:
        meta = PromptMeta(id="test-prompt")
        assert meta.id == "test-prompt"
        assert meta.schema_version == "1.0"
        assert meta.annotations == []

    def test_prompt_meta_with_annotation(self) -> None:
        meta = PromptMeta(
            id="test-prompt",
            intent="Test intent",
            annotations=[
                Annotation(
                    id="ann_01",
                    anchor=Anchor(
                        hash="sha256:abc123",
                        preview="Test text",
                        line_hint=5,
                    ),
                    rationale="Test rationale",
                )
            ],
        )
        assert len(meta.annotations) == 1
        assert meta.annotations[0].id == "ann_01"
