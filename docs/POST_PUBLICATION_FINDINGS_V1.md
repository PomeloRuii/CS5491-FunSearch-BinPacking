# Development-only post-publication diagnosis v1

**Historical diagnosis, retained with its original observations.** Its then-
proposed experiment subsequently completed as Recovery v1.2; see
[measured follow-up](FUSED_V12_MEASURED_RESULTS.md). The accounting estimate
below is not a measurement, and the original state banks remain unchanged.

This adds analytical findings to the existing measured pilot. No Qwen function,
new container, full fitness run or model request was executed for this update.
Published original source/data-state hashes and results are unchanged.

## Structural sampling bias

The FF/BF collectors are Any-Fit: before opening a new bin they use a feasible
occupied bin. At most one occupied bin can have residual capacity at least C/2.
Creating a second would require an item at most C/2, which would fit the first.
Therefore items at least C/2 cannot yield the FF/BF disagreement required by the
original state-selection predicate. Both normal and reserved collectors share
that restriction. Increasing the number of states cannot repair its support.

For Candidate10, let r=bins-item, M=max(r), x=r/M and q=item/(item+M). Its score
is q/2+x*(1-3q/2) in real arithmetic. An available empty bin implies M=C-item,
so ranking changes at item=2*C/3. The development inputs contain86 exact-boundary
OR arrivals and584 above-boundary Weibull arrivals. All16/64/128 fingerprints
exclude even the wider item>=C/2 region. Original audit receipts record the same
reserved decisions, despite different full development fitness. No reserved raw
states or final held-out values were read to construct this analysis/challenges.

Ideal boundary scores tie at1/3; floating rounding and first-maximum selection
still require actual isolated traces. New six-state regression inputs use real
original-order development prefixes under trusted Worst Fit, not a claimed model
trajectory. They were constructed after the known failure and are not independent
test evidence. Their raw values remain private; no model was run on them.

## Cost and next controlled experiment

At16 states, successful pure FP is0.006842s versus12.769564s for ten FP worker
lifecycles. Reusing the same candidate's fresh disposable container for FP plus
conditional full evaluation gives a counterfactual13.878688s+unknown overhead,
versus observed Exact15.055272s. This is not a measured fused speedup. Earlier
trusted-stream fused16 averaged24.666661s versus Exact24.203657s, so success is
not assumed. No process/module state may cross candidates.

The proposal caps a future separately authorized study at45 containers:3 trusted
checks,40 model tasks for two paired Exact/fused16 timing blocks, and2 FP-only
boundary jobs for sources8/10. It keeps old states for the architecture comparison
and separates new boundary diagnostics. Exact code/image/data seals do not yet
exist for the new path; the current fused lock stays closed. Before execution,
replace the legacy host-wide data import with a versioned development-only reader
and verify imports do not touch the legacy/held-out files. No broad rebuild of
the unchanged runtime is needed for that host correction.

A proposed state policy v2 would retain16/64/128 sizes but stratify across both
families, Any-Fit disagreements, trusted Worst-Fit prefixes and large/boundary/
exact-fit/tie states. It must be frozen before new evaluation, validated using
separate development-side inputs and audited independently. Invalid/uncovered
fingerprints must not manufacture a score; any full fallback must be declared
and budgeted. This new policy is not implemented or part of the architecture
comparison, and neither audit findings nor skipped scores are injected into the
old search. No functional-equivalence or general runtime/LLM-call claim follows.

See the November19 Milestone update, scalar analysis CSV/JSON and inactive bounded
protocol added alongside this note. Main540 remains unstarted, both finite pilot
grants remain exhausted, and any new publication/execution requires its own
explicit scope review. This delta does not republish unchanged release artifacts.
