# Manifest Schema

The `prompts.manifest.yaml` file is the root index for repositories with multiple prompts.

## When to Use

- You have more than ~5 prompts
- Multiple teams own different prompts
- You need deployment tracking
- You want governance/compliance automation

## Full Schema

```yaml
# Required: Schema version
schema_version: "1.0"

# Optional: Organization/company name
organization: string

# Optional: Repository name
repository: string

# Optional: Global defaults applied to all prompts
defaults:
  model: string
  template_engine: string
  review_required: boolean

# Required: Domain groupings
domains:
  domain_name:
    description: string
    owners:
      - team: string
        slack: string        # or email, etc.
      - user: string         # individual owner
    
    prompts:
      - id: string           # must match id in .meta.yaml
        path: string         # relative path to .prompt file
        status: string       # "production", "beta", "experimental", "deprecated"
        deployed_to: [string]  # list of services/environments
        experiments:         # optional: active experiments
          - name: string
            tracking_id: string
            started: date

# Optional: Cross-prompt relationships
relationships:
  - type: string             # "replaces", "depends_on", "variant_of"
    from: string             # prompt path
    to: string               # prompt path
    note: string

# Optional: Governance rules
governance:
  production_requirements:
    must_have_intent: boolean
    must_have_evaluation: boolean
    min_annotations: integer
    required_tags: [string]
  
  review_policy:
    domains_requiring_legal_review: [string]
    auto_reviewers:
      domain_name: [string]  # GitHub teams or usernames
```

## Example

```yaml
schema_version: "1.0"
organization: acme-corp
repository: prompt-library

defaults:
  model: claude-sonnet-4-20250514
  template_engine: jinja2
  review_required: true

domains:
  customer-support:
    description: Customer-facing support automation
    owners:
      - team: support-engineering
        slack: "#support-eng"
    prompts:
      - id: refund-handler
        path: customer-support/refund-handler.prompt.md
        status: production
        deployed_to: [support-api, chat-widget]
      
      - id: escalation-detector
        path: customer-support/escalation-detector.prompt.md
        status: production
        deployed_to: [ticket-router]

  product:
    description: Product catalog and content generation
    owners:
      - team: catalog-team
        slack: "#catalog-eng"
    prompts:
      - id: description-generator
        path: product/description-generator.prompt.jinja
        status: production
        deployed_to: [catalog-cms]

  experimental:
    description: Work-in-progress prompts
    owners:
      - team: support-engineering
    prompts:
      - id: new-refund-flow-v3
        path: experimental/new-refund-flow-v3.prompt.md
        status: experimental
        deployed_to: []
        experiments:
          - name: refund-flow-ab-test
            tracking_id: EXP-2024-042
            started: 2024-03-25

relationships:
  - type: replaces
    from: experimental/new-refund-flow-v3
    to: customer-support/refund-handler
    note: Candidate replacement pending A/B test results
  
  - type: depends_on
    from: customer-support/escalation-detector
    to: customer-support/sentiment-tagger
    note: Escalation detector uses sentiment as input

governance:
  production_requirements:
    must_have_intent: true
    must_have_evaluation: true
    min_annotations: 1
    required_tags: [reviewed]
  
  review_policy:
    domains_requiring_legal_review:
      - customer-support
    auto_reviewers:
      customer-support: ["@support-eng-leads"]
      product: ["@catalog-team"]
```

## Relationship Types

| Type | Meaning |
|------|---------|
| `replaces` | New prompt intended to replace old one |
| `depends_on` | Prompt A uses output from prompt B |
| `variant_of` | A/B test variant or localized version |
| `derived_from` | Forked/adapted from another prompt |

## Status Values

| Status | Meaning |
|--------|---------|
| `production` | Actively serving traffic |
| `beta` | Limited rollout, may have issues |
| `experimental` | Not for production use |
| `deprecated` | Being phased out, don't use for new work |
| `archived` | No longer maintained |
