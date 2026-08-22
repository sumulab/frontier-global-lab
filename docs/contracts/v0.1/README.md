# Frontier × CogniTrace contract v0.1

This directory contains the language-neutral JSON Schema for the experimental
Phase B file boundary. Contract version `0.1.0` is intentionally independent
of Frontier product version `0.6`.

The schema exposes three definitions:

- `#/$defs/task`
- `#/$defs/result`
- `#/$defs/receipt`

Runtime validation and deterministic result sealing are available through
`lab integration`. See
`docs/decisions/ADR-0003-versioned-cognitrace-file-contract.md` for authority,
hashing, compatibility, duplicate, and deprecation semantics.

`examples/` contains a synthetic task, sealed result, and accepted receipt for
cross-repository conformance tests. It contains no real operational data.
