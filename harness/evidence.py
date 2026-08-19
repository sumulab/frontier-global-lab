from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SourceStatus(StrEnum):
    CANDIDATE = "candidate"
    DISCOVERED = "discovered"
    FETCHED = "fetched"
    HUMAN_VERIFIED = "human_verified"
    CITED = "cited"


class EvidenceStatus(StrEnum):
    PENDING = "pending"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    topic: str
    importance: str = "normal"


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    claim_id: str
    source_url: str

    status: EvidenceStatus

    excerpt: str
    reasoning: str

    source_title: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    retrieved_at: str | None = None

    # Source-context snapshot captured when evidence is recorded.
    # The excerpt is the direct quote; these fields preserve its scope.
    section_heading: str | None = None
    context_excerpt: str | None = None

    metadata: dict[str, str] = field(default_factory=dict)


def can_support_canonical_claim(
    evidence: Evidence,
) -> bool:
    """Machine gate only.

    Human approval is still required before canonical promotion.
    """
    return (
        evidence.status == EvidenceStatus.SUPPORTED
        and bool(evidence.source_url)
        and bool(evidence.excerpt.strip())
        and bool(evidence.reasoning.strip())
    )
