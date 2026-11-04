# Proposed state-policy v2.0 and controlled validation study

**Design only. Not implemented, built, tuned, executed or authorized.** No values
from final held-out instances or old raw reserved-state banks are inputs here.
The existing16/64/128 banks and all historical results remain immutable.

## Separate method factors

- S0: original FF/BF-disagreement banks at16/64/128 (exact existing hashes).
- S2: the proposed family/arrival/configuration-stratified banks at16/64/128.
- C0: measured v1.2 representative-only exact cache. C1: proposed terminal-source
  decision index described in FILTER_ORDER_AUDIT.md, including suspected provenance.
- F0: measured v1.2 FP-invalid rejection. F1: proposed conservative full fallback
  for recoverable FP numerical/shape/coverage failures; shared full acceptance.

Primary state comparison uses C1/F1 for **both S0 and S2**, so cache/fallback
changes cannot be attributed to new state selection. Exact uses C1 and normal
full validity. One separately labelled C0/F0/S0/N16 bridge retains the measured
v1.2 method; it is a composite bridge and cannot identify individual C1/F1 effects.
Do not silently describe S0+C1/F1 as an exact reproduction of historical v1.2.
Code-only cache/fallback regressions precede any new source-bound execution grant.

## Construction and support, not Candidate10-specific probes

Use only the frozen development instances, with trusted FF, BF, WF and seeded
feasible-random prefix collectors. Build valid states from the actual priority
interface: original bin indices/order, only feasible capacities, original scalar/
Linux dtype semantics, and original first-np.argmax selection. No model program
participates in state construction or selection.

Arrival regions are general capacity fractions: (0,1/4], (1/4,1/2), [1/2,3/4],
(3/4,1). Record rational-boundary flags from the fixed generic set
{1/4,1/3,1/2,2/3,3/4}, exact-fit availability and equal-capacity tie configurations.
No source hash or measured candidate behavior controls selection.

Two competing configurations are required where supported: (A) one feasible
occupied bin plus empty bins, (B) at least two distinct feasible occupied
capacities plus empty bins. All-empty/no-choice states are guards, not substitutes
for competing-state coverage. Prefixes must remain valid packings; do not invent
bin capacities or append an adversarial state just because it catches10.

Allocate N/2 states per family, initially N/16 per arrival/configuration cell.
Use family/cell round-robin so16/64/128 are nested prefixes of one frozen128 bank.
For structurally unavailable cells, redistribute quota deterministically within
the same family/configuration across supported regions in ascending-region
round-robin; log support gaps. OR development has no item>2/3 capacity, so its
>3/4 cells cannot be populated from original items. Do not fabricate data or
claim that region was tested for OR. No duplicate state padding is allowed.

Before candidate execution, verify at least two >=1/2 arrivals per family, both
competing configurations, and family-level exact-fit/equal-capacity guard coverage
where pools support them. State-feature-only deterministic selection may satisfy
these guards within fixed quotas; no candidate outcome may guide swaps. If size/
support requirements cannot be met, freeze/report unsupported status and abstain
from behavioral skipping, rather than silently weaken the promised coverage.

Prospective seeds: split54921000, construction54921001, validation54921002,
audit order54921003, timing order54921004. These are proposed new seeds, not
historical generator metadata. Exact state IDs/bank hashes must be committed
before any candidate evaluation under S2.

Define behavioral-input identity from canonical IEEE-754 item/capacity bits plus
ordered original feasible-bin indices, excluding collector/seed/origin labels.
Store a separate origin ID for instance/order/prefix provenance. Use the input
identity to remove duplicate padding and construction/validation overlap: merely
renaming a state or changing its collector must not make identical inputs appear
independent. This cannot remove similarity between different states; report that
limitation and effective distinct-input counts alongside nominal N.

## Prospective validation separation and contamination limits

Deterministically rank existing development IDs by SHA256 of
`state-policy-v2.0|54921000|family|instance_id`. Use the first8 OR/2 Weibull IDs for
construction, reserve the other4 OR/1 Weibull for prospective validation. No
final held-out IDs/values are loaded or repartitioned. The original split is not
rewritten; this is an explicitly versioned subdivision of development only.

Validation builder uses its separate seed and seeded item-order permutations of
reserved development instances, with the same validity rules and broad collectors.
These are reachable **development diagnostic states**, not altered full-evaluation
instances. Normal full fitness always uses the unchanged15 original-order
development instances. A fixed256-state validation bank is shared across all N/
methods; exclude exact state IDs already present in construction, original banks
and the six previously inspected challenges. No validation state is shown to
normal workers; use a separate FP-only minimized audit image. Validation artifacts
are sealed before method freeze and revealed only to the audit process afterward.

