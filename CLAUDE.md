# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

**prompt-vc** is a CLI tool for version control metadata for LLM prompts. It helps teams manage, annotate, and govern their prompt libraries with structured metadata.

## Architecture

```
src/prompt_vc/
├── cli.py             # Click-based CLI commands
├── models.py          # Pydantic models for meta and manifest schemas
├── hashing.py         # Content hashing for annotation anchoring
├── validation.py      # Validation logic for prompts and metadata
├── view.py            # View/display functionality
├── listing.py         # Prompt listing from manifest or directory
├── annotate.py        # Annotation creation and management
├── fix_annotations.py # Fix orphaned annotations
├── audit.py           # Governance compliance auditing
├── diff.py            # Git-based version comparison
├── render.py          # Template rendering with Jinja2
├── graph.py           # Dependency graph generation (DOT/PNG/SVG)
└── compose.py         # Prompt composition with include resolution
```

## Key Concepts

- **Prompt files**: `.prompt.md`, `.prompt.jinja`, etc. - the actual prompt content
- **Meta files**: `.prompt.meta.yaml` - structured metadata about each prompt
- **Manifest**: `prompts.manifest.yaml` - repository-level configuration and prompt registry
- **Annotations**: Line-level notes with content hashes for tracking why specific text exists

## CLI Commands

Implemented:
- `prompt-vc init [--with-manifest]` - Initialize a prompt-vc repository
- `prompt-vc new <id> [--domain] [--format]` - Create a new prompt with metadata file
- `prompt-vc validate [path] [--strict]` - Validate prompts and metadata
- `prompt-vc view <id> [--annotated] [--meta] [--auto-fix]` - View a prompt (shows hash warnings)
- `prompt-vc list [--domain] [--status] [--owner] [--path]` - List prompts
- `prompt-vc info <id> [--auto-fix]` - Show detailed prompt information (shows hash warnings)
- `prompt-vc annotate <id> [--line] [--rationale] [--source] [--tags] [--author]` - Add annotations
- `prompt-vc fix-annotations <id> [--auto-remove] [--dry-run]` - Fix orphaned annotations
- `prompt-vc audit [--status] [--all]` - Check governance compliance against production_requirements
- `prompt-vc diff <id> [--old] [--new]` - Compare prompt versions between git refs
- `prompt-vc render <id> [--context] [--var] [--output]` - Render prompt with Jinja2 variables
- `prompt-vc graph [--output] [--format] [--no-domains] [--title]` - Generate dependency graph
- `prompt-vc compose <id> [--output] [--show-deps]` - Compose prompt with resolved includes

Note: Commands with `--auto-fix` will automatically update stale `line_hint` values when content has moved.

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

## Module Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              prompt-vc CLI                                   │
│                              (cli.py)                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
        ▼                            ▼                            ▼
┌───────────────┐          ┌─────────────────┐          ┌─────────────────┐
│    init       │          │   validate      │          │    list         │
│    new        │          │   view          │          │                 │
└───────────────┘          │   info          │          └────────┬────────┘
                           │   annotate      │                   │
                           │   fix-annotations│                  │
                           │   audit         │                   │
                           └────────┬────────┘                   │
                                    │                            │
        ┌───────────────────────────┼────────────────────────────┤
        │                           │                            │
        ▼                           ▼                            ▼
┌───────────────┐          ┌─────────────────┐          ┌─────────────────┐
│  validation.py│◄────────►│    view.py      │          │   listing.py    │
│               │          │                 │          │                 │
│ • parse_meta  │          │ • render_prompt │          │ • find_manifest │
│ • validate    │          │ • render_meta   │          │ • parse_manifest│
│ • hash_check  │          │ • render_info   │          │ • list_prompts  │
└───────┬───────┘          └────────┬────────┘          └────────┬────────┘
        │                           │                            │
        ▼                           ▼                            ▼
┌───────────────┐          ┌─────────────────┐          ┌─────────────────┐
│  hashing.py   │          │   annotate.py   │          │    audit.py     │
│               │          │                 │          │                 │
│ • hash_content│          │ • add_annotation│          │ • run_audit     │
│ • find_text   │          │ • generate_id   │          │ • check_reqs    │
│ • similarity  │          └─────────────────┘          └─────────────────┘
└───────────────┘                   │
                                    ▼
                           ┌─────────────────┐          ┌─────────────────┐
                           │fix_annotations.py│         │    graph.py     │
                           │                 │          │                 │
                           │ • fuzzy_match   │          │ • build_graph   │
                           │ • fix_orphaned  │          │ • generate_dot  │
                           └─────────────────┘          │ • render_graph  │
                                                        └─────────────────┘

                                                        ┌─────────────────┐
                                                        │   compose.py    │
                                                        │                 │
                                                        │ • compose_prompt│
                                                        │ • get_deps      │
                                                        │ • resolve_incl  │
                                                        └─────────────────┘
```

## Data Models

```
┌───────────────────────────────────────────────────────────────────────────┐
│                              models.py                                     │
│                                                                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ PromptMeta  │  │  Manifest   │  │ Annotation  │  │ProductionReqs   │  │
│  │             │  │             │  │             │  │                 │  │
│  │ • id        │  │ • domains   │  │ • anchor    │  │ • must_have_*   │  │
│  │ • intent    │  │ • governance│  │ • rationale │  │ • min_*         │  │
│  │ • variables │  │ • defaults  │  │ • tags      │  │ • required_tags │  │
│  │ • annotations│ │ • relations │  │ • source    │  │                 │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   User CLI   │────►│  Parse Meta  │────►│   Validate   │
│   Command    │     │   (YAML)     │     │   (Pydantic) │
└──────────────┘     └──────────────┘     └──────────────┘
                                                  │
                     ┌────────────────────────────┤
                     │                            │
                     ▼                            ▼
              ┌──────────────┐            ┌──────────────┐
              │ Hash Verify  │            │ Governance   │
              │ Annotations  │            │ Compliance   │
              └──────────────┘            └──────────────┘
                     │                            │
                     └────────────┬───────────────┘
                                  │
                                  ▼
                           ┌──────────────┐
                           │ Rich Output  │
                           │ (Terminal)   │
                           └──────────────┘
```

## File System Layout

```
prompts/
├── prompts.manifest.yaml          (repository config & governance)
└── domain/
    ├── prompt-id.prompt.md        (prompt content)
    └── prompt-id.prompt.meta.yaml (metadata & annotations)
```
