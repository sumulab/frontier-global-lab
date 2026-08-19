from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical_claim_ledger import (
    ClaimLedgerValidationResult,
)


@dataclass(frozen=True)
class CanonicalClaimState:
    claim_id: str
    knowledge_id: str
    knowledge_type: str
    text: str
    topic: str

    status: str

    created_at: str
    as_of: str

    last_verified_at: str | None
    next_review_at: str | None

    head_event_id: str

    superseded_by_claim_id: str | None
    contradicted_by_claim_ids: tuple[str, ...]

    review_provenance: dict[str, Any] | None


def project_claim_states(
    ledger: ClaimLedgerValidationResult,
) -> dict[str, CanonicalClaimState]:
    if not ledger.valid:
        raise ValueError(
            "Cannot project an invalid canonical "
            "claim ledger."
        )

    states: dict[str, dict[str, Any]] = {}

    for event in ledger.events:
        claim_id = event["claim_id"]
        event_id = event["event_id"]
        event_type = event["event_type"]
        payload = event["payload"]

        if event_type == "claim_created":
            states[claim_id] = {
                "claim_id": claim_id,
                "knowledge_id": payload[
                    "knowledge_id"
                ],
                "knowledge_type": payload[
                    "knowledge_type"
                ],
                "text": payload["text"],
                "topic": payload["topic"],
                "status": "needs_review",
                "created_at": payload[
                    "created_at"
                ],
                "as_of": payload["as_of"],
                "last_verified_at": None,
                "next_review_at": None,
                "head_event_id": event_id,
                "superseded_by_claim_id": None,
                "contradicted_by_claim_ids": (),
                "review_provenance": None,
            }

            continue

        state = states[claim_id]

        if event_type == "claim_reviewed":
            state["status"] = "active"
            state["as_of"] = payload["as_of"]
            state["last_verified_at"] = (
                payload["last_verified_at"]
            )
            state["next_review_at"] = (
                payload["next_review_at"]
            )
            state["review_provenance"] = (
                payload["review_provenance"]
            )

        elif (
            event_type
            == "claim_marked_needs_review"
        ):
            state["status"] = "needs_review"

        elif event_type == "claim_superseded":
            state["status"] = "superseded"
            state[
                "superseded_by_claim_id"
            ] = payload[
                "superseded_by_claim_id"
            ]

        elif event_type == "claim_contradicted":
            state["status"] = "contradicted"

            targets = payload.get(
                "contradicted_by_claim_ids",
                [],
            )

            state[
                "contradicted_by_claim_ids"
            ] = tuple(targets)

        elif (
            event_type
            == "claim_marked_historical"
        ):
            state["status"] = "historical"

        state["head_event_id"] = event_id

    return {
        claim_id: CanonicalClaimState(
            **state
        )
        for claim_id, state in states.items()
    }
