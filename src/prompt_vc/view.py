"""View functionality for prompt-vc."""

from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text

from .models import Annotation, PromptMeta
from .validation import find_prompt_file, parse_meta_file


def find_meta_file_by_id(prompt_id: str, search_path: Path | None = None) -> Path | None:
    """Find a meta file by prompt ID.

    Searches for .prompt.meta.yaml files and matches by ID field or filename.
    """
    base_path = search_path or Path.cwd()

    # First, try to find by filename pattern
    for meta_path in base_path.rglob("*.prompt.meta.yaml"):
        # Check if filename matches
        name = meta_path.name
        base = name[: -len(".prompt.meta.yaml")]
        if base == prompt_id:
            return meta_path

        # Also check the ID field in the file
        meta, _ = parse_meta_file(meta_path)
        if meta and meta.id == prompt_id:
            return meta_path

    return None


def find_meta_file_by_path(prompt_path: str) -> Path | None:
    """Find a meta file from a prompt or meta file path.

    Accepts:
    - Direct path to .prompt.meta.yaml
    - Path to .prompt.* file (derives meta path)
    - Path to directory containing prompt files
    """
    path = Path(prompt_path)

    if not path.exists():
        return None

    # If it's already a meta file
    if path.name.endswith(".prompt.meta.yaml"):
        return path

    # If it's a prompt file, derive meta path
    if ".prompt." in path.name and not path.name.endswith(".meta.yaml"):
        # Extract base name and construct meta path
        name = path.name
        # Find the .prompt. part
        idx = name.find(".prompt.")
        if idx > 0:
            base = name[:idx]
            meta_path = path.parent / f"{base}.prompt.meta.yaml"
            if meta_path.exists():
                return meta_path

    # If it's a directory, look for a single meta file
    if path.is_dir():
        meta_files = list(path.glob("*.prompt.meta.yaml"))
        if len(meta_files) == 1:
            return meta_files[0]

    return None


def load_prompt_and_meta(
    prompt_id_or_path: str,
) -> tuple[Path | None, Path | None, PromptMeta | None, list[str]]:
    """Load prompt file, meta file, and parsed metadata.

    Args:
        prompt_id_or_path: Either a prompt ID or path to prompt/meta file

    Returns:
        Tuple of (meta_path, prompt_path, parsed_meta, issues)
    """
    issues: list[str] = []

    # Try to find the meta file
    meta_path = find_meta_file_by_path(prompt_id_or_path)
    if meta_path is None:
        meta_path = find_meta_file_by_id(prompt_id_or_path)

    if meta_path is None:
        issues.append(f"Could not find prompt: {prompt_id_or_path}")
        return None, None, None, issues

    # Parse the meta file
    meta, parse_issues = parse_meta_file(meta_path)
    for issue in parse_issues:
        issues.append(issue.message)

    # Find the prompt file
    prompt_path = find_prompt_file(meta_path)
    if prompt_path is None:
        issues.append(f"No prompt file found for {meta_path}")

    return meta_path, prompt_path, meta, issues


def build_line_annotations(meta: PromptMeta, num_lines: int) -> dict[int, list[Annotation]]:
    """Build a mapping of line numbers to annotations.

    Args:
        meta: Parsed prompt metadata
        num_lines: Total number of lines in the prompt file

    Returns:
        Dict mapping line numbers (1-indexed) to list of annotations
    """
    line_map: dict[int, list[Annotation]] = {}

    for annotation in meta.annotations:
        line_hint = annotation.anchor.line_hint
        if line_hint is not None and 1 <= line_hint <= num_lines:
            if line_hint not in line_map:
                line_map[line_hint] = []
            line_map[line_hint].append(annotation)

    return line_map


