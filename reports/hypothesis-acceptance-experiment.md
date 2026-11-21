# Learned finding acceptance: rejected production candidate

The experimental policy learns four finding acceptance heads using terminal REINFORCE reward. It sees public financial discrepancies, including genuine clean near-misses. The v2 source acquisition weights are frozen. Financial arithmetic, documentary evidence construction and ranking up to four proposals per issue type remain deterministic. It does not learn arithmetic, evidence retrieval, hypothesis generation or stopping.

Development used seed 884112 and 84 company/scenario runs. Rates 0.02, 0.1 and 0.3 were compared after 1,000 acceptance episodes. Development F1 was respectively 0.345779, 1 and 1. The fixed tie break selected 0.1 before opening the final holdout.

Final training used five seeds (314159, 271828, 161803, 141421, 173205), each with 300 source acquisition episodes and 1,500 acceptance episodes. Holdout seed 945820137 covers 20 companies in each of seven scenarios, with 700 policy runs per model over the five training seeds. Companies repeat across model seeds, so these are not 700 independent companies. Total experiment wall time was 279.35 seconds on the local machine; this is not a hardware-independent speed claim.

| Policy | Mean episode F1 | Mean reward | Mean steps |
|---|---:|---:|---:|
| Existing v2 | 1.000000 | 0.982000 | 10 |
| Learned acceptance | 0.999048 | 0.980095 | 10 |
| Financial features zeroed | 0.357143 | -0.292143 | 10 |
| Untrained acceptance | 0.163175 | -0.685222 | 10 |
| Random acceptance weights | 0.248706 | -0.511227 | 10 |
| Independent uniform reward | 0.177402 | -0.653116 | 10 |

The learned candidate produced no false positives and missed two findings across all 700 runs. Four training seeds achieved mean F1 1.0; the fifth achieved 0.995238. Median and P90 action counts were both 10 for every model, because acquisition was held constant. This matched comparison uses the mixed source policy for all scenarios; the specialized default period policy remains unchanged at its existing six-step performance.

Acceptance learning clearly contributes relative to its own ablations, but adds no quality or action-cost improvement over v2. It is therefore rejected as a production replacement. Its checkpoint format is explicitly experimental, outside the existing checkpoint dispatcher and website training workflow.

All five frozen candidates also passed the separate causal challenge at seed 2026112207: 25 clean/error pairs per candidate, covering four issue types and the balanced-journal recognition challenge across company sizes. Micro F1 and exact pair consistency were 1.0 for each candidate, with no checkpoint changes. There were 250 policy episodes but only 25 unique company pairs, reused across training seeds. Mean actions were 18.6, median 16 and P90 32. The full causal report is `hypothesis-counterfactual-experiment.json`. This does not undo the two missed allocation findings on the primary holdout or justify deployment of the candidate.

The zero-feature control largely submits silence, scoring correctly on clean episodes. The independent reward control uses uniform noise, not permuted observed rewards. Per-episode precision/recall in the JSON follow the existing evaluator, which returns zero for empty clean episodes even when F1 is one. The table uses mean episode F1, not micro F1. Full rows, per-scenario results, selected configuration and all five frozen checkpoints are in `hypothesis-acceptance-experiment.json`. Reproduce with `python -m scripts.hypothesis_benchmark`; run the frozen causal challenge with `python -c "from scripts.hypothesis_benchmark import paired_checkpoints; paired_checkpoints()"`.
