"""Generate dependency graphs for prompt relationships."""

from dataclasses import dataclass, field
from pathlib import Path

from .listing import find_manifest, parse_manifest
from .models import Manifest


@dataclass
class GraphNode:
    """A node in the dependency graph."""

    id: str
    label: str
    node_type: str  # "prompt", "domain"
    domain: str | None = None
    status: str | None = None


@dataclass
class GraphEdge:
    """An edge in the dependency graph."""

    from_id: str
    to_id: str
    edge_type: str  # "contains", "depends_on", "replaces", "variant_of", "derived_from"
    note: str | None = None


@dataclass
class DependencyGraph:
    """Complete dependency graph for prompt relationships."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    error: str | None = None


def build_graph(
    search_path: Path | None = None,
    include_domains: bool = True,
) -> DependencyGraph:
    """Build a dependency graph from the manifest.

    Args:
        search_path: Directory to search for manifest
        include_domains: Whether to include domain nodes as containers

    Returns:
        DependencyGraph with nodes and edges
    """
    manifest_path = find_manifest(search_path)
    if not manifest_path:
        return DependencyGraph(error="No manifest found")

    manifest, error = parse_manifest(manifest_path)
    if error or manifest is None:
        return DependencyGraph(error=error or "Failed to parse manifest")

    return _build_graph_from_manifest(manifest, include_domains)


def _build_graph_from_manifest(
    manifest: Manifest,
    include_domains: bool,
) -> DependencyGraph:
    """Build graph from a parsed manifest."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    prompt_ids: set[str] = set()

    # Add domain and prompt nodes
    for domain_name, domain in manifest.domains.items():
        if include_domains:
            nodes.append(
                GraphNode(
                    id=f"domain:{domain_name}",
                    label=domain_name,
                    node_type="domain",
                )
            )

        for prompt_ref in domain.prompts:
            prompt_ids.add(prompt_ref.id)
            nodes.append(
                GraphNode(
                    id=prompt_ref.id,
                    label=prompt_ref.id,
                    node_type="prompt",
                    domain=domain_name,
                    status=prompt_ref.status,
                )
            )

            if include_domains:
                edges.append(
                    GraphEdge(
                        from_id=f"domain:{domain_name}",
                        to_id=prompt_ref.id,
                        edge_type="contains",
                    )
                )

    # Add relationship edges
    for rel in manifest.relationships:
        edges.append(
            GraphEdge(
                from_id=rel.from_,
                to_id=rel.to,
                edge_type=rel.type,
                note=rel.note,
            )
        )

        # Add missing nodes for relationships referencing external prompts
        if rel.from_ not in prompt_ids:
            nodes.append(
                GraphNode(
                    id=rel.from_,
                    label=f"{rel.from_} (external)",
                    node_type="prompt",
                )
            )
            prompt_ids.add(rel.from_)

        if rel.to not in prompt_ids:
            nodes.append(
                GraphNode(
                    id=rel.to,
                    label=f"{rel.to} (external)",
                    node_type="prompt",
                )
            )
            prompt_ids.add(rel.to)

    return DependencyGraph(nodes=nodes, edges=edges)


