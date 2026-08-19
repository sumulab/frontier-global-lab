from __future__ import annotations

import re

from pathlib import Path

from .evidence_store import EvidenceStore
from .review_provenance import (
    validate_review_runs,
)


_MARKDOWN_SELF_LINK_RE = re.compile(
    r"^\[(https?://[^\]]+)\]\((https?://[^)]+)\)$"
)


def _normalize_source_url(
    value: str,
) -> str:
    stripped = value.strip()

    match = _MARKDOWN_SELF_LINK_RE.fullmatch(
        stripped
    )

    if (
        match
        and match.group(1)
        == match.group(2)
    ):
        return match.group(1)

    return stripped


def resolve_approved_evidence(
    root: Path,
    *,
    run_id: str,
    evidence_id: str,
) -> dict:
    root = root.resolve()

    for name, value in (
        ("run_id", run_id),
        ("evidence_id", evidence_id),
    ):
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"{name} must be a "
                "non-empty string."
            )

    # Reuse the shared completed-run validator
    # and freeze the run metadata as provenance.
    run_snapshots = validate_review_runs(
        root,
        basis="research_run",
        run_ids=[run_id],
    )

    if len(run_snapshots) != 1:
        raise ValueError(
            "Expected exactly one completed "
            "research run snapshot."
        )

    run_snapshot = run_snapshots[0]

    db = (
        root
        / "10_Harness"
        / "runtime"
        / "runs"
        / run_id
        / "evidence.sqlite"
    ).resolve()

    if not db.is_file():
        raise ValueError(
            f"No evidence database for run: "
            f"{run_id}"
        )

    store = EvidenceStore(db)

    context = (
        store.get_evidence_revision_context(
            evidence_id
        )
    )

    if context is None:
        raise ValueError(
            f"Evidence {evidence_id} "
            f"not found in run {run_id}."
        )

    review = context.get(
        "latest_review"
    )

    if not review:
        raise ValueError(
            f"Evidence {evidence_id} "
            "has not been human reviewed."
        )

    if review.get("decision") != "approved":
        raise ValueError(
            f"Evidence {evidence_id} latest "
            "human review is "
            f"{review.get('decision')!r}, "
            "not 'approved'."
        )

    reviewer = review.get("reviewer")
    reviewed_at = review.get(
        "reviewed_at"
    )

    if (
        not isinstance(reviewer, str)
        or not reviewer.strip()
    ):
        raise ValueError(
            f"Evidence {evidence_id} approved "
            "review has no reviewer."
        )

    if (
        not isinstance(reviewed_at, str)
        or not reviewed_at.strip()
    ):
        raise ValueError(
            f"Evidence {evidence_id} approved "
            "review has no reviewed_at."
        )

    source = (
        store.get_source(
            context["source_url"]
        )
        or {}
    )

    return {
        "run": run_snapshot,
        "evidence_id": (
            context["evidence_id"]
        ),
        "research_claim_id": (
            context["claim_id"]
        ),
        "effective_claim": (
            context["effective_claim"]
        ),
        "source_url": (
            _normalize_source_url(
                context["source_url"]
            )
        ),
        "source_title": (
            context.get("source_title")
        ),
        "publisher": (
            context.get("publisher")
        ),
        "published_at": (
            context.get("published_at")
        ),
        "retrieved_at": (
            context.get("retrieved_at")
        ),
        "source_content_hash": (
            source.get("content_hash")
        ),
        "excerpt": (
            context["excerpt"]
        ),
        "review": {
            "decision": "approved",
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "note": review.get("note"),
        },
    }
