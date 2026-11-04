# State Policy v2 — actual completed research comparison

**PASS: completed after the one explicitly authorized UTF-8 launch.** Manifest
`665043f41d3ac5cd12d8ee6ef82caff49d5f228194a93cfda16e9028051499c3`. Original UTF-8 approval bytes and prior GBK-failure evidence are unchanged.
Only `-X utf8` changed startup; all 173 sealed controls/four image identities matched.
Authority is closed: 241 used, 23 unused nontransferable slots.
No retry, reset, new model generation, final held-out evaluation or GitHub push.

## Main finding

S2 at 16/64/128 distinguished Candidate 10 from 8, fully evaluated 10 and retained it.
S0 at every N still skipped 10. Independent new 256-state validation found 22
selected-bin disagreements for 10/8 and different complete fitness. All S2 skips
had zero observed validation-decision or per-family score disagreements in this
pool. S2 therefore paid one more successful full evaluation per arm, preserving
five successful full-evaluation savings versus Exact instead of S0's six.
S2 was slower than S0 under shared controls, while all S2 settings had lower normal
wall time than their concurrent Exact control. These are observed fixed-pool
tradeoffs, not proof of generalized acceleration/equivalence or reduced LLM calls.

## Actual counts and normal wall times

Counts are per arm/block; times are three-repeat means/sample SD. One pool, not
three independent model runs. All settings have 6 static and1 runtime rejection
per block; source 5 is never repaired or registered.

| Setting | Containers | Full attempted/completed | Direct exact / direct behavioral / propagated | Mean wall ±SD | Lower wall vs Exact |
| --- | ---: | ---: | ---: | ---: | ---: |
| exact_c1 | 9 | 9/8 | 1/0/0 | 15.275489 ± 0.211082s | 0.000% |
| s0_n16_c1_f1 | 9 | 3/2 | 0/6/1 | 12.867453 ± 0.141475s | 15.764% |
| s0_n64_c1_f1 | 9 | 3/2 | 0/6/1 | 12.794445 ± 0.082223s | 16.242% |
| s0_n128_c1_f1 | 9 | 3/2 | 0/6/1 | 12.777312 ± 0.037200s | 16.354% |
| s2_n16_c1_f1 | 9 | 4/3 | 0/5/1 | 13.211130 ± 0.075740s | 13.514% |
| s2_n64_c1_f1 | 9 | 4/3 | 0/5/1 | 13.143197 ± 0.043051s | 13.959% |
| s2_n128_c1_f1 | 9 | 4/3 | 0/5/1 | 13.224019 ± 0.056360s | 13.430% |
| bridge_s0_n16_c0_f0 | 10 | 2/2 | 0/7/0 | 14.047738 ± 0.048112s | 8.037% |

All three actual blocks (prescribed seeded order, reverse, four-position rotation):

| Setting | Block1 | Block2 | Block3 | Range |
| --- | ---: | ---: | ---: | --- |
| exact_c1 | 15.490588s | 15.068667s | 15.267212s | 15.068667–15.490588s |
| s0_n16_c1_f1 | 12.832514s | 12.746721s | 13.023125s | 12.746721–13.023125s |
| s0_n64_c1_f1 | 12.888582s | 12.736686s | 12.758066s | 12.736686–12.888582s |
| s0_n128_c1_f1 | 12.814013s | 12.739631s | 12.778292s | 12.739631–12.814013s |
| s2_n16_c1_f1 | 13.215098s | 13.133484s | 13.284808s | 13.133484–13.284808s |
| s2_n64_c1_f1 | 13.109634s | 13.128220s | 13.191736s | 13.109634–13.191736s |
| s2_n128_c1_f1 | 13.212925s | 13.174031s | 13.285101s | 13.174031–13.285101s |
| bridge_s0_n16_c0_f0 | 14.103228s | 14.017665s | 14.022320s | 14.017665–14.103228s |

Paired S2−S0 contrasts isolate the bank policy with shared C1/F1:

