"""Tests for the prompt-vc web server API."""

from __future__ import annotations

import textwrap
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from prompt_vc.server.app import create_app


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Create a minimal prompt-vc workspace with manifest and prompt files."""
    prompts_dir = tmp_path / "prompts" / "support"
    prompts_dir.mkdir(parents=True)

    # Manifest
    manifest = tmp_path / "prompts" / "prompts.manifest.yaml"
    manifest.write_text(
        textwrap.dedent("""\
            schema_version: "1.0"
            organization: test-org
            repository: test-repo

            defaults:
              model: test-model
              review_required: true

            domains:
              support:
                description: Customer support prompts
                owners:
                  - team: support-team
                prompts:
                  - id: greeting
                    path: support/greeting.prompt.md
                    status: production
                    deployed_to:
                      - prod-api

            relationships: []

            governance:
              production_requirements:
                must_have_intent: true
                must_have_evaluation: false
                min_annotations: 0
                required_tags: []
        """),
        encoding="utf-8",
    )

    # Prompt file
    prompt_file = prompts_dir / "greeting.prompt.md"
    prompt_file.write_text(
        "# Greeting Prompt\n\nHello {{ customer_name }}, how can I help you today?\n",
        encoding="utf-8",
    )

    # Meta file
    meta_file = prompts_dir / "greeting.prompt.meta.yaml"
    meta_file.write_text(
        textwrap.dedent("""\
            schema_version: "1.0"
            id: greeting
            name: Customer Greeting
            created: "2024-01-01"
            authors:
              - test@example.com
            intent: |
              Greet the customer warmly.
            assumptions:
              model: test-model
              template_engine: jinja2
            variables:
              customer_name:
                type: string
                description: The customer's name
                required: true
            evaluation:
              metrics:
                - name: tone
                  target: ">= 4.0"
                  measured_by: human-eval
            annotations:
              - id: ann_test01
                anchor:
                  hash: placeholder
                  preview: "Hello {{ customer_name }}"
                  line_hint: 3
                rationale: Personalized greeting
                tags:
                  - greeting
        """),
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def client(workspace: Path) -> Generator[TestClient, None, None]:
    """Create a test client pointing at the workspace.

    Uses create_app(workspace_root=...) — no os.chdir required.
    """
    app = create_app(workspace_root=workspace, dev=False)
    yield TestClient(app)


# -- Health --


class TestHealth:
    def test_health(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# -- Prompts --


class TestListPrompts:
    def test_list_all(self, client: TestClient) -> None:
        resp = client.get("/api/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["from_manifest"] is True
        assert len(data["prompts"]) >= 1
        ids = [p["id"] for p in data["prompts"]]
        assert "greeting" in ids

    def test_filter_by_domain(self, client: TestClient) -> None:
        resp = client.get("/api/prompts", params={"domain": "support"})
        assert resp.status_code == 200
        assert all(p["domain"] == "support" for p in resp.json()["prompts"])

    def test_filter_no_match(self, client: TestClient) -> None:
        resp = client.get("/api/prompts", params={"domain": "nonexistent"})
        assert resp.status_code == 200
        assert len(resp.json()["prompts"]) == 0


class TestGetPrompt:
    def test_found(self, client: TestClient) -> None:
        resp = client.get("/api/prompts/greeting")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["id"] == "greeting"
        assert "Hello" in data["content"]
        assert data["meta_file"] != ""

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/prompts/nonexistent")
        assert resp.status_code == 404


class TestGetPromptContent:
    def test_raw_content(self, client: TestClient) -> None:
        resp = client.get("/api/prompts/greeting/content")
        assert resp.status_code == 200
        assert "Hello" in resp.json()["content"]

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/prompts/nonexistent/content")
        assert resp.status_code == 404


class TestCreatePrompt:
    def test_create(self, client: TestClient, workspace: Path) -> None:
        resp = client.post(
            "/api/prompts",
            json={"prompt_id": "new-prompt", "domain": "support", "fmt": "md"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["prompt_id"] == "new-prompt"
        # Verify files were created
        assert (workspace / "prompts" / "support" / "new-prompt.prompt.md").exists()
        assert (workspace / "prompts" / "support" / "new-prompt.prompt.meta.yaml").exists()

    def test_create_duplicate(self, client: TestClient) -> None:
        client.post("/api/prompts", json={"prompt_id": "dup-test"})
        resp = client.post("/api/prompts", json={"prompt_id": "dup-test"})
        assert resp.status_code == 409

    def test_create_updates_manifest(self, client: TestClient, workspace: Path) -> None:
        """Creating a prompt should add it to the manifest."""
        client.post(
            "/api/prompts",
            json={"prompt_id": "manifest-test", "domain": "support", "fmt": "md"},
        )
        manifest_path = workspace / "prompts" / "prompts.manifest.yaml"
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
        prompt_ids = [p["id"] for p in manifest["domains"]["support"]["prompts"]]
        assert "manifest-test" in prompt_ids


class TestUpdateContent:
    def test_update(self, client: TestClient) -> None:
        resp = client.put(
            "/api/prompts/greeting/content",
            json={"content": "Updated content."},
        )
        assert resp.status_code == 200
        # Verify
        resp2 = client.get("/api/prompts/greeting/content")
        assert resp2.json()["content"] == "Updated content."

    def test_update_empty(self, client: TestClient) -> None:
        resp = client.put(
            "/api/prompts/greeting/content",
            json={"content": ""},
        )
        assert resp.status_code == 200

    def test_update_too_large(self, client: TestClient) -> None:
        resp = client.put(
            "/api/prompts/greeting/content",
            json={"content": "x" * 1_100_000},
        )
        assert resp.status_code == 422  # Pydantic validation error


# -- Annotations --


class TestAnnotations:
    def test_add_annotation(self, client: TestClient) -> None:
        resp = client.post(
            "/api/prompts/greeting/annotations",
            json={
                "line": 1,
                "rationale": "Title line",
                "tags": ["header"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("ann_")

    def test_add_invalid_line(self, client: TestClient) -> None:
        resp = client.post(
            "/api/prompts/greeting/annotations",
            json={"line": 999},
        )
        assert resp.status_code == 400

    def test_delete_annotation(self, client: TestClient) -> None:
        resp = client.delete("/api/prompts/greeting/annotations/ann_test01")
        assert resp.status_code == 200

    def test_delete_nonexistent(self, client: TestClient) -> None:
        resp = client.delete("/api/prompts/greeting/annotations/ann_nope")
        assert resp.status_code == 404


class TestOrphanedAnnotations:
    def test_detect_orphaned(self, client: TestClient) -> None:
        resp = client.get("/api/prompts/greeting/orphaned-annotations")
        assert resp.status_code == 200
        # The placeholder hash won't match, so it should be orphaned
        data = resp.json()
        assert isinstance(data["orphaned"], list)


# -- Validate --


class TestValidate:
    def test_validate_all(self, client: TestClient) -> None:
        resp = client.get("/api/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["results"], list)
        assert isinstance(data["total_errors"], int)

    def test_validate_single(self, client: TestClient) -> None:
        resp = client.get("/api/validate/greeting")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta_file"] != ""

    def test_validate_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/validate/nonexistent")
        assert resp.status_code == 404


# -- Audit --


class TestAudit:
    def test_audit_production(self, client: TestClient) -> None:
        resp = client.get("/api/audit", params={"status": "production"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["manifest_path"] is not None
        assert isinstance(data["results"], list)

    def test_audit_all(self, client: TestClient) -> None:
        resp = client.get("/api/audit", params={"all": True})
        assert resp.status_code == 200


# -- Render --


class TestRender:
    def test_render_with_context(self, client: TestClient) -> None:
        resp = client.post(
            "/api/prompts/greeting/render",
            json={"context": {"customer_name": "Alice"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Alice" in data["rendered_content"]
        assert data["template_engine"] == "jinja2"

    def test_render_missing_var(self, client: TestClient) -> None:
        resp = client.post("/api/prompts/greeting/render", json={"context": {}})
        assert resp.status_code == 400

    def test_render_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/prompts/nonexistent/render", json={"context": {}})
        assert resp.status_code == 404


# -- Compose --


class TestCompose:
    def test_compose_simple(self, client: TestClient) -> None:
        resp = client.get("/api/prompts/greeting/compose")
        assert resp.status_code == 200
        data = resp.json()
        assert "Hello" in data["composed_content"]

    def test_compose_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/prompts/nonexistent/compose")
        assert resp.status_code == 404


# -- Diff --


class TestDiff:
    def test_diff_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/prompts/nonexistent/diff")
        assert resp.status_code == 404


# -- Graph --


class TestGraph:
    def test_graph_json(self, client: TestClient) -> None:
        resp = client.get("/api/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        # Should have at least one prompt node
        prompt_nodes = [n for n in data["nodes"] if n["node_type"] == "prompt"]
        assert len(prompt_nodes) >= 1

    def test_graph_dot(self, client: TestClient) -> None:
        resp = client.get("/api/graph/dot")
        assert resp.status_code == 200
        assert "digraph" in resp.text

    def test_graph_no_domains(self, client: TestClient) -> None:
        resp = client.get("/api/graph", params={"no_domains": True})
        assert resp.status_code == 200
        data = resp.json()
        domain_nodes = [n for n in data["nodes"] if n["node_type"] == "domain"]
        assert len(domain_nodes) == 0
