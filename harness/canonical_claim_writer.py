from __future__ import annotations

import hashlib
import json
import os
import tempfile

from datetime import date
from pathlib import Path
from uuid import uuid4

from .canonical_claim_ledger import (
    claim_ledger_path,
    read_claim_ledger,
)
from .runtime import (
    load_config,
    project_now,
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
    actor: str,
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

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()

    return event
