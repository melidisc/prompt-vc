"""Tests for prompt_vc.models."""

from prompt_vc.models import (
    Anchor,
    Annotation,
    Assumptions,
    Domain,
    Governance,
    Manifest,
    ProductionRequirements,
    PromptMeta,
    PromptRef,
    Relationship,
    Variable,
)


class TestAnchor:
    """Tests for Anchor model."""

    def test_anchor_minimal(self) -> None:
        anchor = Anchor(hash="sha256:abc123", preview="test")
        assert anchor.hash == "sha256:abc123"
        assert anchor.preview == "test"
        assert anchor.line_hint is None

    def test_anchor_with_line_hint(self) -> None:
        anchor = Anchor(hash="sha256:abc123", preview="test", line_hint=10)
        assert anchor.line_hint == 10


class TestAnnotation:
    """Tests for Annotation model."""

    def test_annotation_minimal(self) -> None:
        ann = Annotation(
            id="ann_01",
            anchor=Anchor(hash="sha256:abc", preview="test"),
            rationale="Why this exists",
        )
        assert ann.id == "ann_01"
        assert ann.rationale == "Why this exists"
        assert ann.tags == []
        assert ann.source is None

    def test_annotation_with_tags(self) -> None:
        ann = Annotation(
            id="ann_01",
            anchor=Anchor(hash="sha256:abc", preview="test"),
            rationale="Why",
            tags=["safety", "legal"],
        )
        assert ann.tags == ["safety", "legal"]

    def test_annotation_with_source(self) -> None:
        ann = Annotation(
            id="ann_01",
            anchor=Anchor(hash="sha256:abc", preview="test"),
            rationale="Why",
            source="https://example.com/evidence",
        )
        assert ann.source == "https://example.com/evidence"


class TestVariable:
    """Tests for Variable model."""

    def test_variable_minimal(self) -> None:
        var = Variable(type="string")
        assert var.type == "string"
        assert var.required is True
        assert var.default is None

    def test_variable_with_default(self) -> None:
        var = Variable(type="string", default="hello", required=False)
        assert var.default == "hello"
        assert var.required is False

    def test_variable_with_description(self) -> None:
        var = Variable(type="integer", description="User age")
        assert var.description == "User age"


class TestAssumptions:
    """Tests for Assumptions model."""

    def test_assumptions_minimal(self) -> None:
        assumptions = Assumptions()
        assert assumptions.model is None
        assert assumptions.max_tokens is None

    def test_assumptions_with_model(self) -> None:
        assumptions = Assumptions(model="claude-sonnet-4-20250514", max_tokens=1000)
        assert assumptions.model == "claude-sonnet-4-20250514"
        assert assumptions.max_tokens == 1000

    def test_assumptions_with_template_engine(self) -> None:
        assumptions = Assumptions(template_engine="jinja2")
        assert assumptions.template_engine == "jinja2"


class TestPromptMeta:
    """Tests for PromptMeta model."""

    def test_prompt_meta_minimal(self) -> None:
        meta = PromptMeta(id="test-prompt")
        assert meta.id == "test-prompt"
        assert meta.schema_version == "1.0"
        assert meta.annotations == []
        assert meta.variables == {}

    def test_prompt_meta_with_intent(self) -> None:
        meta = PromptMeta(id="test", intent="Handle customer refunds")
        assert meta.intent == "Handle customer refunds"

    def test_prompt_meta_with_variables(self) -> None:
        meta = PromptMeta(
            id="test",
            variables={
                "name": Variable(type="string", required=True),
                "age": Variable(type="integer", default=0),
            },
        )
        assert "name" in meta.variables
        assert meta.variables["name"].required is True

    def test_prompt_meta_with_assumptions(self) -> None:
        meta = PromptMeta(
            id="test",
            assumptions=Assumptions(model="claude-sonnet-4-20250514"),
        )
        assert meta.assumptions is not None
        assert meta.assumptions.model == "claude-sonnet-4-20250514"

    def test_prompt_meta_with_annotations(self) -> None:
        meta = PromptMeta(
            id="test",
            annotations=[
                Annotation(
                    id="ann_01",
                    anchor=Anchor(hash="sha256:abc", preview="test"),
                    rationale="Safety",
                )
            ],
        )
        assert len(meta.annotations) == 1


