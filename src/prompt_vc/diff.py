"""Diff functionality for comparing prompt versions across git refs."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import Annotation, PromptMeta


@dataclass
class AnnotationChange:
    """Change to an annotation between versions."""

    annotation_id: str
    change_type: str  # "added", "removed", "modified"
    old_annotation: Annotation | None = None
    new_annotation: Annotation | None = None
    details: str = ""


@dataclass
class LineDiff:
    """A single line in the diff."""

    line_number: int | None  # None for context lines in unified diff
    content: str
    change_type: str  # "added", "removed", "context"
    annotations: list[Annotation] = field(default_factory=list)


@dataclass
class PromptDiff:
    """Complete diff between two versions of a prompt."""

    prompt_id: str
    old_ref: str
    new_ref: str
    prompt_path: str
    meta_path: str
    line_diffs: list[LineDiff] = field(default_factory=list)
    annotation_changes: list[AnnotationChange] = field(default_factory=list)
    old_meta: PromptMeta | None = None
    new_meta: PromptMeta | None = None
    error: str | None = None


def _run_git_command(args: list[str], cwd: Path | None = None) -> tuple[str, str | None]:
    """Run a git command and return stdout or error message."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
        )
        if result.returncode != 0:
            return "", result.stderr.strip()
        return result.stdout, None
    except subprocess.TimeoutExpired:
        return "", "Git command timed out"
    except FileNotFoundError:
        return "", "Git not found"


def _get_file_at_ref(
    file_path: str, ref: str, cwd: Path | None = None
) -> tuple[str | None, str | None]:
    """Get file contents at a specific git ref."""
    output, error = _run_git_command(["show", f"{ref}:{file_path}"], cwd)
    if error:
        if "does not exist" in error or "fatal: path" in error:
            return None, None  # File doesn't exist at this ref
        return None, error
    return output, None


def _parse_meta_from_content(content: str) -> PromptMeta | None:
    """Parse PromptMeta from YAML content string."""
    try:
        raw_data = yaml.safe_load(content)
        if raw_data is None:
            return None
        return PromptMeta.model_validate(raw_data)
    except (yaml.YAMLError, ValueError, TypeError):
        return None


def _compute_annotation_changes(
    old_meta: PromptMeta | None,
    new_meta: PromptMeta | None,
) -> list[AnnotationChange]:
    """Compute changes between annotation sets."""
    changes: list[AnnotationChange] = []

    old_annotations = {a.id: a for a in (old_meta.annotations if old_meta else [])}
    new_annotations = {a.id: a for a in (new_meta.annotations if new_meta else [])}

    # Find removed annotations
    for ann_id, old_ann in old_annotations.items():
        if ann_id not in new_annotations:
            preview = old_ann.anchor.preview
            preview_text = f"{preview[:50]}..." if len(preview) > 50 else preview
            changes.append(
                AnnotationChange(
                    annotation_id=ann_id,
                    change_type="removed",
                    old_annotation=old_ann,
                    details=f"Removed annotation: {preview_text}",
                )
            )

    # Find added annotations
    for ann_id, new_ann in new_annotations.items():
        if ann_id not in old_annotations:
            preview = new_ann.anchor.preview
            preview_text = f"{preview[:50]}..." if len(preview) > 50 else preview
            changes.append(
                AnnotationChange(
                    annotation_id=ann_id,
                    change_type="added",
                    new_annotation=new_ann,
                    details=f"Added annotation: {preview_text}",
                )
            )

    # Find modified annotations
    for ann_id in old_annotations.keys() & new_annotations.keys():
        old_ann = old_annotations[ann_id]
        new_ann = new_annotations[ann_id]

        # Check for changes
        changes_found = []
        if old_ann.anchor.hash != new_ann.anchor.hash:
            changes_found.append("hash changed")
        if old_ann.anchor.line_hint != new_ann.anchor.line_hint:
            old_line = old_ann.anchor.line_hint
            new_line = new_ann.anchor.line_hint
            changes_found.append(f"line moved {old_line} → {new_line}")
        if old_ann.rationale != new_ann.rationale:
            changes_found.append("rationale updated")
        if set(old_ann.tags) != set(new_ann.tags):
            changes_found.append("tags changed")

        if changes_found:
            changes.append(
                AnnotationChange(
                    annotation_id=ann_id,
                    change_type="modified",
                    old_annotation=old_ann,
                    new_annotation=new_ann,
                    details=", ".join(changes_found),
                )
            )

    return changes


