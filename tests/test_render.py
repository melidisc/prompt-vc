"""Tests for prompt_vc.render."""

from pathlib import Path

from prompt_vc.models import PromptMeta, Variable
from prompt_vc.render import (
    RenderResult,
    VariableValidation,
    load_context,
    render_prompt,
    validate_variables,
)


class TestLoadContext:
    """Tests for load_context function."""

    def test_load_json_context(self, tmp_path: Path) -> None:
        context_file = tmp_path / "context.json"
        context_file.write_text('{"name": "Alice", "age": 30}')

        context, error = load_context(context_file)

        assert error is None
        assert context == {"name": "Alice", "age": 30}

    def test_load_yaml_context(self, tmp_path: Path) -> None:
        context_file = tmp_path / "context.yaml"
        context_file.write_text("name: Bob\nage: 25")

        context, error = load_context(context_file)

        assert error is None
        assert context == {"name": "Bob", "age": 25}

    def test_load_yml_context(self, tmp_path: Path) -> None:
        context_file = tmp_path / "context.yml"
        context_file.write_text("value: test")

        context, error = load_context(context_file)

        assert error is None
        assert context == {"value": "test"}

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        context_file = tmp_path / "context.json"
        context_file.write_text("invalid json {")

        context, error = load_context(context_file)

        assert error is not None
        assert "parse" in error.lower()

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        context_file = tmp_path / "nonexistent.json"

        context, error = load_context(context_file)

        assert error is not None
        assert "read" in error.lower()


class TestValidateVariables:
    """Tests for validate_variables function."""

    def test_all_variables_provided(self) -> None:
        meta = PromptMeta(
            id="test",
            variables={
                "name": Variable(type="string", required=True),
                "age": Variable(type="integer", required=True),
            },
        )
        context = {"name": "Alice", "age": 30}

        validations = validate_variables(meta, context)

        assert all(v.valid for v in validations)

    def test_missing_required_variable(self) -> None:
        meta = PromptMeta(
            id="test",
            variables={
                "name": Variable(type="string", required=True),
            },
        )
        context = {}  # Missing name

        validations = validate_variables(meta, context)

        assert len(validations) == 1
        assert validations[0].valid is False
        assert "name" in validations[0].name

    def test_optional_variable_not_required(self) -> None:
        meta = PromptMeta(
            id="test",
            variables={
                "name": Variable(type="string", required=False),
            },
        )
        context = {}

        validations = validate_variables(meta, context)

        # Optional variables should pass validation even if not provided
        assert all(v.valid for v in validations)

    def test_variable_with_default(self) -> None:
        meta = PromptMeta(
            id="test",
            variables={
                "name": Variable(type="string", required=True, default="Default"),
            },
        )
        context = {}  # Not provided but has default

        validations = validate_variables(meta, context)

        assert all(v.valid for v in validations)

    def test_no_variables_defined(self) -> None:
        meta = PromptMeta(id="test")
        context = {"extra": "value"}

        validations = validate_variables(meta, context)

        assert validations == []


class TestRenderResult:
    """Tests for RenderResult dataclass."""

    def test_successful_render_result(self) -> None:
        result = RenderResult(
            prompt_id="test",
            rendered_content="Hello, Alice!",
            template_engine="jinja2",
            variables_used=["name"],
        )
        assert result.error is None
        assert result.rendered_content == "Hello, Alice!"

    def test_error_render_result(self) -> None:
        result = RenderResult(
            prompt_id="test",
            error="Missing variable: name",
            missing_variables=["name"],
        )
        assert result.error is not None
        assert "name" in result.missing_variables


class TestVariableValidation:
    """Tests for VariableValidation dataclass."""

    def test_valid_variable(self) -> None:
        validation = VariableValidation(name="name", valid=True)
        assert validation.valid is True

    def test_invalid_variable(self) -> None:
        validation = VariableValidation(
            name="name",
            valid=False,
            message="Required variable 'name' is missing",
        )
        assert validation.valid is False
        assert "missing" in validation.message


class TestRenderPrompt:
    """Tests for render_prompt function."""

    def test_render_simple_prompt(self, tmp_path: Path) -> None:
        # Create prompt files
        prompt_file = tmp_path / "test.prompt.md"
        prompt_file.write_text("Hello, world!")

        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text("""
schema_version: "1.0"
id: test
""")

        result = render_prompt("test", search_path=tmp_path)

        assert result.error is None
        assert result.rendered_content == "Hello, world!"
        assert result.template_engine == "none"

    def test_render_jinja2_prompt(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "test.prompt.jinja"
        prompt_file.write_text("Hello, {{ name }}!")

        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text("""
schema_version: "1.0"
id: test
assumptions:
  template_engine: jinja2
variables:
  name:
    type: string
    required: true
""")

        result = render_prompt("test", context={"name": "Alice"}, search_path=tmp_path)

        assert result.error is None
        assert result.rendered_content == "Hello, Alice!"
        assert result.template_engine == "jinja2"

    def test_render_with_default_values(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "test.prompt.jinja"
        prompt_file.write_text("Hello, {{ name }}!")

        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text("""
schema_version: "1.0"
id: test
assumptions:
  template_engine: jinja2
variables:
  name:
    type: string
    required: true
    default: "World"
""")

        result = render_prompt("test", search_path=tmp_path)  # No context provided

        assert result.error is None
        assert result.rendered_content == "Hello, World!"

    def test_render_missing_required_variable(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "test.prompt.jinja"
        prompt_file.write_text("Hello, {{ name }}!")

        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text("""
schema_version: "1.0"
id: test
assumptions:
  template_engine: jinja2
variables:
  name:
    type: string
    required: true
""")

        result = render_prompt("test", search_path=tmp_path)  # No context

        assert result.error is not None
        assert "name" in result.missing_variables

    def test_render_prompt_not_found(self, tmp_path: Path) -> None:
        result = render_prompt("nonexistent", search_path=tmp_path)

        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_render_with_context_file(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "test.prompt.jinja"
        prompt_file.write_text("Hello, {{ name }}!")

        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text("""
schema_version: "1.0"
id: test
assumptions:
  template_engine: jinja2
variables:
  name:
    type: string
    required: true
""")

        context_file = tmp_path / "context.json"
        context_file.write_text('{"name": "Bob"}')

        result = render_prompt("test", context_path=context_file, search_path=tmp_path)

        assert result.error is None
        assert result.rendered_content == "Hello, Bob!"

    def test_render_context_overrides_defaults(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "test.prompt.jinja"
        prompt_file.write_text("Hello, {{ name }}!")

        meta_file = tmp_path / "test.prompt.meta.yaml"
        meta_file.write_text("""
schema_version: "1.0"
id: test
assumptions:
  template_engine: jinja2
variables:
  name:
    type: string
    default: "Default"
""")

        result = render_prompt("test", context={"name": "Override"}, search_path=tmp_path)

        assert result.error is None
        assert result.rendered_content == "Hello, Override!"
