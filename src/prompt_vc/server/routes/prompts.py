"""Prompt CRUD and listing endpoints."""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...annotate import create_annotation, get_existing_annotation_ids, save_annotation_to_meta
from ...fix_annotations import detect_orphaned_annotations, remove_annotation_from_meta
from ...listing import list_prompts as do_list_prompts
from ...models import PromptMeta
from ...validation import get_hash_warnings
from ...view import load_prompt_and_meta
from ..deps import WorkspaceSettings, get_settings

router = APIRouter(tags=["prompts"])


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
    content: str


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
async def list_prompts(
    domain: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    settings: WorkspaceSettings = Depends(get_settings),
) -> PromptListResponse:
    prompts, used_manifest = do_list_prompts(
        settings.root,
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
async def get_prompt(prompt_id: str) -> PromptDetailResponse:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(prompt_id)

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
async def get_prompt_content(prompt_id: str) -> dict[str, str]:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(prompt_id)
    if meta is None or prompt_path is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    content = prompt_path.read_text(encoding="utf-8")
    return {"content": content}


@router.post("/prompts", status_code=201)
async def create_prompt(
    body: CreatePromptRequest,
    settings: WorkspaceSettings = Depends(get_settings),
) -> dict[str, str]:
    base_dir = settings.root / "prompts"
    if body.domain:
        base_dir = base_dir / body.domain
    base_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = base_dir / f"{body.prompt_id}.prompt.{body.fmt}"
    meta_file = base_dir / f"{body.prompt_id}.prompt.meta.yaml"

    if prompt_file.exists():
        raise HTTPException(status_code=409, detail="Prompt already exists")

    today = datetime.date.today().isoformat()
    prompt_file.write_text(f"# {body.prompt_id}\n\nYour prompt content here.\n", encoding="utf-8")
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

    return {"prompt_id": body.prompt_id, "path": str(prompt_file)}


@router.put("/prompts/{prompt_id}/content")
async def update_content(prompt_id: str, body: UpdateContentRequest) -> dict[str, str]:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(prompt_id)
    if meta is None or prompt_path is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    prompt_path.write_text(body.content, encoding="utf-8")
    return {"status": "updated"}


@router.post(
    "/prompts/{prompt_id}/annotations",
    response_model=AnnotationResponse,
    status_code=201,
)
async def add_annotation(prompt_id: str, body: AddAnnotationRequest) -> AnnotationResponse:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(prompt_id)
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
async def delete_annotation(prompt_id: str, annotation_id: str) -> dict[str, str]:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(prompt_id)
    if meta is None or meta_path is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if not any(a.id == annotation_id for a in meta.annotations):
        raise HTTPException(status_code=404, detail="Annotation not found")

    remove_annotation_from_meta(meta_path, annotation_id)
    return {"status": "deleted"}


@router.post(
    "/prompts/{prompt_id}/fix-annotations",
    response_model=FixAnnotationsResponse,
)
async def fix_annotations(prompt_id: str) -> FixAnnotationsResponse:
    meta_path, prompt_path, meta, issues = load_prompt_and_meta(prompt_id)
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