class TestPromptRef:
    """Tests for PromptRef model."""

    def test_prompt_ref_minimal(self) -> None:
        ref = PromptRef(id="my-prompt", path="prompts/my-prompt.prompt.md")
        assert ref.id == "my-prompt"
        assert ref.path == "prompts/my-prompt.prompt.md"
        assert ref.status == "experimental"  # default status

    def test_prompt_ref_with_status(self) -> None:
        ref = PromptRef(id="my-prompt", path="p.md", status="production")
        assert ref.status == "production"

    def test_prompt_ref_with_deployed_to(self) -> None:
        ref = PromptRef(
            id="my-prompt",
            path="p.md",
            deployed_to=["api-v1", "chat-widget"],
        )
        assert ref.deployed_to == ["api-v1", "chat-widget"]


class TestDomain:
    """Tests for Domain model."""

    def test_domain_minimal(self) -> None:
        domain = Domain()
        assert domain.prompts == []
        assert domain.description is None

    def test_domain_with_prompts(self) -> None:
        domain = Domain(
            description="Customer support",
            prompts=[
                PromptRef(id="refund", path="cs/refund.prompt.md"),
            ],
        )
        assert domain.description == "Customer support"
        assert len(domain.prompts) == 1


class TestRelationship:
    """Tests for Relationship model."""

    def test_relationship(self) -> None:
        # Note: 'from' is aliased to 'from_' in Python
        rel = Relationship(type="depends_on", to="other-prompt", **{"from": "my-prompt"})
        assert rel.type == "depends_on"
        assert rel.from_ == "my-prompt"
        assert rel.to == "other-prompt"

    def test_relationship_with_note(self) -> None:
        rel = Relationship(
            type="replaces",
            to="old-prompt",
            note="Superseded in v2",
            **{"from": "new-prompt"},
        )
        assert rel.note == "Superseded in v2"


class TestProductionRequirements:
    """Tests for ProductionRequirements model."""

    def test_production_requirements_minimal(self) -> None:
        reqs = ProductionRequirements()
        assert reqs.must_have_intent is True  # default is True
        assert reqs.must_have_evaluation is False
        assert reqs.min_annotations == 0
        assert reqs.required_tags == []

    def test_production_requirements_strict(self) -> None:
        reqs = ProductionRequirements(
            must_have_intent=True,
            must_have_evaluation=True,
            min_annotations=2,
            required_tags=["reviewed", "legal-approved"],
        )
        assert reqs.must_have_intent is True
        assert reqs.min_annotations == 2
        assert "legal-approved" in reqs.required_tags


class TestGovernance:
    """Tests for Governance model."""

    def test_governance_with_requirements(self) -> None:
        gov = Governance(production_requirements=ProductionRequirements(must_have_intent=True))
        assert gov.production_requirements is not None
        assert gov.production_requirements.must_have_intent is True


class TestManifest:
    """Tests for Manifest model."""

    def test_manifest_minimal(self) -> None:
        manifest = Manifest()
        assert manifest.schema_version == "1.0"
        assert manifest.domains == {}
        assert manifest.relationships == []

    def test_manifest_with_domains(self) -> None:
        manifest = Manifest(
            organization="acme",
            domains={
                "support": Domain(
                    description="Support prompts",
                    prompts=[PromptRef(id="refund", path="s/r.md")],
                )
            },
        )
        assert manifest.organization == "acme"
        assert "support" in manifest.domains
        assert len(manifest.domains["support"].prompts) == 1

    def test_manifest_with_governance(self) -> None:
        manifest = Manifest(
            governance=Governance(
                production_requirements=ProductionRequirements(must_have_intent=True)
            )
        )
        assert manifest.governance is not None
        assert manifest.governance.production_requirements.must_have_intent is True

    def test_manifest_with_relationships(self) -> None:
        manifest = Manifest(
            relationships=[
                Relationship(type="depends_on", to="b", **{"from": "a"}),
            ]
        )
        assert len(manifest.relationships) == 1
