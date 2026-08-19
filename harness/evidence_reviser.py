from __future__ import annotations

import json
from pathlib import Path

from agents import Agent, Runner

from harness.evidence_store import EvidenceStore
from harness.providers import resolve_task_runtime
from harness.runtime import load_config


def _parse_json_output(text: str) -> dict:
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

        if text.lower().startswith("json"):
            text = text[4:].lstrip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise RuntimeError(
                "Revision model did not return valid JSON."
            )

        return json.loads(text[start:end + 1])


def propose_evidence_revision(
    *,
    root: Path,
    evidence_db: Path,
    evidence_id: str,
    task_class: str = "local_light",
) -> dict:
    store = EvidenceStore(evidence_db)

    context = store.get_evidence_revision_context(
        evidence_id
    )

    if context is None:
        raise ValueError(
            f"Unknown evidence_id: {evidence_id}"
        )

    review = context.get("latest_review")

    if (
        not review
        or review.get("decision") != "needs_revision"
    ):
        raise ValueError(
            "Revision proposal is allowed only when "
            "the latest human review is needs_revision."
        )

    config = load_config(root)

    runtime = resolve_task_runtime(
        config,
        task_class=task_class,
    )

    instructions = """
You are Frontier Evidence Reviser.

Your only job is to propose a narrower and more defensible
revision of an evidence claim after human review.

Hard rules:

1. Treat the source excerpt as immutable evidence.
2. Never invent facts not supported by the excerpt or its supplied source context.
2a. A section heading or immediately surrounding source context may establish
    scope, subject, geography, or scenario when the excerpt sentence omits it.
3. Never change or reinterpret the source URL.
4. Never add strategic or commercial conclusions to evidence reasoning.
5. Keep the claim atomic and directly supportable by the excerpt.
6. If the human review identifies an unsupported clause, remove or narrow it.
7. Historical facts and scenario projections must remain clearly distinguished.
8. Evidence reasoning must explain only how the excerpt supports the claim.
9. Do not approve, verify, promote, or modify canonical knowledge.
10. Return JSON only.

Required JSON shape:

{
  "revised_claim": "...",
  "revised_reasoning": "...",
  "change_summary": "..."
}
"""

    payload = {
        "evidence_id": context["evidence_id"],
        "topic": context["topic"],
        "machine_status": context["machine_status"],
        "current_claim": context["effective_claim"],
        "current_reasoning": context["effective_reasoning"],
        "source_url": context["source_url"],
        "source_title": context["source_title"],
        "excerpt": context["excerpt"],
        "section_heading": context.get("section_heading"),
        "context_excerpt": context.get("context_excerpt"),
        "human_review_decision": review["decision"],
        "human_review_note": review["note"],
    }

    agent = Agent(
        name="Frontier Evidence Reviser",
        model=runtime.model,
        instructions=instructions,
        tools=[],
    )

    result = Runner.run_sync(
        agent,
        (
            "Revise this evidence item according to the "
            "human review.\n\n"
            + json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
        ),
    )

    proposal = _parse_json_output(
        str(result.final_output)
    )

    revised_claim = str(
        proposal.get("revised_claim", "")
    ).strip()

    revised_reasoning = str(
        proposal.get("revised_reasoning", "")
    ).strip()

    change_summary = str(
        proposal.get("change_summary", "")
    ).strip()

    if not revised_claim:
        raise RuntimeError(
            "Revision proposal has no revised_claim."
        )

    if not revised_reasoning:
        raise RuntimeError(
            "Revision proposal has no revised_reasoning."
        )

    store.add_evidence_revision(
        evidence_id=evidence_id,
        claim_text=revised_claim,
        reasoning=revised_reasoning,
        revised_by=(
            f"agent:{runtime.provider}/"
            f"{runtime.model_name}"
        ),
        note=(
            "AI revision proposal based on human "
            "needs_revision review. "
            f"{change_summary}"
        ).strip(),
    )

    return {
        "evidence_id": evidence_id,
        "task_class": runtime.task_class,
        "provider": runtime.provider,
        "model": runtime.model_name,
        "revised_claim": revised_claim,
        "revised_reasoning": revised_reasoning,
        "change_summary": change_summary,
        "human_approval_required": True,
    }
