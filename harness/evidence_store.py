from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from harness.evidence import Claim, Evidence


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    publisher TEXT,
    published_at TEXT,
    retrieved_at TEXT,
    provider TEXT,
    content_hash TEXT,
    status TEXT NOT NULL DEFAULT 'candidate'
);

CREATE TABLE IF NOT EXISTS source_contents (
    url TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    retrieved_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    topic TEXT NOT NULL,
    importance TEXT NOT NULL DEFAULT 'normal',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    status TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    source_title TEXT,
    publisher TEXT,
    published_at TEXT,
    retrieved_at TEXT,
    section_heading TEXT,
    context_excerpt TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

CREATE TABLE IF NOT EXISTS evidence_revisions (
    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    revised_by TEXT NOT NULL,
    note TEXT,
    revised_at TEXT NOT NULL,
    FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_revisions_evidence
ON evidence_revisions(evidence_id);


CREATE TABLE IF NOT EXISTS evidence_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    note TEXT,
    reviewed_at TEXT NOT NULL,
    FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_evidence
ON evidence_reviews(evidence_id);


CREATE INDEX IF NOT EXISTS idx_evidence_claim
ON evidence(claim_id);

CREATE INDEX IF NOT EXISTS idx_sources_status
ON sources(status);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _derive_source_context(
    content: str,
    excerpt: str,
    *,
    before_chars: int = 1400,
    after_chars: int = 700,
) -> dict[str, str | None]:
    position = content.find(excerpt)

    if position == -1:
        return {
            "section_heading": None,
            "context_excerpt": None,
        }

    before = content[:position]

    section_heading = None

    for line in reversed(before.splitlines()):
        stripped = line.strip()

        if stripped.startswith("#"):
            section_heading = stripped
            break

    start = max(
        0,
        position - before_chars,
    )

    end = min(
        len(content),
        position + len(excerpt) + after_chars,
    )

    return {
        "section_heading": section_heading,
        "context_excerpt": content[start:end].strip(),
    }


class EvidenceStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.executescript(SCHEMA)

            evidence_columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(evidence)"
                ).fetchall()
            }

            if "section_heading" not in evidence_columns:
                conn.execute(
                    "ALTER TABLE evidence "
                    "ADD COLUMN section_heading TEXT"
                )

            if "context_excerpt" not in evidence_columns:
                conn.execute(
                    "ALTER TABLE evidence "
                    "ADD COLUMN context_excerpt TEXT"
                )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert_source(
        self,
        *,
        url: str,
        title: str | None = None,
        publisher: str | None = None,
        published_at: str | None = None,
        retrieved_at: str | None = None,
        provider: str | None = None,
        content_hash: str | None = None,
        status: str = "candidate",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sources (
                    url,
                    title,
                    publisher,
                    published_at,
                    retrieved_at,
                    provider,
                    content_hash,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title = COALESCE(excluded.title, sources.title),
                    publisher = COALESCE(excluded.publisher, sources.publisher),
                    published_at = COALESCE(excluded.published_at, sources.published_at),
                    retrieved_at = COALESCE(excluded.retrieved_at, sources.retrieved_at),
                    provider = COALESCE(excluded.provider, sources.provider),
                    content_hash = COALESCE(excluded.content_hash, sources.content_hash),
                    status = excluded.status
                """,
                (
                    url,
                    title,
                    publisher,
                    published_at,
                    retrieved_at,
                    provider,
                    content_hash,
                    status,
                ),
            )

    def add_claim(self, claim: Claim) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO claims (
                    claim_id,
                    text,
                    topic,
                    importance,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    claim.claim_id,
                    claim.text,
                    claim.topic,
                    claim.importance,
                    _utc_now(),
                ),
            )

    def add_evidence(self, evidence: Evidence) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evidence (
                    evidence_id,
                    claim_id,
                    source_url,
                    status,
                    excerpt,
                    reasoning,
                    source_title,
                    publisher,
                    published_at,
                    retrieved_at,
                    section_heading,
                    context_excerpt,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.evidence_id,
                    evidence.claim_id,
                    evidence.source_url,
                    evidence.status.value,
                    evidence.excerpt,
                    evidence.reasoning,
                    evidence.source_title,
                    evidence.publisher,
                    evidence.published_at,
                    evidence.retrieved_at,
                    evidence.section_heading,
                    evidence.context_excerpt,
                    _utc_now(),
                ),
            )

    def store_source_content(
        self,
        *,
        url: str,
        content: str,
        content_hash: str,
        retrieved_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                '''
                INSERT INTO source_contents (
                    url,
                    content,
                    content_hash,
                    retrieved_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    content = excluded.content,
                    content_hash = excluded.content_hash,
                    retrieved_at = excluded.retrieved_at
                ''',
                (
                    url,
                    content,
                    content_hash,
                    retrieved_at,
                ),
            )

    def derive_source_context(
        self,
        *,
        url: str,
        excerpt: str,
    ) -> dict[str, str | None]:
        content = self.get_source_content(url)

        if not content:
            return {
                "section_heading": None,
                "context_excerpt": None,
            }

        return _derive_source_context(
            content,
            excerpt,
        )

    def get_source_content(
        self,
        url: str,
    ) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                '''
                SELECT content
                FROM source_contents
                WHERE url = ?
                ''',
                (url,),
            ).fetchone()

        return row["content"] if row else None

    def get_source(
        self,
        url: str,
    ) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                '''
                SELECT
                    url,
                    title,
                    publisher,
                    published_at,
                    retrieved_at,
                    provider,
                    content_hash,
                    status
                FROM sources
                WHERE url = ?
                ''',
                (url,),
            ).fetchone()

        return dict(row) if row else None

    def is_fetched_source(
        self,
        url: str,
    ) -> bool:
        source = self.get_source(url)

        if not source:
            return False

        return source["status"] in {
            "fetched",
            "human_verified",
            "cited",
        }

    def add_evidence_revision(
        self,
        *,
        evidence_id: str,
        claim_text: str,
        reasoning: str,
        revised_by: str = "human",
        note: str | None = None,
    ) -> None:
        with self._connect() as conn:
            exists = conn.execute(
                '''
                SELECT 1
                FROM evidence
                WHERE evidence_id = ?
                ''',
                (evidence_id,),
            ).fetchone()

            if not exists:
                raise ValueError(
                    f"Unknown evidence_id: {evidence_id}"
                )

            conn.execute(
                '''
                INSERT INTO evidence_revisions (
                    evidence_id,
                    claim_text,
                    reasoning,
                    revised_by,
                    note,
                    revised_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    evidence_id,
                    claim_text.strip(),
                    reasoning.strip(),
                    revised_by,
                    note,
                    _utc_now(),
                ),
            )

    def latest_evidence_revision(
        self,
        evidence_id: str,
    ) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                '''
                SELECT
                    revision_id,
                    evidence_id,
                    claim_text,
                    reasoning,
                    revised_by,
                    note,
                    revised_at
                FROM evidence_revisions
                WHERE evidence_id = ?
                ORDER BY revision_id DESC
                LIMIT 1
                ''',
                (evidence_id,),
            ).fetchone()

        return dict(row) if row else None

    def add_evidence_review(
        self,
        *,
        evidence_id: str,
        decision: str,
        reviewer: str = "human",
        note: str | None = None,
    ) -> None:
        allowed = {
            "approved",
            "rejected",
            "needs_revision",
        }

        if decision not in allowed:
            raise ValueError(
                f"Invalid review decision: {decision}"
            )

        with self._connect() as conn:
            exists = conn.execute(
                '''
                SELECT 1
                FROM evidence
                WHERE evidence_id = ?
                ''',
                (evidence_id,),
            ).fetchone()

            if not exists:
                raise ValueError(
                    f"Unknown evidence_id: {evidence_id}"
                )

            conn.execute(
                '''
                INSERT INTO evidence_reviews (
                    evidence_id,
                    decision,
                    reviewer,
                    note,
                    reviewed_at
                )
                VALUES (?, ?, ?, ?, ?)
                ''',
                (
                    evidence_id,
                    decision,
                    reviewer,
                    note,
                    _utc_now(),
                ),
            )

    def latest_evidence_review(
        self,
        evidence_id: str,
    ) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                '''
                SELECT
                    evidence_id,
                    decision,
                    reviewer,
                    note,
                    reviewed_at
                FROM evidence_reviews
                WHERE evidence_id = ?
                ORDER BY review_id DESC
                LIMIT 1
                ''',
                (evidence_id,),
            ).fetchone()

        return dict(row) if row else None

    def is_human_verified(
        self,
        evidence_id: str,
    ) -> bool:
        review = self.latest_evidence_review(
            evidence_id
        )

        return bool(
            review
            and review["decision"] == "approved"
        )

    def get_evidence_revision_context(
        self,
        evidence_id: str,
    ) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                '''
                SELECT
                    e.evidence_id,
                    e.claim_id,
                    c.text AS original_claim,
                    c.topic,
                    c.importance,
                    e.status AS machine_status,
                    e.source_url,
                    e.excerpt,
                    e.reasoning AS original_reasoning,
                    e.source_title,
                    e.publisher,
                    e.published_at,
                    e.retrieved_at,
                    e.section_heading,
                    e.context_excerpt
                FROM evidence e
                JOIN claims c
                  ON c.claim_id = e.claim_id
                WHERE e.evidence_id = ?
                ''',
                (evidence_id,),
            ).fetchone()

        if not row:
            return None

        result = dict(row)

        revision = self.latest_evidence_revision(
            evidence_id
        )

        review = self.latest_evidence_review(
            evidence_id
        )

        result["effective_claim"] = (
            revision["claim_text"]
            if revision
            else result["original_claim"]
        )

        result["effective_reasoning"] = (
            revision["reasoning"]
            if revision
            else result["original_reasoning"]
        )

        result["latest_revision"] = revision
        result["latest_review"] = review

        source_content = self.get_source_content(
            result["source_url"]
        )

        if source_content:
            derived = _derive_source_context(
                source_content,
                result["excerpt"],
            )

            if not result.get("section_heading"):
                result["section_heading"] = derived[
                    "section_heading"
                ]

            if not result.get("context_excerpt"):
                result["context_excerpt"] = derived[
                    "context_excerpt"
                ]

        return result

    def counts(self) -> dict[str, int]:
        with self._connect() as conn:
            return {
                "sources": conn.execute(
                    "SELECT COUNT(*) FROM sources"
                ).fetchone()[0],
                "claims": conn.execute(
                    "SELECT COUNT(*) FROM claims"
                ).fetchone()[0],
                "evidence": conn.execute(
                    "SELECT COUNT(*) FROM evidence"
                ).fetchone()[0],
            }
