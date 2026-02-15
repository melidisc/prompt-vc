"""Fix annotations command for prompt-vc."""

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from ruamel.yaml import YAML

from .hashing import extract_preview, find_similar_lines, find_text_in_file, hash_content
from .models import Annotation, PromptMeta


@dataclass
class OrphanedAnnotation:
    """An annotation whose hash no longer matches any content."""

    annotation: Annotation
    suggestions: list[tuple[int, str, float]]  # (line_number, text, similarity)


def detect_orphaned_annotations(
    meta: PromptMeta,
    prompt_path: Path,
) -> list[OrphanedAnnotation]:
    """Detect annotations whose hashes don't match any content.

    Args:
        meta: Parsed prompt metadata
        prompt_path: Path to the prompt file

    Returns:
        List of OrphanedAnnotation objects with suggestions
    """
    orphaned: list[OrphanedAnnotation] = []

    for annotation in meta.annotations:
        target_hash = annotation.anchor.hash
        found_line, _ = find_text_in_file(str(prompt_path), target_hash)

        if found_line is None:
            # Hash doesn't match - find similar lines
            suggestions = find_similar_lines(
                str(prompt_path),
                annotation.anchor.preview,
                threshold=0.4,  # Lower threshold for more suggestions
            )
            orphaned.append(OrphanedAnnotation(
                annotation=annotation,
                suggestions=suggestions[:5],  # Top 5 suggestions
            ))

    return orphaned


def update_annotation_in_meta(
    meta_path: Path,
    annotation_id: str,
    new_line: int,
    new_text: str,
) -> None:
    """Update an annotation's anchor in the meta file.

    Args:
        meta_path: Path to the meta file
        annotation_id: ID of annotation to update
        new_line: New line number
        new_text: New text content (for hash and preview)
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=2, offset=2)

    with open(meta_path, encoding="utf-8") as f:
        raw_data = yaml.load(f)

    if raw_data is None or "annotations" not in raw_data:
        return

    for ann in raw_data["annotations"]:
        if ann.get("id") == annotation_id:
            ann["anchor"]["hash"] = hash_content(new_text)
            ann["anchor"]["preview"] = extract_preview(new_text)
            ann["anchor"]["line_hint"] = new_line
            break

    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.dump(raw_data, f)


def remove_annotation_from_meta(
    meta_path: Path,
    annotation_id: str,
) -> None:
    """Remove an annotation from the meta file.

    Args:
        meta_path: Path to the meta file
        annotation_id: ID of annotation to remove
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=2, offset=2)

    with open(meta_path, encoding="utf-8") as f:
        raw_data = yaml.load(f)

    if raw_data is None or "annotations" not in raw_data:
        return

    raw_data["annotations"] = [
        ann for ann in raw_data["annotations"]
        if ann.get("id") != annotation_id
    ]

    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.dump(raw_data, f)


def display_orphaned_annotation(
    orphan: OrphanedAnnotation,
    console: Console,
    index: int,
) -> None:
    """Display an orphaned annotation with suggestions.

    Args:
        orphan: The orphaned annotation
        console: Rich console
        index: Index number for display
    """
    ann = orphan.annotation
    console.print(f"\n[yellow bold]({index}) {escape(ann.id)}[/yellow bold]")
    console.print(f"  Preview: \"{escape(ann.anchor.preview)}\"")
    if ann.anchor.line_hint:
        console.print(f"  Original line: {ann.anchor.line_hint}")
    if ann.rationale:
        console.print(f"  Rationale: {escape(ann.rationale.strip().split(chr(10))[0][:60])}...")

    if orphan.suggestions:
        console.print("\n  [cyan]Possible matches:[/cyan]")
        for i, (line_num, text, score) in enumerate(orphan.suggestions, 1):
            pct = int(score * 100)
            console.print(f"    [{i}] Line {line_num} ({pct}% match): \"{escape(text[:60])}...\"")
    else:
        console.print("  [dim]No similar lines found[/dim]")


def interactive_fix_annotations(
    prompt_id_or_path: str,
    console: Console,
    auto_remove: bool = False,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Interactive workflow to fix orphaned annotations.

    Args:
        prompt_id_or_path: Prompt ID or path
        console: Rich console
        auto_remove: Automatically remove orphaned annotations
        dry_run: Show what would be done without making changes

    Returns:
        Tuple of (success, message)
    """
    from .view import load_prompt_and_meta

    # Load the prompt and meta
    meta_path, prompt_path, parsed_meta, issues = load_prompt_and_meta(prompt_id_or_path)

    if issues and parsed_meta is None:
        return False, f"Error loading prompt: {'; '.join(issues)}"

    if parsed_meta is None:
        return False, f"Could not parse metadata for: {prompt_id_or_path}"

    if prompt_path is None:
        return False, "No prompt file found"

    if not parsed_meta.annotations:
        return True, "No annotations to check"

    # Detect orphaned annotations
    orphaned = detect_orphaned_annotations(parsed_meta, prompt_path)

    if not orphaned:
        return True, f"All {len(parsed_meta.annotations)} annotation(s) are valid"

    console.print(f"\n[yellow]Found {len(orphaned)} orphaned annotation(s)[/yellow]\n")

    if dry_run:
        for i, orphan in enumerate(orphaned, 1):
            display_orphaned_annotation(orphan, console, i)
        return True, f"Dry run: {len(orphaned)} annotation(s) would need fixing"

    fixed = 0
    removed = 0

    for i, orphan in enumerate(orphaned, 1):
        display_orphaned_annotation(orphan, console, i)

        if auto_remove:
            console.print(f"  [red]Auto-removing {orphan.annotation.id}[/red]")
            remove_annotation_from_meta(meta_path, orphan.annotation.id)
            removed += 1
            continue

        # Interactive prompt
        console.print("\n  Actions: [r]e-anchor to suggestion, [k]eep as-is, [d]elete, [s]kip")

        try:
            action = console.input("  [bold]Choose action:[/bold] ").strip().lower()
        except KeyboardInterrupt:
            return False, "Cancelled"

        if action == "d":
            remove_annotation_from_meta(meta_path, orphan.annotation.id)
            console.print(f"  [red]Removed {orphan.annotation.id}[/red]")
            removed += 1

        elif action.startswith("r") and orphan.suggestions:
            # Re-anchor to a suggestion
            if len(action) > 1 and action[1:].isdigit():
                choice = int(action[1:]) - 1
            else:
                try:
                    choice_input = console.input("  [bold]Enter suggestion number (1-5):[/bold] ")
                    choice = int(choice_input.strip()) - 1
                except (ValueError, KeyboardInterrupt):
                    console.print("  [dim]Skipped[/dim]")
                    continue

            if 0 <= choice < len(orphan.suggestions):
                line_num, text, _ = orphan.suggestions[choice]
                update_annotation_in_meta(meta_path, orphan.annotation.id, line_num, text)
                console.print(f"  [green]Re-anchored to line {line_num}[/green]")
                fixed += 1
            else:
                console.print("  [dim]Invalid choice, skipped[/dim]")

        elif action == "k":
            console.print("  [dim]Kept as-is[/dim]")

        else:
            console.print("  [dim]Skipped[/dim]")

    summary_parts = []
    if fixed > 0:
        summary_parts.append(f"{fixed} re-anchored")
    if removed > 0:
        summary_parts.append(f"{removed} removed")

    if summary_parts:
        return True, f"Fixed annotations: {', '.join(summary_parts)}"
    return True, "No changes made"
