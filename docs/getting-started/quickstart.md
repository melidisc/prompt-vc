# Quick Start

This guide walks you through creating and managing your first prompt with prompt-vc.

## Initialize a Repository

Start by creating a prompt-vc repository:

```bash
prompt-vc init --with-manifest
```

This creates:

- `prompts/` - Directory for your prompt files
- `prompts/prompts.manifest.yaml` - Repository-level configuration

## Create Your First Prompt

```bash
prompt-vc new customer-support --domain support
```

This creates two files:

- `prompts/support/customer-support.prompt.md` - Your prompt content
- `prompts/support/customer-support.prompt.meta.yaml` - Structured metadata

## Edit Your Prompt

Open `prompts/support/customer-support.prompt.md` and add your prompt:

```markdown
# Customer Support Agent

You are a helpful customer support agent for Acme Corp.

## Guidelines

- Be empathetic and professional
- You MUST NOT promise refunds exceeding $100 without manager approval
- Always verify the customer's identity before discussing account details

## Response Format

1. Acknowledge the customer's concern
2. Provide a clear solution or next steps
3. Ask if there's anything else you can help with
```

## Add Metadata

Edit `prompts/support/customer-support.prompt.meta.yaml`:

```yaml
schema_version: "1.0"

id: customer-support
name: Customer Support Agent
created: "2024-03-15"
authors:
  - alice@company.com

intent: |
  Handle customer inquiries with empathy while enforcing
  company policies on refunds and data privacy.

assumptions:
  model: claude-sonnet-4-20250514
  template_engine: none

variables: {}

evaluation:
  metrics:
    - name: policy_compliance
      description: Agent follows refund and privacy policies

annotations: []

changelog:
  - version: "1.0"
    date: "2024-03-15"
    author: alice@company.com
    summary: Initial version
```

## Validate Your Prompt

Check that everything is correct:

```bash
prompt-vc validate
```

Output:

```
✓ prompts/support/customer-support.prompt.meta.yaml
✓ All 1 prompt(s) valid
```

## Add an Annotation

Document why specific text exists:

```bash
prompt-vc annotate customer-support --line 7 \
  --rationale "Legal review required this exact phrasing for liability protection" \
  --source "https://linear.app/company/issue/LEGAL-42" \
  --tags "legal,do-not-modify"
```

## View with Annotations

See your prompt with inline annotations:

```bash
prompt-vc view customer-support --annotated
```

Output:

```
Customer Support Agent

   1 │ # Customer Support Agent
   2 │
   3 │ You are a helpful customer support agent for Acme Corp.
   4 │
   5 │ ## Guidelines
   6 │
   7 │ - Be empathetic and professional
     │   📝 [ann_abc123] Legal review required this exact phrasing...
     │      🔗 https://linear.app/company/issue/LEGAL-42
     │      🏷️  legal, do-not-modify
```

## List All Prompts

```bash
prompt-vc list
```

Output:

```
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Domain   ┃ ID                 ┃ Name                   ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│ support  │ customer-support   │ Customer Support Agent │
└──────────┴────────────────────┴────────────────────────┘
```

## Next Steps

- [End-to-End Example](../end-to-end-example.md) - Complete workflow walkthrough
- [CLI Reference](../cli.md) - All available commands
- [Meta Schema](../meta-schema.md) - Full metadata format
- [Best Practices](../best-practices.md) - Tips for prompt management
