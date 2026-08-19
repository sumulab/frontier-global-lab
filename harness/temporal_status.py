from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class TemporalKnowledgeState:
    lifecycle: str
    review_due: bool
    message: str


def evaluate_temporal_state(
    metadata: dict[str, Any],
    *,
    today: date,
) -> TemporalKnowledgeState:
    status = metadata.get("status")

    if status == "needs_review":
        return TemporalKnowledgeState(
            lifecycle="needs_review",
            review_due=True,
            message=(
                "Knowledge requires review before it can "
                "be treated as current."
            ),
        )

    if status == "superseded":
        return TemporalKnowledgeState(
            lifecycle="superseded",
            review_due=False,
            message=(
                "Knowledge has been formally replaced."
            ),
        )

    if status == "historical":
        return TemporalKnowledgeState(
            lifecycle="historical",
            review_due=False,
            message=(
                "Knowledge is retained as historical context."
            ),
        )

    if status != "active":
        return TemporalKnowledgeState(
            lifecycle="unknown",
            review_due=True,
            message=(
                f"Unknown lifecycle status: {status!r}."
            ),
        )

    raw_next_review = metadata.get(
        "next_review_at"
    )

    if not raw_next_review:
        return TemporalKnowledgeState(
            lifecycle="active",
            review_due=True,
            message=(
                "Active knowledge has no next_review_at."
            ),
        )

    try:
        next_review = date.fromisoformat(
            raw_next_review
        )
    except (TypeError, ValueError):
        return TemporalKnowledgeState(
            lifecycle="active",
            review_due=True,
            message=(
                "Active knowledge has an invalid "
                "next_review_at."
            ),
        )

    if today >= next_review:
        return TemporalKnowledgeState(
            lifecycle="active",
            review_due=True,
            message=(
                f"Freshness review due since "
                f"{next_review.isoformat()}."
            ),
        )

    return TemporalKnowledgeState(
        lifecycle="active",
        review_due=False,
        message=(
            f"Current through review window; "
            f"next review {next_review.isoformat()}."
        ),
    )
