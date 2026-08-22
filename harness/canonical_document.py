from __future__ import annotations

import hashlib
import re


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def freeze_document_identity(
    *,
    url: str,
    content_hash: str,
    retrieved_at: str,
    title: str | None = None,
    publisher: str | None = None,
    published_at: str | None = None,
) -> dict:
    for name, value in (
        ("url", url),
        ("content_hash", content_hash),
        ("retrieved_at", retrieved_at),
    ):
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"Document {name} must be a "
                "non-empty string."
            )

    normalized_url = url.strip()
    normalized_hash = content_hash.strip().lower()

    if not _SHA256_RE.fullmatch(normalized_hash):
        raise ValueError(
            "Document content_hash must be a "
            "lowercase SHA-256 hex digest."
        )

    document_digest = hashlib.sha256(
        normalized_url.encode("utf-8")
    ).hexdigest()
    version_digest = hashlib.sha256(
        (
            normalized_url
            + "\n"
            + normalized_hash
        ).encode("utf-8")
    ).hexdigest()

    return {
        "document_id": (
            "DOC-" + document_digest[:16]
        ),
        "document_version_id": (
            "DOCV-" + version_digest[:16]
        ),
        "url": normalized_url,
        "title": title,
        "publisher": publisher,
        "published_at": published_at,
        "retrieved_at": retrieved_at.strip(),
        "content_hash": normalized_hash,
    }
