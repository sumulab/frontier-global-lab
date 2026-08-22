# ADR-0003: Versioned CogniTrace file contract boundary

- Status: Accepted for Phase B experiment
- Date: 2026-08-22
- Project milestone: Frontier v0.6
- Upstream boundary: CogniTrace ADR-0011

## Context

Frontier v0.5.0 completed its internal Canonical Knowledge lifecycle and is a
frozen public MVP baseline. CogniTrace owns goals, blind-spot hypotheses,
locked action evaluation contracts, result submission receipts, evaluation,
and goal continuation decisions. Frontier owns domain execution, source
Evidence, Claims, Canonical Claims, review, and run provenance.

The two projects need an auditable exchange without sharing a database,
language-specific domain types, or write authority.

## Decision

Phase B belongs to Frontier v0.6. Its first boundary is three versioned JSON
documents exchanged through files or CLI processes:

1. `cognitrace.frontier.task/0.1.0` carries a locked task/action boundary and
   an immutable evaluation-contract reference from CogniTrace to Frontier.
2. `frontier.cognitrace.result/0.1.0` carries one completed Frontier run,
   stable artifact and Evidence references, review state, frozen runtime
   provenance, and a deterministic content hash.
3. `cognitrace.frontier.receipt/0.1.0` acknowledges acceptance, idempotent
   duplicate submission, or rejection. Only CogniTrace issues an authoritative
   receipt; Frontier only validates and verifies it.

References use non-`file:` URIs plus SHA-256 hashes. Local absolute paths are
not exchange identities. A result hash is computed from UTF-8 canonical JSON
with sorted object keys and compact separators after removing
`result_content_hash`. Budget values are non-negative integers so the hashed
wire document does not depend on language-specific floating-point rendering.

The executable boundary is:

```text
lab integration validate task TASK.json
lab integration seal-result RESULT-DRAFT.json --output RESULT.json
lab integration validate result RESULT.json
lab integration verify-receipt RESULT.json RECEIPT.json
```

The language-neutral schema is
`docs/contracts/v0.1/frontier-cognitrace-contracts.schema.json`. The Python
validator is an implementation of the same contract, not a shared CogniTrace
domain model.

## Compatibility and failure semantics

- Contract versions are independent of the Frontier release version.
- Unsupported versions, missing required fields, unknown fields, invalid
  references, and hash mismatches fail closed.
- A duplicate receipt is successful only when task, action, run, and result
  hash identify the same prior submission.
- Rejected receipts contain structured errors; accepted and duplicate receipts
  contain none.
- Incompatible changes require a new contract major version. Additive optional
  changes require a minor version. Clarifications and validator fixes use a
  patch version.
- A deprecated contract remains readable for at least one Frontier minor
  release and receives an explicit removal milestone before deletion.

## Consequences

This creates a narrow, replayable integration seam while both repositories
retain independent storage and lifecycle authority. It deliberately postpones
a shared SDK, network service, automatic CogniTrace ledger writes, and generic
plugin abstraction until repeated real integrations justify them.
