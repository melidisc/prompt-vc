"""Render functionality for prompt templates."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import PromptMeta
from .validation import find_prompt_file, parse_meta_file
from .view import find_meta_file_by_id


@dataclass
class RenderResult:
    """Result of rendering a prompt."""

    prompt_id: str
    rendered_content: str = ""
    template_engine: str = "none"
    variables_used: list[str] = field(default_factory=list)
    missing_variables: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class VariableValidation:
    """Validation result for a variable."""

    name: str
    valid: bool
    message: str = ""


def load_context(context_path: Path) -> tuple[dict[str, Any], str | None]:
    """Load context variables from a JSON or YAML file.

    Args:
        context_path: Path to context file

    Returns:
        Tuple of (context dict, error message or None)
    """
    try:
        content = context_path.read_text(encoding="utf-8")
    except OSError as e:
        return {}, f"Cannot read context file: {e}"

    suffix = context_path.suffix.lower()

    try:
        if suffix == ".json":
            return json.loads(content), None
        elif suffix in (".yaml", ".yml"):
            data = yaml.safe_load(content)
            return data if data else {}, None
        else:
            # Try JSON first, then YAML
            try:
                return json.loads(content), None
            except json.JSONDecodeError:
                data = yaml.safe_load(content)
                return data if data else {}, None
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        return {}, f"Cannot parse context file: {e}"


def validate_variables(
    meta: PromptMeta,
    context: dict[str, Any],
) -> list[VariableValidation]:
    """Validate that required variables are provided.

    Args:
        meta: Prompt metadata with variable definitions
        context: Context dictionary with variable values

    Returns:
        List of validation results
    """
    validations: list[VariableValidation] = []

    if not meta.variables:
        return validations

    for var_name, var_def in meta.variables.items():
        if var_def.required and var_name not in context:
            if var_def.default is None:
                validations.append(
                    VariableValidation(
                        name=var_name,
                        valid=False,
                        message=f"Required variable '{var_name}' is missing",
                    )
                )
            else:
                validations.append(
                    VariableValidation(
                        name=var_name,
                        valid=True,
                        message=f"Using default value for '{var_name}'",
                    )
                )
        else:
            validations.append(
                VariableValidation(
                    name=var_name,
                    valid=True,
                )
            )

    return validations


def _get_defaults(meta: PromptMeta) -> dict[str, str | int | float | bool | None]:
    """Get default values from variable definitions."""
    defaults = {}
    if meta.variables:
        for var_name, var_def in meta.variables.items():
            if var_def.default is not None:
                defaults[var_name] = var_def.default
    return defaults


def _render_jinja2(content: str, context: dict[str, Any]) -> tuple[str, str | None]:
    """Render content using Jinja2.

    Returns:
        Tuple of (rendered content, error message or None)
    """
    try:
        from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError
    except ImportError:
        return "", "Jinja2 is not installed. Install with: pip install jinja2"

    try:
        env = Environment(undefined=StrictUndefined)
        template = env.from_string(content)
        rendered = template.render(**context)
        return rendered, None
    except TemplateSyntaxError as e:
        return "", f"Template syntax error: {e}"
    except UndefinedError as e:
        return "", f"Undefined variable: {e}"
    except (TypeError, ValueError) as e:
        return "", f"Render error: {e}"


def _render_none(content: str, context: dict[str, Any]) -> tuple[str, str | None]:
    """Return content as-is (no templating)."""
    return content, None


def render_prompt(
    prompt_id: str,
    context: dict[str, Any] | None = None,
    context_path: Path | None = None,
    search_path: Path | None = None,
) -> RenderResult:
    """Render a prompt with the given context.

    Args:
        prompt_id: The prompt identifier
        context: Dictionary of variables (takes precedence over context_path)
        context_path: Path to JSON/YAML context file
        search_path: Directory to search for prompt files

    Returns:
        RenderResult with rendered content or error
    """
    # Find the prompt files
    meta_path = find_meta_file_by_id(prompt_id, search_path)
    if not meta_path:
        return RenderResult(
            prompt_id=prompt_id,
            error=f"Prompt '{prompt_id}' not found",
        )

    prompt_path = find_prompt_file(meta_path)
    if not prompt_path or not prompt_path.exists():
        return RenderResult(
            prompt_id=prompt_id,
            error=f"Prompt file not found for '{prompt_id}'",
        )

    # Parse metadata
    meta, issues = parse_meta_file(meta_path)
    if not meta:
        error_msg = issues[0].message if issues else "Unknown error"
        return RenderResult(
            prompt_id=prompt_id,
            error=f"Cannot parse metadata: {error_msg}",
        )

    # Load prompt content
    try:
        content = prompt_path.read_text(encoding="utf-8")
    except OSError as e:
        return RenderResult(
            prompt_id=prompt_id,
            error=f"Cannot read prompt file: {e}",
        )

    # Build context from defaults, context file, and inline context
    final_context = _get_defaults(meta)

    if context_path:
        file_context, error = load_context(context_path)
        if error:
            return RenderResult(
                prompt_id=prompt_id,
                error=error,
            )
        final_context.update(file_context)

    if context:
        final_context.update(context)

    # Validate required variables
    validations = validate_variables(meta, final_context)
    missing = [v.name for v in validations if not v.valid]

    if missing:
        return RenderResult(
            prompt_id=prompt_id,
            missing_variables=missing,
            error=f"Missing required variables: {', '.join(missing)}",
        )

    # Determine template engine
    template_engine = "none"
    if meta.assumptions and meta.assumptions.template_engine:
        template_engine = meta.assumptions.template_engine.lower()

    # Render based on template engine
    if template_engine in ("jinja2", "jinja"):
        rendered, error = _render_jinja2(content, final_context)
    elif template_engine == "none" or not template_engine:
        rendered, error = _render_none(content, final_context)
    else:
        return RenderResult(
            prompt_id=prompt_id,
            template_engine=template_engine,
            error=f"Unsupported template engine: {template_engine}",
        )

    if error:
        return RenderResult(
            prompt_id=prompt_id,
            template_engine=template_engine,
            error=error,
        )

    return RenderResult(
        prompt_id=prompt_id,
        rendered_content=rendered,
        template_engine=template_engine,
        variables_used=list(final_context.keys()),
    )
