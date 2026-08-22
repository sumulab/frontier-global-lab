from __future__ import annotations

import json

from pathlib import Path


CLAIM_EVENT_SCHEMA_VERSION = "0.3.0"

CLAIM_LIFECYCLE = (
    "needs_review",
    "active",
    "superseded",
    "archived",
)

LEGACY_CLAIM_EVENTS = frozenset(
    {
        "claim_contradicted",
        "claim_marked_historical",
    }
)


def load_claim_event_schema(
    root: Path,
) -> dict:
    path = (
        root
        / "10_Harness"
        / "temporal"
        / "claim_event_schema.json"
    )

    schema = json.loads(
        path.read_text(encoding="utf-8")
    )

    version = schema.get("schema_version")

    if version != CLAIM_EVENT_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported canonical claim event "
            f"schema version: {version!r}; expected "
            f"{CLAIM_EVENT_SCHEMA_VERSION!r}."
        )

    return schema


def claim_ledger_path(root: Path) -> Path:
    config_path = (
        root / "10_Harness" / "config.json"
    )

    config = json.loads(
        config_path.read_text(encoding="utf-8")
    )

    relative = config[
        "canonical_claim_store"
    ]["ledger"]

    return root / relative