def render_annotated_prompt(
    prompt_content: str,
    meta: PromptMeta,
    console: Console,
    show_all_lines: bool = True,
) -> None:
    """Render a prompt with inline annotations using rich.

    Args:
        prompt_content: Content of the prompt file
        meta: Parsed prompt metadata
        console: Rich console for output
        show_all_lines: If True, show all lines; if False, only annotated lines
    """
    lines = prompt_content.splitlines()
    line_annotations = build_line_annotations(meta, len(lines))

    # Colors for annotation display
    annotation_style = Style(color="yellow", italic=True)
    tag_style = Style(color="cyan")
    line_num_style = Style(color="bright_black")

    # Print header
    console.print(f"\n[bold]{meta.name or meta.id}[/bold]")
    if meta.intent:
        console.print(f"[dim]{meta.intent.strip()[:100]}...[/dim]\n")

    console.print("[dim]─[/dim]" * 60)

    # Print each line with annotations
    for line_num, line in enumerate(lines, start=1):
        annotations = line_annotations.get(line_num, [])

        if not show_all_lines and not annotations:
            continue

        # Format line number
        line_num_str = f"{line_num:4d}"

        if annotations:
            # Highlighted line with annotations
            text = Text()
            text.append(line_num_str, style=line_num_style)
            text.append(" │ ", style=line_num_style)
            text.append(line, style="bold")
            console.print(text)

            # Show each annotation
            for ann in annotations:
                # Annotation ID and preview
                ann_text = Text()
                ann_text.append("     ", style=line_num_style)
                ann_text.append(" ├─ ", style="yellow")
                ann_text.append(f"[{ann.id}]", style="yellow bold")
                console.print(ann_text)

                # Rationale (if present)
                if ann.rationale:
                    rationale_lines = ann.rationale.strip().split("\n")
                    for i, rat_line in enumerate(rationale_lines[:3]):
                        prefix = " │  " if i < len(rationale_lines[:3]) - 1 else " │  "
                        rat_text = Text()
                        rat_text.append("     ", style=line_num_style)
                        rat_text.append(prefix, style="yellow")
                        rat_text.append(rat_line.strip(), style=annotation_style)
                        console.print(rat_text)

                # Tags
                if ann.tags:
                    tags_text = Text()
                    tags_text.append("     ", style=line_num_style)
                    tags_text.append(" │  ", style="yellow")
                    tags_text.append("tags: ", style="dim")
                    tags_text.append(", ".join(ann.tags), style=tag_style)
                    console.print(tags_text)

                # Source
                if ann.source:
                    source_text = Text()
                    source_text.append("     ", style=line_num_style)
                    source_text.append(" │  ", style="yellow")
                    source_text.append("source: ", style="dim")
                    source_text.append(ann.source, style="blue underline")
                    console.print(source_text)

                # Author and date
                if ann.author or ann.date:
                    info_text = Text()
                    info_text.append("     ", style=line_num_style)
                    info_text.append(" └─ ", style="yellow")
                    if ann.author:
                        info_text.append(ann.author, style="dim")
                    if ann.date:
                        info_text.append(f" ({ann.date})", style="dim")
                    console.print(info_text)

            console.print()  # Blank line after annotated section
        else:
            # Regular line
            text = Text()
            text.append(line_num_str, style=line_num_style)
            text.append(" │ ", style=line_num_style)
            text.append(line)
            console.print(text)

    console.print("[dim]─[/dim]" * 60)

    # Summary
    total_annotations = len(meta.annotations)
    if total_annotations > 0:
        console.print(f"\n[dim]{total_annotations} annotation(s) in this prompt[/dim]")


