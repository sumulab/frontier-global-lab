from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from .canonical_claim_ledger import (
    claim_ledger_path,
    read_claim_ledger,
)
from .canonical_claim_projector import (
    project_claim_states,
)
from .evidence_provenance import (
    resolve_approved_evidence,
)
from .canonical_claim_projector import (
    project_claim_states,
)
from .runtime import (
    load_config,
    project_now,
)
from .review_provenance import (
    validate_review_runs,
)
from .review_provenance import (
    validate_review_runs,
)
from .temporal import (
    knowledge_type_policy,
    load_temporal_schema,
    validate_temporal_metadata,
)
from .temporal_markdown import (
    expected_knowledge_type,
    load_temporal_scope,
    read_markdown_front_matter,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_claim_text(
    value: str,
) -> str:
    normalized = unicodedata.normalize(
        "NFKC",
        value,
    )

    return " ".join(
        normalized.split()
    ).casefold()


def _resolve_claim_owner(
    root: Path,
    document: Path,
) -> dict:
    root = root.resolve()
    document = document.resolve()

    if (
        document == root
        or root not in document.parents
    ):
        raise ValueError(
            "Canonical document must be inside "
            "the repository."
        )

    if not document.is_file():
        raise FileNotFoundError(
            f"Canonical document not found: "
            f"{document}"
        )

    relative = (
        document.relative_to(root)
        .as_posix()
    )

    scope = load_temporal_scope(root)

    expected_type = expected_knowledge_type(
        scope,
        relative,
    )

    if expected_type is None:
        raise ValueError(
            "Canonical document is outside "
            f"Temporal Scope: {relative}"
        )

    metadata, _, has_front_matter = (
        read_markdown_front_matter(
            document
        )
    )

    if not has_front_matter:
        raise ValueError(
            "Canonical document has no "
            "YAML front matter."
        )

    actual_type = metadata.get(
        "knowledge_type"
    )

    if actual_type != expected_type:
        raise ValueError(
            "knowledge_type mismatch: "
            f"expected {expected_type!r}, "
            f"got {actual_type!r}."
        )

    schema = load_temporal_schema(root)

    validation = validate_temporal_metadata(
        schema,
        metadata,
    )

    if not validation.valid:
        detail = "; ".join(
            f"{issue.field}: {issue.message}"
            for issue in validation.issues
        )

        raise ValueError(
            "Canonical owner metadata is invalid: "
            + detail
        )

    policy = knowledge_type_policy(
        schema,
        actual_type,
    )

    if not policy.get(
        "temporal",
        False,
    ):
        raise ValueError(
            f"Knowledge type {actual_type!r} "
            "does not use canonical claim "
            "lifecycle."
        )

    knowledge_id = metadata.get("id")

    if (
        not isinstance(knowledge_id, str)
        or not knowledge_id.strip()
    ):
        raise ValueError(
            "Canonical owner requires a stable id."
        )

    return {
        "path": relative,
        "knowledge_id": knowledge_id,
        "knowledge_type": actual_type,
    }


def append_claim_created(
    root: Path,
    document: Path,
    *,
    text: str,
    topic: str,
    as_of: date,
    provenance_basis: str,
    provenance_note: str,
    evidence_refs: list[tuple[str, str]] | None = None,
    actor: str,
    dry_run: bool = False,
) -> dict:
    root = root.resolve()

    for name, value in (
        ("text", text),
        ("topic", topic),
        ("actor", actor),
    ):
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"{name} must be a "
                "non-empty string."
            )

    if not isinstance(as_of, date):
        raise ValueError(
            "as_of must be a date."
        )

    if provenance_basis not in {
        "manual",
        "research_evidence",
    }:
        raise ValueError(
            "provenance_basis must be "
            "'manual' or 'research_evidence'."
        )

    if (
        not isinstance(
            provenance_note,
            str,
        )
        or not provenance_note.strip()
    ):
        raise ValueError(
            "provenance_note must be a "
            "non-empty rationale."
        )

    evidence_refs = list(
        evidence_refs or []
    )

    if (
        provenance_basis == "manual"
        and evidence_refs
    ):
        raise ValueError(
            "Manual canonical claim creation "
            "must not include evidence refs."
        )

    if (
        provenance_basis
        == "research_evidence"
        and not evidence_refs
    ):
        raise ValueError(
            "Research-evidence canonical claim "
            "creation requires at least one "
            "run/evidence reference."
        )

    resolved_evidence = []

    for index, ref in enumerate(
        evidence_refs
    ):
        if (
            not isinstance(
                ref,
                (tuple, list),
            )
            or len(ref) != 2
        ):
            raise ValueError(
                "Each evidence ref must be "
                "a (run_id, evidence_id) pair; "
                f"invalid ref at index {index}."
            )

        run_id, evidence_id = ref

        resolved_evidence.append(
            resolve_approved_evidence(
                root,
                run_id=run_id,
                evidence_id=evidence_id,
            )
        )

    # The authoritative ledger must already
    # be valid before any mutation is attempted.
    current = read_claim_ledger(root)

    if not current.valid:
        detail = "; ".join(
            f"line {issue.line}: "
            f"{issue.field}: "
            f"{issue.message}"
            for issue in current.issues
        )

        raise ValueError(
            "Canonical claim ledger is invalid; "
            "append refused. "
            + detail
        )

    owner = _resolve_claim_owner(
        root,
        document,
    )

    normalized_text = _normalize_claim_text(
        text
    )

    for existing in current.events:
        if (
            existing.get("event_type")
            != "claim_created"
        ):
            continue

        payload = existing.get(
            "payload",
            {},
        )

        if (
            payload.get("knowledge_id")
            != owner["knowledge_id"]
        ):
            continue

        existing_text = payload.get(
            "text"
        )

        if (
            isinstance(existing_text, str)
            and _normalize_claim_text(
                existing_text
            ) == normalized_text
        ):
            raise ValueError(
                "Duplicate canonical claim refused: "
                f"{existing.get('claim_id')} already "
                "has the same normalized text under "
                f"knowledge_id "
                f"{owner['knowledge_id']!r}."
            )

    config = load_config(root)
    now = project_now(config)

    event = {
        "event_id": (
            "EV-" + uuid4().hex[:16]
        ),
        "event_type": "claim_created",
        "occurred_at": now.isoformat(),
        "actor": actor.strip(),
        "claim_id": (
            "KCL-" + uuid4().hex[:16]
        ),
        "previous_event_id": None,
        "payload": {
            "knowledge_id": (
                owner["knowledge_id"]
            ),
            "knowledge_type": (
                owner["knowledge_type"]
            ),
            "text": text.strip(),
            "topic": topic.strip(),
            "created_at": (
                now.date().isoformat()
            ),
            "as_of": as_of.isoformat(),
            "creation_provenance": {
                "basis": provenance_basis,
                "evidence_refs": (
                    resolved_evidence
                ),
                "note": (
                    provenance_note.strip()
                ),
            },
        },
    }

    ledger = claim_ledger_path(
        root
    ).resolve()

    ledger.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    original = ledger.read_bytes()
    original_hash = _sha256(original)

    event_line = (
        json.dumps(
            event,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )

    candidate = original

    if (
        candidate
        and not candidate.endswith(b"\n")
    ):
        candidate += b"\n"

    candidate += event_line

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=ledger.parent,
            prefix=".canonical_claims.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

            handle.write(candidate)
            handle.flush()
            os.fsync(handle.fileno())

        candidate_result = read_claim_ledger(
            root,
            path=temp_path,
        )

        if not candidate_result.valid:
            detail = "; ".join(
                f"line {issue.line}: "
                f"{issue.field}: "
                f"{issue.message}"
                for issue
                in candidate_result.issues
            )

            raise ValueError(
                "Candidate canonical claim "
                "ledger failed replay validation. "
                + detail
            )

        if dry_run:
            return event

        # Optimistic concurrency guard:
        # refuse to overwrite if another writer
        # changed the ledger after our preflight.
        latest = ledger.read_bytes()

        if _sha256(latest) != original_hash:
            raise RuntimeError(
                "Canonical claim ledger changed "
                "during append; retry the operation."
            )

        os.replace(
            temp_path,
            ledger,
        )

        temp_path = None

        committed = read_claim_ledger(
            root
        )

        if not committed.valid:
            detail = "; ".join(
                f"line {issue.line}: "
                f"{issue.field}: "
                f"{issue.message}"
                for issue in committed.issues
            )

            raise RuntimeError(
                "CRITICAL: canonical claim ledger "
                "failed post-commit replay "
                "verification. "
                + detail
            )

        committed_events = [
            item
            for item in committed.events
            if item.get("event_id")
            == event["event_id"]
        ]

        if len(committed_events) != 1:
            raise RuntimeError(
                "CRITICAL: committed canonical "
                "claim event could not be verified "
                "exactly once in the authoritative "
                "ledger."
            )

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()

    return event


def _append_lifecycle_event(
    root: Path,
    event: dict,
    *,
    dry_run: bool,
) -> dict:
    ledger = claim_ledger_path(
        root
    ).resolve()

    original = ledger.read_bytes()
    original_hash = _sha256(original)

    event_line = (
        json.dumps(
            event,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )

    candidate = original

    if (
        candidate
        and not candidate.endswith(b"\n")
    ):
        candidate += b"\n"

    candidate += event_line

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=ledger.parent,
            prefix=".canonical_claims.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

            handle.write(candidate)
            handle.flush()
            os.fsync(handle.fileno())

        candidate_result = read_claim_ledger(
            root,
            path=temp_path,
        )

        if not candidate_result.valid:
            detail = "; ".join(
                f"line {issue.line}: "
                f"{issue.field}: "
                f"{issue.message}"
                for issue
                in candidate_result.issues
            )

            raise ValueError(
                "Candidate canonical claim "
                "ledger failed replay validation. "
                + detail
            )

        if dry_run:
            return event

        latest = ledger.read_bytes()

        if _sha256(latest) != original_hash:
            raise RuntimeError(
                "Canonical claim ledger changed "
                "during append; retry the operation."
            )

        os.replace(
            temp_path,
            ledger,
        )

        temp_path = None

        committed = read_claim_ledger(
            root
        )

        if not committed.valid:
            detail = "; ".join(
                f"line {issue.line}: "
                f"{issue.field}: "
                f"{issue.message}"
                for issue in committed.issues
            )

            raise RuntimeError(
                "CRITICAL: canonical claim ledger "
                "failed post-commit replay "
                "verification. "
                + detail
            )

        matches = [
            item
            for item in committed.events
            if item.get("event_id")
            == event["event_id"]
        ]

        if len(matches) != 1:
            raise RuntimeError(
                "CRITICAL: committed canonical "
                "claim event could not be verified "
                "exactly once in the authoritative "
                "ledger."
            )

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()

    return event


def append_claim_reviewed(
    root: Path,
    claim_id: str,
    *,
    as_of: date,
    reviewer: str,
    basis: str,
    run_ids: list[str] | None = None,
    note: str | None = None,
    actor: str,
    dry_run: bool = False,
) -> dict:
    root = root.resolve()

    for name, value in (
        ("claim_id", claim_id),
        ("reviewer", reviewer),
        ("basis", basis),
        ("actor", actor),
    ):
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"{name} must be a "
                "non-empty string."
            )

    if not isinstance(as_of, date):
        raise ValueError(
            "as_of must be a date."
        )

    if basis not in {
        "manual",
        "research_run",
        "mixed",
    }:
        raise ValueError(
            f"Unknown review basis: {basis!r}."
        )

    run_ids = list(run_ids or [])

    if basis == "manual" and run_ids:
        raise ValueError(
            "Manual claim review must not "
            "include research run IDs; "
            "use basis 'mixed' instead."
        )

    if (
        note is not None
        and not isinstance(note, str)
    ):
        raise ValueError(
            "note must be a string or null."
        )

    current = read_claim_ledger(
        root
    )

    if not current.valid:
        detail = "; ".join(
            f"line {issue.line}: "
            f"{issue.field}: "
            f"{issue.message}"
            for issue in current.issues
        )

        raise ValueError(
            "Canonical claim ledger is invalid; "
            "review refused. "
            + detail
        )

    states = project_claim_states(
        current
    )

    claim = states.get(
        claim_id
    )

    if claim is None:
        raise ValueError(
            f"Canonical claim not found: "
            f"{claim_id}"
        )

    if claim.status not in {
        "needs_review",
        "active",
    }:
        raise ValueError(
            f"Canonical claim {claim_id} "
            f"cannot be reviewed from status "
            f"{claim.status!r}."
        )

    schema = load_temporal_schema(
        root
    )

    policy = knowledge_type_policy(
        schema,
        claim.knowledge_type,
    )

    review_days = policy.get(
        "default_review_days"
    )

    if (
        not isinstance(review_days, int)
        or review_days <= 0
    ):
        raise ValueError(
            "Claim knowledge type must define "
            "a positive default_review_days."
        )

    config = load_config(root)
    now = project_now(config)
    verified_on = now.date()

    if as_of > verified_on:
        raise ValueError(
            "as_of cannot be later than "
            "the review date."
        )

    runs = validate_review_runs(
        root,
        basis=basis,
        run_ids=run_ids,
    )

    event = {
        "event_id": (
            "EV-" + uuid4().hex[:16]
        ),
        "event_type": "claim_reviewed",
        "occurred_at": now.isoformat(),
        "actor": actor.strip(),
        "claim_id": claim.claim_id,
        "previous_event_id": (
            claim.head_event_id
        ),
        "payload": {
            "as_of": as_of.isoformat(),
            "last_verified_at": (
                verified_on.isoformat()
            ),
            "next_review_at": (
                verified_on
                + timedelta(
                    days=review_days
                )
            ).isoformat(),
            "review_provenance": {
                "reviewer": reviewer.strip(),
                "basis": basis,
                "scope": "claim",
                "runs": runs,
                "note": note,
            },
        },
    }

    return _append_lifecycle_event(
        root,
        event,
        dry_run=dry_run,
    )
