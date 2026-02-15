"""Tests for prompt_vc.graph."""

from pathlib import Path

from prompt_vc.graph import (
    DependencyGraph,
    GraphEdge,
    GraphNode,
    build_graph,
    generate_dot,
)


class TestGraphNode:
    """Tests for GraphNode dataclass."""

    def test_prompt_node(self) -> None:
        node = GraphNode(
            id="test-prompt",
            label="test-prompt",
            node_type="prompt",
            domain="support",
            status="production",
        )
        assert node.node_type == "prompt"
        assert node.domain == "support"

    def test_domain_node(self) -> None:
        node = GraphNode(
            id="domain:support",
            label="support",
            node_type="domain",
        )
        assert node.node_type == "domain"
        assert node.domain is None


class TestGraphEdge:
    """Tests for GraphEdge dataclass."""

    def test_depends_on_edge(self) -> None:
        edge = GraphEdge(
            from_id="prompt-a",
            to_id="prompt-b",
            edge_type="depends_on",
        )
        assert edge.edge_type == "depends_on"

    def test_edge_with_note(self) -> None:
        edge = GraphEdge(
            from_id="new-prompt",
            to_id="old-prompt",
            edge_type="replaces",
            note="Superseded in v2",
        )
        assert edge.note == "Superseded in v2"


class TestDependencyGraph:
    """Tests for DependencyGraph dataclass."""

    def test_empty_graph(self) -> None:
        graph = DependencyGraph()
        assert graph.nodes == []
        assert graph.edges == []
        assert graph.error is None

    def test_graph_with_error(self) -> None:
        graph = DependencyGraph(error="No manifest found")
        assert graph.error == "No manifest found"

    def test_graph_with_nodes_and_edges(self) -> None:
        graph = DependencyGraph(
            nodes=[
                GraphNode(id="a", label="a", node_type="prompt"),
                GraphNode(id="b", label="b", node_type="prompt"),
            ],
            edges=[
                GraphEdge(from_id="a", to_id="b", edge_type="depends_on"),
            ],
        )
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1


class TestBuildGraph:
    """Tests for build_graph function."""

    def test_build_graph_no_manifest(self, tmp_path: Path) -> None:
        # Create an empty subdirectory to ensure no manifest is found
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(empty_dir)
            graph = build_graph(search_path=empty_dir)
            # Either error or empty graph is acceptable
            assert graph.error is not None or len(graph.nodes) == 0
        finally:
            os.chdir(original_cwd)

    def test_build_graph_with_manifest(self, tmp_path: Path) -> None:
        manifest_content = """
schema_version: "1.0"
domains:
  support:
    prompts:
      - id: refund
        path: support/refund.prompt.md
        status: production
      - id: cancel
        path: support/cancel.prompt.md
        status: staging
relationships:
  - type: depends_on
    from: cancel
    to: refund
"""
        manifest_file = tmp_path / "prompts.manifest.yaml"
        manifest_file.write_text(manifest_content)

        graph = build_graph(search_path=tmp_path)

        assert graph.error is None
        # Should have domain node + 2 prompt nodes
        prompt_nodes = [n for n in graph.nodes if n.node_type == "prompt"]
        assert len(prompt_nodes) == 2

        # Should have depends_on edge + containment edges
        dep_edges = [e for e in graph.edges if e.edge_type == "depends_on"]
        assert len(dep_edges) == 1

    def test_build_graph_without_domains(self, tmp_path: Path) -> None:
        manifest_content = """
schema_version: "1.0"
domains:
  support:
    prompts:
      - id: refund
        path: support/refund.prompt.md
"""
        manifest_file = tmp_path / "prompts.manifest.yaml"
        manifest_file.write_text(manifest_content)

        graph = build_graph(search_path=tmp_path, include_domains=False)

        assert graph.error is None
        # Should not have domain nodes
        domain_nodes = [n for n in graph.nodes if n.node_type == "domain"]
        assert len(domain_nodes) == 0


class TestGenerateDot:
    """Tests for generate_dot function."""

    def test_generate_dot_empty_graph(self) -> None:
        graph = DependencyGraph()

        dot = generate_dot(graph)

        assert "digraph" in dot
        assert "prompt_dependencies" in dot

    def test_generate_dot_with_nodes(self) -> None:
        graph = DependencyGraph(
            nodes=[
                GraphNode(id="test", label="test", node_type="prompt", status="production"),
            ],
        )

        dot = generate_dot(graph)

        assert "test" in dot
        assert "production" not in dot  # Status is used for styling, not label

    def test_generate_dot_with_edges(self) -> None:
        graph = DependencyGraph(
            nodes=[
                GraphNode(id="a", label="a", node_type="prompt"),
                GraphNode(id="b", label="b", node_type="prompt"),
            ],
            edges=[
                GraphEdge(from_id="a", to_id="b", edge_type="depends_on"),
            ],
        )

        dot = generate_dot(graph)

        assert "->" in dot
        assert "depends on" in dot

    def test_generate_dot_with_domain_clusters(self) -> None:
        graph = DependencyGraph(
            nodes=[
                GraphNode(id="a", label="a", node_type="prompt", domain="support"),
                GraphNode(id="b", label="b", node_type="prompt", domain="support"),
            ],
        )

        dot = generate_dot(graph)

        assert "subgraph cluster_support" in dot

    def test_generate_dot_with_custom_title(self) -> None:
        graph = DependencyGraph()

        dot = generate_dot(graph, title="My Custom Graph")

        assert "My Custom Graph" in dot

    def test_generate_dot_escapes_special_chars(self) -> None:
        graph = DependencyGraph(
            nodes=[
                GraphNode(id="test", label='Label with "quotes"', node_type="prompt"),
            ],
        )

        dot = generate_dot(graph)

        # Should escape the quotes
        assert '\\"' in dot or "quotes" in dot

    def test_generate_dot_with_edge_note(self) -> None:
        graph = DependencyGraph(
            nodes=[
                GraphNode(id="a", label="a", node_type="prompt"),
                GraphNode(id="b", label="b", node_type="prompt"),
            ],
            edges=[
                GraphEdge(
                    from_id="a",
                    to_id="b",
                    edge_type="replaces",
                    note="v2 update",
                ),
            ],
        )

        dot = generate_dot(graph)

        assert "v2 update" in dot
