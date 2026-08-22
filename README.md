# Frontier Global Lab

Public Frontier Harness engine and versioned domain-knowledge contracts.

Frontier v0.5 is an MVP for evidence-backed research, human-controlled
Canonical Claim lifecycle management, append-only relationship ledgers, and
rebuildable read models. Real learning, market, outreach, review, Evidence, and
Canonical Knowledge data live in a separate private workspace.

Frontier v0.6 is the active development line for the versioned CogniTrace
Phase B file/CLI contract. The v0.5.0 tag remains the stable public baseline.

## Install

```bash
uv sync --dev --locked
uv run lab --help
```

The repository includes a synthetic, empty public example workspace under
`10_Harness/`. It contains schemas and one local smoke workflow, but no real
operational data.

```bash
uv run lab status
uv run lab claim status
./scripts/release_check.sh
```

## CogniTrace Phase B contract

The v0.6 development line adds a narrow JSON file/process boundary without a
shared database or cross-project domain model:

```bash
uv run lab integration validate task task.json
uv run lab integration seal-result result-draft.json --output result.json
uv run lab integration validate result result.json
uv run lab integration verify-receipt result.json receipt.json
```

See `docs/v0.6/COGNITRACE_PHASE_B_CONTRACT.md` and the language-neutral schema
under `docs/contracts/v0.1/`.

## Use an external workspace

A workspace root must contain `10_Harness/config.json`.

```bash
uv run lab \
  --project-root /path/to/private-workspace \
  status
```

Alternatively:

```bash
export FRONTIER_PROJECT_ROOT=/path/to/private-workspace
uv run lab claim status
```

The engine never requires a private workspace to be committed to this
repository.

## Public repository contents

- `harness/`: Python engine and CLI.
- `tests/`: executable lifecycle, provenance, relationship, and index contracts.
- `10_Harness/temporal/`: public schemas plus empty example ledgers.
- `10_Harness/prompts/`, `skills/`, `workflows/`: synthetic public examples.
- `docs/`: public architecture and publication-boundary decisions.
- `scripts/`: smoke, release, and public-boundary checks.

See `PUBLICATION_POLICY.md` before adding files. Real people, companies,
outreach, strategy, learning history, market datasets, run artifacts, Evidence,
or Canonical Claim ledgers are prohibited in this public repository.

## Release

```bash
./scripts/release_check.sh
```

The v0.5 public engine and the private workspace have independent Git history.
They integrate only through the workspace layout and versioned result
contracts.

## License

Licensed under the Apache License 2.0. See `LICENSE`.
