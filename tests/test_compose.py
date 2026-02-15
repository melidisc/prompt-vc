"""Tests for prompt_vc.compose."""

from pathlib import Path

import pytest

from prompt_vc.compose import (
    ComposeResult,
    PromptDependency,
    compose_prompt,
    get_prompt_dependencies,
)


class TestPromptDependency:
    """Tests for PromptDependency dataclass."""

    def test_basic_dependency(self) -> None:
        dep = PromptDependency(
            from_id="parent",
            to_id="child",
            include_type="include",
        )
        assert dep.from_id == "parent"
        assert dep.to_id == "child"
        assert dep.include_type == "include"


class TestComposeResult:
    """Tests for ComposeResult dataclass."""

    def test_successful_compose(self) -> None:
        result = ComposeResult(
            prompt_id="test",
            composed_content="Hello, world!",
            dependencies=[],
            resolved_prompts=["test"],
        )
        assert result.error is None
        assert result.composed_content == "Hello, world!"

    def test_compose_with_error(self) -> None:
        result = ComposeResult(
            prompt_id="test",
            error="Prompt not found",
        )
        assert result.error is not None


class TestComposePrompt:
    """Tests for compose_prompt function."""

    def test_compose_simple_prompt(self, tmp_path: Path) -> None:
        # Create a simple prompt without includes
        prompt_file = tmp_path / "test.prompt.md"
        prompt_file.write_text("Hello, world!")

        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text("""
schema_version: "1.0"
id: test
""")

        result = compose_prompt("test", search_path=tmp_path)

        assert result.error is None
        assert result.composed_content == "Hello, world!"
        assert result.dependencies == []

    def test_compose_with_include(self, tmp_path: Path) -> None:
        # Create main prompt
        main_prompt = tmp_path / "main.prompt.md"
        main_prompt.write_text("Header\n{% include 'sub' %}\nFooter")

        main_meta = tmp_path / "main.prompt.meta.yaml"
        main_meta.write_text("""
schema_version: "1.0"
id: main
""")

        # Create included prompt
        sub_prompt = tmp_path / "sub.prompt.md"
        sub_prompt.write_text("Included content")

        sub_meta = tmp_path / "sub.prompt.meta.yaml"
        sub_meta.write_text("""
schema_version: "1.0"
id: sub
""")

        result = compose_prompt("main", search_path=tmp_path)

        assert result.error is None
        assert "Header" in result.composed_content
        assert "Included content" in result.composed_content
        assert "Footer" in result.composed_content
        assert len(result.dependencies) == 1
        assert result.dependencies[0].from_id == "main"
        assert result.dependencies[0].to_id == "sub"

    def test_compose_with_double_quotes(self, tmp_path: Path) -> None:
        # Test {% include "prompt-id" %} syntax
        main_prompt = tmp_path / "main.prompt.md"
        main_prompt.write_text('Start\n{% include "sub" %}\nEnd')

        main_meta = tmp_path / "main.prompt.meta.yaml"
        main_meta.write_text("""
schema_version: "1.0"
id: main
""")

        sub_prompt = tmp_path / "sub.prompt.md"
        sub_prompt.write_text("Included")

        sub_meta = tmp_path / "sub.prompt.meta.yaml"
        sub_meta.write_text("""
schema_version: "1.0"
id: sub
""")

        result = compose_prompt("main", search_path=tmp_path)

        assert result.error is None
        assert "Included" in result.composed_content

    def test_compose_with_comment_include(self, tmp_path: Path) -> None:
        # Test {# @include prompt-id #} syntax
        main_prompt = tmp_path / "main.prompt.md"
        main_prompt.write_text("Start\n{# @include sub #}\nEnd")

        main_meta = tmp_path / "main.prompt.meta.yaml"
        main_meta.write_text("""
schema_version: "1.0"
id: main
""")

        sub_prompt = tmp_path / "sub.prompt.md"
        sub_prompt.write_text("Included")

        sub_meta = tmp_path / "sub.prompt.meta.yaml"
        sub_meta.write_text("""
schema_version: "1.0"
id: sub
""")

        result = compose_prompt("main", search_path=tmp_path)

        assert result.error is None
        assert "Included" in result.composed_content

    def test_compose_nested_includes(self, tmp_path: Path) -> None:
        # Create nested includes: A -> B -> C
        a_prompt = tmp_path / "a.prompt.md"
        a_prompt.write_text("A-start\n{% include 'b' %}\nA-end")

        a_meta = tmp_path / "a.prompt.meta.yaml"
        a_meta.write_text("schema_version: '1.0'\nid: a")

        b_prompt = tmp_path / "b.prompt.md"
        b_prompt.write_text("B-start\n{% include 'c' %}\nB-end")

        b_meta = tmp_path / "b.prompt.meta.yaml"
        b_meta.write_text("schema_version: '1.0'\nid: b")

        c_prompt = tmp_path / "c.prompt.md"
        c_prompt.write_text("C-content")

        c_meta = tmp_path / "c.prompt.meta.yaml"
        c_meta.write_text("schema_version: '1.0'\nid: c")

        result = compose_prompt("a", search_path=tmp_path)

        assert result.error is None
        assert "A-start" in result.composed_content
        assert "B-start" in result.composed_content
        assert "C-content" in result.composed_content
        assert len(result.dependencies) == 2  # a->b, b->c

    def test_compose_circular_dependency(self, tmp_path: Path) -> None:
        # Create circular: A -> B -> A
        a_prompt = tmp_path / "a.prompt.md"
        a_prompt.write_text("A\n{% include 'b' %}")

        a_meta = tmp_path / "a.prompt.meta.yaml"
        a_meta.write_text("schema_version: '1.0'\nid: a")

        b_prompt = tmp_path / "b.prompt.md"
        b_prompt.write_text("B\n{% include 'a' %}")

        b_meta = tmp_path / "b.prompt.meta.yaml"
        b_meta.write_text("schema_version: '1.0'\nid: b")

        result = compose_prompt("a", search_path=tmp_path)

        assert result.error is not None
        assert "circular" in result.error.lower()

    def test_compose_missing_include(self, tmp_path: Path) -> None:
        main_prompt = tmp_path / "main.prompt.md"
        main_prompt.write_text("{% include 'nonexistent' %}")

        main_meta = tmp_path / "main.prompt.meta.yaml"
        main_meta.write_text("schema_version: '1.0'\nid: main")

        result = compose_prompt("main", search_path=tmp_path)

        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_compose_prompt_not_found(self, tmp_path: Path) -> None:
        result = compose_prompt("nonexistent", search_path=tmp_path)

        assert result.error is not None


