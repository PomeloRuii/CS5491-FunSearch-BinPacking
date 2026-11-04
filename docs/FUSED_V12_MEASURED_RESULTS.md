# Recovery v1.2 — completed paired Fused16 experiment

November 3, 2026. **PASS: authorized campaign completed, all43 tasks terminal and
cleaned up.** Approved manifest:
`4ba1da14bcdd1692ecf068bb41e30c7e3b701c03ad3f1e6c93d5b9243d323a7a`.
Execution used a private finite source-bound approval. No approval receipt is included in this public update.
All100 sealed files, source/data bindings and pinned images verified before
execution and all100 file seals still match afterward. No fixture timings or
historical Exact times enter the paired comparison below.

## Actual timing result

| Block | Order | Exact wall | Fused16 wall | Time saved | Lower wall vs Exact |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Exact → Fused16 | 15.834999s | 14.581414s | 1.253586s | 7.9165% |
| 2 | Fused16 → Exact | 15.721495s | 14.614147s | 1.107348s | 7.0435% |
| Mean | two serial observations | 15.778247s | 14.597780s | 1.180467s | 7.4816% |

Sample SD is0.080260s for Exact,0.023146s for Fused16 and0.103406s for paired
savings. Exact range15.721495–15.834999s; Fused16 range14.581414–14.614147s.
This is a measured **7.48% lower normal wall time in this fixed-pool pilot**,
not statistical superiority, a universal speedup, or reduced LLM-call usage.
Only two balanced timing observations of one16-candidate pool were collected.

Normal timing includes candidate parsing, host source/authority/filter/registration
work, snapshot/logging and all worker startup/transport/evaluation/cleanup. History
verification, trusted validation and boundary diagnostics lie outside that normal
window; their costs remain in complete campaign accounting. Initial restore and
post-loop diagnostic/verification costs follow the declared controller window.
Host observer overhead is included rather than subtracted from arm wall times.

## Counts and overhead

Per normal arm/block:

| Mode | Containers | Full attempted/completed/rejected | Match skips | Registrations |
| --- | ---: | ---: | ---: | ---: |
| Exact | 9 | 9 / 8 / 1 | 1 exact | 8 |
| Fused16 | 10 | 2 / 2 / 0 | 7 behavioral | 2 |

Both modes retain6 static rejections and1 runtime rejection per block. Source5
fails full validity in Exact and fingerprint validity in Fused16; it is never
repaired or registered. Fused therefore has7 fewer full attempts, including that
early validity failure, and **6 fewer completed full evaluations /6 additional
match skips relative to Exact**. Do not label all7 avoided attempts duplicate
savings. Candidate15 has an exact skip in Exact. In Fused,14 was behaviorally
skipped and not retained, so15 needs its own FP task; fused exact matches are0.

Totals: **43 containers =38 normal +3 trusted +2 model boundary**;23 full attempts,
21 complete and2 rejected full evaluations;25 FP invocations,23 complete and2
rejected FP computations. The normal64 candidate-arm records contain24 static
rejections,4 runtime rejections,20 registrations,2 exact skips and14 behavioral
skips. All counts include repeat arms explicitly, not43 different programs.

The three trusted checks passed before model tasks: complete unchanged Best Fit
fitness/15 instances/21,000 calls; matching fingerprint skips fitness; six-state
trusted probe returns expected decisions. These are not research discoveries.

| Per-block cost | Exact block1 / block2 | Fused16 block1 / block2 |
| --- | ---: | ---: |
| Worker lifecycle | 15.037872 /15.054126s | 13.905225 /13.942070s |
| Successful pure full evaluation | 3.704856 /3.701027s | 0.841535 /0.859634s |
| Fingerprint phase, including failed phase/setup | 0 /0s | 0.466863 /0.460065s |
| Successful pure fingerprint work | 0 /0s | 0.006789 /0.006629s |
| Docker create | 1.812598 /1.828298s | 2.017822 /2.030890s |
| Cleanup | 2.639398 /2.651916s | 2.950310 /2.938966s |

