# Method and scope

## Historical separate-worker comparison (unchanged)

The original Online Bin Packing evaluator filters feasible residual capacities,
calls `priority(item, bins)`, and selects the first `np.argmax` score. Fitness is
the equal mean of complete negative per-family mean-bin scores. Shared static
policy v2 and runtime `obp-validity-v1` apply to every comparison setting.
No packing objective, data split or fingerprint state bank was tuned in this run.

The authentic ordered pool contains16 Qwen requests in two waves of8. Wave1
uses genuine post-Slot12 database prompts. Four reviewed sources were evaluated;
three valid results registered in original islands, one was genuinely invalid.
Wave2 used reconstructed real database state and feedback. Its version2 prompts
included the newly evaluated ancestor. Every failure, duplicate and truncation
was retained; ten sources passed static policy, nine exact keys/eight ASTs among
those passes. No manually authored heuristic was substituted into this pool.

Standard, Exact and Behavioral16/64/128 replay the same16 records. Each arm
restores the original comparison checkpoint and empty representative caches.
Exact normalizes only transport fences and requested version header; comments,
local names and numeric spelling remain significant. A representative is kept
only after a complete valid full evaluation. Behavioral first applies that exact
check, then uses selected-bin decisions on nested fixed16/64/128 development
states. A fingerprint match is a suspected duplicate, not functional equivalence.
Skipped programs never receive independent fitness or database registration.

Two serial timing orders are Standard/B64/B128/B16/Exact and its reverse.
Logical trajectories matched in both repetitions; separate database histories,
authority use and cleanup were checked before advancing between blocks.
These are timing repetitions of one fixed pool, not independent research seeds.
The first Standard observation had greater startup time; it is retained.

Every behavioral skip was audited after normal timing, independently of search
state. There were42 block-level skip events,21 unique source/representative/N
checks,21 independent full development evaluations and27 reserved256-state
vectors. Identical repeat events reference those independent receipts; there
were not42 independent full audit runs. Audit results never update search DBs.

Candidate10 matched the seed-like representative at every fingerprint size but
measured fitness-2649.458333 rather than-2750. Reserved audit vectors also matched;
full development fitness exposed the discrepancy. All three N values therefore
had a false match, although no current-best improvement was missed here.
Candidates2/3/13/14/15 had equal measured Best Fit group means and equal queried
development/reserved decisions. Full21000-call bin-choice traces were not logged,
so equivalence of their complete trajectories is not established.

Behavioral saved six successful full evaluations versus Exact per block, while
all ten fingerprint tasks cost about12.8–12.9s in worker lifecycles. Pure
fingerprinting was milliseconds, but disposable container overhead outweighed
the full-evaluation savings. Source5 was rejected during fingerprint validity:
one further avoided full attempt is a validity rejection, not a duplicate saving.
Normal, audit, generation, intermediate learning and timing-repeat costs are
reported separately. Failed pure durations are missing measurements, not zero.

The live multi-seed matched-budget campaign remains unrun. The fixed pool cannot
establish that each arm would generate the same descendants, fewer LLM calls,
or equal long-run search quality. Current evidence does not justify starting the
full540-call campaign unchanged. Larger fingerprint sizes showed no additional
discrimination here;16 is a parsimonious future candidate, not a statistically
selected winner. State coverage and end-to-end cost require further declared
development work before a main protocol is frozen.

## Separately versioned fused follow-up and cache audit

Recovery v1.2 replays the same pool with one disposable candidate worker for
fingerprinting plus conditional full evaluation. It uses fresh concurrent Exact
controls, not historical timing substitution. Means are 15.778s Exact and 14.598s
Fused16 across two reversed blocks; this is a 7.48% pilot normal-wall reduction,
not a general claim. Full completions are eight versus two per block.

Static → Exact → behavioral → full ordering is implemented, but only fully
evaluated representatives enter the measured exact cache. Source 14 is a
behavioral skip; identical source 15 therefore still fingerprints, contributing
to seven behavioral skips and ten Fused containers versus nine Exact containers.
An all-terminal-source index is a proposed future version, not the measured method.

Best fitness equality does not imply preserved island/search behavior: Exact
registers eight sources, Fused two; subsequent prompts differ. Candidate 10's
score-changing collision remains. Six boundary disagreements are development
diagnostics, not independent confirmation. Concurrent Exact outcomes identify
selected-island opportunities for skipped 3 and 13, without a missed global best;
no such scores are inserted into Fused databases.

See docs/FUSED_V12_MEASURED_RESULTS.md, docs/FILTER_ORDER_AUDIT.md and
docs/NEXT_STATE_POLICY_V2.md. Existing banks and outcomes are unchanged; no new
method or main search is authorized by these documents.

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
[the full report](docs/STATE_POLICY_V2_RESULTS.md) and exported scalar tables. The original negative results and historical design
remain preserved. Next: one bounded live-feedback Pilot, then a separately approved
540-call protocol if its pass criteria are met; neither has run.
