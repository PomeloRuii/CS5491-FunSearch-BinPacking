# Reproducing the fused follow-up

The actual paired observations and six measured boundary decision pairs are in
results/fused_v12. Historical separate-container negative timing results remain
unchanged. This update adds the owned checkpoint correction and versioned fused
controller/worker/Windows observer source, but supplies no execution grant.

All private receipts, approvals, consumed slot states, raw development/boundary/
reserved/held-out values, Docker images, private history and personal logs are
excluded. Existing LICENSE/NOTICE remain authoritative and unchanged. Dataset
redistribution/provenance limitations in DATA_AND_SECURITY.md still apply.

Source bodies and scoring are unchanged. The public protocol helper only remaps
the pool/checkpoint to published artifacts and the six-state bank to a separately
supplied local_data/development_boundary_states.json. Its canonical hash is in
protocols/fused_v12_method.json. Existing data/materialization documentation still
applies to development inputs; no raw values are bundled or regenerated here.

The private image IDs require an equivalent locally built/validated environment.
The projected public runtime is NOT independently runtime-validated; the successful
private experiment is not a fresh-machine reproduction certificate. Default
execution fails closed without local inputs, exact manifests and a new approval.
Private manifest/receipt history is not needed or reusable authorization.

The corrected restore can be inspected separately. Public scalar results can be
recomputed without any data, model calls, Docker or candidate execution:

python tools/analyze_fused_v12_results.py

The full result is controlled fixed-pool replay, not live multi-seed evolution.
No decrease in LLM requests, universal speedup or equivalence from fingerprints
is established. Continue development-only probe coverage/independent validation
before committing to the unchanged 540-call main campaign.
