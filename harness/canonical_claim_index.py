from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile

from dataclasses import asdict, dataclass
from pathlib import Path

from .canonical_claim_ledger import (
    read_claim_ledger,
)
from .canonical_claim_projector import (
    project_claim_states,
)
from .canonical_claim_relationship import (
    read_claim_relationships,
)
from .canonical_document import (
    freeze_document_identity,
)
from .runtime import load_config, project_now


INDEX_SCHEMA_VERSION = "0.1.0"

SCHEMA = """
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE canonical_claims (
    claim_id TEXT PRIMARY KEY,
    knowledge_id TEXT NOT NULL,
    knowledge_type TEXT NOT NULL,
    text TEXT NOT NULL,
    topic TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    as_of TEXT NOT NULL,
    last_verified_at TEXT,
    next_review_at TEXT,
    head_event_id TEXT NOT NULL,
    status_changed_at TEXT NOT NULL,
    superseded_by_claim_id TEXT,
    creation_provenance_json TEXT NOT NULL,
    source_provenance_json TEXT NOT NULL,
    review_provenance_json TEXT
);

CREATE TABLE claim_relationships (
    relationship_id TEXT PRIMARY KEY,
    relationship_type TEXT NOT NULL,
    source_claim_id TEXT NOT NULL,
    target_claim_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    provenance_json TEXT NOT NULL
);

CREATE TABLE documents (
    document_version_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    publisher TEXT,
    published_at TEXT,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT NOT NULL
);

CREATE TABLE claim_evidence (
    claim_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    research_claim_id TEXT NOT NULL,
    document_version_id TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    context TEXT,
    location_json TEXT,
    review_json TEXT NOT NULL,
    PRIMARY KEY (claim_id, run_id, evidence_id)
);

CREATE INDEX idx_claim_status
ON canonical_claims(status);

CREATE INDEX idx_relationship_source
ON claim_relationships(source_claim_id);

CREATE INDEX idx_relationship_target
ON claim_relationships(target_claim_id);

CREATE INDEX idx_document_identity
ON documents(document_id);
"""


@dataclass(frozen=True)
class CanonicalIndexSummary:
    schema_version: str
    projection_fingerprint: str
    claim_count: int
    relationship_count: int
    document_count: int
    evidence_count: int


def canonical_index_path(root: Path) -> Path:
    config = load_config(root)
    relative = config[
        "canonical_claim_store"
    ]["index_db"]

    return root / relative


