from __future__ import annotations

import json

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .canonical_claim_contract import (
    claim_ledger_path,
    load_claim_event_schema,
)
from .canonical_source_validation import (
    validate_source_snapshot,
)


@dataclass(frozen=True)
class ClaimLedgerIssue:
    line: int | None
    field: str
    message: str


@dataclass(frozen=True)
class _ParsedClaimEvent:
    line_number: int
    event: dict[str, Any]


@dataclass(frozen=True)
class ClaimLedgerValidationResult:
    valid: bool
    events: list[dict[str, Any]]
    issues: list[ClaimLedgerIssue]


def read_claim_ledger(
    root: Path,
    *,
    path: Path | None = None,
) -> ClaimLedgerValidationResult:
    if path is None:
        path = claim_ledger_path(root)

    if not path.exists():
        return ClaimLedgerValidationResult(
            valid=False,
            events=[],
            issues=[
                ClaimLedgerIssue(
                    line=None,
                    field="ledger",
                    message=(
                        f"Ledger not found: {path}"
                    ),
                )
            ],
        )

    schema = load_claim_event_schema(root)

    parsed_events: list[_ParsedClaimEvent] = []
    issues: list[ClaimLedgerIssue] = []

    for line_number, raw in enumerate(
        path.read_text(
            encoding="utf-8"
        ).splitlines(),
        1,
    ):
        if not raw.strip():
            continue

        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field="json",
                    message=(
                        f"Invalid JSON: {exc.msg}"
                    ),
                )
            )
            continue

        if not isinstance(event, dict):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field="event",
                    message=(
                        "Ledger event must be "
                        "a JSON object."
                    ),
                )
            )
            continue

        _validate_event(
            schema,
            event,
            line_number,
            issues,
        )

        parsed_events.append(
            _ParsedClaimEvent(
                line_number=line_number,
                event=event,
            )
        )

    _validate_event_chains(
        parsed_events,
        issues,
    )

    _validate_claim_relations(
        parsed_events,
        issues,
    )

    _validate_lifecycle_transitions(
        schema,
        parsed_events,
        issues,
    )

    return ClaimLedgerValidationResult(
        valid=not issues,
        events=[
            item.event
            for item in parsed_events
        ],
        issues=issues,
    )


