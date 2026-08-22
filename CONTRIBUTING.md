# Contributing

Run the complete local gate before proposing a change:

```bash
uv sync --dev --locked
./scripts/release_check.sh
```

Contributions must use only synthetic fixtures and public sources approved for
redistribution. Never copy files from an operational Frontier workspace into
this repository.
