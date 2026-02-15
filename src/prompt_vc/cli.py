"""Command-line interface for prompt-vc."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from .models import PromptMeta

console = Console()


def show_hash_warnings(
    prompt_path: Path,
    meta: PromptMeta,
    auto_fix: bool = False,
    meta_path: Path | None = None,
) -> PromptMeta | None:
    """Display warnings about stale annotation hashes.

    Args:
        prompt_path: Path to the prompt file
        meta: Parsed prompt metadata
        auto_fix: If True, auto-update line_hint values
        meta_path: Path to meta file (required if auto_fix is True)

    Returns:
        Updated PromptMeta if auto_fix was applied, otherwise None
    """
    from .validation import auto_update_line_hints, get_hash_warnings

    if not meta.annotations:
        return None

    warnings = get_hash_warnings(meta, prompt_path)
    updated_meta = None

    if auto_fix and meta_path:
        updated = auto_update_line_hints(meta_path, prompt_path, meta)
        if updated:
            console.print(f"[green]✓[/green] Auto-updated line_hint for: {', '.join(updated)}")
            # Re-check for remaining warnings with fresh meta
            from .validation import parse_meta_file
            updated_meta, _ = parse_meta_file(meta_path)
            if updated_meta:
                warnings = get_hash_warnings(updated_meta, prompt_path)

    for warning in warnings:
        console.print(f"[yellow]⚠[/yellow] {warning}")

    return updated_meta


@click.group()
@click.version_option()
def main() -> None:
    """Version control metadata for LLM prompts."""
    pass


@main.command()
@click.option("--with-manifest", is_flag=True, help="Create a manifest file")
def init(with_manifest: bool) -> None:
    """Initialize a prompt-vc repository."""
    import os

    os.makedirs("prompts", exist_ok=True)
    console.print("[green]✓[/green] Created prompts/ directory")

    if with_manifest:
        manifest_content = '''schema_version: "1.0"
organization: my-org
repository: prompt-library

defaults:
  model: claude-sonnet-4-20250514
  template_engine: jinja2
  review_required: true

domains: {}

governance:
  production_requirements:
    must_have_intent: true
    must_have_evaluation: false
    min_annotations: 0
    required_tags: []
'''
        with open("prompts/prompts.manifest.yaml", "w") as f:
            f.write(manifest_content)
        console.print("[green]✓[/green] Created prompts/prompts.manifest.yaml")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  prompt-vc new my-first-prompt")


@main.command()
@click.argument("prompt_id")
@click.option("--domain", "-d", default=None, help="Domain subdirectory")
@click.option("--format", "-f", "fmt", default="md", help="Prompt file format")
def new(prompt_id: str, domain: str | None, fmt: str) -> None:
    """Create a new prompt with metadata file."""
    import os

    base_dir = "prompts"
    if domain:
        base_dir = os.path.join(base_dir, domain)

    os.makedirs(base_dir, exist_ok=True)

    prompt_file = os.path.join(base_dir, f"{prompt_id}.prompt.{fmt}")
    meta_file = os.path.join(base_dir, f"{prompt_id}.prompt.meta.yaml")

    # Create prompt file
    with open(prompt_file, "w") as f:
        f.write(f"# {prompt_id}\n\nYour prompt content here.\n")

    # Create meta file
    meta_content = f'''schema_version: "1.0"

id: {prompt_id}
name: {prompt_id.replace("-", " ").title()}
created: "{__import__('datetime').date.today().isoformat()}"
authors: []

intent: |
  Describe what this prompt should accomplish.

assumptions:
  model: claude-sonnet-4-20250514
  template_engine: none

variables: {{}}

evaluation:
  metrics: []

annotations: []

changelog:
  - version: "1.0"
    date: "{__import__('datetime').date.today().isoformat()}"
    author: ""
    summary: Initial version
    linked_annotations: []
'''
    with open(meta_file, "w") as f:
        f.write(meta_content)

    console.print(f"[green]✓[/green] Created {prompt_file}")
    console.print(f"[green]✓[/green] Created {meta_file}")


@main.command()
@click.argument("path", required=False)
@click.option("--strict", is_flag=True, help="Fail on warnings")
def validate(path: str | None, strict: bool) -> None:
    """Validate prompts and metadata."""
    from pathlib import Path

    from .validation import validate_all

    search_path = Path(path) if path else None
    results = validate_all(search_path)

    if not results:
        console.print("[yellow]⚠[/yellow] No .prompt.meta.yaml files found")
        return

    total_errors = 0
    total_warnings = 0

    for result in results:
        total_errors += result.error_count
        total_warnings += result.warning_count

        # Show file header
        if result.issues:
            rel_path = result.meta_file
            try:
                rel_path = str(Path(result.meta_file).relative_to(Path.cwd()))
            except ValueError:
                pass

            if result.valid:
                console.print(f"\n[yellow]{rel_path}[/yellow]")
            else:
                console.print(f"\n[red]{rel_path}[/red]")

            # Show issues
            for issue in result.issues:
                if issue.level == "error":
                    prefix = "[red]✗[/red]"
                else:
                    prefix = "[yellow]⚠[/yellow]"

                line_info = f" (line {issue.line})" if issue.line else ""
                console.print(f"  {prefix} {issue.message}{line_info}")
        else:
            rel_path = result.meta_file
            try:
                rel_path = str(Path(result.meta_file).relative_to(Path.cwd()))
            except ValueError:
                pass
            console.print(f"[green]✓[/green] {rel_path}")

    # Summary
    console.print()
    if total_errors == 0 and total_warnings == 0:
        console.print(f"[green]✓ All {len(results)} prompt(s) valid[/green]")
    else:
        parts = []
        if total_errors > 0:
            parts.append(f"[red]{total_errors} error(s)[/red]")
        if total_warnings > 0:
            parts.append(f"[yellow]{total_warnings} warning(s)[/yellow]")
        console.print(f"Found {', '.join(parts)} in {len(results)} prompt(s)")

    # Exit with error code if validation failed
    if total_errors > 0 or (strict and total_warnings > 0):
        raise SystemExit(1)


@main.command("list")
@click.option("--domain", "-d", default=None, help="Filter by domain")
@click.option("--status", "-s", default=None, help="Filter by status")
@click.option("--owner", "-o", default=None, help="Filter by owner")
@click.option("--path", "-p", default=None, help="Path to search")
def list_prompts(
    domain: str | None, status: str | None, owner: str | None, path: str | None
) -> None:
    """List all prompts in the repository."""
    from pathlib import Path

    from .listing import list_prompts as do_list_prompts

    search_path = Path(path) if path else None
    prompts, used_manifest = do_list_prompts(
        search_path,
        domain_filter=domain,
        status_filter=status,
        owner_filter=owner,
    )

    if not prompts:
        console.print("[yellow]⚠[/yellow] No prompts found")
        if status and not used_manifest:
            console.print("[dim]Note: --status filter requires a manifest file[/dim]")
        return

    title_suffix = " (from manifest)" if used_manifest else " (from directory scan)"
    table = Table(title="Prompts" + title_suffix)
    table.add_column("Domain", style="cyan")
    table.add_column("ID", style="green")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Deployed To")

    for prompt in prompts:
        deployed = ", ".join(prompt.deployed_to) if prompt.deployed_to else "-"
        status_style = {
            "production": "green",
            "staging": "yellow",
            "experimental": "dim",
            "deprecated": "red",
        }.get(prompt.status, "")
        if status_style:
            status_text = f"[{status_style}]{prompt.status}[/{status_style}]"
        else:
            status_text = prompt.status

        table.add_row(
            prompt.domain or "-",
            prompt.id,
            prompt.name or "-",
            status_text,
            deployed,
        )

    console.print(table)


@main.command()
@click.argument("prompt_id")
@click.option("--annotated", "-a", is_flag=True, help="Show annotations inline")
@click.option("--meta", "-m", is_flag=True, help="Show metadata summary")
@click.option("--auto-fix", is_flag=True, help="Auto-update stale line_hint values")
def view(prompt_id: str, annotated: bool, meta: bool, auto_fix: bool) -> None:
    """View a prompt with optional annotation overlay."""
    from .view import (
        load_prompt_and_meta,
        render_annotated_prompt,
        render_meta_summary,
    )

    meta_path, prompt_path, parsed_meta, issues = load_prompt_and_meta(prompt_id)

    if issues and parsed_meta is None:
        for issue in issues:
            console.print(f"[red]✗[/red] {issue}")
        raise SystemExit(1)

    if parsed_meta is None:
        console.print(f"[red]✗[/red] Could not parse metadata for: {prompt_id}")
        raise SystemExit(1)

    # Show hash warnings (and auto-fix if requested)
    if prompt_path:
        updated_meta = show_hash_warnings(
            prompt_path, parsed_meta, auto_fix=auto_fix, meta_path=meta_path
        )
        if updated_meta:
            parsed_meta = updated_meta

    # Show metadata summary if requested
    if meta:
        render_meta_summary(parsed_meta, console)
        if not annotated:
            return

    # Show annotated view if requested or if --meta wasn't specified
    if annotated or not meta:
        if prompt_path is None:
            console.print("[red]✗[/red] No prompt file found")
            raise SystemExit(1)

        try:
            with open(prompt_path, encoding="utf-8") as f:
                prompt_content = f.read()
        except OSError as e:
            console.print(f"[red]✗[/red] Cannot read prompt file: {e}")
            raise SystemExit(1)

        if annotated:
            render_annotated_prompt(prompt_content, parsed_meta, console)
        else:
            # Just show the raw prompt content with line numbers
            lines = prompt_content.splitlines()
            console.print(f"\n[bold]{parsed_meta.name or parsed_meta.id}[/bold]\n")
            for i, line in enumerate(lines, 1):
                console.print(f"[dim]{i:4d}[/dim] │ {line}")


@main.command()
@click.argument("prompt_id")
@click.option("--line", "-l", type=int, help="Line number to annotate")
@click.option("--rationale", "-r", help="Why this text exists")
@click.option("--source", "-s", help="URL or path to evidence")
@click.option("--tags", "-t", help="Comma-separated tags")
@click.option("--author", "-a", help="Author email")
def annotate(
    prompt_id: str,
    line: int | None,
    rationale: str | None,
    source: str | None,
    tags: str | None,
    author: str | None,
) -> None:
    """Add an annotation to a prompt."""
    from .annotate import interactive_annotate

    success, message = interactive_annotate(
        prompt_id,
        console,
        line=line,
        rationale=rationale,
        source=source,
        tags=tags,
        author=author,
    )

    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[red]✗[/red] {message}")
        raise SystemExit(1)


@main.command("fix-annotations")
@click.argument("prompt_id")
@click.option("--auto-remove", is_flag=True, help="Automatically remove orphaned annotations")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
def fix_annotations(prompt_id: str, auto_remove: bool, dry_run: bool) -> None:
    """Fix orphaned annotations in a prompt."""
    from .fix_annotations import interactive_fix_annotations

    success, message = interactive_fix_annotations(
        prompt_id,
        console,
        auto_remove=auto_remove,
        dry_run=dry_run,
    )

    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[red]✗[/red] {message}")
        raise SystemExit(1)


@main.command()
@click.option("--status", "-s", default="production", help="Status to audit")
@click.option("--all", "-a", "audit_all", is_flag=True, help="Audit all prompts")
def audit(status: str, audit_all: bool) -> None:
    """Check governance compliance across all prompts."""
    from .audit import run_audit

    status_filter = None if audit_all else status
    report = run_audit(status_filter=status_filter)

    if not report.manifest_path:
        console.print(
            "[red]✗[/red] No manifest found. Audit requires a prompts.manifest.yaml file."
        )
        raise SystemExit(1)

    if report.error:
        console.print(f"[red]✗[/red] Failed to parse manifest: {report.error}")
        raise SystemExit(1)

    if not report.requirements:
        console.print("[yellow]⚠[/yellow] No governance requirements defined in manifest.")
        raise SystemExit(0)

    # Show requirements being checked
    console.print("\n[bold]Governance Requirements:[/bold]")
    req = report.requirements
    console.print(f"  • must_have_intent: {req.must_have_intent}")
    console.print(f"  • must_have_evaluation: {req.must_have_evaluation}")
    console.print(f"  • min_annotations: {req.min_annotations}")
    if req.required_tags:
        console.print(f"  • required_tags: {', '.join(req.required_tags)}")
    console.print()

    if not report.results:
        filter_msg = f"with status '{status}'" if not audit_all else ""
        console.print(f"[yellow]⚠[/yellow] No prompts found {filter_msg}.")
        raise SystemExit(0)

    # Build results table
    table = Table(title=f"Audit Results ({status_filter or 'all'} prompts)")
    table.add_column("Prompt", style="cyan")
    table.add_column("Domain")
    table.add_column("Status")
    table.add_column("Compliant", justify="center")
    table.add_column("Issues")

    for result in report.results:
        if result.skipped:
            compliant_str = "[yellow]SKIPPED[/yellow]"
            issues_str = result.skip_reason or "Unknown"
        elif result.compliant:
            compliant_str = "[green]✓[/green]"
            issues_str = ""
        else:
            compliant_str = "[red]✗[/red]"
            issues_str = "; ".join(i.message for i in result.issues)

        table.add_row(
            result.prompt_id,
            result.domain or "-",
            result.status,
            compliant_str,
            issues_str,
        )

    console.print(table)

    # Summary
    console.print()
    if report.non_compliant_count == 0 and report.skipped_count == 0:
        console.print(f"[green]✓[/green] All {report.compliant_count} prompts are compliant.")
    else:
        console.print("[bold]Summary:[/bold]")
        console.print(f"  Compliant: {report.compliant_count}")
        console.print(f"  Non-compliant: {report.non_compliant_count}")
        if report.skipped_count > 0:
            console.print(f"  Skipped: {report.skipped_count}")

    if report.non_compliant_count > 0:
        raise SystemExit(1)


@main.command()
@click.argument("prompt_id")
@click.option("--auto-fix", is_flag=True, help="Auto-update stale line_hint values")
def info(prompt_id: str, auto_fix: bool) -> None:
    """Show detailed information about a prompt."""
    from .listing import find_manifest, parse_manifest
    from .view import load_prompt_and_meta, render_full_info

    meta_path, prompt_path, parsed_meta, issues = load_prompt_and_meta(prompt_id)

    if issues and parsed_meta is None:
        for issue in issues:
            console.print(f"[red]✗[/red] {issue}")
        raise SystemExit(1)

    if parsed_meta is None:
        console.print(f"[red]✗[/red] Could not parse metadata for: {prompt_id}")
        raise SystemExit(1)

    # Show hash warnings (and auto-fix if requested)
    if prompt_path:
        updated_meta = show_hash_warnings(
            prompt_path, parsed_meta, auto_fix=auto_fix, meta_path=meta_path
        )
        if updated_meta:
            parsed_meta = updated_meta

    # Try to get deployment info from manifest
    deployed_to = None
    domain = None
    status = None

    manifest_path = find_manifest()
    if manifest_path:
        manifest, _ = parse_manifest(manifest_path)
        if manifest:
            # Find this prompt in the manifest
            for domain_name, domain_obj in manifest.domains.items():
                for prompt_ref in domain_obj.prompts:
                    if prompt_ref.id == parsed_meta.id:
                        domain = domain_name
                        status = prompt_ref.status
                        deployed_to = prompt_ref.deployed_to
                        break
                if domain:
                    break

    render_full_info(
        parsed_meta,
        console,
        prompt_path=prompt_path,
        deployed_to=deployed_to,
        domain=domain,
        status=status,
    )


@main.command()
@click.argument("prompt_id")
@click.option("--old", "-o", "old_ref", default="HEAD~1", help="Old git ref (default: HEAD~1)")
@click.option("--new", "-n", "new_ref", default="HEAD", help="New git ref (default: HEAD)")
def diff(prompt_id: str, old_ref: str, new_ref: str) -> None:
    """Compare prompt versions between git refs."""
    from rich.markup import escape

    from .diff import diff_prompt

    result = diff_prompt(prompt_id, old_ref=old_ref, new_ref=new_ref)

    if result.error:
        console.print(f"[red]✗[/red] {result.error}")
        raise SystemExit(1)

    # Header
    console.print(f"\n[bold]Diff: {result.prompt_id}[/bold]")
    console.print(f"  {result.old_ref} → {result.new_ref}")
    console.print(f"  File: {result.prompt_path}")
    console.print()

    # Show line diffs with annotation context
    if result.line_diffs:
        console.print("[bold]Content Changes:[/bold]")
        for line_diff in result.line_diffs:
            if line_diff.change_type == "added":
                prefix = "[green]+[/green]"
                line_style = "green"
            elif line_diff.change_type == "removed":
                prefix = "[red]-[/red]"
                line_style = "red"
            else:
                prefix = " "
                line_style = "dim"

            line_num = f"{line_diff.line_number:4d}" if line_diff.line_number else "    "
            content = escape(line_diff.content)
            console.print(f"[dim]{line_num}[/dim] {prefix} [{line_style}]{content}[/{line_style}]")

            # Show annotations for this line
            for ann in line_diff.annotations:
                ann_preview = escape(ann.anchor.preview[:60])
                console.print(f"       [cyan]📝 {ann.id}[/cyan]: {ann_preview}...")
        console.print()
    else:
        console.print("[dim]No content changes found.[/dim]")
        console.print()

    # Show annotation changes
    if result.annotation_changes:
        console.print("[bold]Annotation Changes:[/bold]")
        for change in result.annotation_changes:
            if change.change_type == "added":
                icon = "[green]+[/green]"
                style = "green"
            elif change.change_type == "removed":
                icon = "[red]-[/red]"
                style = "red"
            else:
                icon = "[yellow]~[/yellow]"
                style = "yellow"

            console.print(f"  {icon} [{style}]{change.annotation_id}[/{style}]: {change.details}")
        console.print()
    else:
        console.print("[dim]No annotation changes found.[/dim]")
        console.print()

    # Summary
    added_lines = sum(1 for d in result.line_diffs if d.change_type == "added")
    removed_lines = sum(1 for d in result.line_diffs if d.change_type == "removed")
    added_anns = sum(1 for c in result.annotation_changes if c.change_type == "added")
    removed_anns = sum(1 for c in result.annotation_changes if c.change_type == "removed")
    modified_anns = sum(1 for c in result.annotation_changes if c.change_type == "modified")

    console.print("[bold]Summary:[/bold]")
    console.print(f"  Lines: [green]+{added_lines}[/green] / [red]-{removed_lines}[/red]")
    console.print(
        f"  Annotations: [green]+{added_anns}[/green] / "
        f"[red]-{removed_anns}[/red] / [yellow]~{modified_anns}[/yellow]"
    )


@main.command()
@click.argument("prompt_id")
@click.option(
    "--context", "-c", "context_path",
    type=click.Path(exists=True),
    help="Path to JSON/YAML context file",
)
@click.option("--var", "-v", "variables", multiple=True, help="Variable in key=value format")
@click.option("--output", "-o", "output_path", type=click.Path(), help="Output file")
def render(
    prompt_id: str,
    context_path: str | None,
    variables: tuple[str, ...],
    output_path: str | None,
) -> None:
    """Render a prompt with variables."""
    import json
    from pathlib import Path

    from .render import render_prompt

    # Parse inline variables
    inline_context: dict = {}
    for var in variables:
        if "=" in var:
            key, value = var.split("=", 1)
            # Try to parse as JSON for complex values
            try:
                inline_context[key] = json.loads(value)
            except json.JSONDecodeError:
                inline_context[key] = value
        else:
            console.print(f"[red]✗[/red] Invalid variable format: {var} (expected key=value)")
            raise SystemExit(1)

    result = render_prompt(
        prompt_id,
        context=inline_context if inline_context else None,
        context_path=Path(context_path) if context_path else None,
    )

    if result.error:
        console.print(f"[red]✗[/red] {result.error}")
        if result.missing_variables:
            console.print(f"[dim]Missing: {', '.join(result.missing_variables)}[/dim]")
        raise SystemExit(1)

    # Output the rendered content
    if output_path:
        try:
            Path(output_path).write_text(result.rendered_content, encoding="utf-8")
            console.print(f"[green]✓[/green] Rendered to {output_path}")
            console.print(f"[dim]Template engine: {result.template_engine}[/dim]")
            if result.variables_used:
                console.print(f"[dim]Variables: {', '.join(result.variables_used)}[/dim]")
        except OSError as e:
            console.print(f"[red]✗[/red] Cannot write output file: {e}")
            raise SystemExit(1)
    else:
        # Output to stdout
        console.print(result.rendered_content)


@main.command()
@click.option("--output", "-o", "output_path", type=click.Path(), help="Output file (DOT)")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["dot", "png", "svg", "pdf"]),
    default="dot",
    help="Output format",
)
@click.option("--no-domains", is_flag=True, help="Don't include domain groupings")
@click.option("--title", "-t", default="Prompt Dependencies", help="Graph title")
def graph(
    output_path: str | None, output_format: str, no_domains: bool, title: str
) -> None:
    """Generate a dependency graph of prompts."""
    from pathlib import Path

    from .graph import build_graph, generate_dot, render_graph

    result = build_graph(include_domains=not no_domains)

    if result.error:
        console.print(f"[red]✗[/red] {result.error}")
        raise SystemExit(1)

    if not result.nodes:
        console.print("[yellow]![/yellow] No prompts found in manifest")
        return

    # Generate output
    if output_format == "dot":
        dot_output = generate_dot(result, title=title)
        if output_path:
            try:
                Path(output_path).write_text(dot_output, encoding="utf-8")
                console.print(f"[green]✓[/green] DOT file written to {output_path}")
            except OSError as e:
                console.print(f"[red]✗[/red] Cannot write file: {e}")
                raise SystemExit(1)
        else:
            console.print(dot_output)
    else:
        # Render to image format
        if not output_path:
            output_path = f"prompt-graph.{output_format}"

        success, message = render_graph(
            result,
            Path(output_path),
            output_format=output_format,
            title=title,
        )

        if success:
            console.print(f"[green]✓[/green] {message}")
            console.print(f"[dim]Nodes: {len(result.nodes)}, Edges: {len(result.edges)}[/dim]")
        else:
            console.print(f"[red]✗[/red] {message}")
            raise SystemExit(1)


@main.command()
@click.argument("prompt_id")
@click.option("--output", "-o", "output_path", type=click.Path(), help="Output file")
@click.option("--show-deps", is_flag=True, help="Show dependency information")
def compose(prompt_id: str, output_path: str | None, show_deps: bool) -> None:
    """Compose a prompt by resolving all includes."""
    from pathlib import Path

    from .compose import compose_prompt

    result = compose_prompt(prompt_id)

    if result.error:
        console.print(f"[red]✗[/red] {result.error}")
        raise SystemExit(1)

    if show_deps:
        console.print(f"\n[bold]Composition: {result.prompt_id}[/bold]")
        if result.dependencies:
            console.print("\n[bold]Dependencies:[/bold]")
            for dep in result.dependencies:
                console.print(f"  {dep.from_id} → {dep.to_id} ({dep.include_type})")
        if result.resolved_prompts:
            console.print(f"\n[dim]Resolution order: {' → '.join(result.resolved_prompts)}[/dim]")
        console.print()

    if output_path:
        try:
            Path(output_path).write_text(result.composed_content, encoding="utf-8")
            console.print(f"[green]✓[/green] Composed prompt written to {output_path}")
            if result.dependencies:
                console.print(f"[dim]Resolved {len(result.dependencies)} include(s)[/dim]")
        except OSError as e:
            console.print(f"[red]✗[/red] Cannot write output file: {e}")
            raise SystemExit(1)
    else:
        console.print(result.composed_content)


if __name__ == "__main__":
    main()