def _validate_event(
    schema: dict,
    event: dict[str, Any],
    line_number: int,
    issues: list[ClaimLedgerIssue],
) -> None:
    for field in schema.get(
        "common_required_fields",
        [],
    ):
        if field not in event:
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=field,
                    message=(
                        "Required event field "
                        "is missing."
                    ),
                )
            )

    event_type = event.get(
        "event_type"
    )

    event_policy = (
        schema.get(
            "event_types",
            {},
        ).get(
            event_type
        )
    )

    if event_policy is None:
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field="event_type",
                message=(
                    f"Unknown event_type "
                    f"{event_type!r}."
                ),
            )
        )
        return

    for field in (
        "event_id",
        "actor",
        "claim_id",
    ):
        value = event.get(field)

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=field,
                    message=(
                        "Must be a non-empty "
                        "string."
                    ),
                )
            )

    occurred_at = event.get(
        "occurred_at"
    )

    if isinstance(
        occurred_at,
        str,
    ):
        try:
            parsed = datetime.fromisoformat(
                occurred_at
            )
        except ValueError:
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field="occurred_at",
                    message=(
                        "Must be a valid ISO 8601 "
                        "timestamp."
                    ),
                )
            )
        else:
            if (
                parsed.tzinfo is None
                or parsed.utcoffset() is None
            ):
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field="occurred_at",
                        message=(
                            "Timestamp must include "
                            "timezone information."
                        ),
                    )
                )
    else:
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field="occurred_at",
                message=(
                    "Must be a string."
                ),
            )
        )

    previous_event_id = event.get(
        "previous_event_id"
    )

    if event_type == "claim_created":
        if previous_event_id is not None:
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field="previous_event_id",
                    message=(
                        "claim_created must use "
                        "null previous_event_id."
                    ),
                )
            )
    elif (
        not isinstance(
            previous_event_id,
            str,
        )
        or not previous_event_id.strip()
    ):
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field="previous_event_id",
                message=(
                    "Lifecycle event must reference "
                    "the previous event."
                ),
            )
        )

    payload = event.get(
        "payload"
    )

    if not isinstance(
        payload,
        dict,
    ):
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field="payload",
                message=(
                    "Payload must be a mapping."
                ),
            )
        )
        return

    for field in event_policy.get(
        "required_payload_fields",
        [],
    ):
        value = payload.get(field)

        if value is None or value == "":
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=f"payload.{field}",
                    message=(
                        "Required payload field "
                        "is missing."
                    ),
                )
            )


    if event_type == "claim_created":
        for field in (
            "knowledge_id",
            "knowledge_type",
            "text",
            "topic",
        ):
            value = payload.get(field)

            if (
                not isinstance(value, str)
                or not value.strip()
            ):
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=f"payload.{field}",
                        message=(
                            "Must be a non-empty string."
                        ),
                    )
                )

        _validate_payload_date(
            payload,
            "created_at",
            line_number,
            issues,
        )

        _validate_payload_date(
            payload,
            "as_of",
            line_number,
            issues,
        )

        if "creation_provenance" in payload:
            _validate_creation_provenance(
                schema,
                payload[
                    "creation_provenance"
                ],
                line_number,
                issues,
            )

    elif event_type == "claim_reviewed":
        for field in (
            "as_of",
            "last_verified_at",
            "next_review_at",
        ):
            _validate_payload_date(
                payload,
                field,
                line_number,
                issues,
            )

        as_of = _parse_payload_date(
            payload.get("as_of")
        )

        last_verified_at = _parse_payload_date(
            payload.get("last_verified_at")
        )

        next_review_at = _parse_payload_date(
            payload.get("next_review_at")
        )

        if (
            as_of
            and last_verified_at
            and as_of > last_verified_at
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field="payload.as_of",
                    message=(
                        "as_of cannot be later than "
                        "last_verified_at."
                    ),
                )

            )

        if (
            last_verified_at
            and next_review_at
            and next_review_at
            < last_verified_at
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field="payload.next_review_at",
                    message=(
                        "next_review_at cannot be "
                        "earlier than last_verified_at."
                    ),
                )
            )

        provenance = payload.get(
            "review_provenance"
        )

        if not isinstance(
            provenance,
            dict,
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=(
                        "payload.review_provenance"
                    ),
                    message=(
                        "review_provenance must be "
                        "a mapping."
                    ),
                )
            )

        else:
            reviewer = provenance.get(
                "reviewer"
            )

            if (
                not isinstance(reviewer, str)
                or not reviewer.strip()
            ):
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "review_provenance."
                            "reviewer"
                        ),
                        message=(
                            "Reviewer must be a "
                            "non-empty string."
                        ),
                    )
                )

            basis = provenance.get(
                "basis"
            )

            if basis not in {
                "manual",
                "research_run",
                "mixed",
            }:
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "review_provenance."
                            "basis"
                        ),
                        message=(
                            "Unknown review basis."
                        ),
                    )
                )

            scope = provenance.get(
                "scope"
            )

            allowed_scopes = schema.get(
                "review_scope_values",
                [
                    "claim",
                ],
            )

            if scope not in allowed_scopes:
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "review_provenance."
                            "scope"
                        ),
                        message=(
                            f"Unknown canonical claim "
                            f"review scope {scope!r}. "
                            f"Allowed: "
                            + ", ".join(
                                allowed_scopes
                            )
                        ),
                    )
                )

            runs = provenance.get(
                "runs",
                [],
            )

            if not isinstance(
                runs,
                list,
            ):
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "review_provenance."
                            "runs"
                        ),
                        message=(
                            "runs must be a list."
                        ),
                    )
                )

            elif (
                basis in {
                    "research_run",
                    "mixed",
                }
                and not runs
            ):
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "review_provenance."
                            "runs"
                        ),
                        message=(
                            "Research-backed review "
                            "requires at least one "
                            "run snapshot."
                        ),
                    )
                )

            note = provenance.get(
                "note"
            )

            if (
                basis in {
                    "research_run",
                    "mixed",
                }
                and (
                    not isinstance(note, str)
                    or not note.strip()
                )
            ):
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "review_provenance."
                            "note"
                        ),
                        message=(
                            "Research-backed review "
                            "requires a non-empty "
                            "rationale."
                        ),
                    )
                )

    elif event_type == "claim_source_upgraded":
        _validate_creation_provenance(
            schema,
            {
                "basis": "research_evidence",
                "evidence_refs": payload.get(
                    "evidence_refs"
                ),
                "note": payload.get("reason"),
            },
            line_number,
            issues,
        )


