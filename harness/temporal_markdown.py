from __future__ import annotations

import fnmatch
import json

from dataclasses import dataclass
from pathlib import Path

import yaml

from .temporal import (
    load_temporal_schema,
    validate_temporal_metadata,
)


@dataclass(frozen=True)
class TemporalDocument:
    path: str
    expected_type: str
    has_front_matter: bool
    metadata: dict
    valid: bool
    issues: list[str]


def load_temporal_scope(
    root: Path,
) -> dict:
    path = (
        root
        / "10_Harness"
        / "temporal"
        / "scope.json"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Temporal scope not found: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def read_markdown_front_matter(
    path: Path,
) -> tuple[dict, str, bool]:
    text = path.read_text(
        encoding="utf-8"
    )

    if not text.startswith("---\n"):
        return {}, text, False

    end = text.find(
        "\n---\n",
        4,
    )

    if end == -1:
        raise ValueError(
            f"Unclosed YAML front matter: {path}"
        )

    raw = text[4:end]

    metadata = yaml.safe_load(raw) or {}

    if not isinstance(metadata, dict):
        raise ValueError(
            f"Front matter must be a mapping: {path}"
        )

    body = text[end + 5:]

    return metadata, body, True


def _matches_rule(
    relative_path: str,
    rule: dict,
) -> bool:
    exact = rule.get("path")

    if exact:
        return relative_path == exact

    pattern = rule.get("glob")

    if pattern:
        return fnmatch.fnmatch(
            relative_path,
            pattern,
        )

    return False


def expected_knowledge_type(
    scope: dict,
    relative_path: str,
) -> str | None:
    for rule in scope.get(
        "rules",
        [],
    ):
        if _matches_rule(
            relative_path,
            rule,
        ):
            return rule.get(
                "knowledge_type"
            )

    return None


def scan_temporal_documents(
    root: Path,
) -> list[TemporalDocument]:
    schema = load_temporal_schema(root)
    scope = load_temporal_scope(root)

    results: list[TemporalDocument] = []

    for rule in scope.get(
        "rules",
        [],
    ):
        expected_type = rule.get(
            "knowledge_type"
        )

        paths: list[Path] = []

        if rule.get("path"):
            candidate = (
                root / rule["path"]
            )

            if candidate.exists():
                paths = [candidate]

        elif rule.get("glob"):
            paths = sorted(
                root.glob(
                    rule["glob"]
                )
            )

        for path in paths:
            relative = (
                path.relative_to(root)
                .as_posix()
            )

            metadata, _, has_front_matter = (
                read_markdown_front_matter(
                    path
                )
            )

            issues: list[str] = []

            if not has_front_matter:
                issues.append(
                    "Missing YAML front matter."
                )

            else:
                actual_type = metadata.get(
                    "knowledge_type"
                )

                if (
                    actual_type
                    and actual_type
                    != expected_type
                ):
                    issues.append(
                        "knowledge_type mismatch: "
                        f"expected {expected_type}, "
                        f"got {actual_type}."
                    )

                result = (
                    validate_temporal_metadata(
                        schema,
                        metadata,
                    )
                )

                issues.extend(
                    f"{issue.field}: "
                    f"{issue.message}"
                    for issue in result.issues
                )

            results.append(
                TemporalDocument(
                    path=relative,
                    expected_type=expected_type,
                    has_front_matter=(
                        has_front_matter
                    ),
                    metadata=metadata,
                    valid=not issues,
                    issues=issues,
                )
            )

    return results


def write_markdown_front_matter(
    path: Path,
    metadata: dict,
    body: str,
) -> None:
    front_matter = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
    ).strip()

    text = (
        "---\n"
        + front_matter
        + "\n---\n"
        + body
    )

    path.write_text(
        text,
        encoding="utf-8",
    )
