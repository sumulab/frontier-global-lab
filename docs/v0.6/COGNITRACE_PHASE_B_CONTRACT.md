# Frontier v0.6 × CogniTrace Phase B execution baseline

## Current decision

- Frontier v0.5.0 remains the frozen public MVP baseline.
- Phase B implementation is developed in Frontier v0.6.
- v0.5.x is reserved for security, compatibility, documentation, and defect
  corrections that do not introduce the integration feature set.
- Cross-project authority remains governed by CogniTrace ADR-0011.

## Completed first slice

- Task, result, and receipt wire versions are explicit and independent of the
  product release number.
- `task_id`, `action_id`, and `frontier_run_id` preserve cross-project mapping.
- Artifact, Evidence, prompt, and skill references carry stable non-local URIs
  and SHA-256 content hashes.
- Result review and Evidence review remain explicit and separate.
- Provider, model, prompts, skills, and budget are frozen as runtime
  provenance.
- Result sealing is deterministic and tamper-evident.
- Receipt verification supports accepted and idempotent duplicate submissions,
  and fails closed on rejection or identity mismatch.
- The CLI provides a file/process boundary without a shared database or SDK.
- Synthetic tests exercise compatibility, missing/unknown data, hashing,
  duplicate submission, rejection, and CLI behavior.

## Single current focus

Implement the CogniTrace consumer side against the same JSON fixtures and run
one synthetic round trip. No real private market or learning data should enter
the public fixture set.

## Exit criteria for the Phase B experiment

1. CogniTrace validates a locked task before Frontier execution.
2. Frontier validates the task/action mapping and seals exactly one completed
   run result.
3. CogniTrace verifies the result hash and produces an authoritative receipt.
4. Re-submitting the identical result produces `duplicate`; changing content
   under the same identity is rejected.
5. Both repositories pass independent tests using synthetic fixtures.
6. One private real-data run proves the same boundary without committing the
   package or operational data to the public repository.

Only after these criteria pass should Phase C select a real action for an
end-to-end evaluation.
