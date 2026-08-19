from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def load_config(root: Path) -> dict:
    return json.loads((root / "10_Harness/config.json").read_text(encoding="utf-8"))


def load_workflow(root: Path, workflow_id: str) -> dict:
    path = root / "10_Harness/workflows" / f"{workflow_id.replace('-', '_')}.json"
    if not path.exists():
        # fallback to scan by id
        for candidate in (root / "10_Harness/workflows").glob("*.json"):
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if data.get("id") == workflow_id:
                return data
        raise FileNotFoundError(f"Unknown workflow: {workflow_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def new_run_dir(root: Path, workflow_id: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = root / "10_Harness/runtime/runs" / f"{stamp}-{workflow_id}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def resolve_runtime_policy(
    config: dict,
    task_class: str,
    *,
    mode: str = "standard",
) -> dict:
    """
    Resolve runtime research budgets.

    Priority:
        mode override
        -> task-class policy
        -> global defaults
    """
    policy = config.get(
        "runtime_policy",
        {},
    )

    resolved = dict(
        policy.get(
            "defaults",
            {},
        )
    )

    task_policies = policy.get(
        "task_classes",
        {},
    )

    resolved.update(
        task_policies.get(
            task_class,
            {},
        )
    )

    modes = policy.get(
        "modes",
        {},
    )

    resolved.update(
        modes.get(
            mode,
            {},
        )
    )

    resolved["policy_version"] = (
        policy.get("version")
    )

    resolved["task_class"] = task_class
    resolved["mode"] = mode

    return resolved
