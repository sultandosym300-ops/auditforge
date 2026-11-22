# Final engineering audit and submission record

## Release identity and rollback

Baseline: AuditForge 4.0 commit `9703dd382ae512ae4955e5f0270da33b15cc83a6`. The existing `AuditForge-4.0.zip` is preserved locally and Git branch `backup/auditforge-4-stable` retains the source. Changes are on `audit/final-submission`; history, existing branches and tags are not rewritten. The canonical source workspace remains the existing project. The Desktop folder is a website export, not an alternative development checkout.

The final exact commit is recorded by `submission-manifest.json` inside the released ZIP and the GitHub release tag. A document cannot contain the hash of its own containing commit without changing that hash. Published CI evidence therefore records the exact source commit in a separately generated, hash-checked `web/public/release-evidence.json`. The CI URL, immutable source digest list, test date, generator/check versions, commands and configuration are available in Proof Center. A build with absent evidence explicitly says unverified; stale or mismatching evidence fails the build.

## Confirmed defects and fixes

| Severity | Cause and reproduction | Fix | Regression / result |
|---|---|---|---|
| High | Extended contract IDs were present, but official tools could not discover the corresponding document IDs without trusted UI knowledge | Add bounded, public document links on invoices/payments/documents and neutral context roots on the realistic manifest | `tests/test_agent_only.py`; 20 independent companies, 210 additional source fetches, F1=1, FP=0, max47 actions |
| High | The loopback HTTP server trusted any Host if Origin matched it, leaving a DNS-rebinding exposure | Require the actual local 127.0.0.1/localhost host and port before processing requests | Real HTTP `tests/test_http_host_security.py`: malicious matching Host/Origin rejected; normal loopback and existing demo pass |
| Medium | UI assumed policy execution always returned a final tuple. A policy that exhausted the remaining budget while reading could return None with a terminal trajectory | Derive termination/truncation from the actual last trajectory item when no tuple exists, including trained-policy callback | Browser regression exhausts99 inspections then runs a policy; 100-step truncation must hide finished-episode controls |
| Medium | Proof Center showed only historical CI; obsolete static verification-summary data had no current-source binding | Remove unused summary/state, add exact-commit successful-CI evidence generation and build-time canonical source hash validation | `scripts/check_release_evidence.mjs`: missing proof is unverified; stale and escaped source paths fail |
| Medium | No complete, fail-closed submission validator existed | Validate regenerated20episode content, private/public separation, all recorded actions/observations/rewards, four guarded adapters, exact file hashes and safe ZIP paths | `tests/test_submission.py`: missing files, altered observations, leaked private fields, incomplete splits, empty trajectories, cache files, traversal and unauthorized oracle rejected |
| Medium | New validator initially compared absent optional CSV fields against explicit exported null cells incorrectly | Reconstruct the exact union-column CSV representation; retain all row/value checks and reject ambiguous empty cells | Reproduced failure `Export does not reproduce seed/config`; corrected representation and rerun adversarial tests |
| Medium | Existing Dockerfile omitted documents required to validate a complete submission inside a standalone image | Explicitly copy required source documentation and manifests; keep credentials, runtime and user files out of image | Clean-ZIP Docker build and image unit suite are CI release gates |
| Low | Root documentation accumulated obsolete reports; hosting-tool metadata was tracked as product source | Relocate reports to docs/history, adjust relative links, untrack hosting metadata but preserve its local file and history | Git inventory, packaging exclusions, no force push or branch/tag deletion |
| Low | Required third-party font/library notices were incomplete in the submission | Include pinned dependency inventory and upstream notices, including the bundled Manrope font OFL | `THIRD_PARTY_NOTICES.md`, `docs/licenses/` |

No new confirmed matcher/reward mathematical defect was found. Existing independent small-graph exhaustive and metamorphic tests are retained. The official reward remains `clip(2*F1 - 1 - .002*inspection_steps, -1, 1)`; submit is an action and not a normal inspection. No truth/evidence minimum, budget, timeout or compact API was weakened to raise scores.

