# Design note

AuditForge separates generated economic facts, observed documents and trusted evaluation. The compact profile preserves the official four-table audit task. `realistic_v1` derives additional business events, source documents, postings and state; its independent auditor reconstructs both observed and pristine books rather than calling the generator's report builder.

The agent-facing boundary is initial JSON plus the five official action tools. The production matcher performs deterministic maximum-cardinality one-to-one matching using type, affected IDs, amount tolerance, currency and complete evidence sets. The unchanged reward is `clip(2*F1 - 1 - .002*inspection_steps,-1,1)`. Submit is a total action but not an inspection; exhausted inspections remain chargeable.

The Python host owns private truth/provenance and optional post-terminal explanations. Open demonstration requires explicit intent and completion; closed evaluation rejects explanations even after termination. For untrusted policies, the broker starts a code-only container with no network, no project mount, read-only storage and restricted user/resources. Browser execution is an educational view, not this containment boundary.

REINFORCE updates 21 source-acquisition weights from terminal reward. The policy can query or skip invoices, payments and rates. Accounting arithmetic, proof construction and matching remain deterministic. Checkpoint imports validate finite bounded weights, architecture, versions and history; no arbitrary code is deserialized.

Submission examples are deterministic public train/dev fixtures. Their reference answers are packaged under `evaluator_private` for the trusted evaluator only. Public trajectories are regenerated and replayed through the actual environment, including observations, reward and terminal flags. The oracle adapter is evaluator-only and requires a separate explicit authorization flag.

The new submission checker rejects incomplete or modified examples, mismatched file hashes, contaminated public observations, incomplete trajectories and unsafe ZIP paths. Source installation is unnecessary for Python verification: Python 3.11's standard library suffices. Web dependencies are separately pinned with npm integrity hashes.

Limits remain: synthetic-world generalization, simplified financial processes, no national tax/IFRS compliance, no real-world financial assurance, and no guaranteed hackathon score. Measured results are tied to source hashes and a tested commit; historical checks must not be presented as current execution.
