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
# Install
pip install prompt-vc

# Initialize a prompt repository
prompt-vc init

# Create a new prompt with metadata
prompt-vc new customer-support --domain support

# Validate all prompts
prompt-vc validate

# List prompts
prompt-vc list

# View a prompt with annotations
prompt-vc view customer-support --annotated

# Add an annotation to a prompt
prompt-vc annotate customer-support --line 12

# Check governance compliance
prompt-vc audit

# Compare versions between git refs
prompt-vc diff customer-support --old HEAD~1

# Render a Jinja template with variables
prompt-vc render customer-support -v customer_name=John

# Generate dependency graph (DOT format)
prompt-vc graph

# Compose prompt with resolved includes
prompt-vc compose customer-support
```

## File Formats

### Prompt Files

Use any format you prefer:
- `.md` - Markdown
- `.txt` - Plain text
- `.yaml` - YAML
- `.jinja` / `.jinja2` - Jinja templates
- `.hbs` - Handlebars templates

### Meta Files (`.prompt.meta.yaml`)

See [docs/meta-schema.md](docs/meta-schema.md) for the full schema.

```yaml
schema_version: "1.0"
id: customer-support-v2
intent: |
  Handle refund requests with empathy while enforcing policy limits.

assumptions:
  model: claude-sonnet-4-20250514
  min_context_window: 8000

variables:
  customer_name:
    type: string
    description: Customer's first name

annotations:
  - id: ann_01
    anchor:
      hash: sha256:8f3a2b1c...
      preview: "You MUST NOT promise refunds exceeding"
      line_hint: 12
    author: alice@company.com
    date: 2024-03-15
    source: https://linear.app/issue/CS-123
    rationale: Legal compliance review required exact phrasing
    tags: [legal, do-not-modify]
```

### Manifest File (`prompts.manifest.yaml`)

For repositories with multiple prompts. See [docs/manifest-schema.md](docs/manifest-schema.md).

## Design Principles

1. **Files over databases** - Everything is parseable text in git
2. **Format-agnostic** - Your prompts stay in whatever format works for you
3. **LLM-friendly** - Metadata is structured for easy consumption by LLMs
4. **Minimal overhead** - Start with just a prompt and meta file, add complexity as needed
5. **Git-native** - Complements git, doesn't replace it

## Documentation

- [End-to-End Example](docs/end-to-end-example.md) - Complete walkthrough
- [Meta File Schema](docs/meta-schema.md)
- [Manifest Schema](docs/manifest-schema.md)
- [CLI Reference](docs/cli.md)
- [Best Practices](docs/best-practices.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT
