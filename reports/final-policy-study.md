# Final policy transfer and ablation study

36 independent synthetic companies; 5 checkpoints; 8100 paired policy runs. Train businesses: logistics/trade. Test businesses: manufacturing/IT/services.

| Budget | Policy | F1 | Reward | Steps | FP | FN |
|---:|---|---:|---:|---:|---:|---:|
| 5 | trained | 0.250000 | -0.502000 | 5.000 | 0 | 360 |
| 5 | untrained | 0.250000 | -0.502000 | 5.000 | 0 | 360 |
| 5 | random | 0.250000 | -0.502000 | 5.000 | 0 | 360 |
| 5 | reconciliation | 0.250000 | -0.502000 | 5.000 | 0 | 360 |
| 5 | zero_features | 0.250000 | -0.502000 | 5.000 | 0 | 360 |
| 5 | random_weights | 0.250000 | -0.502000 | 5.000 | 0 | 360 |
| 5 | independent_reward | 0.250000 | -0.502000 | 5.000 | 0 | 360 |
| 5 | forced_sources | 0.250000 | -0.502000 | 5.000 | 0 | 360 |
| 5 | no_financial_decode | 0.250000 | -0.502000 | 5.000 | 0 | 360 |
| 10 | trained | 0.603704 | 0.195407 | 10.000 | 0 | 200 |
| 10 | untrained | 0.250000 | -0.503500 | 8.000 | 0 | 360 |
| 10 | random | 0.250000 | -0.504000 | 9.000 | 0 | 360 |
| 10 | reconciliation | 0.500000 | -0.009000 | 10.000 | 0 | 240 |
| 10 | zero_features | 0.298519 | -0.407463 | 8.133 | 0 | 340 |
| 10 | random_weights | 0.438519 | -0.130996 | 9.217 | 0 | 277 |
| 10 | independent_reward | 0.298519 | -0.407463 | 8.183 | 0 | 340 |
| 10 | forced_sources | 0.603704 | 0.195407 | 10.000 | 0 | 200 |
| 10 | no_financial_decode | 0.250000 | -0.504500 | 10.000 | 0 | 360 |
| 20 | trained | 0.750000 | 0.480833 | 15.333 | 0 | 120 |
| 20 | untrained | 0.250000 | -0.505167 | 11.333 | 0 | 360 |
| 20 | random | 0.250000 | -0.504000 | 9.000 | 0 | 360 |
| 20 | reconciliation | 0.750000 | 0.480833 | 15.333 | 0 | 120 |
| 20 | zero_features | 0.305556 | -0.395156 | 11.533 | 0 | 336 |
| 20 | random_weights | 0.483333 | -0.044767 | 13.583 | 0 | 252 |
| 20 | independent_reward | 0.305556 | -0.395156 | 11.617 | 0 | 336 |
| 20 | forced_sources | 0.750000 | 0.480833 | 15.333 | 0 | 120 |
| 20 | no_financial_decode | 0.250000 | -0.507167 | 15.333 | 0 | 360 |
| 40 | trained | 1.000000 | 0.963333 | 19.333 | 0 | 0 |
| 40 | untrained | 0.250000 | -0.505167 | 11.333 | 0 | 360 |
| 40 | random | 0.250000 | -0.504000 | 9.000 | 0 | 360 |
| 40 | reconciliation | 1.000000 | 0.963333 | 19.333 | 0 | 0 |
| 40 | zero_features | 0.333333 | -0.341267 | 11.800 | 0 | 324 |
| 40 | random_weights | 0.555556 | 0.092111 | 15.733 | 0 | 222 |
| 40 | independent_reward | 0.355556 | -0.297689 | 12.383 | 0 | 312 |
| 40 | forced_sources | 1.000000 | 0.963333 | 19.333 | 0 | 0 |
| 40 | no_financial_decode | 0.250000 | -0.509167 | 19.333 | 0 | 360 |
| 100 | trained | 1.000000 | 0.963333 | 19.333 | 0 | 0 |
| 100 | untrained | 0.250000 | -0.505167 | 11.333 | 0 | 360 |
| 100 | random | 0.250000 | -0.504000 | 9.000 | 0 | 360 |
| 100 | reconciliation | 1.000000 | 0.963333 | 19.333 | 0 | 0 |
| 100 | zero_features | 0.333333 | -0.341267 | 11.800 | 0 | 324 |
| 100 | random_weights | 0.516667 | 0.017267 | 15.100 | 0 | 234 |
| 100 | independent_reward | 0.400000 | -0.210900 | 13.267 | 0 | 294 |
| 100 | forced_sources | 1.000000 | 0.963333 | 19.333 | 0 | 0 |
| 100 | no_financial_decode | 0.250000 | -0.509167 | 19.333 | 0 | 360 |

