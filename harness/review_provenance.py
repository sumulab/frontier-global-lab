from __future__ import annotations

import json

from pathlib import Path


def validate_review_runs(
    root: Path,
    *,
    basis: str,
    run_ids: list[str] | None,
) -> list[dict]:
    run_ids = list(run_ids or [])

    if basis not in {
        "research_run",
        "mixed",
    }:
        return []

    runs_root = (
        root
        / "10_Harness"
        / "runtime"
        / "runs"
    ).resolve()

    snapshots = []

    for run_id in run_ids:
        if Path(run_id).name != run_id:
            raise ValueError(
                f"Invalid run_id: {run_id!r}."
            )

        run_dir = (
            runs_root / run_id
        ).resolve()

        if (
            runs_root not in run_dir.parents
            or not run_dir.is_dir()
        ):
            raise ValueError(
                f"Research run not found: {run_id}"
            )

        state_path = (
            run_dir / "state.json"
        )

        if not state_path.is_file():
            raise ValueError(
                f"Research run has no state.json: "
                f"{run_id}"
            )

        try:
            state = json.loads(
                state_path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Research run has invalid state.json: "
                f"{run_id}"
            ) from exc

        if state.get("status") != "completed":
            raise ValueError(
                f"Research run is not completed: "
                f"{run_id}"
            )

        required_snapshot_fields = (
            "workflow_id",
            "completed_at",
            "research_as_of",
        )

        missing = [
            field
            for field in required_snapshot_fields
            if not state.get(field)
        ]

        if missing:
            raise ValueError(
                f"Research run {run_id} is missing "
                f"provenance fields: "
                + ", ".join(missing)
            )

        snapshots.append(
            {
                "run_id": run_id,
                "workflow_id": state[
                    "workflow_id"
                ],
                "completed_at": state[
                    "completed_at"
                ],
                "research_as_of": state[
                    "research_as_of"
                ],
            }
        )

    return snapshots
