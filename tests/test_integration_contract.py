from __future__ import annotations

import copy
import json

from pathlib import Path

import pytest

from harness.cli import main
from harness.integration_contract import (
    ContractValidationError,
    RECEIPT_CONTRACT_VERSION,
    RESULT_CONTRACT_VERSION,
    TASK_CONTRACT_VERSION,
    canonical_result_hash,
    seal_result,
    validate_receipt,
    validate_result,
    validate_task,
    verify_receipt,
)


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
ROOT = Path(__file__).parents[1]


def task_document():
    return {
        "contract_version": TASK_CONTRACT_VERSION,
        "task_id": "task-001",
        "action_id": "action-001",
        "issued_at": "2026-08-22T12:00:00Z",
        "objective": "Test one locked market-research action.",
        "evaluation_contract": {
            "ref": "cognitrace://actions/action-001/evaluation-contract",
            "content_hash": HASH_A,
            "locked_at": "2026-08-22T11:59:00Z",
        },
        "context_refs": [
            {
                "stable_id": "context-001",
                "uri": "cognitrace://contexts/context-001",
                "content_hash": HASH_B,
            }
        ],
        "constraints": {"language": "en"},
    }


def unsealed_result():
    return {
        "contract_version": RESULT_CONTRACT_VERSION,
        "task_id": "task-001",
        "action_id": "action-001",
        "frontier_run_id": "run-001",
        "completed_at": "2026-08-22T13:00:00+00:00",
        "result_summary": "The synthetic run produced one reviewed artifact.",
        "artifact_refs": [
            {
                "stable_id": "artifact-001",
                "uri": "frontier://runs/run-001/artifacts/report",
                "content_hash": HASH_A,
                "media_type": "text/markdown",
            }
        ],
        "evidence_refs": [
            {
                "stable_id": "evidence-001",
                "uri": "frontier://runs/run-001/evidence/evidence-001",
                "content_hash": HASH_B,
                "review_status": "approved",
            }
        ],
        "review": {
            "status": "approved",
            "reviewed_by": "synthetic-reviewer",
            "reviewed_at": "2026-08-22T13:01:00Z",
        },
        "runtime_provenance": {
            "provider": "synthetic",
            "model": "synthetic-model-v1",
            "prompt_refs": [
                {
                    "stable_id": "prompt-001",
                    "uri": "frontier://prompts/prompt-001",
                    "content_hash": HASH_A,
                }
            ],
            "skill_refs": [],
            "budget": {
                "unit": "tokens",
                "limit": 1000,
                "used": 400,
            },
        },
    }


def result_document():
    return seal_result(unsealed_result())


def receipt_document(result=None, *, status="accepted"):
    result = result or result_document()
    return {
        "contract_version": RECEIPT_CONTRACT_VERSION,
        "submission_id": "submission-001",
        "task_id": result["task_id"],
        "action_id": result["action_id"],
        "frontier_run_id": result["frontier_run_id"],
        "result_content_hash": result["result_content_hash"],
        "received_at": "2026-08-22T13:02:00Z",
        "status": status,
        "errors": [],
    }


def issue_codes(exc):
    return {issue.code for issue in exc.value.issues}


def test_task_contract_accepts_locked_action_boundary():
    validate_task(task_document())


def test_task_contract_rejects_file_reference_and_unknown_field():
    document = task_document()
    document["evaluation_contract"]["ref"] = "file:///tmp/contract.json"
    document["goal_status"] = "complete"

    with pytest.raises(ContractValidationError) as exc:
        validate_task(document)

    assert issue_codes(exc) == {"invalid_uri", "unknown_field"}


def test_seal_result_is_deterministic_and_valid():
    first = seal_result(unsealed_result())
    reordered = dict(reversed(list(unsealed_result().items())))
    second = seal_result(reordered)

    assert first["result_content_hash"] == second["result_content_hash"]
    assert first["result_content_hash"] == canonical_result_hash(first)
    validate_result(first)


def test_result_tamper_is_rejected():
    document = result_document()
    document["result_summary"] = "Tampered after sealing."

    with pytest.raises(ContractValidationError) as exc:
        validate_result(document)

    assert "hash_mismatch" in issue_codes(exc)


def test_result_requires_output_reference():
    document = unsealed_result()
    document["artifact_refs"] = []
    document["evidence_refs"] = []
    document["result_content_hash"] = canonical_result_hash(document)

    with pytest.raises(ContractValidationError) as exc:
        validate_result(document)

    assert "empty_result" in issue_codes(exc)


def test_result_rejects_duplicate_reference_and_excess_budget():
    document = unsealed_result()
    document["artifact_refs"].append(copy.deepcopy(document["artifact_refs"][0]))
    document["runtime_provenance"]["budget"]["used"] = 1001
    document["result_content_hash"] = canonical_result_hash(document)

    with pytest.raises(ContractValidationError) as exc:
        validate_result(document)

    assert issue_codes(exc) >= {"duplicate_id", "budget_exceeded"}


def test_needs_review_cannot_claim_completed_review():
    document = unsealed_result()
    document["review"]["status"] = "needs_review"
    document["result_content_hash"] = canonical_result_hash(document)

    with pytest.raises(ContractValidationError) as exc:
        validate_result(document)

    assert "status_conflict" in issue_codes(exc)


def test_receipt_verifies_result_identity():
    result = result_document()
    receipt = receipt_document(result)

    validate_receipt(receipt)
    verify_receipt(result, receipt)


def test_duplicate_receipt_is_successful_idempotent_acknowledgement():
    result = result_document()
    receipt = receipt_document(result, status="duplicate")

    verify_receipt(result, receipt)


def test_receipt_mismatch_is_rejected():
    result = result_document()
    receipt = receipt_document(result)
    receipt["action_id"] = "action-other"

    with pytest.raises(ContractValidationError) as exc:
        verify_receipt(result, receipt)

    assert "receipt_mismatch" in issue_codes(exc)


def test_rejected_receipt_requires_errors():
    receipt = receipt_document(status="rejected")

    with pytest.raises(ContractValidationError) as exc:
        validate_receipt(receipt)

    assert "status_conflict" in issue_codes(exc)


def test_cli_seal_validate_and_verify(tmp_path: Path, capsys):
    draft_path = tmp_path / "result-draft.json"
    result_path = tmp_path / "result.json"
    receipt_path = tmp_path / "receipt.json"
    draft_path.write_text(
        json.dumps(unsealed_result()),
        encoding="utf-8",
    )

    main(
        [
            "integration",
            "seal-result",
            str(draft_path),
            "--output",
            str(result_path),
        ]
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    receipt_path.write_text(
        json.dumps(receipt_document(result)),
        encoding="utf-8",
    )

    main(["integration", "validate", "result", str(result_path)])
    main(
        [
            "integration",
            "verify-receipt",
            str(result_path),
            str(receipt_path),
        ]
    )

    output = capsys.readouterr().out
    assert "SEALED result" in output
    assert "VALID result" in output
    assert "VERIFIED receipt" in output


def test_published_synthetic_round_trip_examples():
    examples = ROOT / "docs" / "contracts" / "v0.1" / "examples"
    task = json.loads((examples / "task.json").read_text(encoding="utf-8"))
    result = json.loads((examples / "result.json").read_text(encoding="utf-8"))
    receipt = json.loads((examples / "receipt.json").read_text(encoding="utf-8"))

    validate_task(task)
    validate_result(result)
    verify_receipt(result, receipt)
