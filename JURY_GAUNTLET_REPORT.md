# AUDITFORGE_JURY_GAUNTLET

Generator 1.1.4. Root seed `783061141199`. Python 3.11.1.

## Published rubric reproduced locally

| Category | Score | Maximum |
|---|---:|---:|
| Contract & Isolation | 25 | 25 |
| Data & Truth | 25 | 25 |
| Reward Robustness | 25 | 25 |
| Reproducibility & Generalization | 15 | 15 |
| Engineering & Explanation | 10 | 10 |

## Extended checks

| Test | Expected | Observed | Result |
|---|---|---|---|
| Submission inventory, exact regenerated files and trajectory privacy | 11 | 11 | PASS |
| Contract fixed checks | 20 | 20 | PASS |
| Reward fixed checks | 20 | 20 | PASS |
| 80 complete baseline runs | 80, <=100 steps and <60s each | 80, 24 steps, 0.155s maximum | PASS |
| Independent exact-rational financial and causal audit | 1000 | 1000 | PASS |
| Public evidence collected before submit | 50 | 50 | PASS |
| Individual evidence omissions and complete-proof controls | 0 | 0 | PASS |
| Sized batch-payment books at both published endpoints | 4 | 4 | PASS |
| Independent reward and assignment tournament | 20 | 20 | PASS |
| Byte-identical public transcripts across interpreters | 6 | 6 | PASS |
| Renamed/reordered paired companies | 100 | 100 | PASS |
| Disposable mutations detected | 16 | 16 | PASS |
| Controlled reference discrimination | True | True | PASS |

## Mutation sensitivity

| Mutation | Expected detection | Observed failing test (first) | Result |
|---|---|---|---|
| fx_rounding | Independent source-to-ledger conversion disagrees at a fractional minor unit. | test_foreign_allocation_requires_published_fx_evidence (test_allocation_rounding.AllocationRoundingTests.test_foreign_allocation_requires_published_fx_evidence) | killed |
| loose_amount_tolerance | An amount one minor unit beyond tolerance does not earn a TP. | test_07_amount (test_reward.RewardTests.test_07_amount) | killed |
| incorrect_true_positive | The evaluator cannot credit more matches than a complete correct answer contains. | test_evidence_ablation_on_asymmetric_interactions (test_case_improvements.CaseImprovements.test_evidence_ablation_on_asymmetric_interactions) | killed |
| repeated_finding_double_count | Repeating an otherwise correct finding adds a false positive. | test_evidence_and_duplicate_penalty (test_core.CoreTests.test_evidence_and_duplicate_penalty) | killed |
| truth_in_observation | Initial public observation contains a forbidden evaluator field. | test_14_no_leak (test_contract.ContractTests.test_14_no_leak) | killed |
| inclusive_period_end | An entry at the exclusive closing boundary is outside the period. | test_foreign_allocation_requires_published_fx_evidence (test_allocation_rounding.AllocationRoundingTests.test_foreign_allocation_requires_published_fx_evidence) | killed |
| nondeterministic_generation | Identical inputs must yield byte-equivalent financial episodes. | test_foreign_allocation_requires_published_fx_evidence (test_allocation_rounding.AllocationRoundingTests.test_foreign_allocation_requires_published_fx_evidence) | killed |
| allow_101_steps | The hundredth inspection truncates the episode. | test_18_truncate (test_contract.ContractTests.test_18_truncate) | killed |
| wrong_evidence_id | Every required evidence ID resolves to a sufficient public source. | test_evidence_ablation_on_asymmetric_interactions (test_case_improvements.CaseImprovements.test_evidence_ablation_on_asymmetric_interactions) | killed |
| omitted_false_negative | An omitted true issue contributes exactly one FN. | test_evidence_ablation_on_asymmetric_interactions (test_case_improvements.CaseImprovements.test_evidence_ablation_on_asymmetric_interactions) | killed |
| empty_truth_penalty | A clean company with no submitted findings earns F1=1. | test_timeout_has_terminal_reward_and_frozen_flags (test_boundaries.BoundaryTests.test_timeout_has_terminal_reward_and_frozen_flags) | killed |
| cursor_skips_record | Concatenated pages equal the full ordered source table. | test_fx_fingerprint_does_not_replace_financial_reconciliation (test_case_improvements.CaseImprovements.test_fx_fingerprint_does_not_replace_financial_reconciliation) | killed |
| incomplete_evidence | Removing a necessary item from a finding eliminates its TP. | test_evidence_ablation_on_asymmetric_interactions (test_case_improvements.CaseImprovements.test_evidence_ablation_on_asymmetric_interactions) | killed |
| repeat_submit | A second submit cannot produce new terminal reward. | test_timeout_has_terminal_reward_and_frozen_flags (test_boundaries.BoundaryTests.test_timeout_has_terminal_reward_and_frozen_flags) | killed |
| unbalanced_clean_entry | Independent bookkeeping rejects unequal debits and credits in the pristine journal. | test_foreign_allocation_requires_published_fx_evidence (test_allocation_rounding.AllocationRoundingTests.test_foreign_allocation_requires_published_fx_evidence) | killed |
| incorrect_clean_handling | A clean configuration produces zero discrepancies. | test_timeout_has_terminal_reward_and_frozen_flags (test_boundaries.BoundaryTests.test_timeout_has_terminal_reward_and_frozen_flags) | killed |

## Controlled reference configurations

| Reference | Local rubric | With added data controls |
|---|---:|---:|
| Minimal: fixed company books for each configuration, public API and four issue types. | 100 | 75 |
| Shortcut-prone: an incorrect FX rate is always the correct rate plus seven. | 100 | 81.25 |
| Weak evaluator: accepts a claim using only the affected IDs and type. | 95 | 95 |
| Inconsistent truth: the first discrepancy in each dirty company is overstated by one minor unit. | 81.25 | 81.25 |
| Current AuditForge, unmodified. | 100 | 100 |

Detailed inputs, episode IDs, measurements and individual outcomes are in [JURY_GAUNTLET_RESULTS.json](JURY_GAUNTLET_RESULTS.json). A fresh run with a new root seed changes the financial trials.

The rubric is a local reconstruction. Container limits are checked separately by the release workflow.
