# Proposal alignment audit — completed v1.2, no implementation change

The final Proposal (Section2, verified PDF hash83880e62…56c780) requires validity,
exact matching, then sampled behavioral matching and conditional full evaluation.
The original PDF/extraction and all100 v1.2 control seals were checked read-only.
No source, receipt, manifest, score, timing or consumed authority was changed.

## Finding: correct order, incomplete all-seen source coverage

`phase3/replay3.py:process` calls static validation, then `Representatives.exact`,
then dispatches fingerprint/fused only on an exact-cache miss. Ordering is PASS.
However, `phase2/filters.py:Representatives.retain` populates both source and
behavior caches only after a complete accepted full evaluation. It does not
index a source whose outcome was a behavioral skip. This is a representative-only
cache, not an all-seen terminal-source index.

The Proposal says exact matching but does not explicitly define retention for
behaviorally skipped sources. Its previously-evaluated-representative wording
explains the implemented cache. Against the user's clarified intent that exact
repeated sources should not enter fingerprinting again, cache coverage is a
**LIMITATION / DEVIATION**, not a missing/reversed stage. Publication must expose
this choice rather than imply every repeated source is caught before FP.

## Direct trace and reservation evidence

Candidates14/15 share raw SHA
`fd19275a66d36fa879ae54614c80bca9e24d7c8353dda4b97228f33b0158996d`
and exact-normalized key SHA
`7c6d5f49c4c699323cd87f3cb4aafed68ed1a53e99f3192dd86e57dbef952245`.

| Both timing blocks | Candidate14 | Candidate15 |
| --- | --- | --- |
| Exact arm | full evaluation; retained; registered | exact skip→14; no worker |
| Fused16 | fused FP task; behavioral skip→2; not retained | exact-cache miss; fused FP task; behavioral skip→2 |

Candidate15 therefore **was dispatched in both Fused blocks**. The seven matches
in each block are3/10/12/13/14/15/16 and include15. The durable approved dispatch
records agree with the candidate traces. Exact uses9 containers, Fused10.
No skipped candidate is registered or assigned independent fitness.

The measured15.778s/14.598s means, seven behavioral matches, six fewer completed
full evaluations and one extra container per Fused arm remain the actual results.
They must not be retroactively relabelled as six direct behavioral matches plus
an exact skip, or reduced by an estimated container time.

## Future method: terminal-source index C1 (not implemented)

Retain the existing fully evaluated representative cache. Separately index each
static-valid source after a confirmed terminal accepted-full or valid behavioral-
skip outcome. Key the index by the documented exact source key plus configuration,
bank/N, image, data and policy identities. A later identical source can reuse the
terminal decision without re-fingerprinting. No entry is created for pending,
uncertain, timeout/OOM, cleanup-failed or unsupported outcomes. Every arm starts
with empty indexes; no other arm's fitness or cache is imported.

If14 was only suspected equivalent to2, repeat15 must be labelled
`exact_repeat_of_behavioral_skip`, with provenance15→14→2. It inherits only a
suspected skip decision, **not independently verified fitness**. It is not inserted
into the program DB. All such propagated skips remain in the behavioral-risk
audit population; relabelling them must not evade audits or upgrade equivalence.
Pure exact equality must never be inferred from a fingerprint match.

For this trace, C1 would remove one FP task per block but avoid **zero additional
full evaluations**, because15 already skipped full fitness. This is a logical
counterfactual, not measured runtime. New code, validation and a finite new
execution authorization are required before making a performance claim.

## Additional post-hoc island-quality finding

Global best curves matched, but that does not make island histories equivalent.
Using only concurrent Exact scores, skipped3 (Fused island4) and13 (island7)
would each exceed their selected island's then-best -2750 with score-1142.541667.
This occurs in each timing repeat: four events, two source/island opportunities.
Neither would improve the global incumbent. These are post-hoc opportunity
comparisons, not an executed counterfactual search or new independent audits.
No audit score was injected into Fused histories. Track island opportunities and
prompt changes alongside global best and score-changing collisions in future work.

Public evidence: ../results/fused_v12/filter_order_evidence.csv and
../results/fused_v12/island_opportunity_checks.json. The detailed private
audit evidence index is excluded from this export. Exact scientific receipts remain under the closed
v1.2 campaign; no additional candidate/container/model work ran for this audit.
