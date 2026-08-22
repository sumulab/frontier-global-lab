from __future__ import annotations

import json
import shutil

from pathlib import Path

from harness.canonical_claim_index import (
    canonical_index_path,
    rebuild_canonical_index,
)
from harness.canonical_claim_ledger import (
    read_claim_ledger,
)
from harness.canonical_document import (
    freeze_document_identity,
)


ROOT = Path(__file__).parents[1]


def _source_reference() -> dict:
    retrieved_at = "2026-08-22T00:00:00+00:00"
    content_hash = "a" * 64
    document = freeze_document_identity(
        url="https://example.com/report",
        content_hash=content_hash,
        retrieved_at=retrieved_at,
        title="Synthetic report",
        publisher="example.com",
    )
    return {
        "source_contract_version": "0.1.0",
        "run": {
            "run_id": "synthetic-run",
            "workflow_id": "synthetic-workflow",
            "completed_at": retrieved_at,
            "research_as_of": retrieved_at,
        },
        "evidence_id": "E-synthetic",
        "research_claim_id": "C-synthetic",
        "effective_claim": "Synthetic test claim",
        "source_url": "https://example.com/report",
        "source_title": "Synthetic report",
        "publisher": "example.com",
        "published_at": None,
        "retrieved_at": retrieved_at,
        "source_content_hash": content_hash,
        "document": document,
        "excerpt": "Synthetic excerpt.",
        "context": "Synthetic context around the excerpt.",
        "location": {"section_heading": "Test"},
        "review": {
            "decision": "approved",
            "reviewer": "test-reviewer",
            "reviewed_at": retrieved_at,
            "note": "Synthetic fixture review.",
        },
    }


def _created_event() -> dict:
    return {
        "event_id": "EV-synthetic",
        "event_type": "claim_created",
        "occurred_at": "2026-08-22T00:00:00+00:00",
        "actor": "test",
        "claim_id": "KCL-synthetic",
        "previous_event_id": None,
        "payload": {
            "knowledge_id": "synthetic-document",
            "knowledge_type": "research",
            "text": "Synthetic canonical claim",
            "topic": "test",
            "created_at": "2026-08-22",
            "as_of": "2026-08-22",
            "creation_provenance": {
                "basis": "research_evidence",
                "evidence_refs": [_source_reference()],
                "note": "Synthetic index fixture.",
            },
        },
    }


def _root(tmp_path: Path) -> Path:
    temporal = (
        tmp_path / "10_Harness" / "temporal"
    )
    temporal.mkdir(parents=True)
    config = {
        "version": "0.5.0",
        "project_timezone": "UTC",
        "canonical_claim_store": {
            "ledger": (
                "10_Harness/temporal/"
                "canonical_claims.jsonl"
            ),
            "relationship_ledger": (
                "10_Harness/temporal/"
                "claim_relationships.jsonl"
            ),
            "index_db": (
                "10_Harness/runtime/knowledge/"
                "canonical_claims.sqlite"
            ),
        },
    }
    (tmp_path / "10_Harness" / "config.json").write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    for name in (
        "claim_event_schema.json",
        "claim_relationship_schema.json",
    ):
        shutil.copyfile(
            ROOT / "10_Harness" / "temporal" / name,
            temporal / name,
        )

    (temporal / "canonical_claims.jsonl").write_text(
        json.dumps(_created_event()) + "\n",
        encoding="utf-8",
    )

    (temporal / "claim_relationships.jsonl").write_text(
        "",
        encoding="utf-8",
    )

    return tmp_path


def test_document_identity_is_stable_and_versioned():
    first = freeze_document_identity(
        url="https://example.com/report",
        content_hash="a" * 64,
        retrieved_at=(
            "2026-08-22T00:00:00+00:00"
        ),
    )
    repeated = freeze_document_identity(
        url="https://example.com/report",
        content_hash="a" * 64,
        retrieved_at=(
            "2026-08-23T00:00:00+00:00"
        ),
    )
    changed = freeze_document_identity(
        url="https://example.com/report",
        content_hash="b" * 64,
        retrieved_at=(
            "2026-08-23T00:00:00+00:00"
        ),
    )

    assert first["document_id"] == repeated[
        "document_id"
    ]
    assert first["document_version_id"] == (
        repeated["document_version_id"]
    )
    assert first["document_id"] == changed[
        "document_id"
    ]
    assert first["document_version_id"] != (
        changed["document_version_id"]
    )


def test_v05_source_snapshot_fails_closed_when_incomplete(
    tmp_path: Path,
):
    root = _root(tmp_path)
    ledger_path = (
        root
        / "10_Harness"
        / "temporal"
        / "canonical_claims.jsonl"
    )
    events = [
        json.loads(line)
        for line in ledger_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    reference = events[0]["payload"][
        "creation_provenance"
    ]["evidence_refs"][0]
    reference.pop("document")
    ledger_path.write_text(
        "\n".join(
            json.dumps(event) for event in events
        )
        + "\n",
        encoding="utf-8",
    )

    result = read_claim_ledger(root)

    assert not result.valid
    assert any(
        issue.field.endswith(".document")
        for issue in result.issues
    )


def test_index_delete_and_rebuild_is_deterministic(
    tmp_path: Path,
):
    root = _root(tmp_path)
    first = rebuild_canonical_index(root)
    path = canonical_index_path(root)

    assert first.claim_count == 1
    assert first.relationship_count == 0
    assert first.document_count == 1
    assert first.evidence_count == 1

    path.unlink()

    second = rebuild_canonical_index(root)

    assert second == first