| N | Block1 Δ | Block2 Δ | Block3 Δ | Mean Δ ±SD | Relative mean overhead |
| --- | ---: | ---: | ---: | ---: | ---: |
| 16 | 0.382585s | 0.386763s | 0.261683s | 0.343677 ± 0.071039s | 2.671% |
| 64 | 0.221052s | 0.391534s | 0.433670s | 0.348752 ± 0.112581s | 2.726% |
| 128 | 0.398912s | 0.434400s | 0.506809s | 0.446707 ± 0.054991s | 3.496% |

Absolute/relative per-block differences versus concurrent Exact are in
paired_differences.csv, not derived from historical timings. The architecture's
earlier 7.48% result remains a separate historical observation and is not pooled.
The historical-method bridge uses current instrumentation; C0/F0 together differ
from C1/F1, so it is not an isolated C1 or F1 timing ablation.

## Filtering costs and lifecycle overhead

Per-block mean component seconds; successful pure work excludes unmeasured failed
pure work. Failed phases still contribute to measured phase/lifecycle/normal wall.

| Setting | Lifecycle | FP phase | Successful pure FP | Full phase | Successful pure full | Docker create / cleanup |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| exact_c1 | 15.046696 | 0.000000 | 0.000000 | 4.162818 | 3.726380 | 1.804060/2.633716 |
| s0_n16_c1_f1 | 12.714757 | 0.435731 | 0.006139 | 0.875170 | 0.872883 | 1.819785/2.645048 |
| s0_n64_c1_f1 | 12.641362 | 0.450320 | 0.022954 | 0.869821 | 0.867455 | 1.803447/2.638828 |
| s0_n128_c1_f1 | 12.626156 | 0.462729 | 0.043895 | 0.856935 | 0.854680 | 1.803936/2.633582 |
| s2_n16_c1_f1 | 13.050835 | 0.445164 | 0.006318 | 1.303049 | 1.300108 | 1.816724/2.642228 |
| s2_n64_c1_f1 | 12.988204 | 0.447229 | 0.022248 | 1.287824 | 1.284870 | 1.804909/2.627923 |
| s2_n128_c1_f1 | 13.061974 | 0.476027 | 0.043673 | 1.291469 | 1.288569 | 1.806565/2.626766 |
| bridge_s0_n16_c0_f0 | 13.891527 | 0.472068 | 0.006813 | 0.854252 | 0.852864 | 2.005180/2.929512 |

Normal arm windows total **322.022347s**. Complete
controller wall is **390.297507s**, including
trusted gate, image/runner setup within the controller, all normal arms/history
barriers and independent audits. The residual outside normal windows is
68.275160s; it is not all audit cost.
Audit 16-worker lifecycle is **24.971064s**,
successful full pure work 3.774240s and
validation pure work 0.086758s.

The sealed controller does **not** have a dedicated monotonic timer for complete
audit host wall, trusted-gate wall or each post-loop history barrier. These are
not invented after the fact: audit lifecycle is a lower bound to complete audit
cost, and all-in wall includes the omitted components. Do not allocate shared
audits arbitrarily to arms or claim audit-inclusive per-arm speedups. Startup-ready
times overlap lifecycle; phase/pure/lifecycle values are nested, not additive.
Observer hooks are included in timings, not subtracted. Container lifecycle still
dominates the milliseconds of successful pure fingerprint work.

## Independent audit and quality

All **138 behavioral-origin skip events** were covered by **8 independent unique-source full audits and 8 validation-vector tasks**. Source 15 shares source 14's exact bytes and audit receipts; it is not an extra independent execution. The six unique source/representative pairs recur across N/blocks. All events have complete audit coverage, and audit scores never enter normal search DBs.

