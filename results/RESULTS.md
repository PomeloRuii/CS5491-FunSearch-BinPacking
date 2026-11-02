# Measured two-wave controlled replay

| Configuration | Full attempted/completed per block | Match skips | FP tasks | Mean wall s | Range s | Extra wall vs Exact |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| standard | 10/9 | 0 | 0 | 18.590041 | 16.776374–20.403708 | +3.534769 s |
| exact | 9/8 | 1 | 0 | 15.055272 | 14.985150–15.125395 | +0.000000 s |
| behavioral-16 | 2/2 | 7 | 10 | 16.346234 | 16.345152–16.347317 | +1.290962 s |
| behavioral-64 | 2/2 | 7 | 10 | 16.339309 | 16.298112–16.380505 | +1.284036 s |
| behavioral-128 | 2/2 | 7 | 10 | 16.473904 | 16.444001–16.503806 | +1.418631 s |

All five settings retained best fitness -1142.5416666666665 (OR3 mean212.4166667, Weibull mean2072.6666667); last accepted fitness -2750. Behavioral saved six completed full evaluations versus Exact per block, but took8.5–9.4% longer. One further full attempt was avoided by rejecting source5 during fingerprint validity, not by a duplicate match.

Audit:42 skip events,21 unique source/N match checks,21 independent full evaluations and27 reserved vectors. Candidate10 is a score-changing false match at all three sizes despite zero disagreements on reserved256 states. No missed current-best improvement was observed. Equal sampled fingerprints are not functional equivalence.

This is one fixed authentic16-candidate pool, two timing blocks, not a live multi-seed search or proof of fewer LLM calls. Original standard first-block startup was slower; do not remove it or extrapolate statistical superiority. Main540 calls are not authorized.

Successful packing pure time, full lifecycle, fingerprint lifecycle, all raw timing repetitions and audit cost are in the CSV/JSON artifacts. Failed pure durations are missing, not measured zero. Audit wall72.540738s is outside normal-arm time. Complete campaign including supervisor checks:239.087397s.

Generation/learning costs remain separate. Wave2 had a preserved controller RNG incident before its second request; verified unused slots continued with caller-state preservation, no request retry. Both finite grants are exhausted;30 logged pilots exclude unknown earlier connectivity (at least two). No lifetime30/570 certification.
