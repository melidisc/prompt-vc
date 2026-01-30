# CLI Reference

## Installation

```bash
pip install prompt-vc
```

## Commands

### `prompt-vc init`

Initialize a prompt-vc repository.

```bash
prompt-vc init [--with-manifest]
```

**Options:**
- `--with-manifest` - Create a `prompts.manifest.yaml` file

**Creates:**
- `prompts/` directory
- `prompts.manifest.yaml` (if `--with-manifest`)

---

### `prompt-vc new`

Create a new prompt with metadata file.

```bash
prompt-vc new <id> [options]
```

**Options:**
- `--domain <name>` - Place in domain subdirectory
- `--format <ext>` - Prompt file format (default: `md`)
- `--template <name>` - Use a starter template

**Example:**
```bash
prompt-vc new customer-greeting --domain support --format jinja
# Creates:
#   prompts/support/customer-greeting.prompt.jinja
#   prompts/support/customer-greeting.prompt.meta.yaml
```

---

### `prompt-vc validate`

Validate prompts and metadata.

```bash
prompt-vc validate [path] [options]
```

**Options:**
- `--strict` - Fail on warnings
- `--fix` - Auto-fix simple issues (update line hints)

**Checks:**
- Meta file schema validity
- Annotation hash integrity
- Variable references in prompt match meta definitions
- Governance compliance (if manifest exists)

**Example:**
```bash
$ prompt-vc validate

✓ customer-support/refund-handler.prompt.md
✓ customer-support/escalation-detector.prompt.md
⚠ product/description-generator.prompt.jinja
  - Annotation ann_03 has stale line_hint (expected 15, found at 18)
✗ experimental/new-flow.prompt.md
  - Missing required field: intent

2 passed, 1 warning, 1 error
```

---

### `prompt-vc list`

List all prompts in the repository.

```bash
prompt-vc list [options]
```

**Options:**
- `--domain <name>` - Filter by domain
- `--status <status>` - Filter by status
- `--owner <team|user>` - Filter by owner
- `--format <table|json|csv>` - Output format

**Example:**
```bash
$ prompt-vc list --status production

DOMAIN              ID                    STATUS       DEPLOYED TO
customer-support    refund-handler        production   support-api, chat-widget
customer-support    escalation-detector   production   ticket-router
product             description-generator production   catalog-cms
```

---

### `prompt-vc view`

View a prompt with optional annotation overlay.

```bash
prompt-vc view <id|path> [options]
```

**Options:**
- `--annotated` - Show inline annotations
- `--meta` - Show metadata summary
- `--raw` - Show raw prompt only

**Example:**
```bash
$ prompt-vc view refund-handler --annotated

# Refund Handler v2.1
# Intent: Handle refund requests with empathy while enforcing policy limits.

You are a customer support agent for {{company_name}}.

│ [ann_legal_01] Legal compliance - do-not-modify
│ Author: alice@company.com (2024-03-15)
│ Source: https://linear.app/acme/issue/CS-123
│ Rationale: Legal compliance review required exact phrasing
You MUST NOT promise refunds exceeding {{refund_policy.max_amount}}.

│ [ann_empathy_01] Tested improvement
│ Author: bob@company.com (2024-03-20)
│ Source: eval/results/2024-03-18-empathy-ab-test.json
│ Rationale: A/B test showed 12% improvement in empathy score
Always acknowledge the customer's frustration before discussing policy.
```

---

### `prompt-vc annotate`

Add an annotation to a prompt.

```bash
prompt-vc annotate <id|path> [options]
```

**Options:**
- `--line <n>` - Annotate specific line
- `--lines <start>:<end>` - Annotate line range
- `--interactive` - Select text interactively

**Interactive mode prompts for:**
- Source URL or file path
- Rationale
- Tags

---

### `prompt-vc diff`

Compare prompt versions with annotation context.

```bash
prompt-vc diff <ref1> <ref2> <id|path>
```

**Example:**
```bash
$ prompt-vc diff HEAD~3 HEAD customer-support/refund-handler

--- a/customer-support/refund-handler.prompt.md (abc123)
+++ b/customer-support/refund-handler.prompt.md (def456)

@@ -15,6 +15,9 @@
 You MUST NOT promise refunds exceeding {{refund_policy.max_amount}}.

+│ [NEW] ann_empathy_01
+│ Rationale: A/B test showed 12% improvement
+Always acknowledge the customer's frustration before discussing policy.
```

---

### `prompt-vc render`

Render a prompt with variables.

```bash
prompt-vc render <id|path> --context <file>
```

**Example:**
```bash
$ prompt-vc render refund-handler --context test-context.json

# Outputs the prompt with all variables substituted
```

---

### `prompt-vc audit`

Check governance compliance across all prompts.

```bash
prompt-vc audit [options]
```

**Options:**
- `--status <status>` - Only audit prompts with this status
- `--fix-suggestions` - Show how to fix issues

**Example:**
```bash
$ prompt-vc audit --status production

Auditing 5 production prompts against governance rules...

✓ customer-support/refund-handler
✓ customer-support/escalation-detector
✗ product/description-generator
  - Missing evaluation criteria (required for production)
  - Missing tag: reviewed
✓ product/review-summarizer
✓ internal-tools/sql-generator

4/5 compliant
```

---

### `prompt-vc graph`

Generate dependency/relationship graph.

```bash
prompt-vc graph [options]
```

**Options:**
- `--output <file>` - Output file (png, svg, dot)
- `--domain <name>` - Filter to domain

---

### `prompt-vc info`

Show detailed information about a prompt.

```bash
prompt-vc info <id|path>
```

**Example:**
```bash
$ prompt-vc info refund-handler

Prompt: refund-handler
Path:   customer-support/refund-handler.prompt.md
Status: production

Intent:
  Handle refund requests with empathy while enforcing policy limits.

Assumptions:
  Model:          claude-sonnet-4-20250514
  Context Window: 8000+ tokens
  Template:       jinja2

Variables:
  - customer_name (string, required)
  - order_id (string, required)
  - refund_policy (object, required)

Deployed To:
  - support-api
  - chat-widget

Owners:
  - team: support-engineering (#support-eng)

Annotations: 2
  - ann_legal_01 (legal, do-not-modify)
  - ann_empathy_01 (tested, empathy)

Relationships:
  - Will be replaced by: experimental/new-refund-flow-v3
```

---

### `prompt-vc fix-annotations`

Interactively fix orphaned or stale annotations.

```bash
prompt-vc fix-annotations [id|path]
```

Walks through each issue and prompts for resolution:
- Update hash to match current text
- Update line hints
- Remove orphaned annotations
- Re-anchor to similar text