def _projection_fingerprint(
    claims: list[dict],
    relationships: list[dict],
) -> str:
    encoded = json.dumps(
        {
            "claims": claims,
            "relationships": relationships,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _document_from_reference(
    reference: dict,
) -> dict | None:
    document = reference.get("document")

    if isinstance(document, dict):
        return document

    content_hash = reference.get(
        "source_content_hash"
    )
    retrieved_at = reference.get("retrieved_at")

    if not content_hash or not retrieved_at:
        return None

    try:
        return freeze_document_identity(
            url=reference.get("source_url"),
            content_hash=content_hash,
            retrieved_at=retrieved_at,
            title=reference.get("source_title"),
            publisher=reference.get("publisher"),
            published_at=reference.get(
                "published_at"
            ),
        )
    except ValueError:
        return None


def rebuild_canonical_index(
    root: Path,
) -> CanonicalIndexSummary:
    root = root.resolve()
    claim_ledger = read_claim_ledger(root)

    if not claim_ledger.valid:
        raise ValueError(
            "Cannot rebuild index from invalid "
            "canonical claim ledger."
        )

    relationship_result = read_claim_relationships(
        root
    )

    if not relationship_result.valid:
        raise ValueError(
            "Cannot rebuild index from invalid "
            "claim relationship ledger."
        )

    states = project_claim_states(claim_ledger)
    claim_rows = [
        asdict(states[claim_id])
        for claim_id in sorted(states)
    ]
    relationship_rows = [
        asdict(relationship)
        for relationship in sorted(
            relationship_result.relationships,
            key=lambda item: item.relationship_id,
        )
    ]
    fingerprint = _projection_fingerprint(
        claim_rows,
        relationship_rows,
    )
    path = canonical_index_path(root).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=".canonical_claims.",
            suffix=".sqlite",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

        with sqlite3.connect(temp_path) as conn:
            conn.executescript(SCHEMA)
            built_at = project_now(
                load_config(root)
            ).isoformat()
            metadata = {
                "schema_version": INDEX_SCHEMA_VERSION,
                "projection_fingerprint": fingerprint,
                "built_at": built_at,
            }
            conn.executemany(
                "INSERT INTO metadata (key, value) "
                "VALUES (?, ?)",
                sorted(metadata.items()),
            )

            for claim in claim_rows:
                conn.execute(
                    """
                    INSERT INTO canonical_claims (
                        claim_id,
                        knowledge_id,
                        knowledge_type,
                        text,
                        topic,
                        status,
                        created_at,
                        as_of,
                        last_verified_at,
                        next_review_at,
                        head_event_id,
                        status_changed_at,
                        superseded_by_claim_id,
                        creation_provenance_json,
                        source_provenance_json,
                        review_provenance_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim["claim_id"],
                        claim["knowledge_id"],
                        claim["knowledge_type"],
                        claim["text"],
                        claim["topic"],
                        claim["status"],
                        claim["created_at"],
                        claim["as_of"],
                        claim["last_verified_at"],
                        claim["next_review_at"],
                        claim["head_event_id"],
                        claim["status_changed_at"],
                        claim[
                            "superseded_by_claim_id"
                        ],
                        json.dumps(
                            claim["creation_provenance"],
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        json.dumps(
                            claim["source_provenance"],
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        (
                            json.dumps(
                                claim[
                                    "review_provenance"
                                ],
                                ensure_ascii=False,
                                sort_keys=True,
                            )
                            if claim[
                                "review_provenance"
                            ] is not None
                            else None
                        ),
                    ),
                )

                for reference in claim[
                    "source_provenance"
                ].get("evidence_refs", []):
                    document = _document_from_reference(
                        reference
                    )

                    if document is None:
                        continue

                    conn.execute(
                        """
                        INSERT OR IGNORE INTO documents (
                            document_version_id,
                            document_id,
                            url,
                            title,
                            publisher,
                            published_at,
                            retrieved_at,
                            content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            document[
                                "document_version_id"
                            ],
                            document["document_id"],
                            document["url"],
                            document.get("title"),
                            document.get("publisher"),
                            document.get("published_at"),
                            document["retrieved_at"],
                            document["content_hash"],
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO claim_evidence (
                            claim_id,
                            run_id,
                            evidence_id,
                            research_claim_id,
                            document_version_id,
                            excerpt,
                            context,
                            location_json,
                            review_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            claim["claim_id"],
                            reference["run"]["run_id"],
                            reference["evidence_id"],
                            reference[
                                "research_claim_id"
                            ],
                            document[
                                "document_version_id"
                            ],
                            reference["excerpt"],
                            reference.get("context"),
                            json.dumps(
                                reference.get("location"),
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            json.dumps(
                                reference["review"],
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        ),
                    )

            for relationship in relationship_rows:
                conn.execute(
                    """
                    INSERT INTO claim_relationships (
                        relationship_id,
                        relationship_type,
                        source_claim_id,
                        target_claim_id,
                        reason,
                        occurred_at,
                        actor,
                        provenance_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        relationship["relationship_id"],
                        relationship[
                            "relationship_type"
                        ],
                        relationship["source_claim_id"],
                        relationship["target_claim_id"],
                        relationship["reason"],
                        relationship["occurred_at"],
                        relationship["actor"],
                        json.dumps(
                            relationship["provenance"],
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )

        os.replace(temp_path, path)
        temp_path = None
    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()

    return read_canonical_index_summary(root)


def read_canonical_index_summary(
    root: Path,
) -> CanonicalIndexSummary:
    path = canonical_index_path(root)

    if not path.is_file():
        raise FileNotFoundError(
            f"Canonical claim index not found: {path}"
        )

    with sqlite3.connect(path) as conn:
        metadata = dict(
            conn.execute(
                "SELECT key, value FROM metadata"
            ).fetchall()
        )
        counts = {
            "claim_count": conn.execute(
                "SELECT COUNT(*) FROM canonical_claims"
            ).fetchone()[0],
            "relationship_count": conn.execute(
                "SELECT COUNT(*) FROM claim_relationships"
            ).fetchone()[0],
            "document_count": conn.execute(
                "SELECT COUNT(*) FROM documents"
            ).fetchone()[0],
            "evidence_count": conn.execute(
                "SELECT COUNT(*) FROM claim_evidence"
            ).fetchone()[0],
        }

    return CanonicalIndexSummary(
        schema_version=metadata["schema_version"],
        projection_fingerprint=metadata[
            "projection_fingerprint"
        ],
        **counts,
    )
