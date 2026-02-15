"""Annotation management for prompt-vc."""

import datetime
import random
import string
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from .hashing import extract_preview, hash_content
from .models import Anchor, Annotation, PromptMeta


def generate_annotation_id(existing_ids: set[str] | None = None) -> str:
    """Generate a unique annotation ID.

    Format: ann_<random_suffix>

    Args:
        existing_ids: Set of existing IDs to avoid collision

    Returns:
        Unique annotation ID
    """
    existing = existing_ids or set()

    while True:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        new_id = f"ann_{suffix}"
        if new_id not in existing:
            return new_id


def create_annotation(
    line_text: str,
    line_number: int,
    rationale: str | None = None,
    source: str | None = None,
    tags: list[str] | None = None,
    author: str | None = None,
    existing_ids: set[str] | None = None,
) -> Annotation:
    """Create a new annotation for a line of text.

    Args:
        line_text: The text content to annotate
        line_number: Line number in the prompt file
        rationale: Why this text exists
        source: URL or path to evidence
        tags: List of tags
        author: Author email
        existing_ids: Existing annotation IDs to avoid collision

    Returns:
        New Annotation object
    """
    content_hash = hash_content(line_text)
    preview = extract_preview(line_text)

    anchor = Anchor(
        hash=content_hash,
        preview=preview,
        line_hint=line_number,
    )

    annotation = Annotation(
        id=generate_annotation_id(existing_ids),
        anchor=anchor,
        author=author,
        date=datetime.date.today(),
        source=source,
        rationale=rationale,
        tags=tags or [],
    )

    return annotation


def save_annotation_to_meta(
    meta_path: Path,
    annotation: Annotation,
) -> None:
    """Append an annotation to a meta file.

    Args:
        meta_path: Path to the .prompt.meta.yaml file
        annotation: Annotation to add
    """
    import yaml as pyyaml

    # Read existing file
    with open(meta_path, encoding="utf-8") as f:
        raw_data = pyyaml.safe_load(f)

    if raw_data is None:
        raw_data = {}

    # Ensure annotations list exists
    if "annotations" not in raw_data:
        raw_data["annotations"] = []

    # Convert annotation to dict
    ann_dict = {
        "id": annotation.id,
        "anchor": {
            "hash": annotation.anchor.hash,
            "preview": annotation.anchor.preview,
            "line_hint": annotation.anchor.line_hint,
        },
    }

    if annotation.author:
        ann_dict["author"] = annotation.author
    if annotation.date:
        ann_dict["date"] = annotation.date.isoformat()
    if annotation.source:
        ann_dict["source"] = annotation.source
    if annotation.rationale:
        ann_dict["rationale"] = annotation.rationale
    if annotation.tags:
        ann_dict["tags"] = list(annotation.tags)

    raw_data["annotations"].append(ann_dict)

    # Custom dumper for proper indentation
    class IndentDumper(pyyaml.SafeDumper):
        """Custom dumper with proper indentation."""

        def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
            return super().increase_indent(flow, False)

    with open(meta_path, "w", encoding="utf-8") as f:
        pyyaml.dump(
            raw_data, f, Dumper=IndentDumper,
            default_flow_style=False, sort_keys=False, allow_unicode=True
        )


def get_existing_annotation_ids(meta: PromptMeta) -> set[str]:
    """Get all existing annotation IDs from a meta object.

    Args:
        meta: Parsed prompt metadata

    Returns:
        Set of existing annotation IDs
    """
    return {ann.id for ann in meta.annotations}


def display_prompt_for_selection(
    prompt_content: str,
    console: Console,
    highlight_line: int | None = None,
) -> None:
    """Display prompt content with line numbers for selection.

    Args:
        prompt_content: Content of the prompt file
        console: Rich console for output
        highlight_line: Line number to highlight (1-indexed)
    """
    lines = prompt_content.splitlines()

    console.print("\n[bold]Select a line to annotate:[/bold]\n")

    for i, line in enumerate(lines, start=1):
        escaped_line = escape(line)
        if highlight_line and i == highlight_line:
            console.print(f"[yellow bold]→ {i:4d}[/yellow bold] │ [yellow]{escaped_line}[/yellow]")
        else:
            console.print(f"[dim]{i:4d}[/dim] │ {escaped_line}")

    console.print()


def interactive_annotate(
    prompt_id_or_path: str,
    console: Console,
    line: int | None = None,
    rationale: str | None = None,
    source: str | None = None,
    tags: str | None = None,
    author: str | None = None,
) -> tuple[bool, str]:
    """Interactive annotation workflow.

    Args:
        prompt_id_or_path: Prompt ID or path to prompt/meta file
        console: Rich console for output
        line: Pre-selected line number
        rationale: Pre-provided rationale
        source: Pre-provided source
        tags: Pre-provided tags (comma-separated)
        author: Pre-provided author

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

    # Read prompt content
    try:
        with open(prompt_path, encoding="utf-8") as f:
            prompt_content = f.read()
    except OSError as e:
        return False, f"Cannot read prompt file: {e}"

    lines = prompt_content.splitlines()

    # Get line number
    if line is None:
        display_prompt_for_selection(prompt_content, console)
        try:
            line_input = console.input("[bold]Enter line number to annotate:[/bold] ")
            line = int(line_input.strip())
        except (ValueError, KeyboardInterrupt):
            return False, "Cancelled"

    if line < 1 or line > len(lines):
        return False, f"Invalid line number: {line} (file has {len(lines)} lines)"

    line_text = lines[line - 1]

    # Show selected line
    console.print(f"\n[bold]Selected line {line}:[/bold]")
    console.print(f"  [yellow]{escape(line_text)}[/yellow]\n")

    # Get rationale
    if rationale is None:
        console.print("[dim]Why does this text exist? (press Enter to skip)[/dim]")
        try:
            rationale = console.input("[bold]Rationale:[/bold] ").strip() or None
        except KeyboardInterrupt:
            return False, "Cancelled"

    # Get source
    if source is None:
        console.print("[dim]URL or path to evidence (press Enter to skip)[/dim]")
        try:
            source = console.input("[bold]Source:[/bold] ").strip() or None
        except KeyboardInterrupt:
            return False, "Cancelled"

    # Get tags
    tag_list: list[str] = []
    if tags is None:
        console.print("[dim]Comma-separated tags (press Enter to skip)[/dim]")
        try:
            tags_input = console.input("[bold]Tags:[/bold] ").strip()
            if tags_input:
                tag_list = [t.strip() for t in tags_input.split(",") if t.strip()]
        except KeyboardInterrupt:
            return False, "Cancelled"
    else:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Get author
    if author is None:
        console.print("[dim]Author email (press Enter to skip)[/dim]")
        try:
            author = console.input("[bold]Author:[/bold] ").strip() or None
        except KeyboardInterrupt:
            return False, "Cancelled"

    # Create annotation
    existing_ids = get_existing_annotation_ids(parsed_meta)
    annotation = create_annotation(
        line_text=line_text,
        line_number=line,
        rationale=rationale,
        source=source,
        tags=tag_list,
        author=author,
        existing_ids=existing_ids,
    )

    # Save annotation
    try:
        save_annotation_to_meta(meta_path, annotation)
    except OSError as e:
        return False, f"Failed to save annotation: {e}"

    return True, f"Created annotation {annotation.id} for line {line}"
