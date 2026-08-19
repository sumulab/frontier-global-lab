from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path

from .agent_runner import prepare_run, run_openai
from .evidence_store import EvidenceStore
from .kb import build_index, search
from .runtime import (
    load_config,
    project_now,
)
from .research_quality import evaluate_country_scan
from .research_augment import augment_run
from .temporal_report import build_temporal_health_report
from .canonical_claim_report import (
    build_canonical_claim_health_report,
)
from .canonical_claim_writer import (
    append_claim_created,
    append_claim_reviewed,
)
from .temporal_review import review_temporal_document


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
    hits = search(
        root / cfg["index_db"],
        args.query,
        args.limit,
    )

    for i, hit in enumerate(hits, 1):
        print(
            f"[{i}] {hit.title}\n"
            f"    {hit.path}\n"
            f"    {hit.snippet}\n"
        )


def cmd_start(args):
    root = repo_root()
    run_dir = prepare_run(root, args.workflow)
    print(
        f"Prepared run: "
        f"{run_dir.relative_to(root)}"
    )


def cmd_run(args):
    root = repo_root()
    run_dir = run_openai(root, args.workflow)
    print(
        f"Completed run: "
        f"{run_dir.relative_to(root)}"
    )


def cmd_promote(args):
    root = repo_root()
    draft = (root / args.draft).resolve()
    dest = (root / args.destination).resolve()

    if (
        root.resolve() not in draft.parents
        or root.resolve() not in dest.parents
    ):
        raise SystemExit(
            "Paths must be inside the repository"
        )

    if "10_Harness/runtime/drafts" not in draft.as_posix():
        raise SystemExit(
            "Only files under runtime/drafts "
            "can be promoted"
        )

    if "10_Harness/runtime" in dest.as_posix():
        raise SystemExit(
            "Destination must be canonical "
            "knowledge, not runtime"
        )

    if not draft.exists():
        raise SystemExit(
            f"Draft not found: {draft}"
        )

    dest.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        draft,
        dest,
    )

    print(
        f"Promoted {draft.relative_to(root)} "
        f"-> {dest.relative_to(root)}"
    )


def cmd_research_augment(args):
    root = repo_root()

    run_dir = augment_run(
        root,
        args.run_id,
    )

    print(
        f"Completed augment run: "
        f"{run_dir.relative_to(root)}"
    )


def cmd_quality(args):
    root = repo_root()

    db = _evidence_db_for_run(
        root,
        args.run_id,
    )

    report = evaluate_country_scan(db)

    print(
        "Coverage Quality: "
        + ("PASS" if report.passed else "FAIL")
    )

    for check in report.checks:
        mark = (
            "PASS"
            if check.passed
            else "FAIL"
        )

        print(
            f"{mark:4} "
            f"{check.name}: "
            f"{check.actual} "
            f"(required {check.requirement})"
        )

    print()
    print(
        "Semantic Warnings: "
        f"{len(report.warnings)}"
    )

    for warning in report.warnings:
        ids = ", ".join(
            warning.evidence_ids
        )

        print()
        print(
            f"WARN {warning.name}: "
            f"{ids}"
        )
        print(
            f"     {warning.detail}"
        )

    if not report.passed:
        raise SystemExit(2)

def cmd_temporal_review(args):
    from datetime import date

    root = repo_root()
    cfg = load_config(root)

    try:
        as_of = date.fromisoformat(
            args.as_of
        )
    except ValueError as exc:
        raise SystemExit(
            "--as-of must use YYYY-MM-DD."
        ) from exc

    verified_on = project_now(
        cfg
    ).date()

    document = (
        root / args.document
    ).resolve()

    try:
        updated = review_temporal_document(
            root,
            document,
            verified_on=verified_on,
            as_of=as_of,
            reviewer=args.reviewer,
            basis=args.basis,
            run_ids=args.run_id,
            note=args.note,
            dry_run=args.dry_run,
        )
    except (
        ValueError,
        FileNotFoundError,
    ) as exc:
        raise SystemExit(str(exc)) from exc

    action = (
        "DRY RUN"
        if args.dry_run
        else "UPDATED"
    )

    print(
        f"{action}: {args.document}"
    )
    print(
        f"status: {updated['status']}"
    )
    print(
        f"as_of: {updated['as_of']}"
    )
    print(
        "last_verified_at: "
        f"{updated['last_verified_at']}"
    )
    print(
        "next_review_at: "
        f"{updated['next_review_at']}"
    )


