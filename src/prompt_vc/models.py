"""Pydantic models for prompt-vc schemas."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class Anchor(BaseModel):
    """Content anchor for annotations."""
    
    hash: str = Field(description="SHA-256 hash of the annotated text")
    preview: str = Field(description="First ~50 chars of the text for readability")
    line_hint: int | None = Field(default=None, description="Best-effort line number")
    line_end_hint: int | None = Field(default=None, description="End line for multi-line")


class Annotation(BaseModel):
    """Line-level annotation with provenance."""
    
    id: str = Field(description="Unique annotation ID")
    anchor: Anchor
    author: str | None = Field(default=None, description="Author email")
    date: date | None = Field(default=None, description="Date created")
    source: str | None = Field(default=None, description="URL or path to evidence")
    rationale: str | None = Field(default=None, description="Why this text exists")
    tags: list[str] = Field(default_factory=list)


class Variable(BaseModel):
    """Variable definition."""
    
    type: str = Field(description="Type: string, integer, boolean, object, array")
    description: str | None = None
    required: bool = True
    default: Any | None = None
    schema_ref: str | None = Field(default=None, description="Path to JSON schema")


class Metric(BaseModel):
    """Evaluation metric."""
    
    name: str
    target: str = Field(description="Target value, e.g., '>= 4.0', '100%'")
    measured_by: str = Field(description="Path to evaluator or description")


class Evaluation(BaseModel):
    """Evaluation criteria."""
    
    metrics: list[Metric] = Field(default_factory=list)
    test_cases_ref: str | None = None


class Dependency(BaseModel):
    """Upstream or downstream dependency."""
    
    service: str
    provides: list[str] | None = None
    expects: str | None = None


class Assumptions(BaseModel):
    """Runtime assumptions."""
    
    model: str | None = None
    min_context_window: int | None = None
    max_tokens: int | None = None
    expected_latency_ms: int | None = None
    template_engine: str | None = None
    upstream_dependencies: list[Dependency] = Field(default_factory=list)
    downstream_consumers: list[Dependency] = Field(default_factory=list)


class ChangelogEntry(BaseModel):
    """Changelog entry."""
    
    version: str
    date: date
    author: str
    summary: str
    linked_annotations: list[str] = Field(default_factory=list)


class PromptMeta(BaseModel):
    """Complete prompt metadata schema."""
    
    schema_version: str = "1.0"
    id: str
    name: str | None = None
    created: date | None = None
    authors: list[str] = Field(default_factory=list)
    intent: str | None = None
    assumptions: Assumptions | None = None
    variables: dict[str, Variable] = Field(default_factory=dict)
    evaluation: Evaluation | None = None
    annotations: list[Annotation] = Field(default_factory=list)
    changelog: list[ChangelogEntry] = Field(default_factory=list)


# Manifest models

class PromptRef(BaseModel):
    """Reference to a prompt in the manifest."""
    
    id: str
    path: str
    status: str = "experimental"
    deployed_to: list[str] = Field(default_factory=list)


class Owner(BaseModel):
    """Domain owner."""
    
    team: str | None = None
    user: str | None = None
    slack: str | None = None


class Domain(BaseModel):
    """Domain grouping."""
    
    description: str | None = None
    owners: list[Owner] = Field(default_factory=list)
    prompts: list[PromptRef] = Field(default_factory=list)


class Relationship(BaseModel):
    """Cross-prompt relationship."""
    
    type: str = Field(description="replaces, depends_on, variant_of, derived_from")
    from_: str = Field(alias="from")
    to: str
    note: str | None = None


class ProductionRequirements(BaseModel):
    """Governance requirements for production prompts."""
    
    must_have_intent: bool = True
    must_have_evaluation: bool = False
    min_annotations: int = 0
    required_tags: list[str] = Field(default_factory=list)


class Governance(BaseModel):
    """Governance rules."""
    
    production_requirements: ProductionRequirements | None = None
    review_policy: dict[str, Any] | None = None


class Defaults(BaseModel):
    """Global defaults."""
    
    model: str | None = None
    template_engine: str | None = None
    review_required: bool = True


class Manifest(BaseModel):
    """Root manifest schema."""
    
    schema_version: str = "1.0"
    organization: str | None = None
    repository: str | None = None
    defaults: Defaults | None = None
    domains: dict[str, Domain] = Field(default_factory=dict)
    relationships: list[Relationship] = Field(default_factory=list)
    governance: Governance | None = None
