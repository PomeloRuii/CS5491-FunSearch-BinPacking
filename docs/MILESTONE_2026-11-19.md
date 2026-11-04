# CS5491 Milestone update — November 19, 2026

**Project:** Sample-Efficient FunSearch via Behavioral Fingerprinting for Online Bin Packing.

The first public research milestone is complete:
[GitHub repository](https://github.com/PomeloRuii/CS5491-FunSearch-BinPacking),
commit [bbc1855fd75c34633098224eb620eedea7a7c9eb](https://github.com/PomeloRuii/CS5491-FunSearch-BinPacking/commit/bbc1855fd75c34633098224eb620eedea7a7c9eb).
This draft is updated on November 3 using completed measurements. The next
section preserves the earlier separate-worker findings; the measured fused
follow-up and post-success audit below supersede its then-future work status.

We implemented Standard FunSearch, exact-source filtering and behavioral
fingerprints at16/64/128 states, preserving the upstream islands, feasible-bin
filtering, first-maximum `np.argmax` selection and original packing fitness.
A real16-candidate Qwen3.8 pool was generated in two waves with actual intervening
evaluation/database feedback. A fixed-pool comparison then completed two serial,
balanced timing blocks and independent audits:158 disposable Docker tasks,
verified source/task receipts, separate databases and cleanup throughout.

| Setting | Full attempted/completed per block | Mean normal wall time |
| --- | ---: | ---: |
| Standard | 10/9 | 18.590s |
| Exact-source | 9/8 | 15.055s |
| Behavioral16 | 2/2 | 16.346s |
| Behavioral64 | 2/2 | 16.339s |
| Behavioral128 | 2/2 | 16.474s |

Behavioral avoided six successful full evaluations relative to Exact per block,
but was **8.5–9.4% slower end to end**. At16 states, ten fingerprint containers
cost12.770s while successful pure fingerprint work totalled0.00684s. Container
lifecycle dominates. All settings retained best fitness-1142.541667 (OR3 mean
212.416667; Weibull mean2072.666667), matching trusted Best Fit family means.

All42 behavioral skip events were covered by21 independent source/N full audits
and27 reserved-state probes. Candidate10 matched candidate8 at every fingerprint
size yet measured-2649.458333 versus-2750; the256 reserved decisions also matched.
No current-best improvement was missed, but an early Best-Fit-quality incumbent
makes that a limited quality test. Equal fingerprints are not functional equivalence.

Development-only analysis identifies a structural sampling bias: retaining only
FF/BF-disagreement states excludes arrivals at least half the bin capacity.
Candidate10 changes ranking at two-thirds capacity. The development data contain
86 exact-boundary OR arrivals and584 above-boundary Weibull arrivals; all original
fingerprint sizes omit those regions. Increasing N under the same rule cannot
repair that coverage gap.

At that earlier stage we proposed a separately authorized, at-most45-task development experiment:
one fresh container per candidate with fingerprinting plus conditional full
evaluation, compared against Exact, and six development boundary challenges for
sources8/10. No process reuse across candidates is proposed. Before execution,
remove legacy host-wide dataset initialization and validate the narrow change.

Limitations remain: one fixed pool and two timing observations, no demonstrated
reduction in LLM calls or general speedup, post-hoc boundary regression design,
legacy host reference-data loading, retrospective OR exposure, missing Weibull
generator seed, ordinary Docker residual risks and incomplete fresh-machine
runtime reproduction. Both finite pilot grants are exhausted:30 logged requests
plus unresolved earlier connectivity; main0/540. Qwen3.8 is the documented change
from the original Qwen2.5-Coder plan. The unchanged main campaign is **no-go**.
New findings will enter the same GitHub repository through a reviewed incremental
clean export; no further publication or model execution is authorized here.

## November 3 measured update

Recovery v1.2 completed43 disposable Docker tasks and both paired blocks.
Exact took15.835/15.721s; Fused16 took14.581/14.614s, a7.48% mean reduction
with six fewer completed full evaluations per block. All histories, source seals
and cleanup checks passed. Best fitness stayed-1142.541667. Candidate10 still
falsely matches the original bank, while all six development boundary probes
distinguish it from candidate8. Historical negative separate-worker results remain
valid observations. These two timing repeats do not establish general superiority
or reduced LLM calls. Next: development-only coverage mitigation/independent
validation; unchanged540-call campaign remains no-go. See the new measured report.

## Post-success method alignment and next research decision

The actual fused cache includes only fully evaluated sources. Candidate 14 was
behaviorally skipped, so identical source 15 still used a fingerprint container
and is included in the seven behavioral matches. This is a source-coverage
limitation relative to the intended two-stage filter, not reversed filter order.
The measured ten-versus-nine containers and 7.48% timing observation stay unchanged.

Global best equality conceals island opportunities: concurrent Exact scores for
skipped 3 and 13 exceed their Fused selected-island incumbents. This is post-hoc
opportunity analysis, not a simulated evolutionary result. Registration/prompt
differences remain an important unresolved research risk.

The new [state-policy proposal](NEXT_STATE_POLICY_V2.md) separates generic arrival/
configuration coverage, a terminal-source index and numerical fallback changes.
It compares all N against original banks and Exact using shared controls, freezes
development-side validation before source execution, and treats all previously
inspected challenges as diagnostics. No new execution or generation is authorized;
the unchanged 540-call campaign remains NO-GO.

## November 4: State Policy v2 measured follow-up

S2-N16 mean normal wall was 13.211s (sample SD 0.076s), versus concurrently
measured Exact C1 15.275s and S0-N16 C1/F1 12.867s. S2 completed three full
evaluations per arm, S0 two, Exact eight. S2 at all three N values distinguished
Candidate 10 from 8; S0 at all three sizes retained the false match. The prospective
development validation measured 22/256 decision disagreements for that pair.
All 138 behavioral-origin skip events were independently covered using eight
unique-source full audits and eight validation workers; S2 skips had zero observed
decision/fitness false matches. Island opportunities and database/prompt differences
from Exact remain. Same global best is not evidence of equivalent live-search quality.

The study completed 241 disposable tasks and three timing repeats of one known
16-source pool, not three independent live searches. S2 was 2.7–3.5% slower than
S0 and 13.4–14.0% lower in normal wall than concurrent Exact. Audit worker lifecycle
was 24.971s; complete audit host wall was not separately instrumented. All-in
controller wall was 390.298s. Do not claim audit-inclusive per-arm speedups.
No held-out evaluation or new LLM requests were made. The known-pool, post-hoc
state design and finite fingerprints limit generalization. See
[the full report](STATE_POLICY_V2_RESULTS.md) and exported scalar tables. The original negative results and historical design
remain preserved. Next: one bounded live-feedback Pilot, then a separately approved
540-call protocol if its pass criteria are met; neither has run.