def cmd_claim_create(args):
    from datetime import date

    root = repo_root()

    try:
        as_of = date.fromisoformat(
            args.as_of
        )
    except ValueError as exc:
        raise SystemExit(
            "--as-of must use YYYY-MM-DD."
        ) from exc

    document = (
        root / args.document
    ).resolve()

    try:
        event = append_claim_created(
            root,
            document,
            text=args.text,
            topic=args.topic,
            as_of=as_of,
            actor=args.actor,
            dry_run=not args.write,
        )
    except (
        ValueError,
        FileNotFoundError,
        RuntimeError,
    ) as exc:
        raise SystemExit(str(exc)) from exc

    action = (
        "APPENDED"
        if args.write
        else "DRY RUN"
    )

    payload = event["payload"]

    print(
        f"{action}: canonical claim"
    )
    print(
        f"event_id: {event['event_id']}"
    )
    print(
        f"claim_id: {event['claim_id']}"
    )
    print(
        "knowledge: "
        f"{payload['knowledge_id']} "
        f"[{payload['knowledge_type']}]"
    )
    print(
        f"topic: {payload['topic']}"
    )
    print(
        f"as_of: {payload['as_of']}"
    )
    print(
        "initial_status: needs_review"
    )

    if not args.write:
        print(
            "No canonical ledger changes were made."
        )


def cmd_claim_review(args):
    from datetime import date

    root = repo_root()

    try:
        as_of = date.fromisoformat(
            args.as_of
        )
    except ValueError as exc:
        raise SystemExit(
            "--as-of must use YYYY-MM-DD."
        ) from exc

    try:
        event = append_claim_reviewed(
            root,
            args.claim_id,
            as_of=as_of,
            reviewer=args.reviewer,
            basis=args.basis,
            run_ids=args.run_id,
            note=args.note,
            actor=args.actor,
            dry_run=not args.write,
        )
    except (
        ValueError,
        FileNotFoundError,
        RuntimeError,
    ) as exc:
        raise SystemExit(str(exc)) from exc

    action = (
        "APPENDED"
        if args.write
        else "DRY RUN"
    )

    payload = event["payload"]
    provenance = payload[
        "review_provenance"
    ]

    print(
        f"{action}: canonical claim review"
    )
    print(
        f"event_id: {event['event_id']}"
    )
    print(
        f"claim_id: {event['claim_id']}"
    )
    print(
        "previous_event_id: "
        f"{event['previous_event_id']}"
    )
    print(
        f"as_of: {payload['as_of']}"
    )
    print(
        "last_verified_at: "
        f"{payload['last_verified_at']}"
    )
    print(
        "next_review_at: "
        f"{payload['next_review_at']}"
    )
    print(
        f"reviewer: {provenance['reviewer']}"
    )
    print(
        f"basis: {provenance['basis']}"
    )
    print(
        f"runs: {len(provenance['runs'])}"
    )
    print(
        "resulting_status: active"
    )

    if not args.write:
        print(
            "No canonical ledger changes were made."
        )


def cmd_claim_status(args):
    root = repo_root()

    report = build_canonical_claim_health_report(
        root
    )

    print("Canonical Claim Health")
    print()

    if not report.valid:
        print("LEDGER INVALID")

        for issue in report.issues:
            print(
                f"  {issue}"
            )

        raise SystemExit(2)

    print(
        f"Claims: {report.claim_count}"
    )

    if not report.rows:
        return

    print()

    for row in report.rows:
        review = (
            "REVIEW_DUE"
            if row.review_due
            else "OK"
        )

        print(
            row.claim_id,
            row.status.upper(),
            review,
            f"[{row.knowledge_type}]",
        )

        print(
            f"    knowledge: "
            f"{row.knowledge_id}"
        )

        print(
            f"    topic: {row.topic}"
        )

        print(
            f"    as_of: {row.as_of}"
        )

        print(
            f"    head: "
            f"{row.head_event_id}"
        )

        print(
            f"    {row.message}"
        )