class TestGetPromptDependencies:
    """Tests for get_prompt_dependencies function."""

    def test_no_dependencies(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "test.prompt.md"
        prompt_file.write_text("Simple content")

        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text("schema_version: '1.0'\nid: test")

        deps, error = get_prompt_dependencies("test", search_path=tmp_path)

        assert error is None
        assert deps == []

    def test_direct_dependencies_only(self, tmp_path: Path) -> None:
        a_prompt = tmp_path / "a.prompt.md"
        a_prompt.write_text("{% include 'b' %}\n{% include 'c' %}")

        a_meta = tmp_path / "a.prompt.meta.yaml"
        a_meta.write_text("schema_version: '1.0'\nid: a")

        b_prompt = tmp_path / "b.prompt.md"
        b_prompt.write_text("B")

        b_meta = tmp_path / "b.prompt.meta.yaml"
        b_meta.write_text("schema_version: '1.0'\nid: b")

        c_prompt = tmp_path / "c.prompt.md"
        c_prompt.write_text("C")

        c_meta = tmp_path / "c.prompt.meta.yaml"
        c_meta.write_text("schema_version: '1.0'\nid: c")

        deps, error = get_prompt_dependencies("a", search_path=tmp_path, recursive=False)

        assert error is None
        assert len(deps) == 2
        dep_ids = [d.to_id for d in deps]
        assert "b" in dep_ids
        assert "c" in dep_ids

    def test_recursive_dependencies(self, tmp_path: Path) -> None:
        # A -> B -> C
        a_prompt = tmp_path / "a.prompt.md"
        a_prompt.write_text("{% include 'b' %}")

        a_meta = tmp_path / "a.prompt.meta.yaml"
        a_meta.write_text("schema_version: '1.0'\nid: a")

        b_prompt = tmp_path / "b.prompt.md"
        b_prompt.write_text("{% include 'c' %}")

        b_meta = tmp_path / "b.prompt.meta.yaml"
        b_meta.write_text("schema_version: '1.0'\nid: b")

        c_prompt = tmp_path / "c.prompt.md"
        c_prompt.write_text("C")

        c_meta = tmp_path / "c.prompt.meta.yaml"
        c_meta.write_text("schema_version: '1.0'\nid: c")

        deps, error = get_prompt_dependencies("a", search_path=tmp_path, recursive=True)

        assert error is None
        assert len(deps) == 2  # a->b, b->c

    def test_prompt_not_found(self, tmp_path: Path) -> None:
        deps, error = get_prompt_dependencies("nonexistent", search_path=tmp_path)

        assert error is not None
        assert deps == []
