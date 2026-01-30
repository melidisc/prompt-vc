# Meta File Schema

The `.prompt.meta.yaml` file contains all metadata for a prompt.

## Full Schema

```yaml
# Required: Schema version for forward compatibility
schema_version: "1.0"

# Required: Unique identifier for this prompt
id: string

# Optional: Human-readable name
name: string

# Optional: Creation date (ISO 8601)
created: date

# Optional: List of author emails
authors:
  - string

# Recommended: What this prompt should accomplish
intent: string

# Optional: Runtime assumptions
assumptions:
  model: string                    # e.g., "claude-sonnet-4-20250514"
  min_context_window: integer      # minimum tokens required
  max_tokens: integer              # expected max output tokens
  expected_latency_ms: integer     # performance expectation
  template_engine: string          # "jinja2", "handlebars", "none"
  
  upstream_dependencies:           # services that provide input
    - service: string
      provides: [string]
  
  downstream_consumers:            # services that consume output
    - service: string
      expects: string

# Optional: Variable definitions
variables:
  variable_name:
    type: string                   # "string", "integer", "boolean", "object", "array"
    description: string
    required: boolean              # default: true
    default: any                   # default value if not provided
    schema_ref: string             # path to JSON schema file

# Optional: Evaluation criteria
evaluation:
  metrics:
    - name: string
      target: string               # e.g., ">= 4.2", "100%"
      measured_by: string          # path to evaluator or description
  test_cases_ref: string           # path to test cases file

# Optional: Line-level annotations
annotations:
  - id: string                     # unique annotation ID
    anchor:
      hash: string                 # sha256 hash of annotated text
      preview: string              # first ~50 chars for readability
      line_hint: integer           # best-effort line number
    author: string                 # email
    date: date                     # ISO 8601
    source: string                 # URL or file path to evidence
    rationale: string              # why this text exists
    tags: [string]                 # e.g., ["legal", "tested", "do-not-modify"]

# Optional: Change history (supplements git log)
changelog:
  - version: string
    date: date
    author: string
    summary: string
    linked_annotations: [string]   # annotation IDs
```

## Minimal Example

```yaml
schema_version: "1.0"
id: simple-greeting

intent: Greet users in a friendly way.
```

## Full Example

```yaml
schema_version: "1.0"
id: refund-handler-v2
name: Customer Support Refund Handler
created: 2024-01-10
authors:
  - alice@company.com
  - bob@company.com

intent: |
  Handle refund requests with empathy while enforcing policy limits.
  Should de-escalate frustrated customers without over-promising.

assumptions:
  model: claude-sonnet-4-20250514
  min_context_window: 8000
  max_tokens: 1024
  expected_latency_ms: 2000
  template_engine: jinja2
  
  upstream_dependencies:
    - service: order-api
      provides: [order_id, order_total, refund_policy]
    - service: crm
      provides: [customer_name, customer_history]
  
  downstream_consumers:
    - service: ticket-system
      expects: structured refund decision JSON

variables:
  customer_name:
    type: string
    description: Customer's first name from CRM
    required: true
  
  order_id:
    type: string
    description: UUID of the order in question
    required: true
  
  refund_policy:
    type: object
    description: Policy object from policy-service
    schema_ref: ../schemas/refund-policy.schema.json

evaluation:
  metrics:
    - name: empathy_score
      target: ">= 4.2"
      measured_by: eval/empathy-classifier.py
    - name: policy_compliance
      target: "100%"
      measured_by: eval/compliance-checker.py
  test_cases_ref: tests/refund-handler.cases.yaml

annotations:
  - id: ann_legal_01
    anchor:
      hash: sha256:8f3a2b1c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
      preview: "You MUST NOT promise refunds exceeding"
      line_hint: 12
    author: alice@company.com
    date: 2024-03-15
    source: https://linear.app/acme/issue/CS-123
    rationale: |
      Legal compliance review required this exact phrasing.
      See thread with legal team in the linked issue.
    tags: [legal, compliance, do-not-modify]

  - id: ann_empathy_01
    anchor:
      hash: sha256:c7d9e4f2a1b3c5d7e9f1a3b5c7d9e1f3a5b7c9d1
      preview: "Always acknowledge the customer's frustration"
      line_hint: 18
    author: bob@company.com
    date: 2024-03-20
    source: eval/results/2024-03-18-empathy-ab-test.json
    rationale: |
      A/B test showed 12% improvement in empathy score.
      Control: 3.8, Treatment: 4.26, p < 0.01
    tags: [tested, empathy, validated]

changelog:
  - version: "2.1"
    date: 2024-03-20
    author: bob@company.com
    summary: Added empathy acknowledgment line based on A/B test
    linked_annotations: [ann_empathy_01]
  
  - version: "2.0"
    date: 2024-03-15
    author: alice@company.com
    summary: Legal compliance rewrite
    linked_annotations: [ann_legal_01]
  
  - version: "1.0"
    date: 2024-01-10
    author: alice@company.com
    summary: Initial version
    linked_annotations: []
```

## Annotation Anchoring

Annotations reference specific text using content hashes for durability.

### How Hashing Works

1. The CLI extracts the annotated text block
2. Normalizes whitespace (trim, collapse internal whitespace)
3. Computes SHA-256 hash
4. Stores hash + human-readable preview + line hint

### When Hashes Break

If the annotated text is edited, the hash won't match. The CLI will:
1. Flag the annotation as "orphaned"
2. Attempt fuzzy matching to suggest where the text moved
3. Prompt you to update or remove the annotation

```bash
$ prompt-vc validate

⚠ customer-support/refund-handler.prompt.meta.yaml
  Annotation ann_legal_01 is orphaned (hash mismatch)
  
  Expected: "You MUST NOT promise refunds exceeding"
  
  Possible matches:
    Line 14: "You must not promise refunds over" (similarity: 82%)
  
  Run `prompt-vc fix-annotations` to interactively resolve.
```

## Multi-Line Annotations

For annotations spanning multiple lines, the hash covers the entire block:

```yaml
annotations:
  - id: ann_multiline_01
    anchor:
      hash: sha256:...
      preview: "When handling complaints:\n1. Acknowledge..."
      line_hint: 20
      line_end_hint: 25    # optional: marks end of block
    rationale: This structured approach tested better than freeform.
```