def cmd_temporal_status(args):
    root = repo_root()

    report = build_temporal_health_report(
        root
    )

    print("Temporal Knowledge Health")
    print()

    for item in report:
        validity = (
            "VALID"
            if item.metadata_valid
            else "INVALID"
        )

        review = (
            "REVIEW_DUE"
            if item.review_due
            else "OK"
        )

        print(
            validity,
            review,
            item.state.upper(),
            item.path,
            f"[{item.knowledge_type}]",
        )

        print(
            f"    {item.message}"
        )


def cmd_status(args):
    root = repo_root()
    cfg = load_config(root)

    index_path = root / cfg["index_db"]

    runs = sorted(
        [
            p
            for p in (
                root / "10_Harness/runtime/runs"
            ).glob("*")
            if p.is_dir()
        ],
        reverse=True,
    )

    drafts = [
        p
        for p in (
            root / "10_Harness/runtime/drafts"
        ).rglob("*.md")
    ]

    print(f"Frontier Global Lab v{cfg.get('version', 'unknown')}")
    print(
        f"Index: "
        f"{'ready' if index_path.exists() else 'missing'}"
    )
    print(f"Runs: {len(runs)}")
    print(
        f"Drafts awaiting review: "
        f"{len(drafts)}"
    )

    if runs:
        print(
            f"Latest run: {runs[0].name}"
        )


def _evidence_db_for_run(
    root: Path,
    run_id: str,
) -> Path:
    if Path(run_id).name != run_id:
        raise SystemExit(
            "run-id must be a run directory name"
        )

    runs_root = (
        root
        / "10_Harness"
        / "runtime"
        / "runs"
    ).resolve()

    run_dir = (
        runs_root / run_id
    ).resolve()

    if run_dir.parent != runs_root:
        raise SystemExit(
            "Invalid run-id"
        )

    if not run_dir.is_dir():
        raise SystemExit(
            f"Run not found: {run_id}"
        )

    db = run_dir / "evidence.sqlite"

    if not db.exists():
        raise SystemExit(
            f"No evidence database for run: "
            f"{run_id}"
        )

    return db


