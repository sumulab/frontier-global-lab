from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .temporal import (
    knowledge_type_policy,
    validate_temporal_metadata,
)


def review_temporal_metadata(
    schema: dict,
    metadata: dict[str, Any],
    *,
    verified_on: date,
    as_of: date,
) -> dict[str, Any]:
    knowledge_type = metadata.get(
        "knowledge_type"
    )

    policy = knowledge_type_policy(
        schema,
        knowledge_type,
    )

    if not policy.get(
        "temporal",
        False,
    ):
        raise ValueError(
            f"{knowledge_type!r} does not use "
            "document-level temporal review."
        )

    status = metadata.get("status")

    if status in {
        "superseded",
        "historical",
    }:
        raise ValueError(
            f"Cannot review document in "
            f"{status!r} status."
        )

    raw_created_at = metadata.get(
        "created_at"
    )

    if not raw_created_at:
        raise ValueError(
            "created_at is required before review."
        )

    created_at = date.fromisoformat(
        raw_created_at
    )

    if as_of < created_at:
        raise ValueError(
            "as_of cannot be earlier than created_at."
        )

    if as_of > verified_on:
        raise ValueError(
            "as_of cannot be later than verified_on."
        )

    review_days = policy.get(
        "default_review_days"
    )

    if not isinstance(
        review_days,
        int,
    ) or review_days <= 0:
        raise ValueError(
            "Knowledge type must define a positive "
            "default_review_days."
        )

    updated = dict(metadata)

    updated["status"] = "active"
    updated["as_of"] = as_of.isoformat()
    updated["last_verified_at"] = (
        verified_on.isoformat()
    )
    updated["next_review_at"] = (
        verified_on
        + timedelta(days=review_days)
    ).isoformat()

    result = validate_temporal_metadata(
        schema,
        updated,
    )

    if not result.valid:
        detail = "; ".join(
            f"{issue.field}: {issue.message}"
            for issue in result.issues
        )

        raise ValueError(
            f"Reviewed metadata is invalid: {detail}"
        )

    return updated


def review_temporal_document(
    root,
    path,
    *,
    verified_on,
    as_of,
    dry_run=False,
):
    from .temporal import load_temporal_schema
    from .temporal_markdown import (
        expected_knowledge_type,
        load_temporal_scope,
        read_markdown_front_matter,
        write_markdown_front_matter,
    )

    root = root.resolve()
    path = path.resolve()

    if root != path and root not in path.parents:
        raise ValueError(
            "Document must be inside the repository."
        )

    relative_path = (
        path.relative_to(root).as_posix()
    )

    scope = load_temporal_scope(root)

    expected_type = expected_knowledge_type(
        scope,
        relative_path,
    )

    if expected_type is None:
        raise ValueError(
            f"Document is outside temporal scope: "
            f"{relative_path}"
        )

    metadata, body, has_front_matter = (
        read_markdown_front_matter(path)
    )

    if not has_front_matter:
        raise ValueError(
            "Document has no YAML front matter."
        )

    actual_type = metadata.get(
        "knowledge_type"
    )

    if actual_type != expected_type:
        raise ValueError(
            "knowledge_type mismatch: "
            f"expected {expected_type!r}, "
            f"got {actual_type!r}."
        )

    schema = load_temporal_schema(root)

    updated = review_temporal_metadata(
        schema,
        metadata,
        verified_on=verified_on,
        as_of=as_of,
    )

    if not dry_run:
        write_markdown_front_matter(
            path,
            updated,
            body,
        )

    return updated