## Additional-source contribution and scope

`auditforge/agent_only.py` receives only an initial public observation and a step callable. It uses list_records/get_document and submits through the existing API. It obtains contract/acceptance documents for invoice/period claims and bank confirmations for settlement/FX claims. It compares actual document IDs, timestamps, currencies, amounts and exact-rational conversions before submitting. Original required evidence is retained; additional evidence stays within ten IDs.

On20 unique companies across five businesses,40/200-invoice sizes and clean/dirty conditions, the corroborating policy obtained F1=1, no false positives, maximum47 actions and210 extra-source requests. Withheld or inconsistent sources cause unsupported findings to be declined. These are genuine source checks, not arbitrary existence tests. The unchanged reconciliation baseline can still solve the original four-error task; the new sources are not falsely declared mathematically necessary for it. Manufacturing, payroll, tax and other context modules do not gain invented anomaly labels. New sources are also selectable through the site's policy selector as “Corroborate linked sources”.

## Independent RL study

`reports/final-policy-study.json` and its Markdown summary contain a fixed36-company panel on unseen manufacturing/IT/services businesses. Five training seeds each train300episodes on logistics/trade. Five budgets and nine policies yield8100 policy runs. Companies repeat across checkpoints; the independent-company count is36, not8100. Default hyperparameters were fixed before opening the panel. Source and fixture digests must remain unchanged, or the study exits nonzero.

| Action budget | Trained mean F1 | Reconciliation mean F1 |
|---:|---:|---:|
| 5 | .25 | .25 |
| 10 | .603704 | .50 |
| 20 | .75 | .75 |
| 40 | 1.00 | 1.00 |
| 100 | 1.00 | 1.00 |

At budget100 the trained policy has reward=.963333, mean19.333333 actions and zero FP. The company-cluster bootstrap95% interval for its F1 difference at budget10 is [.037037,.185185]. However, a deterministic forced-source control matches EVERY non-timing trained result across all budgets. The budget10 advantage over a conservative full-source baseline is therefore an acquisition/partial-decoding implementation effect, not demonstrated superiority of learned weights. Zero financial features, randomized weights, independent uniform reward and actual decoder-disabled inference are reported separately. Production is not replaced by a worse experimental model.

## Security and accounting audit

Public/private separation, terminal-only demo permission, closed-evaluation rejection, session rotation/logout revocation, calculator restrictions, checkpoint finite-value validation, source discovery and financial export are exercised by regression and integration tests. The policy container remains read-only, unprivileged, without network, mounts or capabilities; the trusted broker supplies only observations. Browser execution is an open demo whose owner can inspect local memory; it is not the closed judging boundary.

Financial checking independently replays both observed and pristine business worlds, including intermediate inventory, assets, payroll, financing, bank reconciliation and declared toy tax. Previous60-company/120-state tests and11 seeded state mutations are retained; source-corroboration adds20 fresh companies and negative controls. No IFRS or national-law compliance is claimed. Full local and constrained-container results are recorded in their JSON/CI artifacts rather than announced as official jury points.

The Python core has no third-party runtime dependencies. Frontend installation uses the pinned npm lockfile; the final installation/build is checked with a fresh dependency install. No custom linter/type checker is claimed where none is configured. Credentials, local env values and private keys are excluded. A Git path-history check found no tracked `.env.local`, PEM or key files in the examined history; this is not proof that all possible historical secret formats are absent.

## Repository and artifact inventory

Current entry points: English README, HACKATHON_COMPLIANCE, this report, SUBMISSION_MANIFEST, docs/DESIGN_NOTE and the live demo script. `auditforge/` contains executable core, `scripts/` reproducible checks and packaging, `tests/` regressions, `configs/` train/dev specs, `datasets/` published data, `trajectories/` public interactions, `web/` browser workbench, `supabase/` optional persistence migration, `reports/` measured results, `docs/history/` archived research and `docs/licenses/` upstream notices.

