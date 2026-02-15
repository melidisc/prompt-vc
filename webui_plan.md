# prompt-vc Web UI Plan

## Goals

Build a lightweight, local-first web UI that exposes the existing prompt-vc CLI capabilities through a browser. The UI should feel like a modern developer tool — fast, keyboard-friendly, and information-dense.

**Non-goals**: This is not a SaaS product. No user accounts, no databases, no cloud deployment. It's a local dev tool that reads/writes the same files the CLI does.

---

## Architecture

### Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Server** | FastAPI | Async, auto-generated OpenAPI docs, Pydantic-native (same models as prompt-vc) |
| **Frontend** | React 19 + Vite | Fast dev loop, broad ecosystem, stable |
| **Styling** | Tailwind CSS v4 | Utility-first, no custom CSS to maintain |
| **State** | TanStack Query v5 | Server-state management with caching, auto-refresh |
| **Routing** | TanStack Router | Type-safe, file-based routing |
| **Code Viewer** | CodeMirror 6 | Syntax highlighting, line gutters for annotations |
| **Graph Viz** | D3.js or `@viz-js/viz` (WASM Graphviz) | Render dependency graphs in-browser |
| **Bundling** | Vite | Produces static assets served by FastAPI in production |

### Why This Stack

- **FastAPI + Pydantic**: prompt-vc already uses Pydantic v2 models. FastAPI natively serializes them — zero translation layer. The existing `models.py` becomes the API schema automatically.
- **React + Vite**: Standard, well-understood. Vite's dev server proxies to FastAPI during development.
- **TanStack Query**: The UI is fundamentally a read-heavy dashboard over file-system state. TanStack Query's stale-while-revalidate pattern keeps the UI responsive while polling for file changes.
- **CodeMirror 6**: Annotations are line-level. We need a real code viewer with gutter support, not a `<pre>` tag.

### Monorepo Layout

```
prompt-vc/
├── src/prompt_vc/           # Existing CLI code (unchanged)
│   ├── cli.py
│   ├── models.py
│   ├── ...
│   └── server/              # New: FastAPI server
│       ├── __init__.py
│       ├── app.py           # FastAPI application factory
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── prompts.py   # CRUD + list/filter
│       │   ├── validate.py  # Validation endpoints
│       │   ├── audit.py     # Audit endpoints
│       │   ├── render.py    # Template rendering
│       │   ├── graph.py     # Dependency graph data
│       │   ├── diff.py      # Version diff
│       │   └── compose.py   # Composition endpoints
│       └── deps.py          # Shared dependencies (workspace path, etc.)
├── web/                     # New: React frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── api/             # Generated or hand-written API client
│       │   └── client.ts
│       ├── routes/
│       │   ├── __root.tsx   # Shell layout
│       │   ├── index.tsx    # Dashboard
│       │   ├── prompts/
│       │   │   ├── index.tsx      # List view
│       │   │   └── $promptId.tsx  # Detail view
│       │   ├── audit.tsx
│       │   ├── graph.tsx
│       │   └── validate.tsx
│       └── components/
│           ├── PromptCard.tsx
│           ├── AnnotatedViewer.tsx   # CodeMirror with annotation gutters
│           ├── MetaPanel.tsx
│           ├── AuditTable.tsx
│           ├── DependencyGraph.tsx
│           ├── DiffViewer.tsx
│           ├── RenderPreview.tsx
│           └── StatusBadge.tsx
└── pyproject.toml           # Add fastapi, uvicorn to deps
```

---

## API Design

The API is a thin HTTP layer over the existing Python modules. Each route module imports from the corresponding `src/prompt_vc/` module and returns JSON.

### Endpoints

#### Prompts

| Method | Path | Maps To | Description |
|--------|------|---------|-------------|
| `GET` | `/api/prompts` | `listing.list_prompts()` | List all prompts (filterable by `?domain=`, `?status=`, `?owner=`) |
| `GET` | `/api/prompts/{id}` | `view.load_prompt_and_meta()` | Get prompt content + metadata |
| `GET` | `/api/prompts/{id}/content` | file read | Raw prompt content |
| `POST` | `/api/prompts` | `cli.new()` logic | Create new prompt |
| `PUT` | `/api/prompts/{id}/content` | file write | Update prompt content |
| `PUT` | `/api/prompts/{id}/meta` | file write | Update metadata |

#### Annotations

| Method | Path | Maps To | Description |
|--------|------|---------|-------------|
| `POST` | `/api/prompts/{id}/annotations` | `annotate.create_annotation()` | Add annotation |
| `DELETE` | `/api/prompts/{id}/annotations/{ann_id}` | `fix_annotations.remove_annotation_from_meta()` | Remove annotation |
| `POST` | `/api/prompts/{id}/fix-annotations` | `fix_annotations.detect_orphaned_annotations()` | Detect and fix orphaned |

