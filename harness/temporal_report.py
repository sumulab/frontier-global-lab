from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .runtime import (
    load_config,
    project_now,
)
from .temporal import (
    knowledge_type_policy,
    load_temporal_schema,
)
from .temporal_markdown import (
    scan_temporal_documents,
)
from .temporal_status import (
    evaluate_temporal_state,
)


@dataclass(frozen=True)
class TemporalHealth:
    path: str
    knowledge_type: str
    metadata_valid: bool
    state: str
    review_due: bool
    message: str


def build_temporal_health_report(
    root: Path,
) -> list[TemporalHealth]:
    config = load_config(root)
    schema = load_temporal_schema(root)

    today = project_now(
        config
    ).date()

    documents = scan_temporal_documents(
        root
    )

    report: list[TemporalHealth] = []

    for document in documents:
        if not document.valid:
            report.append(
                TemporalHealth(
                    path=document.path,
                    knowledge_type=(
                        document.expected_type
                    ),
                    metadata_valid=False,
                    state="invalid",
                    review_due=True,
                    message="; ".join(
                        document.issues
                    ),
                )
            )
            continue

        policy = knowledge_type_policy(
            schema,
            document.expected_type,
        )

        if not policy.get(
            "temporal",
            False,
        ):
            report.append(
                TemporalHealth(
                    path=document.path,
                    knowledge_type=(
                        document.expected_type
                    ),
                    metadata_valid=True,
                    state="identity_only",
                    review_due=False,
                    message=(
                        "Document has canonical identity "
                        "but no document-level freshness "
                        "lifecycle."
                    ),
                )
            )
            continue

        temporal_state = (
            evaluate_temporal_state(
                document.metadata,
                today=today,
            )
        )

        report.append(
            TemporalHealth(
                path=document.path,
                knowledge_type=(
                    document.expected_type
                ),
                metadata_valid=True,
                state=(
                    temporal_state.lifecycle
                ),
                review_due=(
                    temporal_state.review_due
                ),
                message=(
                    temporal_state.message
                ),
            )
        )

    return report