Removed from product tracking: `.openai/hosting.json` (local file and site identity preserved), obsolete `web/public/verification-summary.json` and unused fetch/state. Historical root reports were relocated, not discarded. Local caches, browser profiles, temporary builds, work logs and old ZIPs remain outside Git and the submission. Automatic approval review rejected deletion of temporary browser profiles without a detailed reason; they were retained and excluded instead. No user data or credential files were deleted.

The submission is curated from necessary files, not a copy of the workspace. It includes10train and10dev companies, evaluator-only truth/provenance in a separate directory, three public-policy trajectory sets, four baseline reports/adapters, required schemas, tests, licenses and design/demo notes. Oracle requires an explicit trusted-host flag and is absent from public observations/trajectories. The packager writes a complete machine hash manifest; SUBMISSION_MANIFEST.md describes the layout. Archive extraction rejects traversal, duplicate entries and symlinks before unpacking.

## Reproduction and release gates

```sh
python -m unittest discover -s tests -q
python -m scripts.final_agent_only
python -m scripts.final_policy_study
python -m scripts.v4_verify --full-core
python -m scripts.package_submission --output work/submission/AuditForge-final.zip
python -m scripts.submission_check --archive work/submission/AuditForge-final.zip
npm --prefix web ci
npm run build
node scripts/check_release_evidence.mjs
```

CI builds the evaluator/policy images, validates the submission before generated research reports can dirty the source, runs core/accounting/reward/security checks without network under2CPU/4GiB, then extracts the generated ZIP into a fresh directory, builds its Docker image and runs its tests independently. A separate Node22 job installs the lockfile and builds the frontend. These gates require no private service keys. The heavier exploratory policy study is reproducible separately; the smaller study tests run with every unit suite.

Final publishing is conditional on successful exact-commit CI. The same source commit is fast-forwarded to main, the staged Vercel build is promoted, the seven-stage live demo and additional-source/truncation regressions are run against the real site, and the verified ZIP is attached to the final GitHub release. The exact outcome, commit and archive SHA256 are recorded in the release asset manifest. No pending check is represented as a completed success in this report.

## Remaining limitations

Synthetic procedural companies are not real financial data. Learned scope is21 source-acquisition weights with deterministic financial decoding; a learned financial reasoning advantage was not established. Additional modules remain simplified context where explicitly documented. A human novice comprehension test was not conducted; browser E2E proves mechanics, not universal usability. Closed evaluation requires the broker/container. Current-cloud authenticated checkpoint persistence requires the user's Supabase configuration; guest/local flows are tested separately. Cold browser startup needs the locally bundled Pyodide assets; prepare the build before an offline demonstration. An official jury score and ranking are unknown.

Final local regressions before the clean-container correction: 176 tests passed; an additional no-Git regression was then added. CI uploads the exact ZIP it extracted and tested in a clean Docker build. The final release uses that CI artifact rather than rebuilding a different ZIP; separately attached release-evidence.json binds its source and the deployed frontend to the successful exact-commit CI.

Confirmed clean-container packaging defect: the first release CI failed immediately because package metadata unconditionally invoked the unavailable Git binary. The core image intentionally remains Git-free. Packaging now catches missing Git, uses existing manifest identity when unpacked, or accepts the explicit CI source SHA supplied by the trusted workflow. Seven submission tests including the missing-Git regression pass; the failed run is retained in GitHub history rather than hidden.

Second confirmed CI fixture defect: mutation sandboxes copied only Python directories and omitted the newly required submission metadata. The baseline failed before any mutation was applied; this was not counted as a killed mutant. Sandboxes now include configs, schemas, licenses and required documentation. The isolated sandbox baseline passed177 tests. The final browser regression also passed100-action truncation/control closure and official-action corroboration with real extra-document requests.