#### Validation & Audit

| Method | Path | Maps To | Description |
|--------|------|---------|-------------|
| `GET` | `/api/validate` | `validation.validate_all()` | Validate all prompts |
| `GET` | `/api/validate/{id}` | `validation.parse_meta_file()` | Validate single prompt |
| `GET` | `/api/audit` | `audit.run_audit()` | Run governance audit (`?status=`, `?all=true`) |

#### Rendering & Composition

| Method | Path | Maps To | Description |
|--------|------|---------|-------------|
| `POST` | `/api/prompts/{id}/render` | `render.render_prompt()` | Render template (body: `{context: {...}}`) |
| `GET` | `/api/prompts/{id}/compose` | `compose.compose_prompt()` | Compose with resolved includes |

#### Graph & Diff

| Method | Path | Maps To | Description |
|--------|------|---------|-------------|
| `GET` | `/api/graph` | `graph.build_graph()` | Get dependency graph as JSON nodes/edges |
| `GET` | `/api/graph/dot` | `graph.generate_dot()` | Get DOT source for client-side rendering |
| `GET` | `/api/prompts/{id}/diff` | `diff.diff_prompt()` | Compare versions (`?old=HEAD~1&new=HEAD`) |

#### System

| Method | Path | Maps To | Description |
|--------|------|---------|-------------|
| `GET` | `/api/manifest` | `listing.parse_manifest()` | Get parsed manifest |
| `GET` | `/api/health` | — | Health check |

### Response Format

All responses use standard HTTP status codes. Successful responses return the resource directly (not wrapped). Errors return:

```json
{
  "detail": "Prompt 'foo' not found",
  "code": "PROMPT_NOT_FOUND"
}
```

### Pydantic Model Reuse

FastAPI response models reference the existing Pydantic models directly:

```python
from prompt_vc.models import PromptMeta, Manifest

@router.get("/prompts/{prompt_id}", response_model=PromptDetailResponse)
async def get_prompt(prompt_id: str):
    ...
```

Where `PromptDetailResponse` composes existing models:

```python
class PromptDetailResponse(BaseModel):
    meta: PromptMeta
    content: str
    prompt_file: str
    meta_file: str
    hash_warnings: list[str] = []
```

---

## Frontend Pages

### 1. Dashboard (`/`)

Overview page with:
- Total prompt count, breakdown by status (production/staging/experimental/deprecated)
- Recent validation issues (top 5)
- Audit compliance summary (pass/fail ratio)
- Quick links to prompts needing attention

### 2. Prompt List (`/prompts`)

Filterable table of all prompts:
- Columns: ID, Name, Domain, Status, Annotations count, Deployed To
- Filters: domain dropdown, status chips, search by ID/name
- Click row → detail view
- "New Prompt" button → creation form

### 3. Prompt Detail (`/prompts/:id`)

Split-pane layout:

**Left pane — Content viewer (CodeMirror)**:
- Syntax-highlighted prompt content
- Annotation gutter markers (click to expand)
- Inline annotation display (togglable)
- Line numbers
- Edit mode toggle (switches to editable CodeMirror)

**Right pane — Metadata panel (tabs)**:
- **Meta**: ID, intent, authors, assumptions, variables, changelog
- **Annotations**: List with anchor preview, rationale, tags, hash status
- **Render**: Variable input form → live preview of rendered output
- **Compose**: Show resolved output with dependency list
- **Diff**: Ref selector (two dropdowns) → side-by-side diff
- **Validation**: Issues for this prompt

### 4. Audit (`/audit`)

- Status filter selector
- Table: Prompt ID, Status, Compliance (pass/fail), Issues list
- Expandable rows showing specific compliance failures
- Summary bar: X of Y prompts compliant

### 5. Graph (`/graph`)

- Interactive dependency graph rendered with D3 or Graphviz WASM
- Nodes colored by status, grouped by domain
- Click node → navigate to prompt detail
- Pan/zoom controls
- Toggle domain groupings on/off

### 6. Validate (`/validate`)

- Run validation across all prompts
- Results table: File, Issues (errors in red, warnings in yellow)
- Filter by severity
- Click issue → navigate to prompt detail

---

## CLI Integration

Add a `serve` command to the CLI:

```python
@main.command()
@click.option("--port", "-p", default=8080, help="Port to serve on")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--dev", is_flag=True, help="Enable dev mode (CORS, auto-reload)")
@click.option("--open", "open_browser", is_flag=True, help="Open browser on start")
def serve(port: int, host: str, dev: bool, open_browser: bool) -> None:
    """Start the prompt-vc web UI."""
    ...
```

