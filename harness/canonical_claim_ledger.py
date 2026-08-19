from __future__ import annotations

import json

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ClaimLedgerIssue:
    line: int | None
    field: str
    message: str


@dataclass(frozen=True)
class ClaimLedgerValidationResult:
    valid: bool
    events: list[dict[str, Any]]
    issues: list[ClaimLedgerIssue]


def load_claim_event_schema(
    root: Path,
) -> dict:
    path = (
        root
        / "10_Harness"
        / "temporal"
        / "claim_event_schema.json"
    )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def claim_ledger_path(
    root: Path,
) -> Path:
    config_path = (
        root
        / "10_Harness"
        / "config.json"
    )

    config = json.loads(
        config_path.read_text(
            encoding="utf-8"
        )
    )

    relative = (
        config["canonical_claim_store"][
            "ledger"
        ]
    )

    return root / relative


def read_claim_ledger(
    root: Path,
) -> ClaimLedgerValidationResult:
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

    events: list[dict[str, Any]] = []
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

        events.append(event)

    _validate_event_chains(
        events,
        issues,
    )

    _validate_claim_relations(
        events,
        issues,
    )

    _validate_lifecycle_transitions(
        schema,
        events,
        issues,
    )

    return ClaimLedgerValidationResult(
        valid=not issues,
        events=events,
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

        created_at = _parse_payload_date(
            payload.get("created_at")
        )

        as_of = _parse_payload_date(
            payload.get("as_of")
        )

        if (
            created_at
            and as_of
            and as_of < created_at
        ):
            issues.append(
                ClaimLedgerIssue(
                    line=line_number,
                    field="payload.as_of",
                    message=(
                        "as_of cannot be earlier "
                        "than created_at."
                    ),
                )
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

            if scope != "full_document":
                issues.append(
                    ClaimLedgerIssue(
                        line=line_number,
                        field=(
                            "payload."
                            "review_provenance."
                            "scope"
                        ),
                        message=(
                            "Canonical claim review "
                            "currently requires "
                            "full_document scope."
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
    events: list[dict[str, Any]],
    issues: list[ClaimLedgerIssue],
) -> None:
    current_status: dict[str, str] = {}

    event_types = schema.get(
        "event_types",
        {},
    )

    for line_number, event in enumerate(
        events,
        1,
    ):
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

        current_status[
            claim_id
        ] = resulting_status


def _validate_claim_relations(
    events: list[dict[str, Any]],
    issues: list[ClaimLedgerIssue],
) -> None:
    known_claims = {
        event.get("claim_id")
        for event in events
        if (
            event.get("event_type")
            == "claim_created"
            and isinstance(
                event.get("claim_id"),
                str,
            )
            and event.get("claim_id")
        )
    }

    for line_number, event in enumerate(
        events,
        1,
    ):
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
    events: list[dict[str, Any]],
    issues: list[ClaimLedgerIssue],
) -> None:
    seen_event_ids: set[str] = set()
    claim_heads: dict[str, str] = {}
    created_claims: set[str] = set()

    for index, event in enumerate(
        events,
        1,
    ):
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
