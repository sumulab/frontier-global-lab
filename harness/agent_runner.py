from __future__ import annotations

import json
from pathlib import Path

from .kb import search
from .providers import resolve_task_runtime
from .runtime import load_config, load_workflow, new_run_dir


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


def run_workflow(root: Path, workflow_id: str) -> Path:
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

    run_dir = prepare_run(
        root,
        workflow_id,
    )

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

    skill_text = []

    for skill in [
        "research.md",
        "curator.md",
    ]:
        skill_text.append(
            (
                root
                / "10_Harness"
                / "skills"
                / skill
            ).read_text(
                encoding="utf-8"
            )
        )

    instructions = """
You are the single Orchestrator for Frontier Global Lab.

Work evidence-first.

Search local canonical knowledge before creating new conclusions.

Clearly distinguish:
- facts
- inferences
- assumptions
- unknowns

You may write only draft artifacts through write_draft.
Never claim canonical knowledge has been updated.

This runtime currently has Frontier local tools only.
Do not claim that you searched the public web unless a
Frontier web-search tool is explicitly available.

Before finishing, create every required output file
listed in the workflow when the available evidence
allows it.
"""

    instructions += "\n\n" + "\n\n".join(
        skill_text
    )

    tools = [
        search_local_knowledge,
        read_knowledge_file,
        write_draft,
    ]

    agent = Agent(
        name="Frontier Orchestrator",
        model=runtime.model,
        instructions=instructions,
        tools=tools,
    )

    session = SQLiteSession(
        workflow_id,
        str(root / config["session_db"]),
    )

    prompt = (
        run_dir / "prompt.md"
    ).read_text(
        encoding="utf-8"
    )

    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "status": "running",
                "workflow_id": workflow_id,
                "task_class": runtime.task_class,
                "provider": runtime.provider,
                "model": runtime.model_name,
                "transport": runtime.transport,
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

    result = Runner.run_sync(
        agent,
        prompt,
        session=session,
    )

    (run_dir / "final_output.md").write_text(
        str(result.final_output),
        encoding="utf-8",
    )

    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "workflow_id": workflow_id,
                "task_class": runtime.task_class,
                "provider": runtime.provider,
                "model": runtime.model_name,
                "transport": runtime.transport,
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
