# ADR-0002: Public engine and private operational workspace

- Status: Accepted
- Release: v0.5.0

## Context

Frontier learning, market, outreach, Evidence, review, and Canonical Knowledge
data are real and continuously updated. Publishing the operational workspace in
the same Git history as the reusable engine would expose private context and
make future removal unreliable.

## Decision

The reusable engine, schemas, tests, synthetic examples, and public integration
contracts remain in `frontier-global-lab`.

The operational workspace is maintained in a separate private repository. It
selects an engine version and is supplied at runtime through `--project-root` or
`FRONTIER_PROJECT_ROOT`.

The public repository contains empty Claim and Relationship ledgers. Real
workspace data is never copied into public fixtures. Curated public exports use
a separate explicit publication decision and do not become operational ledger
authority.

## Consequences

- Engine and workspace have independent Git history and release cadence.
- No shared database, Git submodule, or cross-repository direct ledger write is
  introduced.
- The public engine must remain testable with its synthetic workspace.
- The private workspace must pin the compatible engine version.
- Public release automation fails closed on prohibited paths, runtime databases,
  real ledger rows, obvious credential signatures, and local absolute paths.
