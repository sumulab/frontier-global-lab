from __future__ import annotations

import json

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TemporalValidationIssue:
    field: str
    message: str


@dataclass(frozen=True)
class TemporalValidationResult:
    valid: bool
    issues: list[TemporalValidationIssue]


def load_temporal_schema(
    root: Path,
) -> dict:
    path = (
        root
        / "10_Harness"
        / "temporal"
        / "knowledge_schema.json"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Temporal schema not found: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def knowledge_type_policy(
    schema: dict,
    knowledge_type: str,
) -> dict:
    policies = schema.get(
        "knowledge_types",
        {},
    )

    if knowledge_type not in policies:
        raise ValueError(
            f"Unknown knowledge_type: "
            f"{knowledge_type}"
        )

    return policies[knowledge_type]


def _validate_iso_date(
    field: str,
    value: Any,
    issues: list[TemporalValidationIssue],
) -> date | None:
    if not isinstance(value, str):
        issues.append(
            TemporalValidationIssue(
                field=field,
                message=(
                    "Must be an ISO date string "
                    "in YYYY-MM-DD format."
                ),
            )
        )
        return None

    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        issues.append(
            TemporalValidationIssue(
                field=field,
                message=(
                    "Invalid ISO date; expected "
                    "YYYY-MM-DD."
                ),
            )
        )
        return None

    return parsed


def validate_temporal_metadata(
    schema: dict,
    metadata: dict,
) -> TemporalValidationResult:
    issues: list[TemporalValidationIssue] = []

    for field in schema.get(
        "required_identity_fields",
        [
            "id",
            "knowledge_type",
        ],
    ):
        value = metadata.get(field)

        if value is None or value == "":
            issues.append(
                TemporalValidationIssue(
                    field=field,
                    message=(
                        "Required identity field "
                        "is missing."
                    ),
                )
            )

    knowledge_type = metadata.get(
        "knowledge_type"
    )

    if not knowledge_type:
        return TemporalValidationResult(
            valid=False,
            issues=issues,
        )

    try:
        policy = knowledge_type_policy(
            schema,
            knowledge_type,
        )
    except ValueError as exc:
        issues.append(
            TemporalValidationIssue(
                field="knowledge_type",
                message=str(exc),
            )
        )

        return TemporalValidationResult(
            valid=False,
            issues=issues,
        )

    # Non-temporal document types do not require
    # document-level freshness metadata.
    if not policy.get(
        "temporal",
        False,
    ):
        return TemporalValidationResult(
            valid=True,
            issues=[],
        )

    required = schema.get(
        "required_temporal_fields",
        [],
    )

    for field in required:
        value = metadata.get(field)

        if value is None or value == "":
            issues.append(
                TemporalValidationIssue(
                    field=field,
                    message="Required field is missing.",
                )
            )

    knowledge_id = metadata.get("id")

    if (
        knowledge_id is not None
        and (
            not isinstance(
                knowledge_id,
                str,
            )
            or not knowledge_id.strip()
        )
    ):
        issues.append(
            TemporalValidationIssue(
                field="id",
                message=(
                    "Must be a non-empty stable "
                    "knowledge identifier."
                ),
            )
        )

    status = metadata.get("status")

    status_required = (
        schema.get(
            "status_required_fields",
            {},
        ).get(
            status,
            [],
        )
    )

    for field in status_required:
        value = metadata.get(field)

        if value is None or value == "":
            issues.append(
                TemporalValidationIssue(
                    field=field,
                    message=(
                        f"Required when status "
                        f"is '{status}'."
                    ),
                )
            )

    provenance = metadata.get(
        "review_provenance"
    )

    if provenance is not None:
        if not isinstance(
            provenance,
            dict,
        ):
            issues.append(
                TemporalValidationIssue(
                    field="review_provenance",
                    message="Must be a mapping.",
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
                    TemporalValidationIssue(
                        field=(
                            "review_provenance.reviewer"
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

            allowed_basis = schema.get(
                "review_basis_values",
                [],
            )

            if basis not in allowed_basis:
                issues.append(
                    TemporalValidationIssue(
                        field=(
                            "review_provenance.basis"
                        ),
                        message=(
                            f"Unknown review basis "
                            f"{basis!r}. Allowed: "
                            + ", ".join(
                                allowed_basis
                            )
                        ),
                    )
                )

            scope = provenance.get(
                "scope"
            )

            allowed_scopes = schema.get(
                "review_scope_values",
                [],
            )

            if scope not in allowed_scopes:
                issues.append(
                    TemporalValidationIssue(
                        field=(
                            "review_provenance.scope"
                        ),
                        message=(
                            f"Unknown review scope "
                            f"{scope!r}. Allowed: "
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

            if runs is None:
                runs = []

            if not isinstance(
                runs,
                list,
            ):
                issues.append(
                    TemporalValidationIssue(
                        field=(
                            "review_provenance.runs"
                        ),
                        message=(
                            "runs must be a list."
                        ),
                    )
                )

            else:
                required_run_fields = (
                    schema.get(
                        "review_run_snapshot_fields",
                        [
                            "run_id",
                            "workflow_id",
                            "completed_at",
                            "research_as_of",
                        ],
                    )
                )

                seen_run_ids = set()

                for index, run in enumerate(
                    runs
                ):
                    prefix = (
                        "review_provenance."
                        f"runs[{index}]"
                    )

                    if not isinstance(
                        run,
                        dict,
                    ):
                        issues.append(
                            TemporalValidationIssue(
                                field=prefix,
                                message=(
                                    "Run snapshot must "
                                    "be a mapping."
                                ),
                            )
                        )
                        continue

                    for field in required_run_fields:
                        value = run.get(field)

                        if (
                            not isinstance(
                                value,
                                str,
                            )
                            or not value.strip()
                        ):
                            issues.append(
                                TemporalValidationIssue(
                                    field=(
                                        f"{prefix}.{field}"
                                    ),
                                    message=(
                                        "Required non-empty "
                                        "string is missing."
                                    ),
                                )
                            )

                    run_id = run.get(
                        "run_id"
                    )

                    if (
                        isinstance(run_id, str)
                        and run_id.strip()
                    ):
                        if run_id in seen_run_ids:
                            issues.append(
                                TemporalValidationIssue(
                                    field=(
                                        f"{prefix}.run_id"
                                    ),
                                    message=(
                                        "Duplicate run_id "
                                        "in provenance."
                                    ),
                                )
                            )

                        seen_run_ids.add(
                            run_id
                        )

                    parsed_run_times = {}

                    for field in (
                        "completed_at",
                        "research_as_of",
                    ):
                        value = run.get(field)

                        if not isinstance(
                            value,
                            str,
                        ):
                            continue

                        try:
                            parsed = (
                                datetime.fromisoformat(
                                    value
                                )
                            )
                        except ValueError:
                            issues.append(
                                TemporalValidationIssue(
                                    field=(
                                        f"{prefix}.{field}"
                                    ),
                                    message=(
                                        "Must be a valid "
                                        "ISO 8601 timestamp."
                                    ),
                                )
                            )
                            continue

                        if (
                            parsed.tzinfo is None
                            or parsed.utcoffset()
                            is None
                        ):
                            issues.append(
                                TemporalValidationIssue(
                                    field=(
                                        f"{prefix}.{field}"
                                    ),
                                    message=(
                                        "Timestamp must "
                                        "include timezone "
                                        "information."
                                    ),
                                )
                            )
                            continue

                        parsed_run_times[
                            field
                        ] = parsed

                    completed_at = (
                        parsed_run_times.get(
                            "completed_at"
                        )
                    )

                    research_as_of = (
                        parsed_run_times.get(
                            "research_as_of"
                        )
                    )

                    if (
                        completed_at
                        and research_as_of
                        and research_as_of
                        > completed_at
                    ):
                        issues.append(
                            TemporalValidationIssue(
                                field=(
                                    f"{prefix}."
                                    "research_as_of"
                                ),
                                message=(
                                    "research_as_of "
                                    "cannot be later "
                                    "than completed_at."
                                ),
                            )
                        )

                if (
                    basis in {
                        "research_run",
                        "mixed",
                    }
                    and not runs
                ):
                    issues.append(
                        TemporalValidationIssue(
                            field=(
                                "review_provenance.runs"
                            ),
                            message=(
                                "At least one run snapshot "
                                f"is required for basis "
                                f"{basis!r}."
                            ),
                        )
                    )

                if (
                    basis == "manual"
                    and runs
                ):
                    issues.append(
                        TemporalValidationIssue(
                            field=(
                                "review_provenance.runs"
                            ),
                            message=(
                                "Manual review must not "
                                "include research runs; "
                                "use basis 'mixed' instead."
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
                    TemporalValidationIssue(
                        field=(
                            "review_provenance.note"
                        ),
                        message=(
                            "A non-empty review rationale "
                            f"is required for basis "
                            f"{basis!r}."
                        ),
                    )
                )

            elif (
                note is not None
                and not isinstance(
                    note,
                    str,
                )
            ):
                issues.append(
                    TemporalValidationIssue(
                        field=(
                            "review_provenance.note"
                        ),
                        message=(
                            "note must be a string "
                            "or null."
                        ),
                    )
                )

    allowed_statuses = schema.get(
        "document_status",
        [],
    )

    if (
        status is not None
        and status not in allowed_statuses
    ):
        issues.append(
            TemporalValidationIssue(
                field="status",
                message=(
                    f"Unknown status '{status}'. "
                    f"Allowed: "
                    f"{', '.join(allowed_statuses)}"
                ),
            )
        )

    parsed_dates = {}

    for field in (
        "created_at",
        "as_of",
        "last_verified_at",
        "next_review_at",
    ):
        value = metadata.get(field)

        if value:
            parsed_dates[field] = (
                _validate_iso_date(
                    field,
                    value,
                    issues,
                )
            )

    created_at = parsed_dates.get(
        "created_at"
    )
    as_of = parsed_dates.get(
        "as_of"
    )
    last_verified_at = parsed_dates.get(
        "last_verified_at"
    )
    next_review_at = parsed_dates.get(
        "next_review_at"
    )

    if (
        created_at
        and as_of
        and as_of < created_at
    ):
        issues.append(
            TemporalValidationIssue(
                field="as_of",
                message=(
                    "as_of cannot be earlier "
                    "than created_at."
                ),
            )
        )

    if (
        created_at
        and last_verified_at
        and last_verified_at < created_at
    ):
        issues.append(
            TemporalValidationIssue(
                field="last_verified_at",
                message=(
                    "last_verified_at cannot be "
                    "earlier than created_at."
                ),
            )
        )

    if (
        last_verified_at
        and next_review_at
        and next_review_at < last_verified_at
    ):
        issues.append(
            TemporalValidationIssue(
                field="next_review_at",
                message=(
                    "next_review_at cannot be "
                    "earlier than "
                    "last_verified_at."
                ),
            )
        )

    for field in (
        "supersedes",
        "superseded_by",
    ):
        value = metadata.get(field)

        if (
            value is not None
            and not isinstance(
                value,
                str,
            )
        ):
            issues.append(
                TemporalValidationIssue(
                    field=field,
                    message=(
                        "Must be a knowledge ID "
                        "string or null."
                    ),
                )
            )

    if (
        metadata.get("supersedes")
        and metadata.get("superseded_by")
        and metadata["supersedes"]
        == metadata["superseded_by"]
    ):
        issues.append(
            TemporalValidationIssue(
                field="superseded_by",
                message=(
                    "supersedes and "
                    "superseded_by cannot refer "
                    "to the same knowledge ID."
                ),
            )
        )

    return TemporalValidationResult(
        valid=not issues,
        issues=issues,
    )
