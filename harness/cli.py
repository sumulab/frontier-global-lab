from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .agent_runner import prepare_run, run_openai
from .kb import build_index, search
from .runtime import load_config


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def cmd_index(args):
    root = repo_root()
    cfg = load_config(root)
    count = build_index(root, root / cfg["index_db"])
    print(f"Indexed {count} documents -> {cfg['index_db']}")


def cmd_search(args):
    root = repo_root()
    cfg = load_config(root)
    hits = search(root / cfg["index_db"], args.query, args.limit)
    for i, hit in enumerate(hits, 1):
        print(f"[{i}] {hit.title}\n    {hit.path}\n    {hit.snippet}\n")


def cmd_start(args):
    run_dir = prepare_run(repo_root(), args.workflow)
    print(f"Prepared run: {run_dir.relative_to(repo_root())}")


def cmd_run(args):
    run_dir = run_openai(repo_root(), args.workflow)
    print(f"Completed run: {run_dir.relative_to(repo_root())}")


def cmd_promote(args):
    root = repo_root()
    draft = (root / args.draft).resolve()
    dest = (root / args.destination).resolve()
    if root.resolve() not in draft.parents or root.resolve() not in dest.parents:
        raise SystemExit("Paths must be inside the repository")
    if "10_Harness/runtime/drafts" not in draft.as_posix():
        raise SystemExit("Only files under runtime/drafts can be promoted")
    if "10_Harness/runtime" in dest.as_posix():
        raise SystemExit("Destination must be canonical knowledge, not runtime")
    if not draft.exists():
        raise SystemExit(f"Draft not found: {draft}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(draft, dest)
    print(f"Promoted {draft.relative_to(root)} -> {dest.relative_to(root)}")


def cmd_status(args):
    root = repo_root()
    cfg = load_config(root)
    index_path = root / cfg["index_db"]
    runs = sorted([p for p in (root / "10_Harness/runtime/runs").glob("*") if p.is_dir()], reverse=True)
    drafts = [p for p in (root / "10_Harness/runtime/drafts").rglob("*.md")]
    print("Frontier Global Lab v0.2")
    print(f"Index: {'ready' if index_path.exists() else 'missing'}")
    print(f"Runs: {len(runs)}")
    print(f"Drafts awaiting review: {len(drafts)}")
    if runs:
        print(f"Latest run: {runs[0].name}")


def build_parser():
    p = argparse.ArgumentParser(prog="lab", description="Frontier Global Lab harness")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("index", help="Rebuild local FTS knowledge index")
    s.set_defaults(func=cmd_index)
    s = sub.add_parser("search", help="Search local knowledge")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=8)
    s.set_defaults(func=cmd_search)
    s = sub.add_parser("start", help="Prepare a workflow run/context pack without model calls")
    s.add_argument("workflow")
    s.set_defaults(func=cmd_start)
    s = sub.add_parser("run", help="Run a workflow with the OpenAI Agents SDK")
    s.add_argument("workflow")
    s.set_defaults(func=cmd_run)
    s = sub.add_parser("promote", help="Human-approved promotion of a draft into canonical knowledge")
    s.add_argument("draft")
    s.add_argument("destination")
    s.set_defaults(func=cmd_promote)
    s = sub.add_parser("status", help="Show harness status")
    s.set_defaults(func=cmd_status)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
