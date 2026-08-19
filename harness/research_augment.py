from __future__ import annotations

import json
from pathlib import Path

from .agent_runner import run_workflow
from .research_quality import evaluate_country_scan


def _parent_run_dir(
    root: Path,
    parent_run_id: str,
) -> Path:
    if Path(parent_run_id).name != parent_run_id:
        raise ValueError("Invalid parent_run_id.")

    run_dir = (
        root
        / "10_Harness"
        / "runtime"
        / "runs"
        / parent_run_id
    )

    if not run_dir.is_dir():
        raise FileNotFoundError(
            f"Parent run not found: {run_dir}"
        )

    return run_dir


def _build_gap_prompt(report) -> str:
    failed = [
        check
        for check in report.checks
        if not check.passed
    ]

    lines = [
        "This is an INCREMENTAL research run.",
        "",
        "The parent run's evidence database has been inherited.",
        "Do NOT restart the country scan from scratch.",
        "Do NOT recreate existing claims merely to increase counts.",
        "",
        "Current research-quality gaps:",
    ]

    for check in failed:
        lines.append(
            f"- {check.name}: "
            f"actual={check.actual}; "
            f"requirement={check.requirement}"
        )

    lines.extend(
        [
            "",
            "Your job is to close these gaps with the smallest "
            "number of high-quality additions.",
            "",
            "Rules for this augment run:",
            "- Prefer NEW source URLs over sources already used.",
            "- Prefer primary or authoritative sources.",
            "- Fill substantive research gaps, not numerical quotas.",
            "- Re-read the original workflow research questions and "
            "prioritize weakly supported areas.",
            "- Especially look for Nigeria-specific evidence on "
            "power reliability / diesel or backup-power dependence, "
            "real project developers or buyers, financing, regulation, "
            "and supply-chain fit where evidence is still weak.",
            "- Every new important external fact must follow "
            "search_web -> fetch_web_page -> record_claim_evidence.",
            "- Evidence reasoning must only explain how the source "
            "supports the claim; do not insert commercial conclusions.",
            "- Do not alter inherited evidence.",
            "- Stop adding evidence once the identified quality gaps "
            "are reasonably closed.",
            "",
            "The outputs of this child run are incremental drafts. "
            "Clearly distinguish inherited findings from newly added "
            "evidence.",
        ]
    )

    return "\n".join(lines)


def augment_run(
    root: Path,
    parent_run_id: str,
) -> Path:
    parent_dir = _parent_run_dir(
        root,
        parent_run_id,
    )

    state_path = parent_dir / "state.json"
    evidence_db = parent_dir / "evidence.sqlite"

    if not state_path.exists():
        raise FileNotFoundError(
            f"Parent state not found: {state_path}"
        )

    if not evidence_db.exists():
        raise FileNotFoundError(
            f"Parent evidence DB not found: {evidence_db}"
        )

    state = json.loads(
        state_path.read_text(
            encoding="utf-8"
        )
    )

    if state.get("status") != "completed":
        raise ValueError(
            "Only completed runs can be augmented."
        )

    workflow_id = state.get("workflow_id")

    if not workflow_id:
        raise ValueError(
            "Parent run has no workflow_id."
        )

    report = evaluate_country_scan(
        evidence_db
    )

    if report.passed:
        raise ValueError(
            "Parent run already passes the research quality gate."
        )

    prompt_suffix = _build_gap_prompt(
        report
    )

    return run_workflow(
        root,
        workflow_id,
        parent_run_id=parent_run_id,
        inherit_evidence=True,
        prompt_suffix=prompt_suffix,
    )
