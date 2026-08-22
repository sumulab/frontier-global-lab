from __future__ import annotations

import json
import shutil

from pathlib import Path

import pytest

from harness.canonical_claim_ledger import (
    read_claim_ledger,
)
from harness.canonical_claim_projector import (
    project_claim_states,
)
from harness.canonical_claim_relationship import (
    append_claim_relationship,
    read_claim_relationships,
)


ROOT = Path(__file__).parents[1]


def _created(
    claim_id: str,
    event_id: str,
) -> dict:
    return {
        "event_id": event_id,
        "event_type": "claim_created",
        "occurred_at": (
            "2026-08-22T00:00:00+00:00"
        ),
        "actor": "test",
        "claim_id": claim_id,
        "previous_event_id": None,
        "payload": {
            "knowledge_id": "test",
            "knowledge_type": "research",
            "text": f"Statement {claim_id}",
            "topic": "test",
            "created_at": "2026-08-22",
            "as_of": "2026-08-22",
            "creation_provenance": {
                "basis": "manual",
                "evidence_refs": [],
                "note": "test",
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

    claim_events = [
        _created("KCL-source", "EV-source"),
        _created("KCL-target", "EV-target"),
    ]
    (temporal / "canonical_claims.jsonl").write_text(
        "\n".join(
            json.dumps(event)
            for event in claim_events
        )
        + "\n",
        encoding="utf-8",
    )
    (temporal / "claim_relationships.jsonl").write_text(
        "",
        encoding="utf-8",
    )

    return tmp_path


def _relationship(**changes) -> dict:
    record = {
        "relationship_id": "REL-test",
        "relationship_type": "contradicts",
        "source_claim_id": "KCL-source",
        "target_claim_id": "KCL-target",
        "reason": "test contradiction",
        "occurred_at": (
            "2026-08-22T01:00:00+00:00"
        ),
        "actor": "test",
        "provenance": {
            "basis": "manual",
            "note": "test",
        },
    }
    record.update(changes)
    return record


def _write_relationships(
    root: Path,
    records: list[dict],
) -> None:
    path = (
        root
        / "10_Harness"
        / "temporal"
        / "claim_relationships.jsonl"
    )
    path.write_text(
        "\n".join(
            json.dumps(record)
            for record in records
        )
        + ("\n" if records else ""),
        encoding="utf-8",
    )


def test_contradiction_does_not_change_lifecycle(
    tmp_path: Path,
):
    root = _root(tmp_path)
    before = project_claim_states(
        read_claim_ledger(root)
    )
    _write_relationships(root, [_relationship()])

    result = read_claim_relationships(root)
    after = project_claim_states(
        read_claim_ledger(root)
    )

    assert result.valid
    assert len(result.relationships) == 1
    assert before == after
    assert after["KCL-source"].status == (
        "needs_review"
    )
    assert after["KCL-target"].status == (
        "needs_review"
    )


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        (
            {"relationship_type": "unknown"},
            "relationship_type",
        ),
        (
            {"target_claim_id": "KCL-source"},
            "target_claim_id",
        ),
        (
            {"target_claim_id": "KCL-missing"},
            "target_claim_id",
        ),
        (
            {"occurred_at": "2026-08-22"},
            "occurred_at",
        ),
        (
            {"provenance": {"basis": "agent"}},
            "provenance.basis",
        ),
    ],
)
def test_invalid_relationship_fails_closed(
    tmp_path: Path,
    changes: dict,
    field: str,
):
    root = _root(tmp_path)
    _write_relationships(
        root,
        [_relationship(**changes)],
    )

    result = read_claim_relationships(root)

    assert not result.valid
    assert any(
        issue.field == field
        for issue in result.issues
    )


def test_duplicate_relationship_tuple_fails_closed(
    tmp_path: Path,
):
    root = _root(tmp_path)
    _write_relationships(
        root,
        [
            _relationship(),
            _relationship(
                relationship_id="REL-second"
            ),
        ],
    )

    result = read_claim_relationships(root)

    assert not result.valid
    assert any(
        "Duplicate source/target/type"
        in issue.message
        for issue in result.issues
    )


def test_relationship_writer_dry_run_then_append(
    tmp_path: Path,
):
    root = _root(tmp_path)
    ledger = (
        root
        / "10_Harness"
        / "temporal"
        / "claim_relationships.jsonl"
    )

    preview = append_claim_relationship(
        root,
        relationship_type="qualifies",
        source_claim_id="KCL-source",
        target_claim_id="KCL-target",
        reason="test condition",
        actor="test",
        dry_run=True,
    )

    assert preview["relationship_type"] == (
        "qualifies"
    )
    assert ledger.read_text(encoding="utf-8") == ""

    appended = append_claim_relationship(
        root,
        relationship_type="qualifies",
        source_claim_id="KCL-source",
        target_claim_id="KCL-target",
        reason="test condition",
        actor="test",
        dry_run=False,
    )
    result = read_claim_relationships(root)

    assert result.valid
    assert [
        item.relationship_id
        for item in result.relationships
    ] == [appended["relationship_id"]]


def test_legacy_contradiction_projects_compatibly(
    tmp_path: Path,
):
    root = _root(tmp_path)
    claim_ledger = (
        root
        / "10_Harness"
        / "temporal"
        / "canonical_claims.jsonl"
    )
    events = [
        _created("KCL-source", "EV-source"),
        _created("KCL-target", "EV-target"),
        {
            "event_id": "EV-legacy-contradiction",
            "event_type": "claim_contradicted",
            "occurred_at": (
                "2026-08-22T02:00:00+00:00"
            ),
            "actor": "legacy-reviewer",
            "claim_id": "KCL-source",
            "previous_event_id": "EV-source",
            "payload": {
                "reason": "legacy contradiction",
                "provenance": {"basis": "manual"},
                "contradicted_by_claim_ids": [
                    "KCL-target"
                ],
            },
        },
    ]
    claim_ledger.write_text(
        "\n".join(
            json.dumps(event) for event in events
        )
        + "\n",
        encoding="utf-8",
    )

    claims = project_claim_states(
        read_claim_ledger(root)
    )
    relationships = read_claim_relationships(root)

    assert claims["KCL-source"].status == "archived"
    assert relationships.valid
    assert len(relationships.relationships) == 1
    legacy = relationships.relationships[0]
    assert legacy.relationship_type == "contradicts"
    assert legacy.provenance["basis"] == (
        "legacy_event"
    )
