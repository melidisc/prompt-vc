# prompt-vc

Version control metadata for LLM prompts. Track *why* each line exists, not just *what* it is.

## The Problem

Prompts are becoming critical infrastructure, but tooling is immature:

- Git commits bundle unrelated changes
- `git blame` shows *who* and *when*, but not *why* or *what evidence supported it*
- Context gets buried in commit messages nobody reads
- No clear ownership, evaluation criteria, or deployment tracking

## The Solution

A **sidecar metadata format** that lives alongside your prompts:

```
prompts/
  customer-support.prompt.md          # your prompt (any format)
  customer-support.prompt.meta.yaml   # structured metadata + annotations
```

Your prompts stay **portable and tool-agnostic**. The `.meta.yaml` captures:

- **Intent**: What should this prompt accomplish?
- **Assumptions**: Model, context window, dependencies
- **Variables**: Expected inputs with types and descriptions
- **Annotations**: Per-line rationale with links to sources (issues, experiments, reviews)
- **Evaluation**: How do we know if changes are good?

## Quick Start

```bash
# Install with uv (recommended)
uv add prompt-vc

# Or install with pip
pip install prompt-vc

# Initialize a prompt repository
prompt-vc init

# Create a new prompt with metadata
prompt-vc new customer-support --domain support

# Validate all prompts
prompt-vc validate

# View a prompt with annotations
prompt-vc view customer-support --annotated
```

See the [Quick Start Guide](getting-started/quickstart.md) for more details.

## Key Features

| Feature | Description |
|---------|-------------|
| `validate` | Check schema validity and annotation integrity |
| `view` | Display prompts with inline annotations |
| `list` | Browse prompts with filtering by domain/status |
| `annotate` | Add line-level rationale and sources |
| `audit` | Check governance compliance |
| `diff` | Compare versions with annotation context |
| `render` | Apply Jinja/Handlebars variables |
| `graph` | Generate dependency visualizations |
| `compose` | Resolve prompt includes |

## Design Principles

1. **Files over databases** - Everything is parseable text in git
2. **Format-agnostic** - Your prompts stay in whatever format works for you
3. **LLM-friendly** - Metadata is structured for easy consumption by LLMs
4. **Minimal overhead** - Start with just a prompt and meta file, add complexity as needed
5. **Git-native** - Complements git, doesn't replace it

## File Formats

### Prompt Files

Use any format you prefer:

- `.md` - Markdown
- `.txt` - Plain text
- `.yaml` - YAML
- `.jinja` / `.jinja2` - Jinja templates
- `.hbs` - Handlebars templates

### Meta Files

Structured YAML metadata:

```yaml
schema_version: "1.0"
id: customer-support-v2
intent: |
  Handle refund requests with empathy while enforcing policy limits.

annotations:
  - id: ann_01
    anchor:
      hash: sha256:8f3a2b1c...
      preview: "You MUST NOT promise refunds exceeding"
      line_hint: 12
    rationale: Legal compliance review required exact phrasing
    tags: [legal, do-not-modify]
```

See the [Meta Schema](meta-schema.md) for full documentation.