def _evidence_rows(
    db: Path,
):
    # Ensure older run databases receive newly added schema objects.
    EvidenceStore(db)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            e.evidence_id,
            e.claim_id,
            c.text AS claim,
            c.topic,
            c.importance,
            e.status,
            e.source_url,
            e.excerpt,
            e.reasoning,
            rev.claim_text AS revised_claim,
            rev.reasoning AS revised_reasoning,
            rev.revised_by AS revised_by,
            rev.note AS revision_note,
            rev.revised_at AS revised_at,
            r.decision AS review_decision,
            r.reviewer AS reviewer,
            r.note AS review_note,
            r.reviewed_at AS reviewed_at
        FROM evidence e
        JOIN claims c
          ON c.claim_id = e.claim_id
        LEFT JOIN evidence_revisions rev
          ON rev.revision_id = (
              SELECT MAX(rv2.revision_id)
              FROM evidence_revisions rv2
              WHERE rv2.evidence_id = e.evidence_id
          )
        LEFT JOIN evidence_reviews r
          ON r.review_id = (
              SELECT MAX(r2.review_id)
              FROM evidence_reviews r2
              WHERE r2.evidence_id = e.evidence_id
          )
        ORDER BY e.created_at
        """
    ).fetchall()

    conn.close()
    return rows


def _evidence_row(
    db: Path,
    evidence_id: str,
):
    rows = _evidence_rows(db)

    for row in rows:
        if row["evidence_id"] == evidence_id:
            return row

    return None


def _effective_review_state(row) -> str:
    revised_at = row["revised_at"]
    reviewed_at = row["reviewed_at"]

    if revised_at and (
        not reviewed_at
        or revised_at > reviewed_at
    ):
        return "resubmitted"

    return (
        row["review_decision"]
        or "unreviewed"
    )


def _effective_claim(row) -> str:
    return (
        row["revised_claim"]
        or row["claim"]
    )


def _effective_reasoning(row) -> str:
    return (
        row["revised_reasoning"]
        or row["reasoning"]
    )


def cmd_evidence_list(args):
    root = repo_root()
    db = _evidence_db_for_run(
        root,
        args.run_id,
    )

    rows = _evidence_rows(db)

    if not rows:
        print("No evidence found.")
        return

    for i, row in enumerate(rows, 1):
        review = _effective_review_state(row)

        print(
            f"[{i}] {row['evidence_id']}"
        )
        print(
            f"    status: {row['status']}"
        )
        print(
            f"    review: {review}"
        )
        print(
            f"    claim: {_effective_claim(row)}"
        )
        print(
            f"    source: {row['source_url']}"
        )
        print()


def cmd_evidence_show(args):
    root = repo_root()
    db = _evidence_db_for_run(
        root,
        args.run_id,
    )

    row = _evidence_row(
        db,
        args.evidence_id,
    )

    if row is None:
        raise SystemExit(
            f"Evidence not found: "
            f"{args.evidence_id}"
        )

    print(
        f"Evidence ID: {row['evidence_id']}"
    )
    print(
        f"Claim ID: {row['claim_id']}"
    )
    print(
        f"Topic: {row['topic']}"
    )
    print(
        f"Importance: {row['importance']}"
    )
    print(
        f"Machine assessment: "
        f"{row['status']}"
    )

    print("\nClaim:")
    print(_effective_claim(row))

    print("\nSource:")
    print(row["source_url"])

    print("\nExcerpt:")
    print(row["excerpt"])

    print("\nMachine reasoning:")
    print(_effective_reasoning(row))

    if row["revised_at"]:
        print("\nRevision:")
        print(f"Revised by: {row['revised_by']}")
        print(f"Revised at: {row['revised_at']}")
        if row["revision_note"]:
            print(f"Revision note: {row['revision_note']}")

    print("\nHuman review:")
    print(_effective_review_state(row))

    if row["reviewer"]:
        print(
            f"Reviewer: {row['reviewer']}"
        )

    if row["reviewed_at"]:
        print(
            f"Reviewed at: "
            f"{row['reviewed_at']}"
        )

    if row["review_note"]:
        print(
            f"Note: {row['review_note']}"
        )


def _record_review(
    args,
    decision: str,
):
    root = repo_root()
    db = _evidence_db_for_run(
        root,
        args.run_id,
    )

    row = _evidence_row(
        db,
        args.evidence_id,
    )

    if row is None:
        raise SystemExit(
            f"Evidence not found: "
            f"{args.evidence_id}"
        )

    store = EvidenceStore(db)

    store.add_evidence_review(
        evidence_id=args.evidence_id,
        decision=decision,
        reviewer=args.reviewer,
        note=args.note,
    )

    print(
        f"Evidence {args.evidence_id}: "
        f"{decision}"
    )


def cmd_evidence_amend(args):
    root = repo_root()
    db = _evidence_db_for_run(
        root,
        args.run_id,
    )

    row = _evidence_row(
        db,
        args.evidence_id,
    )

    if row is None:
        raise SystemExit(
            f"Evidence not found: "
            f"{args.evidence_id}"
        )

    claim_text = (
        args.claim
        or _effective_claim(row)
    )

    reasoning = (
        args.reasoning
        or _effective_reasoning(row)
    )

    store = EvidenceStore(db)

    store.add_evidence_revision(
        evidence_id=args.evidence_id,
        claim_text=claim_text,
        reasoning=reasoning,
        revised_by=args.reviewer,
        note=args.note,
    )

    print(
        f"Evidence {args.evidence_id}: "
        f"amended and resubmitted"
    )


def cmd_evidence_approve(args):
    _record_review(
        args,
        "approved",
    )


def cmd_evidence_reject(args):
    _record_review(
        args,
        "rejected",
    )


def cmd_evidence_revise(args):
    _record_review(
        args,
        "needs_revision",
    )


def _add_review_args(parser):
    parser.add_argument(
        "run_id",
    )
    parser.add_argument(
        "evidence_id",
    )
    parser.add_argument(
        "--reviewer",
        default="human",
    )
    parser.add_argument(
        "--note",
        default=None,
    )


def build_parser():
    p = argparse.ArgumentParser(
        prog="lab",
        description="Frontier Global Lab harness",
    )

    sub = p.add_subparsers(
        dest="cmd",
        required=True,
    )

    s = sub.add_parser(
        "index",
        help="Rebuild local FTS knowledge index",
    )
    s.set_defaults(
        func=cmd_index,
    )

    s = sub.add_parser(
        "search",
        help="Search local knowledge",
    )
    s.add_argument(
        "query",
    )
    s.add_argument(
        "--limit",
        type=int,
        default=8,
    )
    s.set_defaults(
        func=cmd_search,
    )

    s = sub.add_parser(
        "start",
        help=(
            "Prepare a workflow run/context "
            "pack without model calls"
        ),
    )
    s.add_argument(
        "workflow",
    )
    s.set_defaults(
        func=cmd_start,
    )

    s = sub.add_parser(
        "run",
        help=(
            "Run a workflow with the "
            "configured model runtime"
        ),
    )
    s.add_argument(
        "workflow",
    )
    s.set_defaults(
        func=cmd_run,
    )

    s = sub.add_parser(
        "promote",
        help=(
            "Human-approved promotion of a "
            "draft into canonical knowledge"
        ),
    )
    s.add_argument(
        "draft",
    )
    s.add_argument(
        "destination",
    )
    s.set_defaults(
        func=cmd_promote,
    )

    s = sub.add_parser(
        "quality",
        help="Evaluate research evidence quality for a run",
    )
    s.add_argument(
        "run_id",
    )
    s.set_defaults(
        func=cmd_quality,
    )

    research = sub.add_parser(
        "research",
        help="Research operations",
    )

    research_sub = research.add_subparsers(
        dest="research_cmd",
        required=True,
    )

    s = research_sub.add_parser(
        "augment",
        help="Incrementally fill research gaps for a completed run",
    )
    s.add_argument(
        "run_id",
    )
    s.set_defaults(
        func=cmd_research_augment,
    )

    claim = sub.add_parser(
        "claim",
        help="Canonical claim operations",
    )

    claim_sub = claim.add_subparsers(
        dest="claim_cmd",
        required=True,
    )

    s = claim_sub.add_parser(
        "status",
        help="Show canonical claim health",
    )

    s.set_defaults(
        func=cmd_claim_status,
    )

    s = claim_sub.add_parser(
        "create",
        help=(
            "Preview or append a new "
            "canonical claim"
        ),
    )

    s.add_argument(
        "document",
        help=(
            "Temporal Scope canonical "
            "Markdown owner"
        ),
    )

    s.add_argument(
        "--text",
        required=True,
        help="Canonical factual proposition",
    )

    s.add_argument(
        "--topic",
        required=True,
        help="Claim topic",
    )

    s.add_argument(
        "--as-of",
        required=True,
        help=(
            "Real-world date represented "
            "by the claim (YYYY-MM-DD)"
        ),
    )

    s.add_argument(
        "--actor",
        required=True,
        help=(
            "Human or controlled system "
            "creating the canonical claim"
        ),
    )

    s.add_argument(
        "--write",
        action="store_true",
        help=(
            "Actually append to the canonical "
            "ledger; without this flag the "
            "command is a dry run"
        ),
    )

    s.set_defaults(
        func=cmd_claim_create,
    )

    s = claim_sub.add_parser(
        "review",
        help=(
            "Preview or append a canonical "
            "claim review event"
        ),
    )

    s.add_argument(
        "claim_id",
        help="Stable canonical claim ID",
    )

    s.add_argument(
        "--as-of",
        required=True,
        help=(
            "Real-world date through which "
            "the claim was verified "
            "(YYYY-MM-DD)"
        ),
    )

    s.add_argument(
        "--reviewer",
        required=True,
        help="Reviewer identity or role",
    )

    s.add_argument(
        "--basis",
        required=True,
        choices=[
            "manual",
            "research_run",
            "mixed",
        ],
        help="Basis used for the claim review",
    )

    s.add_argument(
        "--run-id",
        action="append",
        default=[],
        help=(
            "Research run supporting the review; "
            "repeat for multiple runs"
        ),
    )

    s.add_argument(
        "--note",
        default=None,
        help="Optional review audit note",
    )

    s.add_argument(
        "--actor",
        required=True,
        help=(
            "Human or controlled system "
            "recording the review event"
        ),
    )

    s.add_argument(
        "--write",
        action="store_true",
        help=(
            "Actually append to the canonical "
            "ledger; without this flag the "
            "command is a dry run"
        ),
    )

    s.set_defaults(
        func=cmd_claim_review,
    )

    temporal = sub.add_parser(
        "temporal",
        help="Temporal knowledge operations",
    )

    temporal_sub = temporal.add_subparsers(
        dest="temporal_cmd",
        required=True,
    )

    s = temporal_sub.add_parser(
        "status",
        help="Show temporal knowledge health",
    )

    s.set_defaults(
        func=cmd_temporal_status,
    )

    s = temporal_sub.add_parser(
        "review",
        help=(
            "Review temporal knowledge and "
            "refresh its lifecycle metadata"
        ),
    )

    s.add_argument(
        "document",
        help="Repository-relative Markdown path",
    )

    s.add_argument(
        "--as-of",
        required=True,
        help=(
            "Real-world date through which "
            "the knowledge was verified "
            "(YYYY-MM-DD)"
        ),
    )

    s.add_argument(
        "--reviewer",
        required=True,
        help="Reviewer identity or role",
    )

    s.add_argument(
        "--basis",
        required=True,
        choices=[
            "manual",
            "research_run",
            "mixed",
        ],
        help="Basis used for the review",
    )

    s.add_argument(
        "--run-id",
        action="append",
        default=[],
        help=(
            "Research run supporting the review; "
            "repeat for multiple runs"
        ),
    )

    s.add_argument(
        "--note",
        default=None,
        help="Optional review audit note",
    )

    s.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview metadata transition without writing",
    )

    s.set_defaults(
        func=cmd_temporal_review,
    )

    s = sub.add_parser(
        "status",
        help="Show harness status",
    )
    s.set_defaults(
        func=cmd_status,
    )

    evidence = sub.add_parser(
        "evidence",
        help="Review run evidence",
    )

    evidence_sub = evidence.add_subparsers(
        dest="evidence_cmd",
        required=True,
    )

    s = evidence_sub.add_parser(
        "list",
        help="List evidence for a run",
    )
    s.add_argument(
        "run_id",
    )
    s.set_defaults(
        func=cmd_evidence_list,
    )

    s = evidence_sub.add_parser(
        "show",
        help="Show one evidence item",
    )
    s.add_argument(
        "run_id",
    )
    s.add_argument(
        "evidence_id",
    )
    s.set_defaults(
        func=cmd_evidence_show,
    )

    s = evidence_sub.add_parser(
        "amend",
        help="Revise evidence and resubmit for review",
    )
    s.add_argument(
        "run_id",
    )
    s.add_argument(
        "evidence_id",
    )
    s.add_argument(
        "--claim",
        default=None,
    )
    s.add_argument(
        "--reasoning",
        default=None,
    )
    s.add_argument(
        "--reviewer",
        default="human",
    )
    s.add_argument(
        "--note",
        default=None,
    )
    s.set_defaults(
        func=cmd_evidence_amend,
    )

    s = evidence_sub.add_parser(
        "approve",
        help="Approve evidence",
    )
    _add_review_args(s)
    s.set_defaults(
        func=cmd_evidence_approve,
    )

    s = evidence_sub.add_parser(
        "reject",
        help="Reject evidence",
    )
    _add_review_args(s)
    s.set_defaults(
        func=cmd_evidence_reject,
    )

    s = evidence_sub.add_parser(
        "revise",
        help="Mark evidence as needing revision",
    )
    _add_review_args(s)
    s.set_defaults(
        func=cmd_evidence_revise,
    )

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
