from __future__ import annotations

import json
import shutil

from datetime import date
from pathlib import Path

import pytest

from harness.canonical_claim_writer import (
    append_claim_created,
)
from harness.evidence import (
    Claim,
    Evidence,
    EvidenceStatus,
)
from harness.evidence_store import EvidenceStore


ROOT = Path(__file__).parents[1]


def _promotion_root(tmp_path: Path) -> tuple[Path, Path]:
    harness = tmp_path / "10_Harness"
    temporal = harness / "temporal"
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
    (harness / "config.json").write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    for name in (
        "claim_event_schema.json",
        "knowledge_schema.json",
    ):
        shutil.copyfile(
            ROOT / "10_Harness" / "temporal" / name,
            temporal / name,
        )

    (temporal / "scope.json").write_text(
        json.dumps(
            {
                "version": "0.1.0",
                "rules": [
                    {
                        "glob": "fixtures/*.md",
                        "knowledge_type": "research",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    (temporal / "canonical_claims.jsonl").write_text(
        "",
        encoding="utf-8",
    )
    document_dir = tmp_path / "fixtures"
    document_dir.mkdir()
    document = document_dir / "TEST.md"
    document.write_text(
        """---
id: test-research
knowledge_type: research
status: needs_review
created_at: "2026-08-22"
as_of: "2026-08-22"
---

# Test
""",
        encoding="utf-8",
    )
    run_id = "test-run"
    run_dir = harness / "runtime" / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "workflow_id": "test-workflow",
                "completed_at": (
                    "2026-08-22T00:00:00+00:00"
                ),
                "research_as_of": (
                    "2026-08-22T00:00:00+00:00"
                ),
            }
        ),
        encoding="utf-8",
    )
    store = EvidenceStore(run_dir / "evidence.sqlite")
    store.add_claim(
        Claim(
            claim_id="C-test",
            text="Test research claim",
            topic="test",
        )
    )
    store.add_evidence(
        Evidence(
            evidence_id="E-test",
            claim_id="C-test",
            source_url="https://example.com/report",
            status=EvidenceStatus.SUPPORTED,
            excerpt="Test excerpt",
            reasoning="Test reasoning",
            retrieved_at=(
                "2026-08-22T00:00:00+00:00"
            ),
            context_excerpt=(
                "Context around the test excerpt."
            ),
        )
    )

    return tmp_path, document


def test_unreviewed_evidence_cannot_be_promoted(
    tmp_path: Path,
):
    root, document = _promotion_root(tmp_path)

    with pytest.raises(
        ValueError,
        match="has not been human reviewed",
    ):
        append_claim_created(
            root,
            document,
            text="Canonical test claim",
            topic="test",
            as_of=date(2026, 8, 22),
            provenance_basis="research_evidence",
            provenance_note="test promotion",
            evidence_refs=[("test-run", "E-test")],
            actor="test",
            dry_run=True,
        )


def test_approved_evidence_freezes_v05_source_contract(
    tmp_path: Path,
):
    root, document = _promotion_root(tmp_path)
    store = EvidenceStore(
        root
        / "10_Harness"
        / "runtime"
        / "runs"
        / "test-run"
        / "evidence.sqlite"
    )
    store.upsert_source(
        url="https://example.com/report",
        retrieved_at=(
            "2026-08-22T00:00:00+00:00"
        ),
        content_hash="a" * 64,
        status="human_verified",
    )
    store.add_evidence_review(
        evidence_id="E-test",
        decision="approved",
        reviewer="test-reviewer",
        note="approved for promotion test",
    )

    event = append_claim_created(
        root,
        document,
        text="Canonical test claim",
        topic="test",
        as_of=date(2026, 8, 22),
        provenance_basis="research_evidence",
        provenance_note="test promotion",
        evidence_refs=[("test-run", "E-test")],
        actor="test",
        dry_run=True,
    )
    reference = event["payload"][
        "creation_provenance"
    ]["evidence_refs"][0]

    assert reference["source_contract_version"] == (
        "0.1.0"
    )
    assert reference["document"][
        "content_hash"
    ] == "a" * 64
    assert reference["context"] == (
        "Context around the test excerpt."
    )
    assert reference["review"]["decision"] == (
        "approved"
    )