def generate_dot(graph: DependencyGraph, title: str = "Prompt Dependencies") -> str:
    """Generate DOT format output for the graph.

    Args:
        graph: The dependency graph
        title: Title for the graph

    Returns:
        DOT format string
    """
    escaped_title = _escape_dot_string(title)
    lines = [
        "digraph prompt_dependencies {",
        f'    label="{escaped_title}";',
        "    labelloc=t;",
        "    fontsize=16;",
        "    rankdir=TB;",
        "    node [fontname=Helvetica];",
        "    edge [fontname=Helvetica];",
        "",
    ]

    # Define node styles
    lines.append("    // Node styles")
    lines.append('    node [shape=box, style=filled, fillcolor="#e8f4f8"];')
    lines.append("")

    # Group prompts by domain using subgraphs
    domains: dict[str | None, list[GraphNode]] = {}
    for node in graph.nodes:
        if node.node_type == "prompt":
            domain = node.domain
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(node)

    # Add domain subgraphs
    for domain, prompts in domains.items():
        if domain:
            escaped_domain = _escape_dot_string(domain)
            lines.append(f"    subgraph cluster_{_sanitize_id(domain)} {{")
            lines.append(f'        label="{escaped_domain}";')
            lines.append("        style=filled;")
            lines.append('        fillcolor="#f5f5f5";')
            lines.append("")

            for node in prompts:
                node_style = _get_node_style(node)
                lines.append(f'        "{_sanitize_id(node.id)}" [{node_style}];')

            lines.append("    }")
            lines.append("")
        else:
            # External/orphan prompts
            for node in prompts:
                node_style = _get_node_style(node)
                lines.append(f'    "{_sanitize_id(node.id)}" [{node_style}];')

    # Add edges
    lines.append("")
    lines.append("    // Edges")
    for edge in graph.edges:
        if edge.edge_type == "contains":
            continue  # Skip containment edges (handled by subgraphs)

        edge_style = _get_edge_style(edge)
        lines.append(
            f'    "{_sanitize_id(edge.from_id)}" -> "{_sanitize_id(edge.to_id)}" [{edge_style}];'
        )

    lines.append("}")
    return "\n".join(lines)


def _sanitize_id(id_str: str) -> str:
    """Sanitize an ID for DOT format."""
    return id_str.replace("-", "_").replace(":", "_").replace(".", "_")


def _escape_dot_string(s: str) -> str:
    """Escape a string for use in DOT format."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _get_node_style(node: GraphNode) -> str:
    """Get DOT style attributes for a node."""
    escaped_label = _escape_dot_string(node.label)
    parts = [f'label="{escaped_label}"']

    if node.node_type == "domain":
        parts.append("shape=folder")
        parts.append('fillcolor="#d4edda"')
    elif node.status == "production":
        parts.append('fillcolor="#c3e6cb"')  # Green for production
    elif node.status == "staging":
        parts.append('fillcolor="#fff3cd"')  # Yellow for staging
    elif node.status == "deprecated":
        parts.append('fillcolor="#f5c6cb"')  # Red for deprecated
        parts.append('style="filled,dashed"')  # Preserve fill with dashed border

    return ", ".join(parts)


def _get_edge_style(edge: GraphEdge) -> str:
    """Get DOT style attributes for an edge."""
    parts = []

    edge_styles = {
        "depends_on": ('color="#007bff"', 'label="depends on"'),
        "replaces": ('color="#dc3545"', 'label="replaces"', "style=bold"),
        "variant_of": ('color="#6c757d"', 'label="variant of"', "style=dashed"),
        "derived_from": ('color="#17a2b8"', 'label="derived from"'),
    }

    if edge.edge_type in edge_styles:
        parts.extend(edge_styles[edge.edge_type])
    else:
        parts.append(f'label="{edge.edge_type}"')

    if edge.note:
        # Append note to label
        existing_label = next((p for p in parts if p.startswith("label=")), None)
        if existing_label:
            parts.remove(existing_label)
            label_value = existing_label.split("=")[1].strip('"')
            escaped_note = _escape_dot_string(edge.note)
            parts.append(f'label="{label_value}\\n({escaped_note})"')

    return ", ".join(parts)


def render_graph(
    graph: DependencyGraph,
    output_path: Path,
    output_format: str = "png",
    title: str = "Prompt Dependencies",
) -> tuple[bool, str]:
    """Render graph to an image file using graphviz.

    Args:
        graph: The dependency graph
        output_path: Path for output file
        output_format: Output format (png, svg, pdf)
        title: Title for the graph

    Returns:
        Tuple of (success, message)
    """
    try:
        import graphviz
    except ImportError:
        return False, "graphviz package not installed. Install with: pip install graphviz"

    dot_source = generate_dot(graph, title=title)

    try:
        # Create graphviz Source object
        source = graphviz.Source(dot_source)

        # Render to file
        output_stem = str(output_path.with_suffix(""))
        source.render(
            output_stem,
            format=output_format,
            cleanup=True,  # Remove intermediate DOT file
        )

        return True, f"Graph rendered to {output_path}"
    except graphviz.ExecutableNotFound:
        return False, "Graphviz executable not found. Install graphviz system package."
    except (OSError, ValueError) as e:
        return False, f"Failed to render graph: {e}"
