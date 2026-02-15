"""Listing functionality for prompt-vc."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import Manifest
from .validation import find_meta_files, parse_meta_file


@dataclass
class PromptInfo:
    """Information about a prompt for listing."""

    id: str
    domain: str | None
    path: str
    status: str
    deployed_to: list[str] = field(default_factory=list)
    owners: list[str] = field(default_factory=list)
    name: str | None = None


def find_manifest(search_path: Path | None = None) -> Path | None:
    """Find the prompts.manifest.yaml file.

    Looks for manifest in:
    1. The specified path (if it's a file)
    2. prompts.manifest.yaml in the specified directory
    3. prompts/prompts.manifest.yaml
    4. prompts.manifest.yaml in cwd
    """
    base = search_path or Path.cwd()

    if base.is_file() and base.name == "prompts.manifest.yaml":
        return base

    # Check common locations
    candidates = [
        base / "prompts.manifest.yaml",
        base / "prompts" / "prompts.manifest.yaml",
        Path.cwd() / "prompts" / "prompts.manifest.yaml",
        Path.cwd() / "prompts.manifest.yaml",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def parse_manifest(manifest_path: Path) -> tuple[Manifest | None, str | None]:
    """Parse a manifest file.

    Returns:
        Tuple of (parsed manifest or None, error message or None)
    """
    try:
        with open(manifest_path, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return None, f"Invalid YAML: {e}"
    except OSError as e:
        return None, f"Cannot read file: {e}"

    if raw_data is None:
        return None, "Empty manifest file"

    try:
        manifest = Manifest.model_validate(raw_data)
        return manifest, None
    except ValidationError as e:
        return None, f"Schema error: {e}"


def list_from_manifest(
    manifest: Manifest,
    manifest_path: Path,
    domain_filter: str | None = None,
    status_filter: str | None = None,
    owner_filter: str | None = None,
) -> list[PromptInfo]:
    """List prompts from a manifest file.

    Args:
        manifest: Parsed manifest
        manifest_path: Path to manifest (for resolving relative paths)
        domain_filter: Filter by domain name
        status_filter: Filter by status
        owner_filter: Filter by owner (team or user)

    Returns:
        List of PromptInfo objects
    """
    prompts: list[PromptInfo] = []
    manifest_dir = manifest_path.parent

    for domain_name, domain in manifest.domains.items():
        # Apply domain filter
        if domain_filter and domain_name != domain_filter:
            continue

        # Get owner names for this domain
        owner_names = []
        for owner in domain.owners:
            if owner.team:
                owner_names.append(owner.team)
            if owner.user:
                owner_names.append(owner.user)

        # Apply owner filter
        if owner_filter:
            owner_match = any(
                owner_filter.lower() in name.lower() for name in owner_names
            )
            if not owner_match:
                continue

        for prompt_ref in domain.prompts:
            # Apply status filter
            if status_filter and prompt_ref.status != status_filter:
                continue

            # Try to get the name from the meta file
            name = None
            meta_path = manifest_dir / prompt_ref.path.replace(
                ".prompt.md", ".prompt.meta.yaml"
            ).replace(".prompt.jinja", ".prompt.meta.yaml")
            if meta_path.exists():
                meta, _ = parse_meta_file(meta_path)
                if meta:
                    name = meta.name

            prompts.append(
                PromptInfo(
                    id=prompt_ref.id,
                    domain=domain_name,
                    path=prompt_ref.path,
                    status=prompt_ref.status,
                    deployed_to=prompt_ref.deployed_to,
                    owners=owner_names,
                    name=name,
                )
            )

    return prompts


def list_from_directory(
    search_path: Path | None = None,
    domain_filter: str | None = None,
    status_filter: str | None = None,
    owner_filter: str | None = None,
) -> list[PromptInfo]:
    """List prompts by scanning directory for meta files.

    Args:
        search_path: Directory to search
        domain_filter: Filter by domain (directory name)
        status_filter: Not applicable for directory scan (ignored)
        owner_filter: Filter by author in meta file

    Returns:
        List of PromptInfo objects
    """
    prompts: list[PromptInfo] = []
    base_path = search_path or Path.cwd()

    meta_files = find_meta_files(base_path)

    for meta_path in meta_files:
        meta, _ = parse_meta_file(meta_path)
        if meta is None:
            continue

        # Determine domain from directory structure
        try:
            rel_path = meta_path.relative_to(base_path)
            parts = rel_path.parts
            # Domain is typically the first directory level
            domain = parts[0] if len(parts) > 1 else None
        except ValueError:
            domain = None

        # Apply domain filter
        if domain_filter and domain != domain_filter:
            continue

        # Apply owner filter (check authors)
        if owner_filter:
            owner_match = any(
                owner_filter.lower() in author.lower() for author in meta.authors
            )
            if not owner_match:
                continue

        # Derive prompt file path from meta path
        prompt_path = str(meta_path).replace(".meta.yaml", ".md")
        if not Path(prompt_path).exists():
            # Try other extensions
            for ext in [".jinja", ".txt", ".yaml"]:
                alt_path = str(meta_path).replace(".meta.yaml", ext)
                if Path(alt_path).exists():
                    prompt_path = alt_path
                    break

        try:
            rel_prompt_path = str(Path(prompt_path).relative_to(base_path))
        except ValueError:
            rel_prompt_path = prompt_path

        prompts.append(
            PromptInfo(
                id=meta.id,
                domain=domain,
                path=rel_prompt_path,
                status="unknown",  # No status without manifest
                deployed_to=[],
                owners=meta.authors,
                name=meta.name,
            )
        )

    return prompts


def list_prompts(
    search_path: Path | None = None,
    domain_filter: str | None = None,
    status_filter: str | None = None,
    owner_filter: str | None = None,
) -> tuple[list[PromptInfo], bool]:
    """List all prompts, using manifest if available.

    Args:
        search_path: Directory to search
        domain_filter: Filter by domain
        status_filter: Filter by status
        owner_filter: Filter by owner

    Returns:
        Tuple of (list of prompts, whether manifest was used)
    """
    manifest_path = find_manifest(search_path)

    if manifest_path:
        manifest, error = parse_manifest(manifest_path)
        if manifest:
            prompts = list_from_manifest(
                manifest,
                manifest_path,
                domain_filter=domain_filter,
                status_filter=status_filter,
                owner_filter=owner_filter,
            )
            return prompts, True

    # Fall back to directory scanning
    prompts = list_from_directory(
        search_path,
        domain_filter=domain_filter,
        status_filter=status_filter,
        owner_filter=owner_filter,
    )
    return prompts, False
