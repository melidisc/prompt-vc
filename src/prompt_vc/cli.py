"""Command-line interface for prompt-vc."""

import click
from rich.console import Console
from rich.table import Table

console = Console()


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
def list_prompts(domain: str | None, status: str | None, owner: str | None, path: str | None) -> None:
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

    table = Table(title="Prompts" + (" (from manifest)" if used_manifest else " (from directory scan)"))
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
        status_text = f"[{status_style}]{prompt.status}[/{status_style}]" if status_style else prompt.status

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
def view(prompt_id: str, annotated: bool, meta: bool) -> None:
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

    # Show metadata summary if requested
    if meta:
        render_meta_summary(parsed_meta, console)
        if not annotated:
            return

    # Show annotated view if requested or if --meta wasn't specified
    if annotated or not meta:
        if prompt_path is None:
            console.print(f"[red]✗[/red] No prompt file found")
            raise SystemExit(1)

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
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
def audit() -> None:
    """Check governance compliance across all prompts."""
    # TODO: Implement audit
    console.print("[yellow]⚠[/yellow] Audit not yet implemented")


@main.command()
@click.argument("prompt_id")
def info(prompt_id: str) -> None:
    """Show detailed information about a prompt."""
    from .view import load_prompt_and_meta, render_full_info
    from .listing import find_manifest, parse_manifest

    _, prompt_path, parsed_meta, issues = load_prompt_and_meta(prompt_id)

    if issues and parsed_meta is None:
        for issue in issues:
            console.print(f"[red]✗[/red] {issue}")
        raise SystemExit(1)

    if parsed_meta is None:
        console.print(f"[red]✗[/red] Could not parse metadata for: {prompt_id}")
        raise SystemExit(1)

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


if __name__ == "__main__":
    main()
