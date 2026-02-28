"""Tests for prompt_vc.versioning."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from prompt_vc.cli import main
from prompt_vc.models import ChangelogEntry, PromptMeta
from prompt_vc.versioning import (
    SemVer,
    bump_prompt_version,
    bump_version,
    get_current_version,
    parse_version,
)


class TestParseVersion:
    """Tests for parse_version function."""

    def test_parse_two_part_version(self) -> None:
        result = parse_version("2.1")
        assert result is not None
        assert result.major == 2
        assert result.minor == 1
        assert result.patch is None

    def test_parse_three_part_version(self) -> None:
        result = parse_version("2.1.3")
        assert result is not None
        assert result.major == 2
        assert result.minor == 1
        assert result.patch == 3

    def test_parse_version_with_whitespace(self) -> None:
        result = parse_version("  1.0  ")
        assert result is not None
        assert result.major == 1
        assert result.minor == 0

    def test_parse_version_zero(self) -> None:
        result = parse_version("0.0.0")
        assert result is not None
        assert result.major == 0
        assert result.minor == 0
        assert result.patch == 0

    def test_parse_invalid_version_with_v_prefix(self) -> None:
        result = parse_version("v2.1")
        assert result is None

    def test_parse_invalid_version_empty(self) -> None:
        result = parse_version("")
        assert result is None

    def test_parse_invalid_version_single_number(self) -> None:
        result = parse_version("1")
        assert result is None

    def test_parse_invalid_version_four_parts(self) -> None:
        result = parse_version("1.2.3.4")
        assert result is None

    def test_parse_invalid_version_letters(self) -> None:
        result = parse_version("1.2.beta")
        assert result is None


class TestBumpVersion:
    """Tests for bump_version function."""

    def test_bump_major_two_part(self) -> None:
        version = SemVer(major=2, minor=1)
        result = bump_version(version, "major")
        assert result.major == 3
        assert result.minor == 0
        assert result.patch is None

    def test_bump_major_three_part(self) -> None:
        version = SemVer(major=2, minor=1, patch=3)
        result = bump_version(version, "major")
        assert result.major == 3
        assert result.minor == 0
        assert result.patch == 0

    def test_bump_minor_two_part(self) -> None:
        version = SemVer(major=2, minor=1)
        result = bump_version(version, "minor")
        assert result.major == 2
        assert result.minor == 2
        assert result.patch is None

    def test_bump_minor_three_part(self) -> None:
        version = SemVer(major=2, minor=1, patch=3)
        result = bump_version(version, "minor")
        assert result.major == 2
        assert result.minor == 2
        assert result.patch == 0

    def test_bump_patch_two_part(self) -> None:
        version = SemVer(major=2, minor=1)
        result = bump_version(version, "patch")
        assert result.major == 2
        assert result.minor == 1
        assert result.patch == 1

    def test_bump_patch_three_part(self) -> None:
        version = SemVer(major=2, minor=1, patch=3)
        result = bump_version(version, "patch")
        assert result.major == 2
        assert result.minor == 1
        assert result.patch == 4

    def test_bump_major_from_zero(self) -> None:
        version = SemVer(major=0, minor=9, patch=5)
        result = bump_version(version, "major")
        assert result.major == 1
        assert result.minor == 0
        assert result.patch == 0


class TestSemVerStr:
    """Tests for SemVer __str__ method."""

    def test_str_two_part(self) -> None:
        version = SemVer(major=2, minor=1)
        assert str(version) == "2.1"

    def test_str_three_part(self) -> None:
        version = SemVer(major=2, minor=1, patch=3)
        assert str(version) == "2.1.3"

    def test_str_with_zero_patch(self) -> None:
        version = SemVer(major=1, minor=0, patch=0)
        assert str(version) == "1.0.0"


class TestGetCurrentVersion:
    """Tests for get_current_version function."""

    def test_get_version_from_changelog(self) -> None:
        meta = PromptMeta(
            id="test",
            changelog=[
                ChangelogEntry(
                    version="2.1",
                    date=datetime.date(2024, 1, 15),
                    author="test@example.com",
                    summary="Latest change",
                ),
                ChangelogEntry(
                    version="2.0",
                    date=datetime.date(2024, 1, 10),
                    author="test@example.com",
                    summary="Previous change",
                ),
            ],
        )
        assert get_current_version(meta) == "2.1"

    def test_get_version_empty_changelog(self) -> None:
        meta = PromptMeta(id="test", changelog=[])
        assert get_current_version(meta) is None

    def test_get_version_no_changelog(self) -> None:
        meta = PromptMeta(id="test")
        assert get_current_version(meta) is None


class TestBumpPromptVersion:
    """Tests for bump_prompt_version function."""

    @pytest.fixture
    def prompt_with_changelog(self, tmp_path: Path) -> Path:
        """Create a prompt with an existing changelog."""
        prompt = tmp_path / "test.prompt.md"
        prompt.write_text("Test content")

        meta = tmp_path / "test.prompt.meta.yaml"
        meta.write_text("""schema_version: "1.0"
id: test
name: Test Prompt
changelog:
  - version: "2.1"
    date: "2024-01-15"
    author: original@example.com
    summary: Previous update
    linked_annotations: []
""")
        return tmp_path

    @pytest.fixture
    def prompt_without_changelog(self, tmp_path: Path) -> Path:
        """Create a prompt without a changelog."""
        prompt = tmp_path / "test.prompt.md"
        prompt.write_text("Test content")

        meta = tmp_path / "test.prompt.meta.yaml"
        meta.write_text("""schema_version: "1.0"
