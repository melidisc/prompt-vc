"""Prompt CRUD and listing endpoints."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...annotate import create_annotation, get_existing_annotation_ids, save_annotation_to_meta
from ...fix_annotations import detect_orphaned_annotations, remove_annotation_from_meta
from ...listing import find_manifest, parse_manifest
from ...listing import list_prompts as do_list_prompts
from ...models import PromptMeta
from ...validation import get_hash_warnings
from ...view import load_prompt_and_meta
from ..deps import get_workspace_root

router = APIRouter(tags=["prompts"])

MAX_CONTENT_LENGTH = 1_000_000  # 1 MB


# -- Response schemas --


class PromptListItem(BaseModel):
    id: str
    domain: str | None
    path: str
    status: str
    deployed_to: list[str]
    name: str | None


class PromptListResponse(BaseModel):
    prompts: list[PromptListItem]
    from_manifest: bool


class PromptDetailResponse(BaseModel):
    meta: PromptMeta
    content: str
    prompt_file: str
    meta_file: str
    hash_warnings: list[str]


class CreatePromptRequest(BaseModel):
    prompt_id: str
    domain: str | None = None
    fmt: str = "md"


class UpdateContentRequest(BaseModel):
    content: str = Field(max_length=MAX_CONTENT_LENGTH)


class AddAnnotationRequest(BaseModel):
    line: int
    rationale: str | None = None
    source: str | None = None
    tags: list[str] = []
    author: str | None = None


class AnnotationResponse(BaseModel):
    id: str
    message: str


class OrphanedAnnotationItem(BaseModel):
    annotation_id: str
    preview: str
    suggestions: list[dict[str, Any]]


class FixAnnotationsResponse(BaseModel):
    orphaned: list[OrphanedAnnotationItem]


# -- Endpoints --


@router.get("/prompts", response_model=PromptListResponse)
def list_prompts(
    domain: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    root: Path = Depends(get_workspace_root),
) -> PromptListResponse:
    prompts, used_manifest = do_list_prompts(
        root,
        domain_filter=domain,
        status_filter=status,
        owner_filter=owner,
    )
    return PromptListResponse(
        prompts=[
            PromptListItem(
                id=p.id,
                domain=p.domain,
                path=p.path,
                status=p.status,
                deployed_to=p.deployed_to,
                name=p.name,
            )
            for p in prompts
        ],
        from_manifest=used_manifest,
    )


@router.get("/prompts/{prompt_id}", response_model=PromptDetailResponse)
def get_prompt(
    prompt_id: str,
    root: Path = Depends(get_workspace_root),
) -> PromptDetailResponse:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(
        prompt_id, search_path=root,
    )

    if meta is None:
        detail = "; ".join(issues) if issues else "Prompt not found"
        raise HTTPException(status_code=404, detail=detail)

    content = ""
    if prompt_path and prompt_path.exists():
        content = prompt_path.read_text(encoding="utf-8")

    warnings: list[str] = []
    if prompt_path and meta.annotations:
        warnings = get_hash_warnings(meta, prompt_path)

    return PromptDetailResponse(
        meta=meta,
        content=content,
        prompt_file=str(prompt_path) if prompt_path else "",
        meta_file=str(meta_path) if meta_path else "",
        hash_warnings=warnings,
    )


@router.get("/prompts/{prompt_id}/content")
def get_prompt_content(
    prompt_id: str,
    root: Path = Depends(get_workspace_root),
) -> dict[str, str]:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(
        prompt_id, search_path=root,
    )
    if meta is None or prompt_path is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    content = prompt_path.read_text(encoding="utf-8")
    return {"content": content}


@router.post("/prompts", status_code=201)
def create_prompt(
    body: CreatePromptRequest,
    root: Path = Depends(get_workspace_root),
) -> dict[str, str]:
    base_dir = root / "prompts"
    if body.domain:
        base_dir = base_dir / body.domain
    base_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = base_dir / f"{body.prompt_id}.prompt.{body.fmt}"
    meta_file = base_dir / f"{body.prompt_id}.prompt.meta.yaml"

    if prompt_file.exists():
        raise HTTPException(status_code=409, detail="Prompt already exists")

    today = datetime.date.today().isoformat()
    prompt_file.write_text(
        f"# {body.prompt_id}\n\nYour prompt content here.\n", encoding="utf-8",
    )
    meta_file.write_text(
        f'schema_version: "1.0"\n\n'
        f"id: {body.prompt_id}\n"
        f"name: {body.prompt_id.replace('-', ' ').title()}\n"
        f'created: "{today}"\n'
        f"authors: []\n\n"
        f"intent: |\n  Describe what this prompt should accomplish.\n\n"
        f"annotations: []\n",
        encoding="utf-8",
    )

    # Update manifest if one exists
    _add_prompt_to_manifest(root, body.prompt_id, body.domain, body.fmt)

    return {"prompt_id": body.prompt_id, "path": str(prompt_file)}


def _add_prompt_to_manifest(
    root: Path, prompt_id: str, domain: str | None, fmt: str,
) -> None:
    """Best-effort: append new prompt to manifest if one exists."""
    manifest_path = find_manifest(root)
    if manifest_path is None:
        return

    manifest, err = parse_manifest(manifest_path)
    if manifest is None:
        return

    rel_path = f"{domain}/{prompt_id}.prompt.{fmt}" if domain else f"{prompt_id}.prompt.{fmt}"
    target_domain = domain or "default"

    # Avoid duplicate
    if target_domain in manifest.domains:
        for ref in manifest.domains[target_domain].prompts:
            if ref.id == prompt_id:
                return

    # Load raw YAML to preserve formatting
    with open(manifest_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return

    domains = raw.setdefault("domains", {})
    dom_data = domains.setdefault(target_domain, {"prompts": []})
    prompts_list = dom_data.setdefault("prompts", [])
    prompts_list.append({"id": prompt_id, "path": rel_path, "status": "experimental"})

    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


@router.put("/prompts/{prompt_id}/content")
def update_content(
    prompt_id: str,
    body: UpdateContentRequest,
    root: Path = Depends(get_workspace_root),
) -> dict[str, str]:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(
        prompt_id, search_path=root,
    )
    if meta is None or prompt_path is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    prompt_path.write_text(body.content, encoding="utf-8")
    return {"status": "updated"}


@router.post(
    "/prompts/{prompt_id}/annotations",
    response_model=AnnotationResponse,
    status_code=201,
)
def add_annotation(
    prompt_id: str,
    body: AddAnnotationRequest,
    root: Path = Depends(get_workspace_root),
) -> AnnotationResponse:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(
        prompt_id, search_path=root,
    )
    if meta is None or prompt_path is None or meta_path is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    content = prompt_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    if body.line < 1 or body.line > len(lines):
        msg = f"Invalid line number: {body.line} (file has {len(lines)} lines)"
        raise HTTPException(status_code=400, detail=msg)

    line_text = lines[body.line - 1]
    existing_ids = get_existing_annotation_ids(meta)

    annotation = create_annotation(
        line_text=line_text,
        line_number=body.line,
        rationale=body.rationale,
        source=body.source,
        tags=body.tags,
        author=body.author,
        existing_ids=existing_ids,
    )
    save_annotation_to_meta(meta_path, annotation)

    return AnnotationResponse(
        id=annotation.id,
        message=f"Created annotation {annotation.id} for line {body.line}",
    )


@router.delete("/prompts/{prompt_id}/annotations/{annotation_id}")
def delete_annotation(
    prompt_id: str,
    annotation_id: str,
    root: Path = Depends(get_workspace_root),
) -> dict[str, str]:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(
        prompt_id, search_path=root,
    )
    if meta is None or meta_path is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if not any(a.id == annotation_id for a in meta.annotations):
        raise HTTPException(status_code=404, detail="Annotation not found")

    remove_annotation_from_meta(meta_path, annotation_id)
    return {"status": "deleted"}


@router.get(
    "/prompts/{prompt_id}/orphaned-annotations",
    response_model=FixAnnotationsResponse,
)
def get_orphaned_annotations(
    prompt_id: str,
    root: Path = Depends(get_workspace_root),
) -> FixAnnotationsResponse:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(
        prompt_id, search_path=root,
    )
    if meta is None or prompt_path is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    orphaned = detect_orphaned_annotations(meta, prompt_path)
    items = []
    for o in orphaned:
        items.append(
            OrphanedAnnotationItem(
                annotation_id=o.annotation.id,
                preview=o.annotation.anchor.preview,
                suggestions=[
                    {"line": ln, "text": txt, "similarity": round(sim, 2)}
                    for ln, txt, sim in o.suggestions
                ],
            )
        )

    return FixAnnotationsResponse(orphaned=items)
