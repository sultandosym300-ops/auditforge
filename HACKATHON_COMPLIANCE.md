# Hackathon compliance

This matrix maps the case supplied by the user to implementation and executable checks. It is not an official hidden-judge result. Exact final outcomes and tested commit are recorded in `FINAL_AUDIT_REPORT.md` and release evidence.

| Published requirement | Implementation | Code | Test/evidence | Reproduce |
|---|---|---|---|---|
| Python 3.11 and CPU-only offline core | Standard-library runtime, pinned Python image | `pyproject.toml`, `requirements.txt`, `Dockerfile` | Container CI records Python, network, CPU and memory limits | `docker run --rm --network none --cpus 2 --memory 4g auditforge-evaluator:2.0.1` |
| reset/step observations and five tools | Separate evaluator process and JSON tools | `auditforge/env.py` | `tests/test_contract.py` (20 cases) | `python -m unittest tests.test_contract -q` |
| 100 actions, 60 seconds, 50-record pages | Authoritative environment budget and timer | `auditforge/env.py` | Contract and terminal boundary tests | `python -m unittest tests.test_contract -q` |
| Four independently configurable error classes | Counts, clean cases, causal injections | `auditforge/generator.py` | Financial reconstruction and data tests | `python -m auditforge.financial_audit --count 1000 --seed 2026112001` |
| Two interacting scenarios and compensated errors | Interaction modes, source/book controls | `auditforge/generator.py`, `auditforge/recognition_worlds.py` | Ultimate matrix and causal pairs | `python -m scripts.ultimate_verify` |
| Correct documentary evidence | Exact amounts, currencies and sufficient evidence sets | `auditforge/matcher.py`, `auditforge/financial_audit.py` | Independent reward cases and proof fixtures | `python -m scripts.v4_proof_check` |
| Independent one-to-one matcher | Maximum-cardinality matching with duplicate-claim control | `auditforge/matcher.py` | Exhaustive small assignment graphs and adversarial cases | `python -m scripts.ultimate_evidence` |
| Official reward formula and inspection cost | Exact clipped F1 formula | `auditforge/matcher.py`, `auditforge/env.py` | `tests/test_reward.py` (20 cases) | `python -m unittest tests.test_reward -q` |
| Hidden truth and provenance | Evaluator-owned references; policy broker forwards only public observations | `auditforge/env.py`, `auditforge/agent_runner.py` | Boundary and Docker containment tests | `python -m scripts.verify_container` |
| Reproducibility and renamed/shuffled pairs | Seeded generation, consistent ID transformation | `auditforge/verify.py`, `auditforge/proof.py` | Actual observation/action replay and transformed answers | `python -m scripts.v4_proof_check` |
| Ten train and ten dev episodes | Separate seed/config lists, generated public data and evaluator-only reference files | `configs/train.json`, `configs/dev.json`, `scripts/package_submission.py` | Complete deterministic file comparison | `python -m scripts.submission_check --archive work/submission/AuditForge-final.zip` |
| Four baseline adapters | Random, reconciliation, mark-all, guarded evaluator-only oracle | `scripts/run_baselines.py` | All adapters executed; ordinary oracle access rejected | `python -m scripts.run_baselines --policy all --allow-evaluator-oracle` |
| Recorded trajectories | Episode, step, action, observation, reward and terminal flags | `trajectories/trajectories.jsonl` | Complete replay, no private observation keys | `python -m scripts.submission_check --root EXTRACTED_DIRECTORY` |
| Schemas, design note, license and dependencies | Public/file/action and finding schemas, architecture note, license inventory | `docs/public.schema.json`, `docs/findings.schema.json`, `docs/DESIGN_NOTE.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md` | Submission content and hash checks | `python -m scripts.package_submission` |
| Autonomous one-command verification | Full core plus realistic-world, proof, HTTP and training checks | `scripts/v4_verify.py` | Nonzero exit on failed stage | `python -m scripts.v4_verify --full-core` |
| Bounded submission size | Curated source/data package, less than one decimal GB expanded | `scripts/package_submission.py`, `scripts/submission_check.py` | ZIP/expanded size, path and digest checks | `python -m scripts.submission_check --archive work/submission/AuditForge-final.zip` |
| Explainable live demonstration | Actual company, official tools, post-terminal proofs and learning | `web/src/App.jsx`, `web/src/ProofCenter.jsx`, `JURY_LIVE_DEMO_SCRIPT.md` | Published-site E2E evidence in final report | Follow `JURY_LIVE_DEMO_SCRIPT.md` |

Extended financial modules and learned-policy metrics are additional diagnostics. They do not replace correctness of the environment or independently prove a higher official score. The proof interface distinguishes browser-run fixtures from externally executed Docker checks.
