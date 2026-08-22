from __future__ import annotations

from datetime import datetime

from .canonical_document import (
    freeze_document_identity,
)


SOURCE_CONTRACT_VERSION = "0.1.0"


def validate_source_snapshot(
    reference: dict,
) -> list[tuple[str, str]]:
    version = reference.get(
        "source_contract_version"
    )

    if version is None:
        return []

    issues: list[tuple[str, str]] = []

    if version != SOURCE_CONTRACT_VERSION:
        issues.append(
            (
                "source_contract_version",
                "Unsupported source contract version.",
            )
        )
        return issues

    document = reference.get("document")

    if not isinstance(document, dict):
        issues.append(
            (
                "document",
                "v0.5 source snapshot requires a "
                "Document mapping.",
            )
        )
        return issues

    try:
        expected = freeze_document_identity(
            url=document.get("url"),
            content_hash=document.get(
                "content_hash"
            ),
            retrieved_at=document.get(
                "retrieved_at"
            ),
            title=document.get("title"),
            publisher=document.get("publisher"),
            published_at=document.get(
                "published_at"
            ),
        )
    except ValueError as exc:
        issues.append(("document", str(exc)))
    else:
        for field in (
            "document_id",
            "document_version_id",
        ):
            if document.get(field) != expected[field]:
                issues.append(
                    (
                        f"document.{field}",
                        "Does not match deterministic "
                        "Document identity.",
                    )
                )

        if document.get("url") != reference.get(
            "source_url"
        ):
            issues.append(
                (
                    "document.url",
                    "Must equal source_url.",
                )
            )

        if document.get(
            "content_hash"
        ) != reference.get("source_content_hash"):
            issues.append(
                (
                    "document.content_hash",
                    "Must equal source_content_hash.",
                )
            )

        retrieved_at = document.get("retrieved_at")

        try:
            parsed = datetime.fromisoformat(
                retrieved_at
            )
        except (TypeError, ValueError):
            parsed = None

        if (
            parsed is None
            or parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            issues.append(
                (
                    "document.retrieved_at",
                    "Must be a timezone-aware ISO "
                    "8601 timestamp.",
                )
            )

    context = reference.get("context")

    if (
        not isinstance(context, str)
        or not context.strip()
    ):
        issues.append(
            (
                "context",
                "v0.5 source snapshot requires "
                "non-empty frozen context.",
            )
        )

    location = reference.get("location")

    if not isinstance(location, dict):
        issues.append(
            (
                "location",
                "v0.5 source snapshot requires a "
                "location mapping.",
            )
        )

    return issues