def _parse_unified_diff(diff_output: str, new_annotations: list[Annotation]) -> list[LineDiff]:
    """Parse unified diff output into LineDiff objects."""
    line_diffs: list[LineDiff] = []

    # Build annotation lookup by line
    annotations_by_line: dict[int, list[Annotation]] = {}
    for ann in new_annotations:
        if ann.anchor.line_hint:
            annotations_by_line.setdefault(ann.anchor.line_hint, []).append(ann)

    lines = diff_output.splitlines()
    new_line_num = 0
    in_hunk = False

    for line in lines:
        if line.startswith("@@"):
            # Parse hunk header: @@ -old_start[,old_count] +new_start[,new_count] @@
            # Count may be omitted when it's 1
            in_hunk = True
            try:
                parts = line.split()
                new_range = parts[2]  # +new_start or +new_start,new_count
                # Handle both "+10" and "+10,5" formats
                new_start_str = new_range.lstrip("+").split(",")[0]
                new_start = int(new_start_str)
                new_line_num = new_start - 1  # Will be incremented for first line
            except (IndexError, ValueError):
                new_line_num = 0
            continue

        if not in_hunk:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            new_line_num += 1
            line_diffs.append(
                LineDiff(
                    line_number=new_line_num,
                    content=line[1:],  # Remove the + prefix
                    change_type="added",
                    annotations=annotations_by_line.get(new_line_num, []),
                )
            )
        elif line.startswith("-") and not line.startswith("---"):
            line_diffs.append(
                LineDiff(
                    line_number=None,
                    content=line[1:],  # Remove the - prefix
                    change_type="removed",
                    annotations=[],
                )
            )
        elif line.startswith(" "):
            new_line_num += 1
            line_diffs.append(
                LineDiff(
                    line_number=new_line_num,
                    content=line[1:],  # Remove the space prefix
                    change_type="context",
                    annotations=annotations_by_line.get(new_line_num, []),
                )
            )

    return line_diffs


def _find_prompt_files(
    prompt_id: str, search_path: Path | None = None
) -> tuple[Path | None, Path | None]:
    """Find meta and prompt files by ID.

    Returns:
        Tuple of (meta_path, prompt_path)
    """
    from .validation import find_prompt_file
    from .view import find_meta_file_by_id

    meta_path = find_meta_file_by_id(prompt_id, search_path)
    if meta_path is None:
        return None, None

    prompt_path = find_prompt_file(meta_path)
    return meta_path, prompt_path


def diff_prompt(
    prompt_id: str,
    old_ref: str = "HEAD~1",
    new_ref: str = "HEAD",
    search_path: Path | None = None,
) -> PromptDiff:
    """Compare a prompt between two git refs.

    Args:
        prompt_id: The prompt identifier
        old_ref: Git ref for old version (default: HEAD~1)
        new_ref: Git ref for new version (default: HEAD)
        search_path: Directory to search for prompt files

    Returns:
        PromptDiff with comparison results
    """
    cwd = search_path or Path.cwd()

    # Find the prompt files
    meta_path, prompt_path = _find_prompt_files(prompt_id, search_path)

    if not meta_path:
        return PromptDiff(
            prompt_id=prompt_id,
            old_ref=old_ref,
            new_ref=new_ref,
            prompt_path="",
            meta_path="",
            error=f"Prompt '{prompt_id}' not found",
        )

    # Get relative paths for git
    try:
        rel_meta_path = str(meta_path.relative_to(cwd))
        rel_prompt_path = str(prompt_path.relative_to(cwd)) if prompt_path else ""
    except ValueError:
        rel_meta_path = str(meta_path)
        rel_prompt_path = str(prompt_path) if prompt_path else ""

    # Get meta files at each ref
    old_meta_content, old_meta_error = _get_file_at_ref(rel_meta_path, old_ref, cwd)
    new_meta_content, new_meta_error = _get_file_at_ref(rel_meta_path, new_ref, cwd)

    if old_meta_error and new_meta_error:
        return PromptDiff(
            prompt_id=prompt_id,
            old_ref=old_ref,
            new_ref=new_ref,
            prompt_path=rel_prompt_path,
            meta_path=rel_meta_path,
            error=f"Could not read meta file: {old_meta_error}",
        )

    old_meta = _parse_meta_from_content(old_meta_content) if old_meta_content else None
    new_meta = _parse_meta_from_content(new_meta_content) if new_meta_content else None

    # Get prompt diff
    line_diffs: list[LineDiff] = []
    if rel_prompt_path:
        diff_output, diff_error = _run_git_command(
            ["diff", f"{old_ref}..{new_ref}", "--", rel_prompt_path],
            cwd,
        )
        if diff_output and not diff_error:
            new_annotations = new_meta.annotations if new_meta else []
            line_diffs = _parse_unified_diff(diff_output, new_annotations)

    # Compute annotation changes
    annotation_changes = _compute_annotation_changes(old_meta, new_meta)

    return PromptDiff(
        prompt_id=prompt_id,
        old_ref=old_ref,
        new_ref=new_ref,
        prompt_path=rel_prompt_path,
        meta_path=rel_meta_path,
        line_diffs=line_diffs,
        annotation_changes=annotation_changes,
        old_meta=old_meta,
        new_meta=new_meta,
    )
