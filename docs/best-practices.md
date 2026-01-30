# Best Practices

## Writing Good Intents

The `intent` field is the most important piece of metadata. It should answer:
- What should this prompt accomplish?
- What should the output look like?
- What should the prompt NOT do?

**Bad:**
```yaml
intent: Handle customer support
```

**Good:**
```yaml
intent: |
  Handle refund requests for orders under $500. Should:
  - Acknowledge customer frustration before discussing policy
  - Never promise refunds above the policy limit
  - Offer alternatives (store credit, exchange) when refund isn't possible
  - Escalate to human if customer mentions legal action
  
  Output: JSON with decision, reasoning, and suggested_response fields.
```

---

## When to Annotate

Not every line needs an annotation. Annotate when:

| Situation | Why |
|-----------|-----|
| Legal/compliance required specific wording | Prevents accidental edits |
| A/B test validated the line | Documents evidence |
| A bug was fixed | Prevents regression |
| Someone will ask "why is this here?" | Saves future confusion |
| The line contradicts intuition | Explains the reasoning |

---

## Annotation Quality

**Bad annotation:**
```yaml
rationale: Added this line
```

**Good annotation:**
```yaml
rationale: |
  A/B test (2024-03-18) showed 12% improvement in empathy score.
  Control: 3.8, Treatment: 4.26, p < 0.01, n=1200.
  See full analysis in linked source.
```

---

## Organizing Large Repositories

### Directory Structure

```
prompts/
├── prompts.manifest.yaml
├── schemas/              # shared JSON schemas for variables
├── eval/                 # shared evaluation code
├── templates/            # starter templates for new prompts
│
├── <domain>/             # group by business domain
│   ├── <prompt>.prompt.md
│   └── <prompt>.prompt.meta.yaml
```

### Naming Conventions

- **Prompt IDs**: kebab-case, descriptive (`refund-handler`, not `prompt1`)
- **Domains**: match team/product boundaries
- **Files**: `<id>.prompt.<ext>` and `<id>.prompt.meta.yaml`

---

## Version Numbering

Use the `changelog` in meta files for semantic versioning:

- **Major** (2.0 → 3.0): Breaking changes to output format or behavior
- **Minor** (2.0 → 2.1): New capabilities, backward compatible
- **Patch** (2.0.0 → 2.0.1): Bug fixes, wording tweaks

---

## Review Checklist

Before merging prompt changes:

- [ ] Intent still accurately describes behavior
- [ ] All new/changed lines have annotations if non-obvious
- [ ] Variables are documented with types
- [ ] Evaluation criteria exist for production prompts
- [ ] No orphaned annotations
- [ ] Tested with edge cases

---

## Working with Templates

If using Jinja/Handlebars:

1. **Document all variables** in the meta file
2. **Provide example values** in a `test-context.json`
3. **Test rendering** before committing: `prompt-vc render <id> --context test-context.json`

---

## Governance Recommendations

For production prompts, require:
- `intent` field (always)
- At least one evaluation metric
- `reviewed` tag from a second person
- Legal review for customer-facing prompts

Enforce with:
```yaml
# prompts.manifest.yaml
governance:
  production_requirements:
    must_have_intent: true
    must_have_evaluation: true
    min_annotations: 0  # not required, but encouraged
    required_tags: [reviewed]
```

---

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Annotations reference line numbers only | Break on any edit | Use content hashes |
| No intent field | Nobody knows what the prompt does | Always write intent first |
| Copying prompts without updating ID | Duplicate IDs in manifest | Generate new ID |
| Huge prompts in one file | Hard to annotate, review | Split into composable parts |
| Skipping meta for "simple" prompts | Tech debt accumulates | Every prompt gets a meta file |
