# Strict core audit

These are local checks against the supplied case, not an organizer score.

## Reproduced failures and fixes

- **High: invalid financial source histories passed validation.** Adding 100,000,000 minor units to a payment document (in public and pristine branches) left invoice allocations unchanged, yet `validate` returned true. Replacing every cash account with an unrelated asset also passed because only aggregate debits and credits were checked. Validation now independently verifies invoice line totals, payment allocation totals, exact invoice recognition pairs, complete settlement pairs, dates, rates, amounts, identities and manifest counts.
- **High: unrelated evidence passed validation.** Replacing every truth evidence set with one arbitrary existing invoice document passed validation and gave the truth oracle F1=1. Validation now requires every admissible evidence set to contain the complete independently recovered evidence. Evidence sufficiency remains scoped to the four documented synthetic mechanisms.
- **High: provenance omitted changed mirror postings.** The generator changed both sides of payment, FX and period postings but logged only one final row. Duplicate provenance also failed to describe its actual before-state. All changed journal rows are now recorded. Validation replays mutations from pristine books and demands exact equality with the public journal; document changes must also be explained by the source history.
- **High: policy backpressure escaped the broker deadline.** A policy can request a page then stop reading stdin; the broker's synchronous flush could block indefinitely. Writes now run through a bounded deadline. Terminal observations are not written after scoring, and named Docker containers are explicitly removed on exit. The regression uses a real child process that never reads stdin and a 1 MB observation.
- **Medium: null record IDs succeeded.** `get_record` without an ID matched absent optional dictionary fields and returned the first row. Missing, null, empty and nonstring IDs now produce the bounded error and consume a step.
- **Medium: episode mutation contaminated later generation.** The manifest shared the global currency exponent dictionary. Mutating one generated episode could alter subsequent books with the same seed. Manifests now own a copy. Boolean configuration types, integer seeds and valid ISO UTC offsets are checked explicitly.
- **Medium: the second interaction lacked two interacting error types.** A duplicate plus a refund distractor did not make the independently injected period error interact with the duplicate. Interaction 2 now moves recognition of the same duplicated obligation across the reporting boundary while retaining its documented refund.
- **Medium: metamorphic scoring was partly tautological.** Comparing truth-derived oracles on two transformed truths cannot demonstrate policy generalization or transition reproducibility. Pair verification now replays identical actions and observations, then executes public reconciliation through the tool interface on renamed and shuffled records, comparing actual final metrics, rewards and step counts.

## Reproduction and evidence

Run `python -m unittest discover -s tests -v` from the project directory. `tests/test_strict_audit.py` contains the corruptions, nonreading-process probe, shared-state probe, invalid-input probes, and alternate configuration/transformed-transition tests. The focused suite complements the existing contract and matcher attack tests.

An additional pre-fix sweep covered 2,250 combinations: seeds 0..149, invoice counts 40/41/50/100/200, all three interaction settings and all four issue counts set to 3. No generated-truth/reconciliation mismatch occurred in that sweep. This does not independently prove accounting or evidence validity; the new corruption tests address that distinction.

## Remaining limits

- Docker is not installed on the audit machine. Container build/run, Linux behavior and actual cgroup/network confinement remain unexecuted; the native broker is explicitly for trusted policies.
- Source-history validation is intentionally specialized to the generator's native KZT invoices, four currencies, fixed reporting period and four known error mechanisms. It is not a general accounting validator and does not establish realism or sufficient task difficulty.
- Direct `AuditEnv` callers are trusted. Untrusted policies require the separate broker/container boundary; a Python process alone is not an OS sandbox.
- Pair checks are local known transformations. Organizer hidden seed/parameter checks, hardware limits and official grading have not been observed.
- The timeout regression measures bounded write behavior, not a complete 60-second adversarial Docker run. End-to-end container watchdog and forced cleanup still require a Docker host.