def _validate_timezone_timestamp(
    value,
    field,
    line_number,
    issues,
):
    if not isinstance(value, str):
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field=field,
                message=(
                    "Must be an ISO 8601 "
                    "timestamp string."
                ),
            )
        )
        return

    try:
        parsed = datetime.fromisoformat(
            value
        )
    except ValueError:
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field=field,
                message=(
                    "Must be a valid ISO 8601 "
                    "timestamp."
                ),
            )
        )
        return

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field=field,
                message=(
                    "Timestamp must include "
                    "timezone information."
                ),
            )
        )


def _validate_creation_provenance(
    schema,
    provenance,
    line_number,
    issues,
):
    base = "payload.creation_provenance"

    if not isinstance(provenance, dict):
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field=base,
                message=(
                    "creation_provenance must "
                    "be a mapping."
                ),
            )
        )
        return

    basis = provenance.get("basis")

    allowed_basis = schema.get(
        "creation_provenance_basis_values",
        [
            "manual",
            "research_evidence",
        ],
    )

    if basis not in allowed_basis:
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field=f"{base}.basis",
                message=(
                    "Unknown creation provenance "
                    "basis."
                ),
            )
        )

    note = provenance.get("note")

    if (
        not isinstance(note, str)
        or not note.strip()
    ):
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field=f"{base}.note",
                message=(
                    "Creation provenance requires "
                    "a non-empty rationale."
                ),
            )
        )

    refs = provenance.get(
        "evidence_refs"
    )

    if not isinstance(refs, list):
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field=(
                    f"{base}.evidence_refs"
                ),
                message=(
                    "evidence_refs must be "
                    "a list."
                ),
            )
        )
        return

    if basis == "manual":
        if refs:
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=(
                        f"{base}.evidence_refs"
                    ),
                    message=(
                        "Manual provenance must "
                        "not include evidence_refs."
                    ),
                )
            )

        return

    if basis != "research_evidence":
        return

    if not refs:
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field=(
                    f"{base}.evidence_refs"
                ),
                message=(
                    "Research-evidence provenance "
                    "requires at least one "
                    "approved evidence snapshot."
                ),
            )
        )
        return

    seen = set()

    for index, ref in enumerate(refs):
        ref_base = (
            f"{base}.evidence_refs[{index}]"
        )

        if not isinstance(ref, dict):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=ref_base,
                    message=(
                        "Evidence reference must "
                        "be a mapping."
                    ),
                )
            )
            continue

        for field in (
            "evidence_id",
            "research_claim_id",
            "effective_claim",
            "source_url",
            "excerpt",
        ):
            value = ref.get(field)

            if (
                not isinstance(value, str)
                or not value.strip()
            ):
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            f"{ref_base}.{field}"
                        ),
                        message=(
                            "Must be a non-empty "
                            "string."
                        ),
                    )
                )

        content_hash = ref.get(
            "source_content_hash"
        )

        if (
            content_hash is not None
            and (
                not isinstance(
                    content_hash,
                    str,
                )
                or not content_hash.strip()
            )
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=(
                        f"{ref_base}."
                        "source_content_hash"
                    ),
                    message=(
                        "Must be a non-empty "
                        "string or null."
                    ),
                )
            )

        for field, message in (
            validate_source_snapshot(ref)
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=f"{ref_base}.{field}",
                    message=message,
                )
            )

        run = ref.get("run")

        if not isinstance(run, dict):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=f"{ref_base}.run",
                    message=(
                        "Run snapshot must be "
                        "a mapping."
                    ),
                )
            )
            run_id = None

        else:
            for field in (
                "run_id",
                "workflow_id",
            ):
                value = run.get(field)

                if (
                    not isinstance(value, str)
                    or not value.strip()
                ):
                    issues.append(
                        ClaimLedgerIssue(
                            line=line_number,
                            field=(
                                f"{ref_base}."
                                f"run.{field}"
                            ),
                            message=(
                                "Must be a "
                                "non-empty string."
                            ),
                        )
                    )

            for field in (
                "completed_at",
                "research_as_of",
            ):
                _validate_timezone_timestamp(
                    run.get(field),
                    (
                        f"{ref_base}."
                        f"run.{field}"
                    ),
                    line_number,
                    issues,
                )

            run_id = run.get("run_id")

        evidence_id = ref.get(
            "evidence_id"
        )

        if (
            isinstance(run_id, str)
            and run_id
            and isinstance(
                evidence_id,
                str,
            )
            and evidence_id
        ):
            identity = (
                run_id,
                evidence_id,
            )

            if identity in seen:
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            f"{ref_base}."
                            "evidence_id"
                        ),
                        message=(
                            "Duplicate evidence "
                            "reference."
                        ),
                    )
                )
            else:
                seen.add(identity)

        review = ref.get("review")

        if not isinstance(review, dict):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=(
                        f"{ref_base}.review"
                    ),
                    message=(
                        "Evidence review snapshot "
                        "must be a mapping."
                    ),
                )
            )
            continue

        if (
            review.get("decision")
            != "approved"
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=(
                        f"{ref_base}."
                        "review.decision"
                    ),
                    message=(
                        "Canonical promotion "
                        "requires an approved "
                        "evidence review snapshot."
                    ),
                )
            )

        reviewer = review.get(
            "reviewer"
        )

        if (
            not isinstance(reviewer, str)
            or not reviewer.strip()
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=(
                        f"{ref_base}."
                        "review.reviewer"
                    ),
                    message=(
                        "Approved evidence review "
                        "requires a reviewer."
                    ),
                )
            )

        _validate_timezone_timestamp(
            review.get("reviewed_at"),
            (
                f"{ref_base}."
                "review.reviewed_at"
            ),
            line_number,
            issues,
        )

        review_note = review.get("note")

        if (
            review_note is not None
            and not isinstance(
                review_note,
                str,
            )
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field=(
                        f"{ref_base}."
                        "review.note"
                    ),
                    message=(
                        "Review note must be "
                        "a string or null."
                    ),
                )
            )


