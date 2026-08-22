# Public Repository Publication Policy

## Purpose

This repository publishes the reusable Frontier Harness engine, public domain
contracts, tests, and synthetic examples. It is not the operational Frontier
workspace and is not a data publication channel.

## Allowed

- Python engine and CLI source;
- tests and release tooling;
- versioned schemas and public technical ADRs;
- empty ledgers and synthetic examples;
- documentation written for public engine users.

## Prohibited

- credentials, tokens, `.env`, private endpoints, or session databases;
- real people, organization, supplier, outreach, or contact records;
- real learning history, reviews, strategy, market datasets, or private notes;
- real run directories, drafts, prompts captured from runs, or Evidence SQLite;
- operational Canonical Claim or Relationship ledger rows;
- CogniTrace goals, evaluations, receipts, or other private cross-domain state;
- licensed source text unless separately approved for redistribution.

## Curated exports

Real results may be published only as separately reviewed release artifacts.
They must have an explicit public-release decision, stable identifier, content
hash, source/license review, and removal of personal or operational provenance.
They must never be copied directly from the private workspace ledger.

## Enforcement

`scripts/check_public_boundary.py` is an allowlist-oriented release gate. It is
run locally and in CI. Passing automation does not replace human publication
review.

## License

The public engine, schemas, tests, synthetic examples, and documentation are
licensed under Apache-2.0. Private workspace content and curated data exports
are separate works and are not automatically covered by this repository's
license.
