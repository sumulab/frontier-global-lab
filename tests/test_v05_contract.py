from __future__ import annotations

import json
import re
import tomllib

from pathlib import Path

from harness import __version__


ROOT = Path(__file__).parents[1]
TEMPORAL = ROOT / "10_Harness" / "temporal"

LIFECYCLE = [
    "needs_review",
    "active",
    "superseded",
    "archived",
]

RELATIONSHIPS = [
    "supports",
    "contradicts",
    "qualifies",
    "supersedes",
]

NORMATIVE_DOCUMENTS = [
    ROOT
    / "docs"
    / "decisions"
    / "ADR-0001-canonical-claim-contract.md",
    ROOT
    / "docs"
    / "decisions"
    / "ADR-0002-public-engine-private-workspace.md",
    ROOT
    / "docs"
    / "architecture"
    / "WORKSPACE_BOUNDARY.md",
]


def _load_json(name: str) -> dict:
    return json.loads(
        (TEMPORAL / name).read_text(
            encoding="utf-8"
        )
    )


def test_schema_uses_one_lifecycle_vocabulary():
    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    config = json.loads(
        (ROOT / "10_Harness" / "config.json").read_text(
            encoding="utf-8"
        )
    )

    assert __version__ == "0.5.0"
    assert project["project"]["version"] == __version__
    assert config["version"] == __version__
    assert project["build-system"] == {
        "requires": ["setuptools>=61"],
        "build-backend": "setuptools.build_meta",
    }

    schema = _load_json("claim_schema.json")

    assert schema["claim_status"] == LIFECYCLE
    assert set(
        schema["status_required_fields"]
    ) == set(LIFECYCLE)


def test_schema_uses_one_relationship_vocabulary():
    claim_schema = _load_json(
        "claim_schema.json"
    )
    relationship_schema = _load_json(
        "claim_relationship_schema.json"
    )

    assert claim_schema["relation_types"] == (
        RELATIONSHIPS
    )
    assert relationship_schema[
        "relationship_types"
    ] == RELATIONSHIPS


def test_event_schema_matches_legal_transitions():
    claim_schema = _load_json(
        "claim_schema.json"
    )
    event_schema = _load_json(
        "claim_event_schema.json"
    )

    policies = event_schema["event_types"]

    for event_type, transition in (
        claim_schema["legal_transitions"].items()
    ):
        policy = policies[event_type]

        assert not policy.get("legacy", False)
        assert set(
            policy["allowed_previous_statuses"]
        ) == set(transition["from"])
        assert policy["resulting_status"] == (
            transition["to"]
        )


def test_normative_docs_do_not_publish_old_target_enum():
    old_uppercase_value = re.compile(
        r"^(DRAFT|REVIEW|CANONICAL|ACTIVE|"
        r"SUPERSEDED|ARCHIVED)$",
        re.MULTILINE,
    )
    renamed_time_field = re.compile(
        r"(?<!last_)verified_at"
    )

    for path in NORMATIVE_DOCUMENTS:
        text = path.read_text(
            encoding="utf-8"
        )

        assert old_uppercase_value.search(text) is None
        assert renamed_time_field.search(text) is None
