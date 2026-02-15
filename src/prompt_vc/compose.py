"""Compose prompts with include support."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .validation import find_prompt_file
from .view import find_meta_file_by_id


@dataclass
class PromptDependency:
    """A dependency between prompts."""

    from_id: str
    to_id: str
    include_type: str = "include"  # include, extends, import


@dataclass
class ComposeResult:
    """Result of composing a prompt."""

    prompt_id: str
    composed_content: str = ""
    dependencies: list[PromptDependency] = field(default_factory=list)
    resolved_prompts: list[str] = field(default_factory=list)
    error: str | None = None


def _find_includes(content: str) -> list[str]:
    """Find all include directives in content.

    Supports:
    - {% include 'prompt-id' %}
    - {% include "prompt-id" %}
    - {# @include prompt-id #}

    Returns:
        List of prompt IDs to include
    """
    includes: list[str] = []

    # Match Jinja2 include: {% include 'prompt-id' %} or {% include "prompt-id" %}
    jinja_pattern = r"\{%\s*include\s+['\"]([^'\"]+)['\"]\s*%\}"
    for match in re.finditer(jinja_pattern, content):
        includes.append(match.group(1))

    # Match comment-style include: {# @include prompt-id #}
    comment_pattern = r"\{#\s*@include\s+(\S+)\s*#\}"
    for match in re.finditer(comment_pattern, content):
        includes.append(match.group(1))

    return includes


def _load_prompt_content(prompt_id: str, search_path: Path | None) -> tuple[str, str | None]:
    """Load content for a prompt by ID.

    Returns:
        Tuple of (content, error message or None)
    """
    meta_path = find_meta_file_by_id(prompt_id, search_path)
    if not meta_path:
        return "", f"Prompt '{prompt_id}' not found"

    prompt_path = find_prompt_file(meta_path)
    if not prompt_path or not prompt_path.exists():
        return "", f"Prompt file not found for '{prompt_id}'"

    try:
        content = prompt_path.read_text(encoding="utf-8")
        return content, None
    except OSError as e:
        return "", f"Cannot read prompt file '{prompt_id}': {e}"


def _resolve_includes(
    prompt_id: str,
    content: str,
    search_path: Path | None,
    visited: set[str],
    all_dependencies: list[PromptDependency],
    resolved_order: list[str],
) -> tuple[str, str | None]:
    """Recursively resolve includes in content.

    Args:
        prompt_id: Current prompt ID
        content: Content to process
        search_path: Directory to search for prompts
        visited: Set of already visited prompt IDs (for cycle detection)
        all_dependencies: List to collect all dependencies
        resolved_order: List to track resolution order

    Returns:
        Tuple of (resolved content, error message or None)
    """
    # Find all includes
    includes = _find_includes(content)

    if not includes:
        if prompt_id not in resolved_order:
            resolved_order.append(prompt_id)
        return content, None

    # Check for cycles
    for inc_id in includes:
        if inc_id in visited:
            cycle_path = " -> ".join(list(visited) + [inc_id])
            return "", f"Circular dependency detected: {cycle_path}"

    resolved_content = content

    for inc_id in includes:
        # Track dependency
        all_dependencies.append(PromptDependency(
            from_id=prompt_id,
            to_id=inc_id,
            include_type="include",
        ))

        # Load included prompt
        inc_content, error = _load_prompt_content(inc_id, search_path)
        if error:
            return "", error

        # Recursively resolve includes in the included content
        new_visited = visited | {prompt_id}
        resolved_inc, error = _resolve_includes(
            inc_id,
            inc_content,
            search_path,
            new_visited,
            all_dependencies,
            resolved_order,
        )
        if error:
            return "", error

        # Replace include directive with resolved content
        # Handle both quote styles
        patterns = [
            rf"\{{% include '{re.escape(inc_id)}' %\}}",
            rf'\{{% include "{re.escape(inc_id)}" %\}}',
            rf"\{{# @include {re.escape(inc_id)} #\}}",
        ]

        for pattern in patterns:
            resolved_content = re.sub(pattern, resolved_inc.strip(), resolved_content)

    if prompt_id not in resolved_order:
        resolved_order.append(prompt_id)

    return resolved_content, None


def compose_prompt(
    prompt_id: str,
    search_path: Path | None = None,
) -> ComposeResult:
    """Compose a prompt by resolving all includes.

    Args:
        prompt_id: The prompt identifier
        search_path: Directory to search for prompt files

    Returns:
        ComposeResult with composed content and dependency info
    """
    # Load the main prompt
    content, error = _load_prompt_content(prompt_id, search_path)
    if error:
        return ComposeResult(prompt_id=prompt_id, error=error)

    # Track dependencies and resolution order
    dependencies: list[PromptDependency] = []
    resolved_order: list[str] = []

    # Resolve includes
    composed, error = _resolve_includes(
        prompt_id,
        content,
        search_path,
        visited=set(),
        all_dependencies=dependencies,
        resolved_order=resolved_order,
    )

    if error:
        return ComposeResult(
            prompt_id=prompt_id,
            dependencies=dependencies,
            error=error,
        )

    return ComposeResult(
        prompt_id=prompt_id,
        composed_content=composed,
        dependencies=dependencies,
        resolved_prompts=resolved_order,
    )


def get_prompt_dependencies(
    prompt_id: str,
    search_path: Path | None = None,
    recursive: bool = True,
) -> tuple[list[PromptDependency], str | None]:
    """Get dependencies for a prompt without composing.

    Args:
        prompt_id: The prompt identifier
        search_path: Directory to search for prompt files
        recursive: Whether to recursively find dependencies

    Returns:
        Tuple of (list of dependencies, error message or None)
    """
    content, error = _load_prompt_content(prompt_id, search_path)
    if error:
        return [], error

    if not recursive:
        # Just find direct includes
        includes = _find_includes(content)
        return [
            PromptDependency(from_id=prompt_id, to_id=inc_id)
            for inc_id in includes
        ], None

    # Use compose to get all dependencies
    result = compose_prompt(prompt_id, search_path)
    return result.dependencies, result.error