def render_meta_summary(meta: PromptMeta, console: Console) -> None:
    """Render a summary of the prompt metadata.

    Args:
        meta: Parsed prompt metadata
        console: Rich console for output
    """
    # Basic info
    console.print(f"\n[bold]Prompt:[/bold] {meta.name or meta.id}")
    console.print(f"[dim]ID:[/dim] {meta.id}")
    console.print(f"[dim]Schema Version:[/dim] {meta.schema_version}")

    if meta.created:
        console.print(f"[dim]Created:[/dim] {meta.created}")

    if meta.authors:
        console.print(f"[dim]Authors:[/dim] {', '.join(meta.authors)}")

    # Intent
    if meta.intent:
        console.print("\n[bold]Intent:[/bold]")
        for line in meta.intent.strip().split("\n")[:5]:
            console.print(f"  {line}")

    # Assumptions
    if meta.assumptions:
        console.print("\n[bold]Assumptions:[/bold]")
        if meta.assumptions.model:
            console.print(f"  Model: {meta.assumptions.model}")
        if meta.assumptions.template_engine:
            console.print(f"  Template: {meta.assumptions.template_engine}")
        if meta.assumptions.max_tokens:
            console.print(f"  Max Tokens: {meta.assumptions.max_tokens}")

    # Variables
    if meta.variables:
        console.print(f"\n[bold]Variables:[/bold] ({len(meta.variables)})")
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Required")
        table.add_column("Description")

        for name, var in list(meta.variables.items())[:10]:
            required = "[green]yes[/green]" if var.required else "[dim]no[/dim]"
            desc = (var.description or "")[:40]
            table.add_row(name, var.type, required, desc)

        console.print(table)

        if len(meta.variables) > 10:
            console.print(f"  [dim]... and {len(meta.variables) - 10} more[/dim]")

    # Annotations summary
    if meta.annotations:
        console.print(f"\n[bold]Annotations:[/bold] ({len(meta.annotations)})")
        for ann in meta.annotations[:5]:
            tags = f" [{', '.join(ann.tags)}]" if ann.tags else ""
            console.print(f"  • {ann.id}: {ann.anchor.preview[:50]}...{tags}")

        if len(meta.annotations) > 5:
            console.print(f"  [dim]... and {len(meta.annotations) - 5} more[/dim]")

    # Changelog
    if meta.changelog:
        console.print("\n[bold]Recent Changes:[/bold]")
        for entry in meta.changelog[:3]:
            console.print(f"  v{entry.version} ({entry.date}): {entry.summary}")

    console.print()