Fused is faster here **despite one additional container per arm**. It avoids a
second full worker for each FP nonmatch and reduces costly full work on matching
sources. It does not eliminate startup overhead: mean fused lifecycle13.923647s
still dominates its0.850584s successful pure full work and0.006709s pure FP work.
The FP phase0.463464s includes import/namespace/validation work, not only priority
calls. Fused lifecycle is counted once per combined task, never twice as FP+full.

All-task lifecycle total67.960890s; trusted lifecycle7.520092s; model boundary
lifecycle2.501506s. Trusted wall7.911508s; boundary wall2.530864s; complete campaign
wall73.407508s. The observer measured0.802509s inside audit hooks across the run.
The first trusted create took3.527563s (retained); normal creates were about0.2s.
Ready times are part of start/attach/wait and must not be added again. Pure failed
work is incomplete timing, not zero-cost work. Detailed lifecycle fields remain in the preserved private worker table; aggregate fields are exported in arm_measurements.csv.

There was no concurrent separate-container Behavioral arm in this campaign.
The historical separate-BF result (8.5–9.4% slower than Exact) remains unchanged
and is not pooled with the new timing observations. The13.879s accounting estimate
was never used as a measured value or timing control.

## Quality and real database trajectories

This is controlled replay of the same authentic16-source two-wave Qwen pool,
using `qwen3.8:27b-q4_K_M` generation artifacts. It is not a new live evolutionary
run or the formal matched-budget multi-seed campaign. The documented model change
from the submitted Qwen2.5-Coder plan remains a Proposal deviation.

Both modes retain identical best-so-far curves and final incumbent fitness
**-1142.5416666666665**, OR3 mean212.41666666666666 and Weibull mean2072.6666666666665.
Last accepted fitness is-2750 in both, a distinct quantity from final incumbent.
Every accepted full result covers all15 instances and21,000 priority calls.

Each arm starts from the identical original checkpoint and empty representative
caches. Exact registers IDs2/3/8/10/12/13/14/16 in islands9/4/5/0/4/3/8/1;
Fused registers only2/8 in islands9/5. Each setting repeats the same logical
trajectory across blocks. Cross-mode registration diverges at3, and actual
prompt metadata/code differs at candidates12/13/14. No skipped source receives
an independent score or database registration. All64 prompt/state transitions,
final states and unchanged initial dictionaries were independently checked from
actual receipts with AST/database operations after closure; no extra source ran.

The concurrent Exact arm exposes the unchanged false match10→8 in each block:
Candidate10 measured-2649.4583333333335 (OR3 mean492.916667, Weibull4806), versus
representative8's-2750 (500/5000). These are2 repeat events of one source pair,
not two independent collision discoveries. The difference would improve the
representative by100.541667 fitness, but not the already Best-Fit-quality incumbent.
No current-best improvement was missed; this is weak evidence for general quality
preservation because the best program arrives at position2.

Fourteen skip events were checked post hoc against concurrent Exact outcomes,
using its verified exact representative14 for identical source15. These are
cross-arm quality checks, **not new independent audit evaluations**. No additional
audit tasks were authorized or run. Matching fitness is not functional equivalence.

## Measured boundary diagnostics

The six challenges are predeclared development-derived trusted Worst-Fit prefix
states, constructed after the known failure: diagnostic regression, not an
independent validation set. Both approved model FP-only tasks ran once.
Numbers below are original bin indices, not positions in the filtered vector.

| Challenge | Family / instance | Region | Candidate8 | Candidate10 |
| --- | --- | --- | ---: | ---: |
| 1 | OR3 /u500_02 | exactly2/3 | 127 | 1 |
| 2 | OR3 /u500_05 | exactly2/3 | 28 | 4 |
| 3 | OR3 /u500_06 | exactly2/3 | 150 | 8 |
| 4 | Weibull /test_0 | above2/3 | 67 | 3 |
| 5 | Weibull /test_2 | above2/3 | 24 | 10 |
| 6 | Weibull /test_3 | above2/3 | 19 | 13 |

