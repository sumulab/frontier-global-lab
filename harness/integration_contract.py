from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


TASK_CONTRACT_VERSION = "cognitrace.frontier.task/0.1.0"
RESULT_CONTRACT_VERSION = "frontier.cognitrace.result/0.1.0"
RECEIPT_CONTRACT_VERSION = "cognitrace.frontier.receipt/0.1.0"

_HASH_PREFIX = "sha256:"
_HASH_LENGTH = len(_HASH_PREFIX) + 64


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    code: str
    message: str


class ContractValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = tuple(issues)
        super().__init__(
            "; ".join(
                f"{issue.field}: {issue.message}"
                for issue in issues
            )
        )


def load_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractValidationError(
            [
                ValidationIssue(
                    field="$",
                    code="invalid_json",
                    message=str(exc),
                )
            ]
        ) from exc

    if not isinstance(value, dict):
        raise ContractValidationError(
            [
                ValidationIssue(
                    field="$",
                    code="invalid_type",
                    message="Contract document must be a JSON object.",
                )
            ]
        )
    return value


def canonical_result_hash(document: dict[str, Any]) -> str:
    payload = dict(document)
    payload.pop("result_content_hash", None)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _HASH_PREFIX + hashlib.sha256(encoded).hexdigest()


def seal_result(document: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(document)
    candidate["result_content_hash"] = canonical_result_hash(candidate)
    validate_result(candidate)
    return candidate


def validate_task(document: dict[str, Any]) -> None:
    issues: list[ValidationIssue] = []
    _object_shape(
        document,
        "$",
        required={
            "contract_version",
            "task_id",
            "action_id",
            "issued_at",
            "objective",
            "evaluation_contract",
        },
        optional={"context_refs", "constraints"},
        issues=issues,
    )
    _version(
        document,
        TASK_CONTRACT_VERSION,
        issues,
    )
    _identifier(document.get("task_id"), "task_id", issues)
    _identifier(document.get("action_id"), "action_id", issues)
    _timestamp(document.get("issued_at"), "issued_at", issues)
    _nonempty_text(document.get("objective"), "objective", issues)

    evaluation = document.get("evaluation_contract")
    if _object_shape(
        evaluation,
        "evaluation_contract",
        required={"ref", "content_hash", "locked_at"},
        optional=set(),
        issues=issues,
    ):
        _uri(evaluation.get("ref"), "evaluation_contract.ref", issues)
        _hash(
            evaluation.get("content_hash"),
            "evaluation_contract.content_hash",
            issues,
        )
        _timestamp(
            evaluation.get("locked_at"),
            "evaluation_contract.locked_at",
            issues,
        )

    _references(
        document.get("context_refs", []),
        "context_refs",
        issues,
    )
    constraints = document.get("constraints", {})
    if not isinstance(constraints, dict):
        _issue(
            issues,
            "constraints",
            "invalid_type",
            "constraints must be an object.",
        )
    _raise(issues)


def validate_result(document: dict[str, Any]) -> None:
    issues: list[ValidationIssue] = []
    _object_shape(
        document,
        "$",
        required={
            "contract_version",
            "task_id",
            "action_id",
            "frontier_run_id",
            "completed_at",
            "result_summary",
            "artifact_refs",
            "evidence_refs",
            "review",
            "runtime_provenance",
            "result_content_hash",
        },
        optional=set(),
        issues=issues,
    )
    _version(document, RESULT_CONTRACT_VERSION, issues)
    for field in ("task_id", "action_id", "frontier_run_id"):
        _identifier(document.get(field), field, issues)
    _timestamp(document.get("completed_at"), "completed_at", issues)
    _nonempty_text(
        document.get("result_summary"),
        "result_summary",
        issues,
    )

    artifacts = document.get("artifact_refs")
    evidence = document.get("evidence_refs")
    _references(artifacts, "artifact_refs", issues, artifact=True)
    _references(evidence, "evidence_refs", issues, evidence=True)
    if (
        isinstance(artifacts, list)
        and isinstance(evidence, list)
        and not artifacts
        and not evidence
    ):
        _issue(
            issues,
            "artifact_refs",
            "empty_result",
            "A completed result needs at least one artifact or evidence reference.",
        )

    _review(document.get("review"), issues)
    _runtime_provenance(document.get("runtime_provenance"), issues)
    supplied_hash = document.get("result_content_hash")
    if _hash(supplied_hash, "result_content_hash", issues):
        expected = canonical_result_hash(document)
        if supplied_hash != expected:
            _issue(
                issues,
                "result_content_hash",
                "hash_mismatch",
                f"Expected {expected}.",
            )
    _raise(issues)


def validate_receipt(document: dict[str, Any]) -> None:
    issues: list[ValidationIssue] = []
    _object_shape(
        document,
        "$",
        required={
            "contract_version",
            "submission_id",
            "task_id",
            "action_id",
            "frontier_run_id",
            "result_content_hash",
            "received_at",
            "status",
            "errors",
        },
        optional=set(),
        issues=issues,
    )
    _version(document, RECEIPT_CONTRACT_VERSION, issues)
    for field in (
        "submission_id",
        "task_id",
        "action_id",
        "frontier_run_id",
    ):
        _identifier(document.get(field), field, issues)
    _hash(
        document.get("result_content_hash"),
        "result_content_hash",
        issues,
    )
    _timestamp(document.get("received_at"), "received_at", issues)

    status = document.get("status")
    if status not in {"accepted", "duplicate", "rejected"}:
        _issue(
            issues,
            "status",
            "unknown_value",
            "status must be accepted, duplicate, or rejected.",
        )
    errors = document.get("errors")
    if not isinstance(errors, list):
        _issue(
            issues,
            "errors",
            "invalid_type",
            "errors must be an array.",
        )
    else:
        for index, error in enumerate(errors):
            field = f"errors[{index}]"
            if _object_shape(
                error,
                field,
                required={"code", "field", "message"},
                optional=set(),
                issues=issues,
            ):
                for name in ("code", "field", "message"):
                    _nonempty_text(
                        error.get(name),
                        f"{field}.{name}",
                        issues,
                    )
        if status in {"accepted", "duplicate"} and errors:
            _issue(
                issues,
                "errors",
                "status_conflict",
                "Accepted or duplicate receipts cannot contain errors.",
            )
        if status == "rejected" and not errors:
            _issue(
                issues,
                "errors",
                "status_conflict",
                "Rejected receipts must contain at least one error.",
            )
    _raise(issues)


def verify_receipt(
    result: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    validate_result(result)
    validate_receipt(receipt)
    issues: list[ValidationIssue] = []
    for field in (
        "task_id",
        "action_id",
        "frontier_run_id",
        "result_content_hash",
    ):
        if result[field] != receipt[field]:
            _issue(
                issues,
                field,
                "receipt_mismatch",
                "Receipt does not identify the supplied result.",
            )
    if receipt["status"] == "rejected":
        _issue(
            issues,
            "status",
            "submission_rejected",
            "CogniTrace rejected this result submission.",
        )
    _raise(issues)


def _references(
    value: Any,
    field: str,
    issues: list[ValidationIssue],
    *,
    artifact: bool = False,
    evidence: bool = False,
) -> None:
    if not isinstance(value, list):
        _issue(issues, field, "invalid_type", f"{field} must be an array.")
        return
    seen: set[str] = set()
    for index, reference in enumerate(value):
        base = f"{field}[{index}]"
        required = {"stable_id", "uri", "content_hash"}
        optional: set[str] = set()
        if artifact:
            required.add("media_type")
        if evidence:
            required.add("review_status")
        if not _object_shape(
            reference,
            base,
            required=required,
            optional=optional,
            issues=issues,
        ):
            continue
        stable_id = reference.get("stable_id")
        _identifier(stable_id, f"{base}.stable_id", issues)
        if isinstance(stable_id, str):
            if stable_id in seen:
                _issue(
                    issues,
                    f"{base}.stable_id",
                    "duplicate_id",
                    "stable_id must be unique within the reference list.",
                )
            seen.add(stable_id)
        _uri(reference.get("uri"), f"{base}.uri", issues)
        _hash(reference.get("content_hash"), f"{base}.content_hash", issues)
        if artifact:
            media_type = reference.get("media_type")
            _nonempty_text(media_type, f"{base}.media_type", issues)
            if isinstance(media_type, str) and "/" not in media_type:
                _issue(
                    issues,
                    f"{base}.media_type",
                    "invalid_media_type",
                    "media_type must use type/subtype syntax.",
                )
        if evidence and reference.get("review_status") not in {
            "approved",
            "needs_review",
            "rejected",
        }:
            _issue(
                issues,
                f"{base}.review_status",
                "unknown_value",
                "review_status must be approved, needs_review, or rejected.",
            )


def _review(value: Any, issues: list[ValidationIssue]) -> None:
    if not _object_shape(
        value,
        "review",
        required={"status"},
        optional={"reviewed_by", "reviewed_at", "note"},
        issues=issues,
    ):
        return
    status = value.get("status")
    if status not in {"approved", "needs_review", "rejected"}:
        _issue(
            issues,
            "review.status",
            "unknown_value",
            "status must be approved, needs_review, or rejected.",
        )
    reviewer = value.get("reviewed_by")
    reviewed_at = value.get("reviewed_at")
    if status in {"approved", "rejected"}:
        _nonempty_text(reviewer, "review.reviewed_by", issues)
        _timestamp(reviewed_at, "review.reviewed_at", issues)
    elif reviewer is not None or reviewed_at is not None:
        _issue(
            issues,
            "review",
            "status_conflict",
            "needs_review cannot claim a completed reviewer or review time.",
        )
    if value.get("note") is not None:
        _nonempty_text(value.get("note"), "review.note", issues)


def _runtime_provenance(value: Any, issues: list[ValidationIssue]) -> None:
    if not _object_shape(
        value,
        "runtime_provenance",
        required={"provider", "model", "prompt_refs", "skill_refs", "budget"},
        optional=set(),
        issues=issues,
    ):
        return
    _nonempty_text(value.get("provider"), "runtime_provenance.provider", issues)
    _nonempty_text(value.get("model"), "runtime_provenance.model", issues)
    _references(value.get("prompt_refs"), "runtime_provenance.prompt_refs", issues)
    _references(value.get("skill_refs"), "runtime_provenance.skill_refs", issues)
    budget = value.get("budget")
    if _object_shape(
        budget,
        "runtime_provenance.budget",
        required={"unit", "limit", "used"},
        optional=set(),
        issues=issues,
    ):
        _nonempty_text(budget.get("unit"), "runtime_provenance.budget.unit", issues)
        limit = budget.get("limit")
        used = budget.get("used")
        for name, number in (("limit", limit), ("used", used)):
            if isinstance(number, bool) or not isinstance(number, int) or number < 0:
                _issue(
                    issues,
                    f"runtime_provenance.budget.{name}",
                    "invalid_number",
                    f"{name} must be a non-negative integer.",
                )
        if (
            isinstance(limit, int)
            and not isinstance(limit, bool)
            and isinstance(used, int)
            and not isinstance(used, bool)
            and used > limit
        ):
            _issue(
                issues,
                "runtime_provenance.budget.used",
                "budget_exceeded",
                "used cannot exceed the declared limit.",
            )


def _version(
    document: dict[str, Any],
    expected: str,
    issues: list[ValidationIssue],
) -> None:
    if document.get("contract_version") != expected:
        _issue(
            issues,
            "contract_version",
            "unsupported_version",
            f"Expected {expected}.",
        )


def _object_shape(
    value: Any,
    field: str,
    *,
    required: set[str],
    optional: set[str],
    issues: list[ValidationIssue],
) -> bool:
    if not isinstance(value, dict):
        _issue(issues, field, "invalid_type", f"{field} must be an object.")
        return False
    for name in sorted(required - value.keys()):
        prefix = "" if field == "$" else f"{field}."
        _issue(
            issues,
            f"{prefix}{name}",
            "missing_field",
            "Required field is missing.",
        )
    allowed = required | optional
    for name in sorted(value.keys() - allowed):
        prefix = "" if field == "$" else f"{field}."
        _issue(
            issues,
            f"{prefix}{name}",
            "unknown_field",
            "Unknown field is not allowed by this contract version.",
        )
    return True


def _identifier(value: Any, field: str, issues: list[ValidationIssue]) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        _issue(
            issues,
            field,
            "invalid_identifier",
            "Identifier must be a non-empty string of at most 160 characters.",
        )
        return False
    if any(character.isspace() for character in value):
        _issue(
            issues,
            field,
            "invalid_identifier",
            "Identifier cannot contain whitespace.",
        )
        return False
    return True


def _nonempty_text(value: Any, field: str, issues: list[ValidationIssue]) -> bool:
    if not isinstance(value, str) or not value.strip():
        _issue(
            issues,
            field,
            "invalid_text",
            "Value must be a non-empty string.",
        )
        return False
    return True


def _timestamp(value: Any, field: str, issues: list[ValidationIssue]) -> bool:
    if not isinstance(value, str):
        _issue(
            issues,
            field,
            "invalid_timestamp",
            "Timestamp must be an RFC 3339 string with a timezone.",
        )
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        _issue(
            issues,
            field,
            "invalid_timestamp",
            "Timestamp must be RFC 3339 and include a timezone.",
        )
        return False
    return True


def _uri(value: Any, field: str, issues: list[ValidationIssue]) -> bool:
    if not isinstance(value, str) or not value.strip():
        _issue(issues, field, "invalid_uri", "URI must be a non-empty string.")
        return False
    parsed = urlparse(value)
    if not parsed.scheme or parsed.scheme == "file":
        _issue(
            issues,
            field,
            "invalid_uri",
            "URI must have a non-file scheme so it remains stable across workspaces.",
        )
        return False
    return True


def _hash(value: Any, field: str, issues: list[ValidationIssue]) -> bool:
    if (
        not isinstance(value, str)
        or len(value) != _HASH_LENGTH
        or not value.startswith(_HASH_PREFIX)
    ):
        valid = False
    else:
        try:
            int(value[len(_HASH_PREFIX) :], 16)
            valid = value == value.lower()
        except ValueError:
            valid = False
    if not valid:
        _issue(
            issues,
            field,
            "invalid_hash",
            "Hash must be sha256: followed by 64 lowercase hexadecimal characters.",
        )
    return valid


def _issue(
    issues: list[ValidationIssue],
    field: str,
    code: str,
    message: str,
) -> None:
    issues.append(ValidationIssue(field=field, code=code, message=message))


def _raise(issues: list[ValidationIssue]) -> None:
    if issues:
        raise ContractValidationError(issues)
