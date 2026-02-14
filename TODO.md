# TODO

## Phase 1: Core CLI Implementation

- [x] **Implement `validate` command**
  - Parse `.prompt.meta.yaml` files using Pydantic models
  - Check schema validity
  - Verify annotation hashes match content in prompt files
  - Report orphaned annotations (hash mismatch)
  - Check variable references in prompt match meta definitions

- [x] **Implement `view --annotated` command**
  - Load prompt file and corresponding meta file
  - Parse annotations and match to lines via `line_hint`
  - Render prompt with inline annotation display (using `rich`)

- [x] **Implement `list` command**
  - Parse `prompts.manifest.yaml` if present
  - Fall back to directory scanning if no manifest
  - Support filtering by domain, status, owner

- [x] **Implement `info` command**
  - Display full metadata summary for a prompt
  - Show variables, assumptions, annotations, deployment info

## Phase 2: Annotation Management

- [x] **Implement `annotate` command**
  - Interactive mode: select line(s), enter rationale, source, tags
  - Compute content hash automatically
  - Append to meta file annotations list
  - Generate unique annotation ID

- [x] **Implement `fix-annotations` command**
  - Detect orphaned annotations (hash doesn't match any content)
  - Fuzzy match to suggest where text may have moved
  - Interactive prompts to update, re-anchor, or remove

- [x] **Hash verification on every command**
  - Warn if any annotation hash is stale
  - Auto-update `line_hint` when content is found at different line

## Phase 3: Governance & Audit

- [ ] **Implement `audit` command**
  - Load governance rules from manifest
  - Check each prompt against `production_requirements`
  - Report compliance status per prompt

- [ ] **Implement `diff` command**
  - Compare two git refs for a prompt
  - Show annotation context alongside text changes
  - Highlight new/removed/modified annotations

## Phase 4: Rendering & Templates

- [ ] **Implement `render` command**
  - Load prompt file
  - Detect template engine from meta (`jinja2`, `handlebars`, `none`)
  - Apply variables from `--context` JSON/YAML file
  - Output rendered prompt to stdout or file

- [ ] **Variable validation**
  - Check required variables are provided
  - Validate types against schema if `schema_ref` is specified

## Phase 5: Developer Experience

- [ ] **VS Code extension**
  - Syntax highlighting for `.prompt.meta.yaml`
  - Hover to show annotation details on prompt lines
  - CodeLens to jump to annotation source URLs

- [ ] **GitHub Actions**
  - `prompt-vc validate` on PR
  - Block merge if governance requirements not met
  - Comment on PR with annotation changes

- [ ] **Pre-commit hook**
  - Auto-update `line_hint` values
  - Warn on orphaned annotations

## Phase 6: Advanced Features

- [ ] **Implement `graph` command**
  - Parse relationships from manifest
  - Generate dependency graph (DOT, PNG, SVG)
  - Show cross-prompt dependencies

- [ ] **Prompt composition**
  - Support `{% include 'other-prompt.md' %}` or similar
  - Track dependencies in manifest automatically

- [ ] **Evaluation integration**
  - Link to eval frameworks (promptfoo, etc.)
  - Store eval results and link from annotations
  - `prompt-vc eval <id>` to run associated tests

## Backlog / Ideas

- [ ] Web UI for browsing prompt library
- [ ] Slack bot for prompt change notifications
- [ ] LLM-assisted annotation suggestions ("why might this line exist?")
- [ ] Import from existing prompt files (auto-generate meta stubs)
- [ ] Export to LangChain / LlamaIndex / other frameworks
- [ ] Prompt playground integration (test prompts with real LLM calls)
- [ ] Semantic diff (not just text diff, but "meaning changed" detection)
- [ ] Multi-language support (i18n for prompts)

## Tech Debt

- [ ] Add more comprehensive tests for models
- [ ] Add CLI integration tests (click.testing.CliRunner)
- [ ] Set up GitHub Actions for CI
- [ ] Add type stubs for better IDE support
- [ ] Documentation site (mkdocs or similar)
