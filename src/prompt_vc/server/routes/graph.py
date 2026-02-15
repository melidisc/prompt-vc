"""Graph endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ...graph import build_graph, generate_dot
from ..deps import WorkspaceSettings, get_settings

router = APIRouter(tags=["graph"])


class GraphNodeResponse(BaseModel):
    id: str
    label: str
    node_type: str
    domain: str | None
    status: str | None


class GraphEdgeResponse(BaseModel):
    from_id: str
    to_id: str
    edge_type: str
    note: str | None


class GraphResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    no_domains: bool = False,
    settings: WorkspaceSettings = Depends(get_settings),
) -> GraphResponse:
    result = build_graph(search_path=settings.root, include_domains=not no_domains)

    if result.error:
        raise HTTPException(status_code=400, detail=result.error)

    return GraphResponse(
        nodes=[
            GraphNodeResponse(
                id=n.id,
                label=n.label,
                node_type=n.node_type,
                domain=n.domain,
                status=n.status,
            )
            for n in result.nodes
        ],
        edges=[
            GraphEdgeResponse(
                from_id=e.from_id,
                to_id=e.to_id,
                edge_type=e.edge_type,
                note=e.note,
            )
            for e in result.edges
        ],
    )


@router.get("/graph/dot", response_class=PlainTextResponse)
async def get_graph_dot(
    title: str = "Prompt Dependencies",
    no_domains: bool = False,
    settings: WorkspaceSettings = Depends(get_settings),
) -> str:
    result = build_graph(search_path=settings.root, include_domains=not no_domains)

    if result.error:
        raise HTTPException(status_code=400, detail=result.error)

    return generate_dot(result, title=title)
