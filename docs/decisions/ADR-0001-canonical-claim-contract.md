# ADR-0001: Canonical Claim lifecycle and relationship contract

- Status: Accepted
- Release: v0.5.0

## Decision

Canonical Claim lifecycle values are exactly:

```text
needs_review
active
superseded
archived
```

Research Claim draft/review state and Canonical promotion are separate from
this lifecycle. A new Canonical Claim begins in `needs_review`; only explicit
human review can make it `active`.

Claim relationships are separate immutable facts with exactly these types:

```text
supports
contradicts
qualifies
supersedes
```

A relationship never changes lifecycle state implicitly. JSONL ledgers are the
authority; SQLite indexes are disposable projections. Unknown schema versions,
broken event chains, invalid transitions, missing provenance, and duplicate IDs
fail closed.

Operational claims and Evidence are workspace-owned data and are not included
in the public engine repository.
