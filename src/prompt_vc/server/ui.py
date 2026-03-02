"""HTML UI routes for the prompt-vc web dashboard."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..annotate import create_annotation, get_existing_annotation_ids, save_annotation_to_meta
from ..compose import compose_prompt
from ..diff import diff_prompt
from ..fix_annotations import detect_orphaned_annotations, remove_annotation_from_meta
from ..graph import build_graph, generate_dot
from ..listing import list_prompts as do_list_prompts
from ..render import render_prompt
from ..validation import get_hash_warnings, validate_all
from ..view import load_prompt_and_meta
from .deps import get_workspace_root

_PROMPT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
MAX_CONTENT_LENGTH = 1_048_576  # 1 MB


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _validate_prompt_id(prompt_id: str) -> None:
    """Reject prompt IDs that could enable path traversal."""
    if not _PROMPT_ID_RE.match(prompt_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid prompt ID. Use only lowercase letters, numbers, and hyphens.",
        )


def create_ui_router(templates: Jinja2Templates) -> APIRouter:
    """Create the /ui/ router with all HTML page and fragment routes."""
    router = APIRouter(prefix="/ui", default_response_class=HTMLResponse)

    def _ctx(request: Request, **kwargs: Any) -> dict[str, Any]:
        """Build template context with request and extra data."""
        return {"request": request, **kwargs}

    def _flash_oob(flash_type: str, flash_message: str) -> str:
        """Render an OOB flash fragment safe for concatenation after primary content."""
        return templates.get_template("partials/flash.html").render(
            flash_type=flash_type, flash_message=flash_message
        )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @router.get("/", name="ui_dashboard")
    def dashboard(
        request: Request,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        prompts, from_manifest = do_list_prompts(search_path=workspace)

        domains = {p.domain for p in prompts if p.domain}

        return templates.TemplateResponse(
            "dashboard.html",
            _ctx(
                request,
                active_page="dashboard",
                prompts=prompts,
                prompt_count=len(prompts),
                domain_count=len(domains),
            ),
        )

    # ------------------------------------------------------------------
    # Dashboard validation fragment (lazy-loaded via HTMX)
    # ------------------------------------------------------------------
    @router.get("/validation-summary", name="ui_validation_summary")
    def validation_summary(
        request: Request,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        results = validate_all(path=workspace)
        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)

        return templates.TemplateResponse(
            "partials/validation_summary.html",
            _ctx(
                request,
                validation_results=results,
                total_errors=total_errors,
                total_warnings=total_warnings,
            ),
        )

    # ------------------------------------------------------------------
    # Prompt List
    # ------------------------------------------------------------------
    @router.get("/prompts", name="ui_prompt_list")
    def prompt_list(
        request: Request,
        domain: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        # Always load all prompts first, then filter in Python
        all_prompts, from_manifest = do_list_prompts(search_path=workspace)

        # Apply filters
        filtered = all_prompts
        if domain:
            filtered = [p for p in filtered if p.domain == domain]
        if status:
            filtered = [p for p in filtered if p.status == status]
        if owner:
            filtered = [p for p in filtered if any(owner.lower() in o.lower() for o in p.owners)]

        # For HTMX partial swap, return just the table body
        if _is_htmx(request):
            return templates.TemplateResponse(
                "partials/prompt_table_body.html",
                _ctx(request, prompts=filtered),
            )

        domains = sorted({p.domain for p in all_prompts if p.domain})
        statuses = sorted({p.status for p in all_prompts if p.status})

        return templates.TemplateResponse(
            "prompt_list.html",
            _ctx(
                request,
                active_page="prompts",
                prompts=filtered,
                from_manifest=from_manifest,
                domains=domains,
                statuses=statuses,
                filters={"domain": domain, "status": status, "owner": owner},
            ),
        )

    # ------------------------------------------------------------------
    # Create Prompt
    # ------------------------------------------------------------------
    @router.get("/prompts/new", name="ui_prompt_new_form")
    def prompt_new_form(request: Request) -> Response:
        return templates.TemplateResponse(
            "prompt_new.html",
            _ctx(request, active_page="prompts"),
        )

    @router.post("/prompts/new", name="ui_prompt_new")
    def prompt_new(
        request: Request,
        prompt_id: str = Form(...),
        domain: str = Form(""),
        fmt: str = Form("md"),
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        _validate_prompt_id(prompt_id)

        domain_dir = domain if domain else None
        if domain_dir:
            _validate_prompt_id(domain_dir)  # domain must also be safe
            base_dir = workspace / "prompts" / domain_dir
        else:
            base_dir = workspace / "prompts"
        base_dir.mkdir(parents=True, exist_ok=True)

        prompt_file = base_dir / f"{prompt_id}.prompt.{fmt}"
        meta_file = base_dir / f"{prompt_id}.prompt.meta.yaml"

        # Check if prompt already exists
        if prompt_file.exists() or meta_file.exists():
            return templates.TemplateResponse(
                "prompt_new.html",
                _ctx(
                    request,
                    active_page="prompts",
                    error=f"Prompt '{prompt_id}' already exists.",
                ),
                status_code=409,
            )

        prompt_file.write_text(f"# {prompt_id}\n\nYour prompt content here.\n")
        meta_content = (
            f"schema_version: '1.0'\n"
            f"id: {prompt_id}\n"
            f"name: {prompt_id}\n"
            f"created: '{datetime.date.today().isoformat()}'\n"
            f"authors: []\n"
            f"intent: ''\n"
            f"annotations: []\n"
        )
        meta_file.write_text(meta_content)

        return RedirectResponse(url=f"/ui/prompts/{prompt_id}", status_code=303)

    # ------------------------------------------------------------------
    # Prompt Detail
    # ------------------------------------------------------------------
    @router.get("/prompts/{prompt_id}", name="ui_prompt_detail")
    def prompt_detail(
        request: Request,
        prompt_id: str,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        meta_path, prompt_path, meta, errors = load_prompt_and_meta(
            prompt_id, search_path=workspace
        )
        if meta is None:
            return HTMLResponse(
                content="<h1>Prompt not found</h1><p><a href='/ui/prompts'>Back to prompts</a></p>",
                status_code=404,
            )

        content = ""
        content_lines: list[dict[str, Any]] = []
        prompt_file_str = ""
        if prompt_path and prompt_path.exists():
            content = prompt_path.read_text()
            prompt_file_str = str(prompt_path.relative_to(workspace))
            for i, line_text in enumerate(content.splitlines(), 1):
                content_lines.append({"num": i, "text": line_text})

        hash_warnings: list[str] = []
        if prompt_path and prompt_path.exists():
            hash_warnings = get_hash_warnings(meta, prompt_path)

        # Build set of annotated line numbers and line->annotations mapping
        annotated_lines: set[int] = set()
        annotations_by_line: dict[int, list[Any]] = {}
        for ann in meta.annotations:
            if ann.anchor.line_hint:
                annotated_lines.add(ann.anchor.line_hint)
                annotations_by_line.setdefault(ann.anchor.line_hint, []).append(ann)

        meta_file_str = str(meta_path.relative_to(workspace)) if meta_path else ""

        return templates.TemplateResponse(
            "prompt_detail.html",
            _ctx(
                request,
                active_page="prompts",
                meta=meta,
                prompt_id=prompt_id,
                content=content,
                content_lines=content_lines,
                prompt_file=prompt_file_str,
                meta_file=meta_file_str,
                hash_warnings=hash_warnings,
                annotated_lines=annotated_lines,
                annotations_by_line=annotations_by_line,
            ),
        )

    # ------------------------------------------------------------------
    # Prompt Editor
    # ------------------------------------------------------------------
    @router.get("/prompts/{prompt_id}/edit", name="ui_prompt_edit_form")
    def prompt_edit_form(
        request: Request,
        prompt_id: str,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        meta_path, prompt_path, meta, errors = load_prompt_and_meta(
            prompt_id, search_path=workspace
        )
        if meta is None:
            return HTMLResponse(
                content="<h1>Prompt not found</h1><p><a href='/ui/prompts'>Back to prompts</a></p>",
                status_code=404,
            )

        content = ""
        prompt_file_str = ""
        if prompt_path and prompt_path.exists():
            content = prompt_path.read_text()
            prompt_file_str = str(prompt_path.relative_to(workspace))

        return templates.TemplateResponse(
            "prompt_editor.html",
            _ctx(
                request,
                active_page="prompts",
                meta=meta,
                prompt_id=prompt_id,
                content=content,
                prompt_file=prompt_file_str,
            ),
        )

    @router.post("/prompts/{prompt_id}/edit", name="ui_prompt_edit")
    def prompt_edit(
        request: Request,
        prompt_id: str,
        content: str = Form(..., max_length=MAX_CONTENT_LENGTH),
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        meta_path, prompt_path, _meta, _errors = load_prompt_and_meta(
            prompt_id, search_path=workspace
        )
        if not prompt_path or not prompt_path.exists():
            return HTMLResponse(
                content="<h1>Prompt file not found</h1>"
                "<p><a href='/ui/prompts'>Back to prompts</a></p>",
                status_code=404,
            )

        prompt_path.write_text(content)
        return RedirectResponse(url=f"/ui/prompts/{prompt_id}", status_code=303)

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------
    @router.post("/prompts/{prompt_id}/annotations", name="ui_annotation_add")
    def annotation_add(
        request: Request,
        prompt_id: str,
        line: int = Form(...),
        rationale: str = Form(""),
        source: str = Form(""),
        tags: str = Form(""),
        author: str = Form(""),
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        meta_path, prompt_path, meta, errors = load_prompt_and_meta(
            prompt_id, search_path=workspace
        )

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        if prompt_path and meta_path and meta:
            lines = prompt_path.read_text().splitlines()
            if 1 <= line <= len(lines):
                line_text = lines[line - 1]
                existing_ids = get_existing_annotation_ids(meta)
                ann = create_annotation(
                    line_text=line_text,
                    line_number=line,
                    rationale=rationale or None,
                    source=source or None,
                    tags=tag_list or None,
                    author=author or None,
                    existing_ids=existing_ids,
                )
                save_annotation_to_meta(meta_path, ann)

        detail_url = f"/ui/prompts/{prompt_id}"

        if _is_htmx(request):
            # Tell HTMX to do a client-side redirect back to the detail page
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = detail_url
            return response

        return RedirectResponse(url=detail_url, status_code=303)

    @router.delete(
        "/prompts/{prompt_id}/annotations/{annotation_id}",
        name="ui_annotation_delete",
    )
    def annotation_delete(
        request: Request,
        prompt_id: str,
        annotation_id: str,
        workspace: Path = Depends(get_workspace_root),
    ) -> HTMLResponse:
        meta_path, _prompt_path, _meta, _errors = load_prompt_and_meta(
            prompt_id, search_path=workspace
        )
        if meta_path:
            remove_annotation_from_meta(meta_path, annotation_id)

        # Return empty primary content (removes the card) + flash OOB
        flash_html = _flash_oob("success", "Annotation removed.")
        return HTMLResponse("" + flash_html)

    @router.get("/prompts/{prompt_id}/orphaned", name="ui_orphaned_annotations")
    def orphaned_annotations(
        request: Request,
        prompt_id: str,
        workspace: Path = Depends(get_workspace_root),
    ) -> HTMLResponse:
        meta_path, prompt_path, meta, _errors = load_prompt_and_meta(
            prompt_id, search_path=workspace
        )
        orphans: list[Any] = []
        if meta and prompt_path and prompt_path.exists():
            orphans = detect_orphaned_annotations(meta, prompt_path)

        return templates.TemplateResponse(
            "partials/orphaned_list.html",
            _ctx(request, orphans=orphans),
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @router.get("/validate", name="ui_validate")
    def validation_page(
        request: Request,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        results = validate_all(path=workspace)
        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)

        return templates.TemplateResponse(
            "validation.html",
            _ctx(
                request,
                active_page="validate",
                results=results,
                total_errors=total_errors,
                total_warnings=total_warnings,
            ),
        )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    @router.get("/audit", name="ui_audit")
    def audit_page(
        request: Request,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        from ..audit import run_audit

        error: str | None = None
        report = None
        try:
            report = run_audit(search_path=workspace)
            if report.error:
                error = report.error
        except Exception as exc:
            error = str(exc)

        return templates.TemplateResponse(
            "audit.html",
            _ctx(
                request,
                active_page="audit",
                report=report,
                error=error,
            ),
        )

    # ------------------------------------------------------------------
    # Render Preview
    # ------------------------------------------------------------------
    @router.get("/prompts/{prompt_id}/render", name="ui_render_form")
    def render_form(
        request: Request,
        prompt_id: str,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        meta_path, _prompt_path, meta, _errors = load_prompt_and_meta(
            prompt_id, search_path=workspace
        )
        variables = meta.variables if meta else {}

        return templates.TemplateResponse(
            "render_preview.html",
            _ctx(
                request,
                active_page="prompts",
                prompt_id=prompt_id,
                variables=variables,
                rendered_content=None,
                template_engine=None,
                variables_used=None,
                render_error=None,
            ),
        )

    @router.post("/prompts/{prompt_id}/render", name="ui_render")
    async def render_execute(
        request: Request,
        prompt_id: str,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        form_data = await request.form()
        context: dict[str, Any] = {}
        for key, value in form_data.items():
            if key.startswith("var:"):
                var_name = key[4:]
                context[var_name] = value

        render_error: str | None = None
        rendered_content: str | None = None
        template_engine: str | None = None
        variables_used: list[str] | None = None

        try:
            result = render_prompt(prompt_id, context=context, search_path=workspace)
            if result.error:
                render_error = result.error
            else:
                rendered_content = result.rendered_content
                template_engine = result.template_engine
                variables_used = result.variables_used
        except Exception as exc:
            render_error = str(exc)

        return templates.TemplateResponse(
            "partials/render_output.html",
            _ctx(
                request,
                rendered_content=rendered_content,
                template_engine=template_engine,
                variables_used=variables_used,
                render_error=render_error,
            ),
        )

    # ------------------------------------------------------------------
    # Compose View
    # ------------------------------------------------------------------
    @router.get("/prompts/{prompt_id}/compose", name="ui_compose")
    def compose_view(
        request: Request,
        prompt_id: str,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        error: str | None = None
        composed_content = ""
        dependencies: list[Any] = []
        resolved_prompts: list[str] = []

        try:
            result = compose_prompt(prompt_id, search_path=workspace)
            if result.error:
                error = result.error
            else:
                composed_content = result.composed_content
                dependencies = result.dependencies
                resolved_prompts = result.resolved_prompts
        except Exception as exc:
            error = str(exc)

        return templates.TemplateResponse(
            "compose_view.html",
            _ctx(
                request,
                active_page="prompts",
                prompt_id=prompt_id,
                composed_content=composed_content,
                dependencies=dependencies,
                resolved_prompts=resolved_prompts,
                error=error,
            ),
        )

    # ------------------------------------------------------------------
    # Diff Viewer
    # ------------------------------------------------------------------
    @router.get("/prompts/{prompt_id}/diff", name="ui_diff")
    def diff_view(
        request: Request,
        prompt_id: str,
        old: str = "HEAD~1",
        new: str = "HEAD",
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        diff_error: str | None = None
        line_diffs: list[Any] | None = None
        annotation_changes: list[Any] = []
        prompt_path = ""

        # Only run diff if this is an HTMX request or has explicit query params
        run_diff = _is_htmx(request) or request.query_params.get("old") is not None

        if run_diff:
            try:
                result = diff_prompt(prompt_id, old_ref=old, new_ref=new, search_path=workspace)
                if result.error:
                    diff_error = result.error
                else:
                    line_diffs = result.line_diffs
                    annotation_changes = result.annotation_changes
                    prompt_path = result.prompt_path
            except Exception as exc:
                diff_error = str(exc)

        if _is_htmx(request):
            return templates.TemplateResponse(
                "partials/diff_output.html",
                _ctx(
                    request,
                    diff_error=diff_error,
                    line_diffs=line_diffs,
                    annotation_changes=annotation_changes,
                    prompt_path=prompt_path,
                    old_ref=old,
                    new_ref=new,
                ),
            )

        return templates.TemplateResponse(
            "diff_viewer.html",
            _ctx(
                request,
                active_page="prompts",
                prompt_id=prompt_id,
                old_ref=old,
                new_ref=new,
                diff_error=diff_error,
                line_diffs=line_diffs,
                annotation_changes=annotation_changes,
                prompt_path=prompt_path,
            ),
        )

    # ------------------------------------------------------------------
    # Graph
    # ------------------------------------------------------------------
    @router.get("/graph", name="ui_graph")
    def graph_page(
        request: Request,
        workspace: Path = Depends(get_workspace_root),
    ) -> Response:
        error: str | None = None
        dot_source: str | None = None

        try:
            graph = build_graph(search_path=workspace)
            if graph.error:
                error = graph.error
            else:
                dot_source = generate_dot(graph, title="Prompt Dependencies")
        except Exception as exc:
            error = str(exc)

        return templates.TemplateResponse(
            "graph.html",
            _ctx(
                request,
                active_page="graph",
                dot_source=dot_source,
                error=error,
            ),
        )

    return router