| Setting | Skip events over 3 blocks | Decision / fitness false-match events | Missed global best | Selected-island opportunities |
| --- | ---: | ---: | ---: | ---: |
| exact_c1 | 0 | 0/0 | 0 | 0 |
| s0_n16_c1_f1 | 21 | 3/3 | 0 | 6 |
| s0_n64_c1_f1 | 21 | 3/3 | 0 | 6 |
| s0_n128_c1_f1 | 21 | 3/3 | 0 | 6 |
| s2_n16_c1_f1 | 18 | 0/0 | 0 | 6 |
| s2_n64_c1_f1 | 18 | 0/0 | 0 | 6 |
| s2_n128_c1_f1 | 18 | 0/0 | 0 | 6 |
| bridge_s0_n16_c0_f0 | 21 | 3/3 | 0 | 6 |

False-match events are repeats of **one unique pair,10→8**, not independent
collision discoveries. Candidate 10 has OR3 mean 492.916667/Weibull 4806,
fitness -2649.4583333333335;8 has 500/5000,fitness -2750. Their 22/256 validation
disagreements (8.59375%) are outside every construction bank and come from the
new frozen diagnostic bank, not the six known boundary challenges or old reserved
audit states. Source10 improves its matched representative by 100.541667 fitness,
but cannot improve the already BF-quality global incumbent. S2 does not skip 10,
so that pair is correctly absent from S2's skip-audit population.

BF-quality sources 2/3/13/14 (15 exact alias of 14) have equal observed per-family
scores and identical selected-bin vectors on these 256 states. This does not prove
identical 21000-call packing trajectories or functional equivalence; full decision
traces were not recorded. validation_pair_matrix.csv exposes every measured pair.

All settings retain best/final database incumbent **-1142.5416666666665**, with
OR3 mean212.41666666666666 and Weibull2072.6666666666665. Last accepted fitness
is a different quantity: Exact/S0/bridge end at-2750 (500/5000), S2 at
-2649.4583333333335 (492.916667/4806). Keeping global best does not establish
preserved live-search quality, particularly because the best program arrives 2nd.

## Registration, prompts, and unresolved island loss

| Setting | Registered source IDs | Real islands | Prompt-code differences vs Exact |
| --- | --- | --- | --- |
| exact_c1 | [2, 3, 8, 10, 12, 13, 14, 16] | [9, 4, 5, 0, 4, 3, 8, 1] | [] |
| s0_n16_c1_f1 | [2, 8] | [9, 5] | [12, 14] |
| s0_n64_c1_f1 | [2, 8] | [9, 5] | [12, 14] |
| s0_n128_c1_f1 | [2, 8] | [9, 5] | [12, 14] |
| s2_n16_c1_f1 | [2, 8, 10] | [9, 5, 0] | [12, 14] |
| s2_n64_c1_f1 | [2, 8, 10] | [9, 5, 0] | [12, 14] |
| s2_n128_c1_f1 | [2, 8, 10] | [9, 5, 0] | [12, 14] |
| bridge_s0_n16_c0_f0 | [2, 8] | [9, 5] | [12, 14] |

Every arm starts from the same independently owned original checkpoint and empty
caches; all24 history barriers pass and each setting repeats the same logical
trajectory across three blocks. Registration diverges from Exact when 3 is skipped.
S2 adds measured 10 compared with S0, but still suppresses BF-like 3/13 in their
selected islands. Independent scores identify those as island opportunities,
despite zero missed global-best improvements. These are opportunity comparisons
at the actual skip positions, not executed counterfactual descendants. The true
subsequent prompts come from the arm's own actual registrations; no audit fitness,
historical state or preferred island is injected. The fixed pool does not regenerate
descendants from those differing prompts, so this is not live multi-seed evolution.

## C1/F1 effects, separately from S2

C1 makes 15→14→2 an exact repeat of a terminal suspected skip in each C1 behavioral
arm; no independent score/registration is assigned. It removes one FP container
per arm relative to the C0 bridge, but avoids zero additional complete fitness
evaluations because the bridge also behaviorally skipped 15. Exact already skips 15
using 14's fully evaluated source. All propagated skips stay audited.

