"""Semantic versioning for prompts."""

from __future__ import annotations

import datetime
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ruamel.yaml import YAML

from .models import ChangelogEntry, PromptMeta

if TYPE_CHECKING:
    pass


@dataclass
class SemVer:
    """Semantic version representation."""

    major: int
    minor: int
    patch: int | None = None  # Allow 2-part versions like "2.1"

    def __str__(self) -> str:
        if self.patch is not None:
            return f"{self.major}.{self.minor}.{self.patch}"
        return f"{self.major}.{self.minor}"


BumpType = Literal["major", "minor", "patch"]


def parse_version(version_str: str) -> SemVer | None:
    """Parse a version string into SemVer.

    Supports:
    - "1.0" -> SemVer(1, 0)
    - "1.0.0" -> SemVer(1, 0, 0)
    - "2.1.3" -> SemVer(2, 1, 3)

    Returns None if parsing fails.
    """
    pattern = r"^(\d+)\.(\d+)(?:\.(\d+))?$"
    match = re.match(pattern, version_str.strip())
    if not match:
        return None

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3)) if match.group(3) else None

    return SemVer(major=major, minor=minor, patch=patch)


def bump_version(version: SemVer, bump_type: BumpType) -> SemVer:
    """Bump a version based on the bump type.

    Rules:
    - major: 2.1 -> 3.0, 2.1.3 -> 3.0.0
    - minor: 2.1 -> 2.2, 2.1.3 -> 2.2.0
    - patch: 2.1 -> 2.1.1, 2.1.3 -> 2.1.4
    """
    if bump_type == "major":
        return SemVer(
            major=version.major + 1,
            minor=0,
            patch=0 if version.patch is not None else None,
        )
    elif bump_type == "minor":
        return SemVer(
            major=version.major,
            minor=version.minor + 1,
            patch=0 if version.patch is not None else None,
        )
    else:  # patch
        current_patch = version.patch if version.patch is not None else 0
        return SemVer(
            major=version.major,
            minor=version.minor,
            patch=current_patch + 1,
        )


def get_current_version(meta: PromptMeta) -> str | None:
    """Get the current version from changelog[0].version.

    Returns None if no changelog entries exist.
    """
    if not meta.changelog:
        return None
    return meta.changelog[0].version


def get_git_author() -> str | None:
    """Get the author from git config.

    Returns email from `git config user.email` or None if unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


@dataclass
class BumpResult:
    """Result of a version bump operation."""

    success: bool
    message: str
    old_version: str | None = None
    new_version: str | None = None
    changelog_entry: ChangelogEntry | None = None


def add_changelog_entry(
    meta_path: Path,
    entry: ChangelogEntry,
) -> None:
    """Add a new changelog entry to the meta file (prepending to changelog list).

    Uses ruamel.yaml to preserve formatting.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=2, offset=2)

    with open(meta_path, encoding="utf-8") as f:
        raw_data = yaml.load(f)

    if raw_data is None:
        raw_data = {}

    # Ensure changelog exists
    if "changelog" not in raw_data:
        raw_data["changelog"] = []

    # Convert entry to dict
    entry_dict: dict[str, str | list[str]] = {
        "version": entry.version,
        "date": entry.date.isoformat(),
        "author": entry.author,
        "summary": entry.summary,
        "linked_annotations": list(entry.linked_annotations) if entry.linked_annotations else [],
    }

    # Prepend to changelog (newest first)
    raw_data["changelog"].insert(0, entry_dict)

    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.dump(raw_data, f)


def bump_prompt_version(
    prompt_id_or_path: str,
    bump_type: BumpType,
    summary: str,
    author: str | None = None,
    linked_annotations: list[str] | None = None,
    dry_run: bool = False,
) -> BumpResult:
    """Bump a prompt's version and add a changelog entry.

    Args:
        prompt_id_or_path: Prompt ID or path to meta file
        bump_type: "major", "minor", or "patch"
        summary: Required summary for the changelog entry
        author: Optional author (defaults to git config user.email)
        linked_annotations: Optional list of annotation IDs to link
        dry_run: If True, preview changes without writing

    Returns:
        BumpResult with success/failure and details
    """
    from .view import load_prompt_and_meta

    # Load the prompt and meta
    meta_path, prompt_path, parsed_meta, issues = load_prompt_and_meta(prompt_id_or_path)

    if parsed_meta is None:
        error_msg = "; ".join(issues) if issues else f"Could not find prompt: {prompt_id_or_path}"
        return BumpResult(
            success=False,
            message=error_msg,
        )

    if meta_path is None:
        return BumpResult(
            success=False,
            message="No meta file found",
        )

    # Get current version
    current_version_str = get_current_version(parsed_meta)

    if current_version_str is None:
        # No changelog - start at 1.0
        new_version_str = "1.0"
        old_version_str = None
    else:
        # Parse and bump
        current_version = parse_version(current_version_str)
        if current_version is None:
            return BumpResult(
                success=False,
                message=f"Invalid version format: '{current_version_str}'. "
                "Expected semver (e.g., '1.0', '2.1.3')",
            )

        new_version = bump_version(current_version, bump_type)
        new_version_str = str(new_version)
        old_version_str = current_version_str

    # Get author
    resolved_author = author or get_git_author()
    if resolved_author is None:
        return BumpResult(
            success=False,
            message="No author specified and could not determine from git config. "
            "Use --author flag.",
        )

    # Create changelog entry
    entry = ChangelogEntry(
        version=new_version_str,
        date=datetime.date.today(),
        author=resolved_author,
        summary=summary,
        linked_annotations=linked_annotations or [],
    )

    # Add to meta file (unless dry run)
    if dry_run:
        return BumpResult(
            success=True,
            message=f"Would bump version from {old_version_str or '(none)'} to {new_version_str}",
            old_version=old_version_str,
            new_version=new_version_str,
            changelog_entry=entry,
        )

    try:
        add_changelog_entry(meta_path, entry)
    except OSError as e:
        return BumpResult(
            success=False,
            message=f"Failed to write changelog: {e}",
        )

    return BumpResult(
        success=True,
        message=f"Bumped version from {old_version_str or '(none)'} to {new_version_str}",
        old_version=old_version_str,
        new_version=new_version_str,
        changelog_entry=entry,
    )
