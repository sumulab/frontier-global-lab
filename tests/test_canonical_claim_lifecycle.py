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


REPOSITORY_ROOT = Path(__file__).parents[1]


def _write_ledger(
    tmp_path: Path,
    events: list[dict],
) -> Path:
    root = tmp_path

    harness = (
        root
        / "10_Harness"
    )

    temporal = (
        harness
        / "temporal"
    )

    temporal.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        harness
        / "config.json"
    ).write_text(
        """
{
  "version": "0.4.0",
  "project_timezone": "UTC",
  "canonical_claim_store": {
    "ledger": "10_Harness/temporal/canonical_claims.jsonl",
    "index_db": "10_Harness/runtime/knowledge/canonical_claims.sqlite"
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    shutil.copyfile(
        REPOSITORY_ROOT
        / "10_Harness"
        / "temporal"
        / "claim_event_schema.json",
        temporal / "claim_event_schema.json",
    )

    (
        temporal
        / "canonical_claims.jsonl"
    ).write_text(
        "\n".join(
            json.dumps(event)
            for event in events
        )
        + "\n",
        encoding="utf-8",
    )

    return root


def _created_event() -> dict:
    return {
        "event_id": "EV-create",
        "event_type": "claim_created",
        "occurred_at": "2026-08-20T00:00:00+00:00",
        "actor": "test",
        "claim_id": "KCL-test",
        "previous_event_id": None,
        "payload": {
            "knowledge_id": "test",
            "knowledge_type": "research",
            "text": "Test claim",
            "topic": "test",
            "created_at": "2026-08-20",
            "as_of": "2026-08-20",
            "creation_provenance": {
                "basis": "manual",
                "evidence_refs": [],
                "note": "test",
            },
        },
    }


def _event(
    event_type: str,
    previous: str,
) -> dict:
    if event_type == "claim_reviewed":
        payload = {
            "as_of": "2026-08-20",
            "last_verified_at": "2026-08-20",
            "next_review_at": "2026-10-19",
            "review_provenance": {
                "reviewer": "test-reviewer",
                "basis": "manual",
                "scope": "claim",
                "runs": [],
                "note": "test review",
            },
        }
    else:
        payload = {"reason": "test transition"}

    return {
        "event_id": f"EV-{event_type}",
        "event_type": event_type,
        "occurred_at": "2026-08-20T00:01:00+00:00",
        "actor": "test",
        "claim_id": "KCL-test",
        "previous_event_id": previous,
        "payload": payload,
    }


def _transition_event(
    event_type: str,
    previous: str,
    *,
    event_id: str,
) -> dict:
    if event_type == "claim_reviewed":
        payload = _event(
            event_type,
            previous,
        )["payload"]
    elif event_type == "claim_superseded":
        payload = {
            "superseded_by_claim_id": (
                "KCL-replacement"
            ),
            "reason": "replacement test",
        }
    else:
        payload = {"reason": "transition test"}

    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": (
            "2026-08-20T00:02:00+00:00"
        ),
        "actor": "test",
        "claim_id": "KCL-test",
        "previous_event_id": previous,
        "payload": payload,
    }


def _events_for_status(status: str) -> list[dict]:
    replacement = _created_event() | {
        "event_id": "EV-replacement",
        "claim_id": "KCL-replacement",
    }
    created = _created_event()

    if status == "needs_review":
        return [replacement, created]

    reviewed = _transition_event(
        "claim_reviewed",
        "EV-create",
        event_id="EV-reviewed",
    )

    if status == "active":
        return [replacement, created, reviewed]

    if status == "superseded":
        superseded = _transition_event(
            "claim_superseded",
            "EV-reviewed",
            event_id="EV-superseded",
        )

        return [
            replacement,
            created,
            reviewed,
            superseded,
        ]

    if status == "archived":
        archived = _transition_event(
            "claim_archived",
            "EV-reviewed",
            event_id="EV-archived",
        )

        return [
            replacement,
            created,
            reviewed,
            archived,
        ]

    raise AssertionError(f"unknown status {status}")


def test_claim_created_then_reviewed_is_valid(
    tmp_path: Path,
):
    root = _write_ledger(
        tmp_path,
        [
            _created_event(),
            _event(
                "claim_reviewed",
                "EV-create",
            ),
        ],
    )

    result = read_claim_ledger(root)

    assert result.valid


def test_historical_cannot_become_active(
    tmp_path: Path,
):
    root = _write_ledger(
        tmp_path,
        [
            _created_event(),
            _event(
                "claim_marked_historical",
                "EV-create",
            ),
            _event(
                "claim_reviewed",
                "EV-claim_marked_historical",
            ),
        ],
    )

    result = read_claim_ledger(root)

    assert not result.valid
    assert any(
        "Illegal lifecycle transition"
        in issue.message
        for issue in result.issues
    )


def test_legacy_historical_projects_to_archived(
    tmp_path: Path,
):
    root = _write_ledger(
        tmp_path,
        [
            _created_event(),
            _event(
                "claim_marked_historical",
                "EV-create",
            ),
        ],
    )

    ledger = read_claim_ledger(root)
    states = project_claim_states(ledger)
    claim = states["KCL-test"]

    assert claim.status == "archived"
    assert claim.status_changed_at == (
        "2026-08-20T00:01:00+00:00"
    )


def test_public_repository_ledger_is_empty_and_valid():
    ledger = read_claim_ledger(REPOSITORY_ROOT)
    states = project_claim_states(ledger)

    assert ledger.valid
    assert ledger.events == []
    assert states == {}


@pytest.mark.parametrize(
    ("status", "event_type", "allowed"),
    [
        (status, event_type, status in allowed_from)
        for event_type, allowed_from in {
            "claim_reviewed": {
                "needs_review",
                "active",
            },
            "claim_marked_needs_review": {
                "active"
            },
            "claim_superseded": {
                "needs_review",
                "active",
            },
            "claim_archived": {
                "needs_review",
                "active",
                "superseded",
            },
        }.items()
        for status in (
            "needs_review",
            "active",
            "superseded",
            "archived",
        )
    ],
)
def test_v05_transition_matrix_fails_closed(
    tmp_path: Path,
    status: str,
    event_type: str,
    allowed: bool,
):
    events = _events_for_status(status)
    head = events[-1]["event_id"]
    events.append(
        _transition_event(
            event_type,
            head,
            event_id="EV-candidate",
        )
    )

    result = read_claim_ledger(
        _write_ledger(tmp_path, events)
    )

    assert result.valid is allowed

    if not allowed:
        assert any(
            "Illegal lifecycle transition"
            in issue.message
            for issue in result.issues
        )


def test_duplicate_event_id_fails_closed(
    tmp_path: Path,
):
    duplicate = _created_event() | {
        "claim_id": "KCL-other"
    }
    result = read_claim_ledger(
        _write_ledger(
            tmp_path,
            [_created_event(), duplicate],
        )
    )

    assert not result.valid
    assert any(
        "Duplicate event_id" in issue.message
        for issue in result.issues
    )


def test_broken_event_chain_fails_closed(
    tmp_path: Path,
):
    result = read_claim_ledger(
        _write_ledger(
            tmp_path,
            [
                _created_event(),
                _transition_event(
                    "claim_reviewed",
                    "EV-wrong-head",
                    event_id="EV-review",
                ),
            ],
        )
    )

    assert not result.valid
    assert any(
        "current claim head" in issue.message
        for issue in result.issues
    )


def test_unknown_event_type_fails_closed(
    tmp_path: Path,
):
    unknown = _transition_event(
        "claim_archived",
        "EV-create",
        event_id="EV-unknown",
    )
    unknown["event_type"] = "claim_magic"
    result = read_claim_ledger(
        _write_ledger(
            tmp_path,
            [_created_event(), unknown],
        )
    )

    assert not result.valid
    assert any(
        issue.field == "event_type"
        and "Unknown" in issue.message
        for issue in result.issues
    )
