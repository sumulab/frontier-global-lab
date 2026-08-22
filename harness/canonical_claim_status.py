from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .canonical_claim_projector import (
    CanonicalClaimState,
)


@dataclass(frozen=True)
class CanonicalClaimHealth:
    lifecycle: str
    review_due: bool
    message: str


def evaluate_claim_health(
    claim: CanonicalClaimState,
    *,
    today: date,
) -> CanonicalClaimHealth:
    if claim.status == "needs_review":
        return CanonicalClaimHealth(
            lifecycle="needs_review",
            review_due=True,
            message=(
                "Canonical claim requires review "
                "before it can be treated as current."
            ),
        )

    if claim.status == "superseded":
        return CanonicalClaimHealth(
            lifecycle="superseded",
            review_due=False,
            message=(
                "Canonical claim has been formally "
                "replaced by a newer claim."
            ),
        )

    if claim.status == "archived":
        return CanonicalClaimHealth(
            lifecycle="archived",
            review_due=False,
            message=(
                "Canonical claim is retained as "
                "historical knowledge."
            ),
        )

    if claim.status != "active":
        return CanonicalClaimHealth(
            lifecycle="unknown",
            review_due=True,
            message=(
                f"Unknown claim lifecycle status: "
                f"{claim.status!r}."
            ),
        )

    if not claim.next_review_at:
        return CanonicalClaimHealth(
            lifecycle="active",
            review_due=True,
            message=(
                "Active canonical claim has no "
                "next_review_at."
            ),
        )

    try:
        next_review = date.fromisoformat(
            claim.next_review_at
        )
    except ValueError:
        return CanonicalClaimHealth(
            lifecycle="active",
            review_due=True,
            message=(
                "Active canonical claim has an "
                "invalid next_review_at."
            ),
        )

    if today >= next_review:
        return CanonicalClaimHealth(
            lifecycle="active",
            review_due=True,
            message=(
                f"Canonical claim freshness review "
                f"due since "
                f"{next_review.isoformat()}."
            ),
        )

    return CanonicalClaimHealth(
        lifecycle="active",
        review_due=False,
        message=(
            f"Canonical claim is current through "
            f"its review window; next review "
            f"{next_review.isoformat()}."
        ),
    )