**6/6 selected-bin disagreements.** Candidate8 picks an unused maximum-capacity
bin on all six. Candidate10 picks a minimum feasible capacity on the three
above-boundary Weibull states, agreeing with the analytical ranking reversal.

At exact2/3, real arithmetic makes Candidate10's scores tie. The first feasible
OR indices are1/2/8, whereas its measured decisions are1/4/8. Challenge2 therefore
departs from the ideal constant-score first-argmax prediction under actual NumPy
evaluation. Raw score vectors/ULPs were not logged, so no numerical error magnitude
or complete decision trace is invented. No host-side model replica was evaluated.

This supports the structural diagnosis: the original FF/BF-disagreement sampler
excludes arrivals>=1/2, covering neither the2/3 tie nor reversal region. Increasing
16 to64/128 or using the old reserved256 collector cannot repair missing support.
The original fingerprint bank remains unchanged. Fusing lifecycle operations
**does not fix collisions**. Any stratified state-policy/fallback change remains
a separate future method with predeclared development validation and audits.

## Safety/provenance and next decision

All43 source/body/task/image identities, readonly/non-root/no-network/no-host-mount
configuration, resource limits, result coverage and terminal cleanup receipts were
verified. Both block barriers and final barrier passed; read-only postflight Docker
inspection found no containers. Authority is closed with43 used and2 unused,
nontransferable slots. No retry/reset or follow-on execution is permitted.

The host observer recorded no blocked operation, legacy dataset module or host
model/network request; guarded JSON reads were confined to sealed development,
control and authorization inputs. Sealed preflight inputs contain no held-out or
reserved raw values. Original checkpoints, datasets, earlier failed receipts and
all100 active source seals remain unchanged. Ordinary Docker shared-kernel,
controller, resource and score-integrity risks still exist; these results do not
certify arbitrary hostile Python isolation. No new Qwen requests or main calls
were made. Known logged Pilot remains30 plus unresolved earlier connectivity.

**GO** to report the observed architecture result and prepare/review an incremental
GitHub update. **NO-GO** to the unchanged540-call campaign or an untuned claim that
Fused16 preserves quality generally. Next research priority: freeze a development-
only stratified probe policy at16/64/128, use independent development-side
validation/audits, then seek a finite new authorization. Additional timing blocks
should be separately bounded and balanced, not silently added here.

Publish the new source correction/method and actual CSV/JSON findings alongside,
not over, historical negative results. Export no approvals, private controller
receipts/history, raw datasets/states, model-service logs or personal paths. The
public baseline remains`bbc1855fd75c34633098224eb620eedea7a7c9eb`; no push was made.

Public evidence: summary.json, paired_comparison.csv, arm_measurements.csv,
candidate_outcomes.csv, boundary_decisions.csv, trajectory_differences.csv and
quality_checks.csv under results/fused_v12. Raw task/authority receipts, detailed
worker table and receipt hash inventory remain private. The public export does
not pretend to supply those confidential inputs.

## Post-success interpretation (no new execution)

See [filter-order audit](FILTER_ORDER_AUDIT.md): exact matching precedes FP,
but only fully evaluated sources are indexed. Candidate 15 is included in the
seven behavioral matches because 14 was not retained. Do not retroactively
change measured counts. The proposed terminal-source index could remove one
fingerprint task per block, but would avoid no additional full evaluations;
its timing has not been measured.

Concurrent Exact results also expose selected-island opportunities for skipped
3 and 13 (four repeated events, two source/island opportunities). These do not
improve the global best, and are not an executed counterfactual or new independent
audits. Best/final fitness equality does not establish preserved search feedback.
