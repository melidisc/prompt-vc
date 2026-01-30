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
    # TODO: Implement validation
    console.print("[yellow]⚠[/yellow] Validation not yet implemented")


@main.command("list")
@click.option("--domain", "-d", default=None, help="Filter by domain")
@click.option("--status", "-s", default=None, help="Filter by status")
def list_prompts(domain: str | None, status: str | None) -> None:
    """List all prompts in the repository."""
    # TODO: Implement listing from manifest
    table = Table(title="Prompts")
    table.add_column("Domain", style="cyan")
    table.add_column("ID", style="green")
    table.add_column("Status")
    table.add_column("Deployed To")
    
    # Placeholder
    table.add_row("(none)", "(no prompts found)", "-", "-")
    
    console.print(table)


@main.command()
@click.argument("prompt_id")
@click.option("--annotated", "-a", is_flag=True, help="Show annotations inline")
@click.option("--meta", "-m", is_flag=True, help="Show metadata summary")
def view(prompt_id: str, annotated: bool, meta: bool) -> None:
    """View a prompt with optional annotation overlay."""
    # TODO: Implement view
    console.print(f"[yellow]⚠[/yellow] View not yet implemented for: {prompt_id}")


@main.command()
@click.argument("prompt_id")
@click.option("--line", "-l", type=int, help="Line number to annotate")
def annotate(prompt_id: str, line: int | None) -> None:
    """Add an annotation to a prompt."""
    # TODO: Implement annotation
    console.print("[yellow]⚠[/yellow] Annotate not yet implemented")


@main.command()
def audit() -> None:
    """Check governance compliance across all prompts."""
    # TODO: Implement audit
    console.print("[yellow]⚠[/yellow] Audit not yet implemented")


@main.command()
@click.argument("prompt_id")
def info(prompt_id: str) -> None:
    """Show detailed information about a prompt."""
    # TODO: Implement info
    console.print(f"[yellow]⚠[/yellow] Info not yet implemented for: {prompt_id}")


if __name__ == "__main__":
    main()
