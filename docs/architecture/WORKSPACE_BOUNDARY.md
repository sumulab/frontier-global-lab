# Engine and Workspace Boundary

## Decision

`harness/` is the reusable Python execution engine. A Frontier workspace is an
external project root containing `10_Harness/config.json` and domain-owned
content. The public repository bundles only an empty synthetic workspace for
tests and local evaluation.

The runtime dependency is one-way:

```text
public harness engine
    -> workspace config, prompts, skills, workflows
    -> workspace Evidence and Canonical Knowledge authorities
    -> workspace-local derived runtime artifacts
```

The workspace does not import the engine. It selects an engine version and
invokes the CLI with `--project-root` or `FRONTIER_PROJECT_ROOT`.

## Authority

- Python behavior is authoritative in the public engine release.
- Operational knowledge and review history are authoritative only in the
  private workspace.
- SQLite indexes, sessions, runs, and drafts are local generated state.
- Cross-project consumers receive only versioned result contracts, stable
  references, hashes, and minimal summaries.

## Non-goals

The split does not create a shared database, allow external writes to Frontier
ledgers, or make private workspace content part of the Python package.