def _parse_payload_date(
    value,
):
    from datetime import date

    if not isinstance(
        value,
        str,
    ):
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _validate_payload_date(
    payload,
    field,
    line_number,
    issues,
):
    value = payload.get(field)

    if not isinstance(
        value,
        str,
    ):
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field=f"payload.{field}",
                message=(
                    "Must be an ISO date string."
                ),
            )
        )
        return

    if _parse_payload_date(value) is None:
        issues.append(
            ClaimLedgerIssue(
                line=line_number,
                field=f"payload.{field}",
                message=(
                    "Must use YYYY-MM-DD."
                ),
            )
        )


def _validate_lifecycle_transitions(
    schema: dict,
    events: list[_ParsedClaimEvent],
    issues: list[ClaimLedgerIssue],
) -> None:
    current_status: dict[str, str] = {}

    event_types = schema.get(
        "event_types",
        {},
    )

    for item in events:
        line_number = item.line_number
        event = item.event

        claim_id = event.get(
            "claim_id"
        )

        event_type = event.get(
            "event_type"
        )

        if (
            not isinstance(claim_id, str)
            or not claim_id
        ):
            continue

        policy = event_types.get(
            event_type
        )

        if not isinstance(
            policy,
            dict,
        ):
            continue

        resulting_status = policy.get(
            "resulting_status"
        )

        if event_type == "claim_created":
            # Duplicate creation is reported by
            # the chain validator. Do not reset
            # lifecycle state here.
            if claim_id not in current_status:
                current_status[
                    claim_id
                ] = resulting_status

            continue

        if claim_id not in current_status:
            # Missing creation is reported by
            # the chain validator.
            continue

        previous_status = current_status[
            claim_id
        ]

        allowed = policy.get(
            "allowed_previous_statuses",
            [],
        )

        if previous_status not in allowed:
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field="event_type",
                    message=(
                        f"Illegal lifecycle transition: "
                        f"{previous_status!r} -> "
                        f"{resulting_status!r} via "
                        f"{event_type!r}."
                    ),
                )
            )
            continue

        if policy.get("preserve_status", False):
            continue

        current_status[
            claim_id
        ] = resulting_status


