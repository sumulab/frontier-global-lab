from __future__ import annotations

import hashlib
import json
import os
import tempfile

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .canonical_claim_ledger import (
    read_claim_ledger,
)
from .runtime import load_config, project_now


RELATIONSHIP_SCHEMA_VERSION = "0.1.0"


@dataclass(frozen=True)
class ClaimRelationshipIssue:
    line: int | None
    field: str
    message: str


@dataclass(frozen=True)
class ClaimRelationship:
    relationship_id: str
    relationship_type: str
    source_claim_id: str
    target_claim_id: str
    reason: str
    occurred_at: str
    actor: str
    provenance: dict[str, Any]


@dataclass(frozen=True)
class ClaimRelationshipValidationResult:
    valid: bool
    relationships: list[ClaimRelationship]
    issues: list[ClaimRelationshipIssue]


def relationship_ledger_path(root: Path) -> Path:
    config = load_config(root)
    relative = config[
        "canonical_claim_store"
    ]["relationship_ledger"]

    return root / relative


def load_relationship_schema(root: Path) -> dict:
    path = (
        root
        / "10_Harness"
        / "temporal"
        / "claim_relationship_schema.json"
    )
    schema = json.loads(
        path.read_text(encoding="utf-8")
    )
    version = schema.get("schema_version")

    if version != RELATIONSHIP_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported claim relationship schema "
            f"version: {version!r}; expected "
            f"{RELATIONSHIP_SCHEMA_VERSION!r}."
        )

    return schema


def read_claim_relationships(
    root: Path,
    *,
    path: Path | None = None,
) -> ClaimRelationshipValidationResult:
    root = root.resolve()
    schema = load_relationship_schema(root)
    claim_ledger = read_claim_ledger(root)

    if not claim_ledger.valid:
        return ClaimRelationshipValidationResult(
            valid=False,
            relationships=[],
            issues=[
                ClaimRelationshipIssue(
                    line=issue.line,
                    field=f"claim_ledger.{issue.field}",
                    message=issue.message,
                )
                for issue in claim_ledger.issues
            ],
        )

    known_claims = {
        event["claim_id"]
        for event in claim_ledger.events
        if event["event_type"] == "claim_created"
    }
    explicit_path = (
        path
        if path is not None
        else relationship_ledger_path(root)
    )
    raw_lines = (
        explicit_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if explicit_path.exists()
        else []
    )
    relationships: list[ClaimRelationship] = []
    issues: list[ClaimRelationshipIssue] = []
    seen_ids: set[str] = set()
    seen_tuples: set[tuple[str, str, str]] = set()

    for line_number, raw in enumerate(
        raw_lines,
        1,
    ):
        if not raw.strip():
            continue

        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            issues.append(
                ClaimRelationshipIssue(
                    line=line_number,
                    field="json",
                    message=f"Invalid JSON: {exc.msg}",
                )
            )
            continue

        relationship = _validate_relationship(
            schema,
            record,
            line_number,
            known_claims,
            seen_ids,
            seen_tuples,
            issues,
        )

        if relationship is not None:
            relationships.append(relationship)

    _append_legacy_relationships(
        claim_ledger.events,
        relationships,
        seen_ids,
        seen_tuples,
    )

    return ClaimRelationshipValidationResult(
        valid=not issues,
        relationships=relationships,
        issues=issues,
    )


