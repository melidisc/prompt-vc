# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

**prompt-vc** is a CLI tool for version control metadata for LLM prompts. It helps teams manage, annotate, and govern their prompt libraries with structured metadata.

## Architecture

```
src/prompt_vc/
├── cli.py        # Click-based CLI commands
├── models.py     # Pydantic models for meta and manifest schemas
├── hashing.py    # Content hashing for annotation anchoring
├── validation.py # Validation logic for prompts and metadata
├── view.py       # View/display functionality
└── listing.py    # Prompt listing from manifest or directory
```

## Key Concepts

- **Prompt files**: `.prompt.md`, `.prompt.jinja`, etc. - the actual prompt content
- **Meta files**: `.prompt.meta.yaml` - structured metadata about each prompt
- **Manifest**: `prompts.manifest.yaml` - repository-level configuration and prompt registry
- **Annotations**: Line-level notes with content hashes for tracking why specific text exists

## CLI Commands

Implemented:
- `prompt-vc validate [path]` - Validate prompts and metadata
- `prompt-vc view <id> [--annotated] [--meta]` - View a prompt
- `prompt-vc list [--domain] [--status] [--owner]` - List prompts
- `prompt-vc info <id>` - Show detailed prompt information

Stubbed (TODO):
- `prompt-vc annotate <id>` - Add annotations
- `prompt-vc audit` - Check governance compliance

## Development

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run CLI
prompt-vc --help
```

## File Patterns

- Meta files: `*.prompt.meta.yaml`
- Prompt files: `*.prompt.{md,jinja,txt,yaml}`
- Manifest: `prompts.manifest.yaml`

## Code Style

- Python 3.9+ with type hints
- Pydantic v2 for data models
- Click for CLI
- Rich for terminal output