In production mode, FastAPI serves the pre-built Vite static assets from a bundled directory. In dev mode, Vite's dev server runs separately and proxies API calls to FastAPI.

---

## Implementation Plan

### Phase 1: API Server

1. Add `fastapi`, `uvicorn` to project dependencies
2. Create `src/prompt_vc/server/app.py` — FastAPI app factory
3. Create `src/prompt_vc/server/deps.py` — shared deps (workspace root resolution)
4. Implement route modules one at a time, reusing existing module functions:
   - `routes/prompts.py` — list, get, create, update
   - `routes/validate.py` — validation endpoints
   - `routes/audit.py` — audit endpoints
   - `routes/render.py` — render endpoint
   - `routes/graph.py` — graph data endpoint
   - `routes/diff.py` — diff endpoint
   - `routes/compose.py` — compose endpoint
5. Add `serve` command to `cli.py`
6. Write API tests using `httpx` + `TestClient`

### Phase 2: Frontend Shell

1. Scaffold React app in `web/` with Vite, TypeScript, Tailwind
2. Set up TanStack Router with route structure
3. Set up TanStack Query with API client
4. Build layout shell (sidebar nav, header)
5. Implement Dashboard page with summary cards
6. Implement Prompt List page with filtering

### Phase 3: Prompt Detail

1. Integrate CodeMirror 6 with read-only prompt display
2. Build annotation gutter plugin (custom CodeMirror extension)
3. Build metadata panel with tab navigation
4. Add annotation creation form (click line → add annotation)
5. Implement edit mode for prompt content
6. Implement edit mode for metadata

### Phase 4: Advanced Features

1. Render preview (variable form → live render)
2. Compose view with dependency display
3. Diff viewer with ref selection
4. Dependency graph visualization
5. Audit page with compliance table
6. Validation page with issue list

### Phase 5: Polish

1. Keyboard shortcuts (Cmd+K search, navigation)
2. File watcher integration (auto-refresh on file changes via SSE or polling)
3. Dark mode (Tailwind's `dark:` variant)
4. Bundle frontend into Python package for `prompt-vc serve`
5. Error boundaries and loading states
6. Responsive layout

---

## Dependencies to Add

### Python (in `pyproject.toml`)

```toml
[project.optional-dependencies]
web = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
]
```

Keep web deps optional — the CLI works without them.

### JavaScript (in `web/package.json`)

```json
{
  "dependencies": {
    "react": "^19.0",
    "react-dom": "^19.0",
    "@tanstack/react-query": "^5.0",
    "@tanstack/react-router": "^1.0",
    "codemirror": "^6.0",
    "@codemirror/lang-markdown": "^6.0",
    "@codemirror/lang-yaml": "^6.0",
    "@viz-js/viz": "^3.0",
    "clsx": "^2.0"
  },
  "devDependencies": {
    "vite": "^6.0",
    "@vitejs/plugin-react": "^4.0",
    "tailwindcss": "^4.0",
    "typescript": "^5.7",
    "@types/react": "^19.0",
    "@types/react-dom": "^19.0"
  }
}
```

---

## Key Design Decisions

### 1. Thin API over existing modules

The server does **no business logic**. Every endpoint is a 5–15 line function that calls into the existing prompt-vc modules and returns the result. This means:
- CLI and web always behave identically
- No logic duplication
- Existing tests cover the core logic

### 2. Optional web dependency

Users who only want the CLI don't install FastAPI. The `serve` command checks for the import and gives a helpful error:

```python
try:
    from prompt_vc.server.app import create_app
except ImportError:
    click.echo("Install web dependencies: pip install prompt-vc[web]")
    raise SystemExit(1)
```

### 3. Static asset bundling

For distribution, `vite build` outputs to `src/prompt_vc/server/static/`. FastAPI mounts this as a static directory. No Node.js needed at runtime.

### 4. No WebSocket complexity

File changes are detected via polling (TanStack Query's `refetchInterval`). A 2-second poll is good enough for a local dev tool and avoids WebSocket infrastructure.

### 5. CodeMirror for annotation UX

The core value proposition of prompt-vc is line-level annotations. CodeMirror 6's extension system supports custom gutter markers, inline widgets, and tooltips — exactly what's needed to show annotation anchors visually.

---

## Open Questions

1. **Graph rendering**: D3 (custom force layout) vs `@viz-js/viz` (Graphviz WASM, uses existing DOT output). Leaning toward viz-js since the DOT generation already exists.
2. **Prompt editing**: Should the web UI support editing prompt files directly, or stay read-only with annotation-only writes? Starting read-only for content, write for annotations/metadata.
3. **Multi-repo support**: Should the server support switching between multiple prompt-vc workspaces? Deferring — v1 serves the current working directory only.
