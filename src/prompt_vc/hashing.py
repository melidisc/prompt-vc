"""Utilities for content hashing and annotation anchoring."""

import hashlib
import re


def normalize_text(text: str) -> str:
    """Normalize text for consistent hashing.

    - Strips leading/trailing whitespace
    - Collapses internal whitespace to single spaces
    - Normalizes line endings
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Strip and collapse whitespace
    text = " ".join(text.split())
    return text


def hash_content(text: str, normalize: bool = True) -> str:
    """Compute SHA-256 hash of text content.

    Args:
        text: The text to hash
        normalize: Whether to normalize whitespace before hashing

    Returns:
        Hash string in format "sha256:<hex>"
    """
    if normalize:
        text = normalize_text(text)

    hash_bytes = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{hash_bytes}"


def extract_preview(text: str, max_length: int = 50) -> str:
    """Extract a preview of text for human readability.

    Args:
        text: The text to preview
        max_length: Maximum preview length

    Returns:
        Truncated preview with ellipsis if needed
    """
    # Normalize to single line for preview
    preview = " ".join(text.split())

    if len(preview) <= max_length:
        return preview

    return preview[: max_length - 3] + "..."


def find_text_in_file(filepath: str, target_hash: str) -> tuple[int | None, str | None]:
    """Find text matching a hash in a file.

    Searches line by line and in paragraph chunks.

    Args:
        filepath: Path to the file
        target_hash: Hash to search for

    Returns:
        Tuple of (line_number, matched_text) or (None, None) if not found
    """
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    # Try single lines
    for i, line in enumerate(lines, start=1):
        if hash_content(line) == target_hash:
            return i, line.strip()

    # Try consecutive line pairs
    for i in range(len(lines) - 1):
        chunk = lines[i] + lines[i + 1]
        if hash_content(chunk) == target_hash:
            return i + 1, chunk.strip()

    # Try paragraphs (blank-line separated)
    paragraphs = re.split(r"\n\s*\n", "".join(lines))
    line_num = 1
    for para in paragraphs:
        if hash_content(para) == target_hash:
            return line_num, para.strip()
        line_num += para.count("\n") + 2  # +2 for the blank line separator

    return None, None


def similarity_score(text1: str, text2: str) -> float:
    """Compute simple similarity score between two texts.

    Uses word overlap (Jaccard similarity).

    Returns:
        Score between 0.0 and 1.0
    """
    words1 = set(normalize_text(text1).lower().split())
    words2 = set(normalize_text(text2).lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union)


def find_similar_lines(
    filepath: str, target_text: str, threshold: float = 0.6
) -> list[tuple[int, str, float]]:
    """Find lines similar to target text.

    Args:
        filepath: Path to the file
        target_text: Text to match against
        threshold: Minimum similarity score

    Returns:
        List of (line_number, line_text, similarity_score) tuples
    """
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    matches = []
    for i, line in enumerate(lines, start=1):
        score = similarity_score(target_text, line)
        if score >= threshold:
            matches.append((i, line.strip(), score))

    # Sort by score descending
    matches.sort(key=lambda x: x[2], reverse=True)
    return matches