All development instances were historically evaluated, and S0 was built before
this subdivision. Thus this is prospective independence of **selection/access**,
not a previously unseen dataset or a pristine statistical holdout. The known
16-program pool is also a regression corpus, not independent confirmation.
The old256 reserved bank and six challenges are diagnostic history only. If
validation results prompt any method change, that bank becomes development data:
version the change and require a newly committed validation protocol. Do not
reroll states/seeds until a favorable result appears. A later genuinely unseen
Qwen pool needs separate finite generation/execution approvals; no calls are
allocated here and final held-out data remain untouched.

## Fixed comparison and bounded prospective budget

Replay the same authentic16 records in generation order from identical original
checkpoints/empty arm caches through eight settings:

1. Exact C1.
2–4. S0 at16/64/128, C1/F1.
5–7. S2 at16/64/128, C1/F1.
8. Diagnostic bridge S0/N16/C0/F0.

Three timing blocks use one seeded permutation, its reverse and a four-position
rotation. Publish the realized order before dispatch; three blocks do not fully
counterbalance eight positions, so report that limitation. Use fresh disposable
workers, fixed resources/deadlines and serial jobs. No persistent process reuse.
Generation cost is0; normal/audit/trusted/whole-campaign costs remain separate.

A proposed upper bound is266 containers:240 normal (8×3×10 static-valid sources),
6 focused trusted branch checks, up to10 independent full audit jobs and10
validation-vector jobs. Full ceiling255 (240+5 trusted+10 audit), FP ceiling223
(210+3 trusted+10 audit). This is a design ceiling, **not** an executable manifest
or authorization. Exact future sources/images/task slots must be sealed after
implementation; actual skips leave unused slots nontransferable.

Trusted checks: complete FF/BF (two jobs), fused match, fused nonmatch, recoverable
FP-error→full-valid fallback, full-invalid rejection. F1 fallback stays in the same
candidate's disposable worker with a fresh namespace and remaining original10s
deadline. Full validity is never weakened. Timeout/OOM/process/cleanup/transport
uncertainty cannot trigger an automatic retry or pretend fitness; stop the arm
and report incomplete measurements. Unsupported fallback paths fail closed.

## Audits and preregistered metrics

Audit every behavioral-origin skip, including propagated C1 exact repeats.
Deduplicate audit work by exact source/representative/bank provenance, not by
claimed semantic equivalence. Independently full-evaluate each unique skipped
source once, and obtain validation vectors for each unique candidate/representative
source once. Link repeat/N events to those receipts explicitly; do not inflate
independent sample counts. Worst-case10 valid-source hashes bound those jobs.
Audit scores never enter a search DB or change the original replay trajectory.

Predefine:

- **Decision false match:** matched construction vectors but at least one
  differing selected-bin index on the fixed validation bank. Report mismatch
  counts and paired valid-state coverage; audit errors are not zero disagreement.
- **Fitness false match:** any complete per-family mean-bin difference beyond
  1e-9 (well below a single-bin aggregate step), even if combined fitness ties.
  Report raw scores/bin totals. This tolerance is audit classification only,
  never a change to packing fitness.
- **Missed improvement:** independently audited fitness exceeds global best at
  original skip position by1e-9. Also report selected-island opportunities,
  clustering/registration changes and subsequent prompt divergence separately.
- **Savings:** completed full evaluations and attempts versus concurrent Exact;
  direct behavioral skips, direct exact skips and propagated suspected skips
  separately. Invalid early rejection is not duplicate saving.
- **Cost:** pure FP, setup/fused lifecycle, full pure cost, source/index/DB costs,
  normal wall, audit wall and all-in wall. Report each timing block, paired
  differences, mean/SD/range, failures and uncaptured durations. No fewer-fulls
  equals faster-wall assumption; no historical Exact timing substitution.
- **Quality:** best/final incumbent, last accepted score, OR/Weibull means,
  per-island bests, unique clusters/program counts and real prompt sequence.

Report S2−S0 at each N under shared C1/F1, and each method−Exact. The bridge is
context only. Predeclare smallest N with zero observed decision/fitness false
matches and missed-global-best events, complete coverage/audits, and mean normal
wall no higher than concurrent Exact as a **candidate for further validation**.
If none qualifies, report no winner; do not tune thresholds using validation.
Island opportunities are an explicit unresolved evolution-risk metric, not
automatic proof of wrong fitness or permission to register skipped candidates.

**NO-GO to the unchanged540-call campaign.** Even a clean result on this known
pool does not prove equivalence/generalization or matched-budget live-search
quality. Freeze a later confirmation protocol and obtain finite approvals before
new model generation or candidate execution. No operation in this plan runs now.