F1 tries full evaluation after 5's recoverable FP failure, using a fresh namespace
within the same worker/deadline. All 18 C1/F1 behavioral arms confirm the original
source 5 remains full-invalid; F0 bridge rejects during FP without that full attempt.
Complete valid full counts are unchanged by this validity correction. Thus counts
identify each mechanism, but the bridge's C0/F0→C1/F1 runtime difference is combined,
not an individual causal ablation. Primary S2−S0 comparisons keep C1/F1 fixed.

## Accounting, integrity and limitations

- containers: 241
- normal_containers: 219
- trusted_containers: 6
- audit_full_tasks: 8
- validation_vector_tasks: 8
- full_attempted: 109
- full_completed: 87
- full_invalid: 22
- fp_invocations: 203
- fp_completed: 181
- normal_static_rejections: 144
- normal_runtime_rejections: 24
- normal_registrations: 75
- normal_candidate_records: 384
- audit_events: 138
- all_cleanup_verified: True
- unused_nontransferable: 23

All 241 reservations have terminal receipts and verified cleanup; postflight finds
no campaign container. Observer create counts agree with authority counts. All 173
controls, four images, original approval bytes and initial failed-attempt
evidence remain unchanged. Authority is consumed/closed and unused 23 slots cannot
be transferred or resumed. There were no retries, no extra model calls, no main
540-call search, no final held-out values and no GitHub push. The original GBK
startup failure remains a separate zero-dispatch attempt, not a timing sample.
Source5's24 normal runtime rejections and the trusted invalid-full rejection are
genuine expected validity outcomes; no source is rewritten. There are no incomplete
arms or audit observations. Failed pure timing granularity remains unavailable as
described above, rather than represented as measured zero cost.

**Research conclusion:** S2 improves observed discrimination on this known pool at
the cost of one additional full evaluation and about 0.34–0.45s/arm versus S0;
both still save full work and normal wall versus concurrent Exact here. No larger
N improves discrimination in this pool. Under the predeclared smallest-qualifying-N
rule, S2 N16 is a candidate for later confirmation, not a statistically established
winner. Small timing differences among S2 sizes do not justify changing that rule.

**GO to report these bounded development results; NO-GO to the unchanged 540-call
campaign.** Before a matched-budget live experiment, independently confirm with
genuinely unseen sources under fresh finite approvals, address island/prompt
diversity loss, and predeclare size/protocol without tuning on final held-out data.
One previously inspected 16-source pool, three timing repeats, non-complete order
counterbalance and development inputs all historically exposed limit generalization.
The new 256-state bank provides prospective selection/access separation only,
not a pristine held-out test. S2 construction is post-hoc to the known blind spot,
and exact rational landmarks are not guaranteed. Finite fingerprints can still
collide; zero observed S2 failures is not proof of equivalence/quality preservation.
Ordinary Docker residual risks, missing original Weibull generation seed and
unknown historical connectivity count remain. Logged pilot remains 30 plus that
unresolved history; this experiment consumes zero LLM requests.

Public supporting artifacts are under results/state_policy_v2/. The public audit
table omits private dispatch-slot locators but retains source hashes and every
measured disagreement/opportunity. Primary task receipts remain private.

## Additional state-policy trajectory detail and unused slots

S2 versus S0 under the same N/C1/F1 registers only one additional program, 10,
into real island 0 in every block. Final per-island best-score arrays are equal,
while island 0 contains one additional program/cluster. **No subsequent prompt
metadata or code differs between S2 and S0 anywhere in this 16-source stream**;
their additional database content was not exposed by the prescribed remaining
prompt draws. Do not manufacture prompt novelty or claim this demonstrates a
new generation-feedback step. Both methods still differ from Exact.
See s2_s0_trajectory_comparison.csv and s2_s0_database_differences.json.

category_accounting.csv reconciles all worker phases. The 23 unused slots were
21 normal repeated-source slots and two ineligible source-5 audit slots. Historical
failed-attempt evidence remains preserved privately; it is not a timing sample.