## Paired uncertainty

| Budget | Metric | Trained minus reconciliation | Company-bootstrap 95% |
|---:|---|---:|---|
| 5 | f1 | 0.000000 | [0.000000, 0.000000] |
| 5 | reward | 0.000000 | [0.000000, 0.000000] |
| 10 | f1 | 0.103704 | [0.037037, 0.185185] |
| 10 | reward | 0.204407 | [0.073074, 0.365370] |
| 20 | f1 | 0.000000 | [0.000000, 0.000000] |
| 20 | reward | 0.000000 | [0.000000, 0.000000] |
| 40 | f1 | 0.000000 | [0.000000, 0.000000] |
| 40 | reward | 0.000000 | [0.000000, 0.000000] |
| 100 | f1 | 0.000000 | [0.000000, 0.000000] |
| 100 | reward | 0.000000 | [0.000000, 0.000000] |

## Interpretation

No production policy replacement is made by this study. At budgets where both policies have complete evidence, compare identical paired rows rather than selecting the best seed. If zero-feature or forced-source controls match the learned policy, that is evidence of limited acquisition complexity, not an additional learned financial skill.

## Limitations

- Same 36 company fixtures repeat across five checkpoints, nine policies and five budgets; 8100 runs are not 8100 independent companies.
- Evaluator fixtures share immutable source records; each step returns deep-copied observations and a final hash check verifies no fixture changed. Source generation/reset timing is excluded from inference timing.
- Transfer is within one procedural generator and the same procurement error mechanism, not external finance generalization.
- Zero-features means non-bias feature ablation at inference, not retraining a featureless architecture.
- Independent reward is uniform noise, not shuffled recorded rewards.
- Budgeted reconciliation keeps its four-table acquisition order and makes no claims if full sources cannot fit. Random reserves one submit action.
- The official environment remains 100 steps and 60 seconds; smaller budgets are strategy constraints imposed through public observations.
- Forced source gates plus documentary decoding are deterministic controls, not learned-model improvements.
- Financial arithmetic remains hand engineered; high F1 does not establish learned bookkeeping or superiority over deterministic reconciliation.

## Measured conclusions

At 100 actions, trained F1=1.000000, reconciliation F1=1.000000, reward=0.963333, mean steps=19.333333.
Zero non-bias features: F1=0.333333; random weights=0.516667; independent reward=0.400000; decoder removed=0.250000.
Every non-timing trained row matches the deterministic forced-source control: True. Therefore this study does not establish a learned advantage over that stronger deterministic control.
At budget 10 the trained policy exceeds full-source reconciliation on this panel, but the forced-source control has exactly the same result. This is an effect of partial-document decoding/budget adaptation, not evidence that learned weights outperform deterministic acquisition.
The panel contains nine clean companies out of 36. F1=.25 from an always-empty decoder is correct abstention on these clean companies, not detection of financial violations.
The decoder ablation uses a scoped replacement of the deterministic decode callable with empty findings; the financial arithmetic is not executed for this control. Source acquisition and evaluator remain unchanged.

Decoder-control verification: {"all_non_timing_metrics_unchanged": true, "method": "Scoped test-only replacement of deterministic decode with empty findings, leaving acquisition, public evidence and Session unchanged.", "runs_recomputed": 900, "seconds": 3.646087400004035}

Source hashes normalize CRLF to LF for portability. `sources_unchanged` must be true before this report is treated as final.
