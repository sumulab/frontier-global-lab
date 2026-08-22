# Frontier Global Lab

Public Frontier Harness engine and versioned domain-knowledge contracts.

Frontier v0.5 is an MVP for evidence-backed research, human-controlled
Canonical Claim lifecycle management, append-only relationship ledgers, and
rebuildable read models. Real learning, market, outreach, review, Evidence, and
Canonical Knowledge data live in a separate private workspace.

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
