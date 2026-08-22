from __future__ import annotations

import os

from pathlib import Path


PROJECT_ROOT_ENV = "FRONTIER_PROJECT_ROOT"


def _is_workspace_root(path: Path) -> bool:
    return (
        path / "10_Harness" / "config.json"
    ).is_file()


def resolve_project_root(
    explicit: str | Path | None = None,
    *,
    cwd: Path | None = None,
) -> Path:
    candidates: list[Path] = []

    if explicit is not None:
        candidates.append(Path(explicit))
    else:
        configured = os.environ.get(
            PROJECT_ROOT_ENV
        )
        if configured:
            candidates.append(Path(configured))

        candidates.append(cwd or Path.cwd())
        candidates.append(
            Path(__file__).resolve().parents[1]
        )

    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if _is_workspace_root(resolved):
            return resolved

    requested = (
        str(explicit)
        if explicit is not None
        else os.environ.get(PROJECT_ROOT_ENV)
    )
    detail = (
        f" at {requested!r}"
        if requested
        else ""
    )
    raise FileNotFoundError(
        "Frontier workspace root not found"
        f"{detail}; expected 10_Harness/config.json. "
        "Use --project-root or set "
        f"{PROJECT_ROOT_ENV}."
    )