id: test
name: Test Prompt
""")
        return tmp_path

    def test_bump_patch_version(
        self, prompt_with_changelog: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_with_changelog)

        result = bump_prompt_version(
            prompt_id_or_path="test",
            bump_type="patch",
            summary="Fixed typo",
            author="dev@example.com",
        )

        assert result.success
        assert result.old_version == "2.1"
        assert result.new_version == "2.1.1"
        assert result.changelog_entry is not None
        assert result.changelog_entry.summary == "Fixed typo"

    def test_bump_minor_version(
        self, prompt_with_changelog: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_with_changelog)

        result = bump_prompt_version(
            prompt_id_or_path="test",
            bump_type="minor",
            summary="Added new feature",
            author="dev@example.com",
        )

        assert result.success
        assert result.old_version == "2.1"
        assert result.new_version == "2.2"

    def test_bump_major_version(
        self, prompt_with_changelog: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_with_changelog)

        result = bump_prompt_version(
            prompt_id_or_path="test",
            bump_type="major",
            summary="Breaking change",
            author="dev@example.com",
        )

        assert result.success
        assert result.old_version == "2.1"
        assert result.new_version == "3.0"

    def test_bump_without_changelog_starts_at_1_0(
        self, prompt_without_changelog: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_without_changelog)

        result = bump_prompt_version(
            prompt_id_or_path="test",
            bump_type="patch",
            summary="Initial release",
            author="dev@example.com",
        )

        assert result.success
        assert result.old_version is None
        assert result.new_version == "1.0"

    def test_bump_with_linked_annotations(
        self, prompt_with_changelog: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_with_changelog)

        result = bump_prompt_version(
            prompt_id_or_path="test",
            bump_type="minor",
            summary="Added safety rule",
            author="dev@example.com",
            linked_annotations=["ann_safety_01", "ann_legal_02"],
        )

        assert result.success
        assert result.changelog_entry is not None
        assert result.changelog_entry.linked_annotations == ["ann_safety_01", "ann_legal_02"]

    def test_bump_dry_run_does_not_write(
        self, prompt_with_changelog: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_with_changelog)
        meta_file = prompt_with_changelog / "test.prompt.meta.yaml"
        original_content = meta_file.read_text()

        result = bump_prompt_version(
            prompt_id_or_path="test",
            bump_type="patch",
            summary="Test change",
            author="dev@example.com",
            dry_run=True,
        )

        assert result.success
        assert "Would bump" in result.message
        assert result.new_version == "2.1.1"
        # File should not have changed
        assert meta_file.read_text() == original_content

    def test_bump_nonexistent_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        result = bump_prompt_version(
            prompt_id_or_path="nonexistent",
            bump_type="patch",
            summary="Test",
            author="dev@example.com",
        )

        assert not result.success
        assert "Could not find prompt" in result.message

    def test_bump_without_author_fails_without_git(
        self, prompt_with_changelog: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_with_changelog)
        monkeypatch.setattr("prompt_vc.versioning.get_git_author", lambda: None)

        result = bump_prompt_version(
            prompt_id_or_path="test",
            bump_type="patch",
            summary="Test",
            author=None,
        )

        assert not result.success
        assert "No author specified" in result.message


class TestBumpCLI:
    """CLI integration tests for bump command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    @pytest.fixture
    def prompt_dir(self, tmp_path: Path) -> Path:
        prompt = tmp_path / "test.prompt.md"
        prompt.write_text("Test content")

        meta = tmp_path / "test.prompt.meta.yaml"
        meta.write_text("""schema_version: "1.0"
id: test
changelog:
  - version: "1.0"
    date: "2024-01-01"
    author: original@example.com
    summary: Initial
    linked_annotations: []
""")
        return tmp_path

    def test_bump_cli_success(
        self, runner: CliRunner, prompt_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_dir)

        result = runner.invoke(
            main,
            ["bump", "test", "patch", "-s", "Fixed bug", "-a", "dev@example.com"],
        )

        assert result.exit_code == 0
        assert "1.0.1" in result.output

    def test_bump_cli_missing_summary(
        self, runner: CliRunner, prompt_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_dir)

        result = runner.invoke(main, ["bump", "test", "patch"])

        assert result.exit_code != 0

    def test_bump_cli_invalid_bump_type(
        self, runner: CliRunner, prompt_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_dir)

        result = runner.invoke(
            main,
            ["bump", "test", "invalid", "-s", "Test"],
        )

        assert result.exit_code != 0

    def test_bump_cli_with_link(
        self, runner: CliRunner, prompt_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_dir)

        result = runner.invoke(
            main,
            [
                "bump", "test", "minor",
                "-s", "Added safety rule",
                "-a", "dev@example.com",
                "-l", "ann_01",
                "-l", "ann_02",
            ],
        )

        assert result.exit_code == 0
        assert "1.1" in result.output

    def test_bump_cli_dry_run(
        self, runner: CliRunner, prompt_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(prompt_dir)
        meta_file = prompt_dir / "test.prompt.meta.yaml"
        original_content = meta_file.read_text()

        result = runner.invoke(
            main,
            [
                "bump", "test", "patch",
                "-s", "Test change",
                "-a", "dev@example.com",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "dry run" in result.output
        assert meta_file.read_text() == original_content
