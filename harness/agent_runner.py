from __future__ import annotations

from .runtime import resolve_runtime_policy

import json
import shutil
from pathlib import Path

from .kb import search
from .providers import resolve_task_runtime
from .prompt_policy import (
    compose_prompt_profiles,
    resolve_prompt_ids,
)
from .skill_policy import (
    compose_skill_profiles,
    resolve_skill_ids,
)
from .runtime import (
    load_config,
    load_workflow,
    new_run_dir,
    project_now_iso,
)


def build_context(root: Path, workflow: dict, limit: int = 5) -> str:
    config = load_config(root)
    db = root / config["index_db"]

    sections = []

    for query in workflow.get("context_queries", []):
        hits = search(db, query, limit=limit)

        sections.append(f"## Query: {query}")

        if not hits:
            sections.append("No local hits.")
            continue

        for hit in hits:
            sections.append(
                f"### {hit.title}\n"
                f"Path: {hit.path}\n"
                f"{hit.snippet}"
            )

    return "\n\n".join(sections)


def prepare_run(root: Path, workflow_id: str) -> Path:
    config = load_config(root)
    workflow = load_workflow(root, workflow_id)
    run_dir = new_run_dir(root, workflow_id)

    context = build_context(root, workflow)

    (run_dir / "context.md").write_text(
        context,
        encoding="utf-8",
    )

    (run_dir / "workflow.json").write_text(
        json.dumps(
            workflow,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    prompt = (
        f"# Task\n{workflow['title']}\n\n"
        f"## Goal\n{workflow['goal']}\n\n"
        f"## Instructions\n"
    )

    prompt += "\n".join(
        f"- {item}"
        for item in workflow.get("instructions", [])
    )

    prompt += "\n\n## Local Context\n" + context

    (run_dir / "prompt.md").write_text(
        prompt,
        encoding="utf-8",
    )

    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "status": "prepared",
                "prepared_at": project_now_iso(config),
                "workflow_id": workflow_id,
                "task_class": workflow.get(
                    "task_class",
                    "local_light",
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return run_dir


def run_workflow(
    root: Path,
    workflow_id: str,
    *,
    parent_run_id: str | None = None,
    inherit_evidence: bool = False,
    prompt_suffix: str | None = None,
) -> Path:
    try:
        from agents import (
            Agent,
            Runner,
            SQLiteSession,
            function_tool,
        )
    except ImportError as exc:
        raise RuntimeError(
            "openai-agents is not installed. "
            "Run `pip install -e .`"
        ) from exc

    config = load_config(root)
    workflow = load_workflow(root, workflow_id)

    task_class = workflow.get(
        "task_class",
        "local_light",
    )

    runtime = resolve_task_runtime(
        config,
        task_class=task_class,
    )

    run_mode = (
        "augment"
        if parent_run_id
        else "standard"
    )

    runtime_policy = resolve_runtime_policy(
        config,
        runtime.task_class,
        mode=run_mode,
    )

    prompt_ids, prompt_policy_version = (
        resolve_prompt_ids(
            config,
            workflow,
            runtime.task_class,
        )
    )

    prompt_instructions, prompt_manifest = (
        compose_prompt_profiles(
            root,
            prompt_ids,
        )
    )

    skill_ids, skill_policy_version = (
        resolve_skill_ids(
            config,
            workflow,
            runtime.task_class,
        )
    )

    skill_instructions, skill_manifest = (
        compose_skill_profiles(
            root,
            skill_ids,
        )
    )

    run_dir = prepare_run(
        root,
        workflow_id,
    )

    prepared_state = json.loads(
        (run_dir / "state.json").read_text(
            encoding="utf-8"
        )
    )

    prepared_at = prepared_state.get(
        "prepared_at"
    )

    started_at = project_now_iso(config)

    draft_root = (
        root
        / config["agent_write_root"]
        / run_dir.name
    )

    draft_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    db_path = root / config["index_db"]

    @function_tool
    def search_local_knowledge(
        query: str,
        limit: int = 8,
    ) -> str:
        """
        Search the local canonical knowledge base.
        Always check local knowledge before doing new research.
        """

        hits = search(
            db_path,
            query,
            limit=limit,
        )

        return "\n\n".join(
            (
                f"{hit.title}\n"
                f"Path: {hit.path}\n"
                f"{hit.snippet}"
            )
            for hit in hits
        ) or "No hits."

    @function_tool
    def read_knowledge_file(
        relative_path: str,
    ) -> str:
        """
        Read a UTF-8 canonical knowledge file from
        the Frontier repository.
        """

        target = (
            root / relative_path
        ).resolve()

        root_resolved = root.resolve()

        if (
            root_resolved not in target.parents
            and target != root_resolved
        ):
            raise ValueError(
                "Path escapes repository"
            )

        if "10_Harness/runtime" in target.as_posix():
            raise ValueError(
                "Runtime internals are not "
                "canonical knowledge"
            )

        return target.read_text(
            encoding="utf-8"
        )[:50000]

    @function_tool
    def write_draft(
        filename: str,
        content: str,
    ) -> str:
        """
        Write a draft artifact for human review.
        Canonical knowledge cannot be modified directly.
        """

        safe_name = Path(filename).name

        if not safe_name.endswith(".md"):
            safe_name += ".md"

        target = draft_root / safe_name

        target.write_text(
            content,
            encoding="utf-8",
        )

        return (
            "Draft written: "
            + target.relative_to(root).as_posix()
        )

    instructions = prompt_instructions

    if skill_instructions:
        instructions += (
            "\n\n"
            + skill_instructions
        )

    (run_dir / "system_prompt.md").write_text(
        instructions,
        encoding="utf-8",
    )

    (run_dir / "skill_manifest.json").write_text(
        json.dumps(
            {
                "skill_policy_version": (
                    skill_policy_version
                ),
                "skills": skill_manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    (run_dir / "prompt_manifest.json").write_text(
        json.dumps(
            {
                "prompt_policy_version": (
                    prompt_policy_version
                ),
                "profiles": prompt_manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tools = [
        search_local_knowledge,
        read_knowledge_file,
        write_draft,
    ]

    web_enabled = (
        task_class in {"research_fast", "research_deep"}
        and config.get("web_search", {}).get("enabled", False)
    )

    if web_enabled:
        from .web_tools import build_web_tools

        evidence_db = run_dir / "evidence.sqlite"

        if inherit_evidence:
            if not parent_run_id:
                raise ValueError(
                    "inherit_evidence requires parent_run_id."
                )

            if Path(parent_run_id).name != parent_run_id:
                raise ValueError(
                    "Invalid parent_run_id."
                )

            parent_db = (
                root
                / "10_Harness"
                / "runtime"
                / "runs"
                / parent_run_id
                / "evidence.sqlite"
            )

            if not parent_db.exists():
                raise FileNotFoundError(
                    f"Parent evidence DB not found: {parent_db}"
                )

            shutil.copy2(
                parent_db,
                evidence_db,
            )

        tools.extend(
            build_web_tools(
                evidence_db=evidence_db,
                runtime_policy=runtime_policy,
            )
        )

    agent = Agent(
        name="Frontier Orchestrator",
        model=runtime.model,
        instructions=instructions,
        tools=tools,
    )

    session = SQLiteSession(
        run_dir.name,
        str(root / config["session_db"]),
    )

    prompt = (
        run_dir / "prompt.md"
    ).read_text(
        encoding="utf-8"
    )

    if prompt_suffix:
        prompt += (
            "\n\n## Incremental Research Instructions\n"
            + prompt_suffix.strip()
        )

        (run_dir / "prompt.md").write_text(
            prompt,
            encoding="utf-8",
        )

    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "status": "running",
                "prepared_at": prepared_at,
                "started_at": started_at,
                "workflow_id": workflow_id,
                "task_class": runtime.task_class,
                "provider": runtime.provider,
                "model": runtime.model_name,
                "transport": runtime.transport,
                "run_mode": run_mode,
                "parent_run_id": parent_run_id,
                "runtime_policy": runtime_policy,
                "prompt_policy_version": (
                    prompt_policy_version
                ),
                "prompt_profiles": prompt_manifest,
                "skill_policy_version": (
                    skill_policy_version
                ),
                "skill_profiles": skill_manifest,
                "draft_root": (
                    draft_root
                    .relative_to(root)
                    .as_posix()
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    max_turns = runtime_policy["max_turns"]

    result = Runner.run_sync(
        agent,
        prompt,
        session=session,
        max_turns=max_turns,
    )

    (run_dir / "final_output.md").write_text(
        str(result.final_output),
        encoding="utf-8",
    )

    completed_at = project_now_iso(config)

    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "prepared_at": prepared_at,
                "started_at": started_at,
                "completed_at": completed_at,
                "research_as_of": completed_at,
                "workflow_id": workflow_id,
                "task_class": runtime.task_class,
                "provider": runtime.provider,
                "model": runtime.model_name,
                "transport": runtime.transport,
                "run_mode": run_mode,
                "parent_run_id": parent_run_id,
                "runtime_policy": runtime_policy,
                "prompt_policy_version": (
                    prompt_policy_version
                ),
                "prompt_profiles": prompt_manifest,
                "skill_policy_version": (
                    skill_policy_version
                ),
                "skill_profiles": skill_manifest,
                "draft_root": (
                    draft_root
                    .relative_to(root)
                    .as_posix()
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return run_dir


# Temporary compatibility alias.
# CLI will be renamed in the next step.
run_openai = run_workflow