def render_full_info(
    meta: PromptMeta,
    console: Console,
    prompt_path: Path | None = None,
    deployed_to: list[str] | None = None,
    domain: str | None = None,
    status: str | None = None,
) -> None:
    """Render complete detailed information about a prompt.

    Args:
        meta: Parsed prompt metadata
        console: Rich console for output
        prompt_path: Path to the prompt file (for file info)
        deployed_to: Deployment targets from manifest
        domain: Domain from manifest
        status: Status from manifest
    """
    # Header
    console.print()
    console.print(
        Panel(
            f"[bold]{meta.name or meta.id}[/bold]\n[dim]{meta.id}[/dim]",
            title="Prompt Info",
            border_style="blue",
        )
    )

    # Basic metadata
    console.print("\n[bold cyan]Metadata[/bold cyan]")
    console.print(f"  Schema Version: {meta.schema_version}")
    if meta.created:
        console.print(f"  Created: {meta.created}")
    if meta.authors:
        console.print(f"  Authors: {', '.join(meta.authors)}")
    if prompt_path:
        console.print(f"  File: {prompt_path}")

    # Deployment info (from manifest)
    if domain or status or deployed_to:
        console.print("\n[bold cyan]Deployment[/bold cyan]")
        if domain:
            console.print(f"  Domain: {domain}")
        if status:
            status_style = {
                "production": "green",
                "staging": "yellow",
                "experimental": "dim",
                "deprecated": "red",
            }.get(status, "")
            if status_style:
                console.print(f"  Status: [{status_style}]{status}[/{status_style}]")
            else:
                console.print(f"  Status: {status}")
        if deployed_to:
            console.print(f"  Deployed To: {', '.join(deployed_to)}")

    # Intent
    if meta.intent:
        console.print("\n[bold cyan]Intent[/bold cyan]")
        for line in meta.intent.strip().split("\n"):
            console.print(f"  {line}")

    # Assumptions
    if meta.assumptions:
        console.print("\n[bold cyan]Assumptions[/bold cyan]")
        assumptions = meta.assumptions
        if assumptions.model:
            console.print(f"  Model: {assumptions.model}")
        if assumptions.template_engine:
            console.print(f"  Template Engine: {assumptions.template_engine}")
        if assumptions.min_context_window:
            console.print(f"  Min Context Window: {assumptions.min_context_window:,}")
        if assumptions.max_tokens:
            console.print(f"  Max Tokens: {assumptions.max_tokens:,}")
        if assumptions.expected_latency_ms:
            console.print(f"  Expected Latency: {assumptions.expected_latency_ms}ms")

        # Upstream dependencies
        if assumptions.upstream_dependencies:
            console.print("\n  [bold]Upstream Dependencies:[/bold]")
            for dep in assumptions.upstream_dependencies:
                provides = f" (provides: {', '.join(dep.provides)})" if dep.provides else ""
                console.print(f"    • {dep.service}{provides}")

        # Downstream consumers
        if assumptions.downstream_consumers:
            console.print("\n  [bold]Downstream Consumers:[/bold]")
            for dep in assumptions.downstream_consumers:
                expects = f" (expects: {dep.expects})" if dep.expects else ""
                console.print(f"    • {dep.service}{expects}")

    # Variables - full table
    if meta.variables:
        console.print(f"\n[bold cyan]Variables[/bold cyan] ({len(meta.variables)})")
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Required")
        table.add_column("Default")
        table.add_column("Description")

        for name, var in meta.variables.items():
            required = "[green]yes[/green]" if var.required else "[dim]no[/dim]"
            default = str(var.default) if var.default is not None else "-"
            if len(default) > 20:
                default = default[:17] + "..."
            desc = (var.description or "-")[:50]
            table.add_row(name, var.type, required, default, desc)

        console.print(table)

    # Evaluation
    if meta.evaluation:
        console.print("\n[bold cyan]Evaluation[/bold cyan]")
        if meta.evaluation.test_cases_ref:
            console.print(f"  Test Cases: {meta.evaluation.test_cases_ref}")
        if meta.evaluation.metrics:
            console.print("  [bold]Metrics:[/bold]")
            for metric in meta.evaluation.metrics:
                console.print(f"    • {metric.name}: target {metric.target}")
                console.print(f"      [dim]measured by: {metric.measured_by}[/dim]")

    # Annotations - full details
    if meta.annotations:
        console.print(f"\n[bold cyan]Annotations[/bold cyan] ({len(meta.annotations)})")
        for ann in meta.annotations:
            console.print(f"\n  [yellow][{escape(ann.id)}][/yellow]")
            console.print(f'    Preview: "{escape(ann.anchor.preview)}"')
            if ann.anchor.line_hint:
                console.print(f"    Line: {ann.anchor.line_hint}")
            if ann.rationale:
                console.print(f"    Rationale: {escape(ann.rationale.strip().split(chr(10))[0])}")
            if ann.tags:
                console.print(f"    Tags: [cyan]{escape(', '.join(ann.tags))}[/cyan]")
            if ann.source:
                console.print(f"    Source: [blue underline]{escape(ann.source)}[/blue underline]")
            if ann.author:
                date_str = f" ({ann.date})" if ann.date else ""
                console.print(f"    Author: {escape(ann.author)}{date_str}")

    # Changelog - full history
    if meta.changelog:
        console.print("\n[bold cyan]Changelog[/bold cyan]")
        for entry in meta.changelog:
            linked = f" [{', '.join(entry.linked_annotations)}]" if entry.linked_annotations else ""
            version_info = f"v{escape(entry.version)}"
            console.print(f"  [bold]{version_info}[/bold] ({entry.date}) - {escape(entry.author)}")
            console.print(f"    {escape(entry.summary)}{linked}")

    console.print()