def _validate_relationship(
    schema: dict,
    record: Any,
    line_number: int,
    known_claims: set[str],
    seen_ids: set[str],
    seen_tuples: set[tuple[str, str, str]],
    issues: list[ClaimRelationshipIssue],
) -> ClaimRelationship | None:
    if not isinstance(record, dict):
        issues.append(
            ClaimRelationshipIssue(
                line=line_number,
                field="relationship",
                message="Must be a JSON object.",
            )
        )
        return None

    for field in schema["required_fields"]:
        if field not in record:
            issues.append(
                ClaimRelationshipIssue(
                    line=line_number,
                    field=field,
                    message="Required field is missing.",
                )
            )

    string_fields = (
        "relationship_id",
        "relationship_type",
        "source_claim_id",
        "target_claim_id",
        "reason",
        "occurred_at",
        "actor",
    )

    for field in string_fields:
        value = record.get(field)

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            issues.append(
                ClaimRelationshipIssue(
                    line=line_number,
                    field=field,
                    message="Must be a non-empty string.",
                )
            )

    relationship_type = record.get(
        "relationship_type"
    )

    if relationship_type not in schema[
        "relationship_types"
    ]:
        issues.append(
            ClaimRelationshipIssue(
                line=line_number,
                field="relationship_type",
                message=(
                    "Unknown relationship type: "
                    f"{relationship_type!r}."
                ),
            )
        )

    relationship_id = record.get(
        "relationship_id"
    )

    if relationship_id in seen_ids:
        issues.append(
            ClaimRelationshipIssue(
                line=line_number,
                field="relationship_id",
                message="Duplicate relationship ID.",
            )
        )
    elif isinstance(relationship_id, str):
        seen_ids.add(relationship_id)

    source = record.get("source_claim_id")
    target = record.get("target_claim_id")

    for field, claim_id in (
        ("source_claim_id", source),
        ("target_claim_id", target),
    ):
        if (
            isinstance(claim_id, str)
            and claim_id
            and claim_id not in known_claims
        ):
            issues.append(
                ClaimRelationshipIssue(
                    line=line_number,
                    field=field,
                    message=(
                        "Referenced canonical claim "
                        f"does not exist: {claim_id}"
                    ),
                )
            )

    if source == target and isinstance(source, str):
        issues.append(
            ClaimRelationshipIssue(
                line=line_number,
                field="target_claim_id",
                message=(
                    "A claim relationship cannot "
                    "reference itself."
                ),
            )
        )

    identity = (source, target, relationship_type)

    if all(isinstance(value, str) for value in identity):
        if identity in seen_tuples:
            issues.append(
                ClaimRelationshipIssue(
                    line=line_number,
                    field="relationship_type",
                    message=(
                        "Duplicate source/target/type "
                        "relationship."
                    ),
                )
            )
        else:
            seen_tuples.add(identity)

    occurred_at = record.get("occurred_at")

    if isinstance(occurred_at, str):
        try:
            parsed = datetime.fromisoformat(
                occurred_at
            )
        except ValueError:
            parsed = None

        if (
            parsed is None
            or parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            issues.append(
                ClaimRelationshipIssue(
                    line=line_number,
                    field="occurred_at",
                    message=(
                        "Must be a timezone-aware "
                        "ISO 8601 timestamp."
                    ),
                )
            )

    provenance = record.get("provenance")

    if not isinstance(provenance, dict):
        issues.append(
            ClaimRelationshipIssue(
                line=line_number,
                field="provenance",
                message="Must be a mapping.",
            )
        )
    elif provenance.get("basis") not in schema[
        "provenance_basis_values"
    ]:
        issues.append(
            ClaimRelationshipIssue(
                line=line_number,
                field="provenance.basis",
                message="Unknown provenance basis.",
            )
        )

    if issues and issues[-1].line == line_number:
        return None

    return ClaimRelationship(**record)


def _append_legacy_relationships(
    events: list[dict[str, Any]],
    relationships: list[ClaimRelationship],
    seen_ids: set[str],
    seen_tuples: set[tuple[str, str, str]],
) -> None:
    for event in events:
        if event["event_type"] != "claim_contradicted":
            continue

        for index, target in enumerate(
            event["payload"].get(
                "contradicted_by_claim_ids",
                [],
            )
        ):
            identity = (
                event["claim_id"],
                target,
                "contradicts",
            )

            if identity in seen_tuples:
                continue

            relationship_id = (
                f"REL-legacy-{event['event_id']}-"
                f"{index}"
            )

            if relationship_id in seen_ids:
                continue

            relationships.append(
                ClaimRelationship(
                    relationship_id=relationship_id,
                    relationship_type="contradicts",
                    source_claim_id=event["claim_id"],
                    target_claim_id=target,
                    reason=event["payload"]["reason"],
                    occurred_at=event["occurred_at"],
                    actor=event["actor"],
                    provenance={
                        "basis": "legacy_event",
                        "event_id": event["event_id"],
                    },
                )
            )
            seen_ids.add(relationship_id)
            seen_tuples.add(identity)


def append_claim_relationship(
    root: Path,
    *,
    relationship_type: str,
    source_claim_id: str,
    target_claim_id: str,
    reason: str,
    actor: str,
    provenance_basis: str = "manual",
    provenance_note: str | None = None,
    dry_run: bool = False,
) -> dict:
    root = root.resolve()
    schema = load_relationship_schema(root)

    values = {
        "relationship_type": relationship_type,
        "source_claim_id": source_claim_id,
        "target_claim_id": target_claim_id,
        "reason": reason,
        "actor": actor,
        "provenance_basis": provenance_basis,
    }

    for name, value in values.items():
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"{name} must be a non-empty string."
            )

    if relationship_type not in schema[
        "relationship_types"
    ]:
        raise ValueError(
            "Unknown relationship type: "
            f"{relationship_type!r}."
        )

    if provenance_basis not in {
        "manual",
        "research_evidence",
    }:
        raise ValueError(
            "New relationships require manual or "
            "research_evidence provenance."
        )

    current = read_claim_relationships(root)

    if not current.valid:
        detail = "; ".join(
            f"line {issue.line}: {issue.field}: "
            f"{issue.message}"
            for issue in current.issues
        )
        raise ValueError(
            "Claim relationship ledger is invalid; "
            f"append refused. {detail}"
        )

    config = load_config(root)
    now = project_now(config)
    record = {
        "relationship_id": (
            "REL-" + uuid4().hex[:16]
        ),
        "relationship_type": (
            relationship_type.strip()
        ),
        "source_claim_id": source_claim_id.strip(),
        "target_claim_id": target_claim_id.strip(),
        "reason": reason.strip(),
        "occurred_at": now.isoformat(),
        "actor": actor.strip(),
        "provenance": {
            "basis": provenance_basis,
            "note": (
                provenance_note.strip()
                if isinstance(provenance_note, str)
                else None
            ),
        },
    }
    ledger = relationship_ledger_path(root).resolve()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    original = (
        ledger.read_bytes() if ledger.exists() else b""
    )
    original_hash = hashlib.sha256(original).digest()
    candidate = original

    if candidate and not candidate.endswith(b"\n"):
        candidate += b"\n"

    candidate += (
        json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=ledger.parent,
            prefix=".claim_relationships.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(candidate)
            handle.flush()
            os.fsync(handle.fileno())

        checked = read_claim_relationships(
            root,
            path=temp_path,
        )

        if not checked.valid:
            detail = "; ".join(
                f"line {issue.line}: {issue.field}: "
                f"{issue.message}"
                for issue in checked.issues
            )
            raise ValueError(
                "Candidate claim relationship ledger "
                f"is invalid. {detail}"
            )

        if dry_run:
            return record

        latest = (
            ledger.read_bytes()
            if ledger.exists()
            else b""
        )

        if hashlib.sha256(latest).digest() != (
            original_hash
        ):
            raise RuntimeError(
                "Claim relationship ledger changed "
                "during append; retry the operation."
            )

        os.replace(temp_path, ledger)
        temp_path = None
        committed = read_claim_relationships(root)

        if not committed.valid:
            raise RuntimeError(
                "CRITICAL: committed relationship "
                "ledger failed replay validation."
            )

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()

    return record