def _validate_claim_relations(
    events: list[_ParsedClaimEvent],
    issues: list[ClaimLedgerIssue],
) -> None:
    known_claims = {
        item.event.get("claim_id")
        for item in events
        if (
            item.event.get("event_type")
            == "claim_created"
            and isinstance(
                item.event.get("claim_id"),
                str,
            )
            and item.event.get("claim_id")
        )
    }

    for item in events:
        line_number = item.line_number
        event = item.event
        event_type = event.get(
            "event_type"
        )

        claim_id = event.get(
            "claim_id"
        )

        payload = event.get(
            "payload"
        )

        if not isinstance(
            payload,
            dict,
        ):
            continue

        if event_type == "claim_superseded":
            target = payload.get(
                "superseded_by_claim_id"
            )

            if (
                not isinstance(target, str)
                or not target.strip()
            ):
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "superseded_by_claim_id"
                        ),
                        message=(
                            "Must be a non-empty "
                            "canonical claim ID."
                        ),
                    )
                )
                continue

            if target == claim_id:
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "superseded_by_claim_id"
                        ),
                        message=(
                            "A claim cannot supersede "
                            "itself."
                        ),
                    )
                )

            elif target not in known_claims:
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "superseded_by_claim_id"
                        ),
                        message=(
                            f"Referenced canonical claim "
                            f"does not exist: {target}"
                        ),
                    )
                )

        elif event_type == "claim_contradicted":
            targets = payload.get(
                "contradicted_by_claim_ids"
            )

            if targets is None:
                continue

            if not isinstance(
                targets,
                list,
            ):
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "contradicted_by_claim_ids"
                        ),
                        message=(
                            "Must be a list of "
                            "canonical claim IDs."
                        ),
                    )
                )
                continue

            seen_targets: set[str] = set()

            for index, target in enumerate(
                targets
            ):
                field = (
                    "payload."
                    "contradicted_by_claim_ids"
                    f"[{index}]"
                )

                if (
                    not isinstance(target, str)
                    or not target.strip()
                ):
                    issues.append(
                        ClaimLedgerIssue(
                            line=line_number,
                            field=field,
                            message=(
                                "Must be a non-empty "
                                "canonical claim ID."
                            ),
                        )
                    )
                    continue

                if target in seen_targets:
                    issues.append(
                        ClaimLedgerIssue(
                            line=line_number,
                            field=field,
                            message=(
                                "Duplicate contradiction "
                                "claim reference."
                            ),
                        )
                    )
                    continue

                seen_targets.add(target)

                if target == claim_id:
                    issues.append(
                        ClaimLedgerIssue(
                            line=line_number,
                            field=field,
                            message=(
                                "A claim cannot contradict "
                                "itself."
                            ),
                        )
                    )

                elif target not in known_claims:
                    issues.append(
                        ClaimLedgerIssue(
                            line=line_number,
                            field=field,
                            message=(
                                f"Referenced canonical claim "
                                f"does not exist: {target}"
                            ),
                        )
                    )


def _validate_event_chains(
    events: list[_ParsedClaimEvent],
    issues: list[ClaimLedgerIssue],
) -> None:
    seen_event_ids: set[str] = set()
    claim_heads: dict[str, str] = {}
    created_claims: set[str] = set()

    for item in events:
        index = item.line_number
        event = item.event

        event_id = event.get(
            "event_id"
        )

        claim_id = event.get(
            "claim_id"
        )

        event_type = event.get(
            "event_type"
        )

        previous_event_id = event.get(
            "previous_event_id"
        )

        if (
            not isinstance(event_id, str)
            or not event_id
        ):
            continue

        if event_id in seen_event_ids:
            issues.append(
                ClaimLedgerIssue(
                    line=index,
                    field="event_id",
                    message=(
                        f"Duplicate event_id "
                        f"{event_id!r}."
                    ),
                )
            )
            continue

        seen_event_ids.add(event_id)

        if (
            not isinstance(claim_id, str)
            or not claim_id
        ):
            continue

        if event_type == "claim_created":
            if claim_id in created_claims:
                issues.append(
                    ClaimLedgerIssue(
                        line=index,
                        field="claim_id",
                        message=(
                            "Claim has more than one "
                            "claim_created event."
                        ),
                    )
                )
                continue

            created_claims.add(
                claim_id
            )
            claim_heads[
                claim_id
            ] = event_id
            continue

        if claim_id not in created_claims:
            issues.append(
                ClaimLedgerIssue(
                    line=index,
                    field="claim_id",
                    message=(
                        "Lifecycle event appears "
                        "before claim_created."
                    ),
                )
            )
            continue

        expected_previous = claim_heads.get(
            claim_id
        )

        if (
            previous_event_id
            != expected_previous
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=index,
                    field="previous_event_id",
                    message=(
                        "Event does not reference "
                        "the current claim head. "
                        f"Expected "
                        f"{expected_previous!r}."
                    ),
                )
            )
            continue

        claim_heads[
            claim_id
        ] = event_id
