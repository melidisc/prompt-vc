"""Validation logic for prompt-vc."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .hashing import find_text_in_file, hash_content
from .models import PromptMeta


@dataclass
class ValidationIssue:
    """A single validation issue."""

    level: str  # "error" or "warning"
    file: str
    message: str
    line: int | None = None
    annotation_id: str | None = None


@dataclass
class ValidationResult:
    """Result of validating a prompt."""

    meta_file: str
    prompt_file: str | None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return not any(issue.level == "error" for issue in self.issues)

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return sum(1 for issue in self.issues if issue.level == "error")

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for issue in self.issues if issue.level == "warning")


def find_prompt_file(meta_path: Path) -> Path | None:
    """Find the corresponding prompt file for a meta file.

    Given a .prompt.meta.yaml file, looks for matching .prompt.* file.
    """
    # Extract the base name without .prompt.meta.yaml
    name = meta_path.name
    if not name.endswith(".prompt.meta.yaml"):
        return None

    base = name[:-len(".prompt.meta.yaml")]
    parent = meta_path.parent

    # Look for matching prompt files
    extensions = [".md", ".txt", ".yaml", ".jinja", ".jinja2", ".hbs"]
    for ext in extensions:
        prompt_path = parent / f"{base}.prompt{ext}"
        if prompt_path.exists():
            return prompt_path

    return None


def parse_meta_file(meta_path: Path) -> tuple[PromptMeta | None, list[ValidationIssue]]:
    """Parse and validate a meta file against the Pydantic model.

    Returns:
        Tuple of (parsed model or None, list of issues)
    """
    issues: list[ValidationIssue] = []

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        issues.append(ValidationIssue(
            level="error",
            file=str(meta_path),
            message=f"Invalid YAML: {e}"
        ))
        return None, issues
    except OSError as e:
        issues.append(ValidationIssue(
            level="error",
            file=str(meta_path),
            message=f"Cannot read file: {e}"
        ))
        return None, issues

    if raw_data is None:
        issues.append(ValidationIssue(
            level="error",
            file=str(meta_path),
            message="Empty meta file"
        ))
        return None, issues

    try:
        meta = PromptMeta.model_validate(raw_data)
        return meta, issues
    except ValidationError as e:
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            issues.append(ValidationIssue(
                level="error",
                file=str(meta_path),
                message=f"Schema error at '{loc}': {error['msg']}"
            ))
        return None, issues


def extract_variables_from_prompt(prompt_content: str) -> set[str]:
    """Extract variable references from a prompt file.

    Supports:
    - Jinja2: {{ var }}, {{ var.field }}
    - Handlebars: {{var}}, {{var.field}}
    """
    variables: set[str] = set()
    loop_variables: set[str] = set()

    # First, find all loop variables ({% for x in collection %})
    for_pattern = r"\{%\s*for\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    for match in re.finditer(for_pattern, prompt_content):
        loop_var = match.group(1)
        collection_var = match.group(2)
        loop_variables.add(loop_var)
        variables.add(collection_var)

    # Match {{ var }} or {{var}} patterns
    # Captures the root variable name (before any dot)
    pattern = r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)"

    # Jinja2 control flow keywords to skip
    jinja_keywords = {
        "if", "else", "endif", "for", "endfor", "include", "block",
        "endblock", "extends", "macro", "endmacro", "set", "raw", "endraw",
        "loop", "true", "false", "none", "True", "False", "None"
    }

    for match in re.finditer(pattern, prompt_content):
        var_name = match.group(1)
        # Skip Jinja2 control flow keywords and loop variables
        if var_name not in jinja_keywords and var_name not in loop_variables:
            variables.add(var_name)

    return variables


def verify_annotation_hashes(
    meta: PromptMeta,
    prompt_path: Path,
    meta_path: Path
) -> list[ValidationIssue]:
    """Verify that annotation hashes match content in the prompt file.

    Returns list of issues for orphaned or mismatched annotations.
    """
    issues: list[ValidationIssue] = []

    if not meta.annotations:
        return issues

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_content = f.read()
            prompt_lines = prompt_content.splitlines()
    except OSError as e:
        issues.append(ValidationIssue(
            level="error",
            file=str(meta_path),
            message=f"Cannot read prompt file for hash verification: {e}"
        ))
        return issues

    for annotation in meta.annotations:
        anchor = annotation.anchor
        target_hash = anchor.hash
        preview = anchor.preview
        line_hint = anchor.line_hint

        # Try to find the text by hash
        found_line, found_text = find_text_in_file(str(prompt_path), target_hash)

        if found_line is not None:
            # Hash matches, check if line_hint needs updating
            if line_hint is not None and found_line != line_hint:
                issues.append(ValidationIssue(
                    level="warning",
                    file=str(meta_path),
                    message=f"Annotation '{annotation.id}' line_hint is {line_hint} but content found at line {found_line}",
                    line=line_hint,
                    annotation_id=annotation.id
                ))
        else:
            # Hash doesn't match - orphaned annotation
            # Try to find similar content by preview text
            suggestion = ""
            if preview and line_hint is not None and 1 <= line_hint <= len(prompt_lines):
                # Check if preview text exists at or near the hinted line
                actual_line = prompt_lines[line_hint - 1]
                if preview in actual_line or preview[:30] in actual_line:
                    suggestion = f" Content appears modified at line {line_hint}."

            issues.append(ValidationIssue(
                level="error",
                file=str(meta_path),
                message=f"Orphaned annotation '{annotation.id}': hash does not match any content in prompt file.{suggestion}",
                line=line_hint,
                annotation_id=annotation.id
            ))

    return issues


def check_variable_references(
    meta: PromptMeta,
    prompt_path: Path,
    meta_path: Path
) -> list[ValidationIssue]:
    """Check that variables used in the prompt are defined in metadata.

    Returns list of issues for undefined or unused variables.
    """
    issues: list[ValidationIssue] = []

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_content = f.read()
    except OSError:
        # Already reported elsewhere
        return issues

    used_vars = extract_variables_from_prompt(prompt_content)
    defined_vars = set(meta.variables.keys()) if meta.variables else set()

    # Check for undefined variables (used but not defined)
    undefined = used_vars - defined_vars
    for var in sorted(undefined):
        issues.append(ValidationIssue(
            level="error",
            file=str(meta_path),
            message=f"Variable '{var}' used in prompt but not defined in meta"
        ))

    # Check for unused variables (defined but not used) - warning only
    unused = defined_vars - used_vars
    for var in sorted(unused):
        issues.append(ValidationIssue(
            level="warning",
            file=str(meta_path),
            message=f"Variable '{var}' defined in meta but not used in prompt"
        ))

    return issues


def validate_prompt(meta_path: Path) -> ValidationResult:
    """Validate a single prompt and its metadata.

    Args:
        meta_path: Path to the .prompt.meta.yaml file

    Returns:
        ValidationResult with all issues found
    """
    prompt_path = find_prompt_file(meta_path)
    result = ValidationResult(
        meta_file=str(meta_path),
        prompt_file=str(prompt_path) if prompt_path else None
    )

    # Parse and validate the meta file
    meta, parse_issues = parse_meta_file(meta_path)
    result.issues.extend(parse_issues)

    if meta is None:
        # Cannot continue validation without parsed meta
        return result

    # Check if prompt file exists
    if prompt_path is None or not prompt_path.exists():
        result.issues.append(ValidationIssue(
            level="error",
            file=str(meta_path),
            message=f"No corresponding prompt file found for meta file"
        ))
        return result

    # Verify annotation hashes
    hash_issues = verify_annotation_hashes(meta, prompt_path, meta_path)
    result.issues.extend(hash_issues)

    # Check variable references
    var_issues = check_variable_references(meta, prompt_path, meta_path)
    result.issues.extend(var_issues)

    return result


def find_meta_files(path: Path | None = None) -> list[Path]:
    """Find all .prompt.meta.yaml files in a directory tree.

    Args:
        path: Directory to search, or None for current directory

    Returns:
        List of paths to meta files
    """
    search_path = path or Path.cwd()

    if search_path.is_file():
        # Single file specified
        if search_path.name.endswith(".prompt.meta.yaml"):
            return [search_path]
        return []

    # Recursively find all meta files
    return list(search_path.rglob("*.prompt.meta.yaml"))


def validate_all(path: Path | None = None) -> list[ValidationResult]:
    """Validate all prompts in a directory tree.

    Args:
        path: Directory to search, or None for current directory

    Returns:
        List of ValidationResult for each prompt
    """
    meta_files = find_meta_files(path)
    results = []

    for meta_path in sorted(meta_files):
        result = validate_prompt(meta_path)
        results.append(result)

    return results


@dataclass
class HashCheckResult:
    """Result of checking annotation hashes."""

    annotation_id: str
    status: str  # "valid", "moved", "orphaned"
    original_line: int | None
    found_line: int | None = None
    message: str = ""


def check_annotation_hashes(
    meta: PromptMeta,
    prompt_path: Path,
) -> list[HashCheckResult]:
    """Check all annotation hashes and report their status.

    Args:
        meta: Parsed prompt metadata
        prompt_path: Path to the prompt file

    Returns:
        List of HashCheckResult for each annotation
    """
    from .hashing import find_text_in_file

    results: list[HashCheckResult] = []

    if not meta.annotations:
        return results

    for annotation in meta.annotations:
        target_hash = annotation.anchor.hash
        line_hint = annotation.anchor.line_hint

        # Try to find the text by hash
        found_line, _ = find_text_in_file(str(prompt_path), target_hash)

        if found_line is not None:
            if line_hint is not None and found_line != line_hint:
                # Content moved to different line
                results.append(HashCheckResult(
                    annotation_id=annotation.id,
                    status="moved",
                    original_line=line_hint,
                    found_line=found_line,
                    message=f"Content moved from line {line_hint} to line {found_line}",
                ))
            else:
                # Valid - hash matches and line is correct
                results.append(HashCheckResult(
                    annotation_id=annotation.id,
                    status="valid",
                    original_line=line_hint,
                    found_line=found_line,
                ))
        else:
            # Orphaned - hash doesn't match any content
            results.append(HashCheckResult(
                annotation_id=annotation.id,
                status="orphaned",
                original_line=line_hint,
                message=f"Hash does not match any content in file",
            ))

    return results


def auto_update_line_hints(
    meta_path: Path,
    prompt_path: Path,
    meta: PromptMeta,
) -> list[str]:
    """Auto-update line_hint values for annotations where content has moved.

    Args:
        meta_path: Path to the meta file
        prompt_path: Path to the prompt file
        meta: Parsed prompt metadata

    Returns:
        List of annotation IDs that were updated
    """
    from ruamel.yaml import YAML

    results = check_annotation_hashes(meta, prompt_path)
    moved = [r for r in results if r.status == "moved"]

    if not moved:
        return []

    # Load and update the meta file
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=2, offset=2)

    with open(meta_path, "r", encoding="utf-8") as f:
        raw_data = yaml.load(f)

    if raw_data is None or "annotations" not in raw_data:
        return []

    updated_ids = []
    for result in moved:
        for ann in raw_data["annotations"]:
            if ann.get("id") == result.annotation_id:
                ann["anchor"]["line_hint"] = result.found_line
                updated_ids.append(result.annotation_id)
                break

    if updated_ids:
        with open(meta_path, "w", encoding="utf-8") as f:
            yaml.dump(raw_data, f)

    return updated_ids


def get_hash_warnings(
    meta: PromptMeta,
    prompt_path: Path,
) -> list[str]:
    """Get warning messages for stale annotation hashes.

    Args:
        meta: Parsed prompt metadata
        prompt_path: Path to the prompt file

    Returns:
        List of warning messages
    """
    results = check_annotation_hashes(meta, prompt_path)
    warnings = []

    for result in results:
        if result.status == "moved":
            warnings.append(
                f"Annotation '{result.annotation_id}' line_hint is stale: "
                f"content moved from line {result.original_line} to {result.found_line}"
            )
        elif result.status == "orphaned":
            warnings.append(
                f"Annotation '{result.annotation_id}' is orphaned: {result.message}"
            )

    return warnings
