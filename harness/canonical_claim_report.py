from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .canonical_claim_ledger import (
    read_claim_ledger,
)
from .canonical_claim_projector import (
    project_claim_states,
)
from .canonical_claim_status import (
    evaluate_claim_health,
)
from .runtime import (
    load_config,
    project_now,
)


@dataclass(frozen=True)
class CanonicalClaimHealthRow:
    claim_id: str
    knowledge_id: str
    knowledge_type: str
    topic: str
    status: str
    review_due: bool
    as_of: str

    creation_provenance_basis: str
    creation_evidence_ids: tuple[str, ...]

    review_provenance_basis: str | None
    review_provenance_scope: str | None

    head_event_id: str
    message: str


@dataclass(frozen=True)
class CanonicalClaimHealthReport:
    valid: bool
    claim_count: int
    rows: list[CanonicalClaimHealthRow]
    issues: list[str]


def build_canonical_claim_health_report(
    root: Path,
) -> CanonicalClaimHealthReport:
    root = root.resolve()

    ledger = read_claim_ledger(
        root
    )

    if not ledger.valid:
        return CanonicalClaimHealthReport(
            valid=False,
            claim_count=0,
            rows=[],
            issues=[
                (
                    f"line {issue.line}: "
                    f"{issue.field}: "
                    f"{issue.message}"
                )
                for issue in ledger.issues
            ],
        )

    states = project_claim_states(
        ledger
    )

    config = load_config(root)

    today = project_now(
        config
    ).date()

    rows: list[CanonicalClaimHealthRow] = []

    for claim_id in sorted(states):
        claim = states[claim_id]

        health = evaluate_claim_health(
            claim,
            today=today,
        )

        rows.append(
            CanonicalClaimHealthRow(
                claim_id=claim.claim_id,
                knowledge_id=(
                    claim.knowledge_id
                ),
                knowledge_type=(
                    claim.knowledge_type
                ),
                topic=claim.topic,
                status=health.lifecycle,
                review_due=(
                    health.review_due
                ),
                as_of=claim.as_of,
                creation_provenance_basis=(
                    claim.source_provenance[
                        "basis"
                    ]
                ),
                creation_evidence_ids=tuple(
                    ref["evidence_id"]
                    for ref in
                    claim.source_provenance.get(
                        "evidence_refs",
                        [],
                    )
                ),
                review_provenance_basis=(
                    claim.review_provenance[
                        "basis"
                    ]
                    if claim.review_provenance
                    else None
                ),
                review_provenance_scope=(
                    claim.review_provenance[
                        "scope"
                    ]
                    if claim.review_provenance
                    else None
                ),
                head_event_id=(
                    claim.head_event_id
                ),
                message=health.message,
            )
        )

    return CanonicalClaimHealthReport(
        valid=True,
        claim_count=len(rows),
        rows=rows,
        issues=[],
    )
