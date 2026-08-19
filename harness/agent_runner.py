from __future__ import annotations

import json
import os
from pathlib import Path

from .kb import search
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
            sections.append(f"### {hit.title}\nPath: {hit.path}\n{hit.snippet}")
    return "\n\n".join(sections)


def prepare_run(root: Path, workflow_id: str) -> Path:
    workflow = load_workflow(root, workflow_id)
    run_dir = new_run_dir(root, workflow_id)
    context = build_context(root, workflow)
    (run_dir / "context.md").write_text(context, encoding="utf-8")
    (run_dir / "workflow.json").write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    prompt = f"""# Task\n{workflow['title']}\n\n## Goal\n{workflow['goal']}\n\n## Instructions\n"""
    prompt += "\n".join(f"- {x}" for x in workflow.get("instructions", []))
    prompt += "\n\n## Local Context\n" + context
    (run_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    (run_dir / "state.json").write_text(json.dumps({"status": "prepared", "workflow_id": workflow_id}, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def run_openai(root: Path, workflow_id: str) -> Path:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Run `lab start ...` for a local context pack, or export the key before `lab run`. ")

    try:
        from agents import Agent, Runner, SQLiteSession, WebSearchTool, function_tool
    except ImportError as e:
        raise RuntimeError("openai-agents is not installed. Run `pip install -e .`") from e

    config = load_config(root)
    workflow = load_workflow(root, workflow_id)
    run_dir = prepare_run(root, workflow_id)
    draft_root = root / config["agent_write_root"] / run_dir.name
    draft_root.mkdir(parents=True, exist_ok=True)
    db_path = root / config["index_db"]

    @function_tool
    def search_local_knowledge(query: str, limit: int = 8) -> str:
        """Search the local canonical knowledge base. Use this before external research."""
        hits = search(db_path, query, limit=limit)
        return "\n\n".join(
            f"{h.title}\nPath: {h.path}\n{h.snippet}" for h in hits
        ) or "No hits."

    @function_tool
    def read_knowledge_file(relative_path: str) -> str:
        """Read a UTF-8 text file from the repository. Only repository-relative paths are allowed."""
        target = (root / relative_path).resolve()
        if root.resolve() not in target.parents and target != root.resolve():
            raise ValueError("Path escapes repository")
        if "10_Harness/runtime" in target.as_posix():
            raise ValueError("Runtime internals are not canonical knowledge")
        return target.read_text(encoding="utf-8")[:50000]

    @function_tool
    def write_draft(filename: str, content: str) -> str:
        """Write a draft artifact for human review. Cannot write canonical knowledge directly."""
        safe_name = Path(filename).name
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        target = draft_root / safe_name
        target.write_text(content, encoding="utf-8")
        return f"Draft written: {target.relative_to(root).as_posix()}"

    skill_text = []
    for skill in ["research.md", "curator.md"]:
        skill_text.append((root / "10_Harness/skills" / skill).read_text(encoding="utf-8"))

    instructions = """
You are the single Orchestrator for Frontier Global Lab v0.2.
Work evidence-first. Search local knowledge before the web. Distinguish facts, inferences, assumptions, and unknowns.
You may write only draft artifacts through write_draft; never claim canonical knowledge was updated.
Use web search for current or external facts. Prefer primary/official sources.
Before finishing, create every required output file listed in the workflow.
""" + "\n\n".join(skill_text)

    model = os.getenv("LAB_MODEL", config["default_model"])
    tools = [search_local_knowledge, read_knowledge_file, write_draft]
    if config.get("web_search", {}).get("enabled", True):
        tools.append(WebSearchTool())

    agent = Agent(name="Lab Orchestrator", model=model, instructions=instructions, tools=tools)
    session = SQLiteSession(workflow_id, str(root / config["session_db"]))
    prompt = (run_dir / "prompt.md").read_text(encoding="utf-8")
    result = Runner.run_sync(agent, prompt, session=session)
    (run_dir / "final_output.md").write_text(str(result.final_output), encoding="utf-8")
    (run_dir / "state.json").write_text(json.dumps({"status": "completed", "workflow_id": workflow_id, "draft_root": draft_root.relative_to(root).as_posix()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir
