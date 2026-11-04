"""Deterministic instance partition and real-prefix states, development only."""
import hashlib
import json
from pathlib import Path
import numpy as np

import phase2_bootstrap
from phase2_bootstrap import ROOT
from development_data_v1 import canonical_hash as content_hash

PARTITION_SEED=5491
STATE_SEED=5492


def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(",",":")),encoding="utf-8")


def collect(groups,seed,maximum_per_family):
    """Reservoir sample nontrivial decisions on trusted FF/BF prefix traces."""
    output={}
    for family,instances in groups.items():
        rng=np.random.default_rng(seed+(0 if family=="OR3" else 100))
        pool=[];seen=0
        for instance_id,instance in sorted(instances.items()):
            for collector in ("FF","BF"):
                # Match the actual linux/amd64 worker, not Windows' native int
                # default or an unconditional float conversion.
                dtype='int64' if type(instance['capacity']) is int else 'float64'
                bins=np.full(instance["num_items"],instance["capacity"],dtype=dtype)
                for index,item in enumerate(instance["items"]):
                    valid=np.nonzero((bins-item)>=0)[0]; feasible=bins[valid]
                    # Require an actual FF/BF decision disagreement, not just many empty bins.
                    if len(feasible)>1 and feasible[0]>feasible.min():
                        seen+=1
                        slot=len(pool) if len(pool)<maximum_per_family else int(rng.integers(seen))
                        if slot<maximum_per_family:
                            state={"family":family,"instance_id":instance_id,"collector":collector,
                                   "item_index":index,"item":item,"bins":feasible.tolist(),
                                   "bins_dtype":bins.dtype.name,"item_scalar_type":type(item).__name__,
                                   "valid_bin_indices":valid.tolist(),"original_bin_count":len(bins)}
                            state["state_id"]=content_hash(state)
                            if slot==len(pool):pool.append(state)
                            else:pool[slot]=state
                    choice=0 if collector=="FF" else int(np.argmax(-feasible))
                    bins[valid[choice]]-=item
        if len(pool)<maximum_per_family:raise ValueError("Not enough nontrivial states: "+family)
        rng.shuffle(pool);output[family]={"eligible_seen":seen,"states":pool}
    states=[]
    families=sorted(output)
    for i in range(maximum_per_family):
        for family in families:states.append(output[family]["states"][i])
    return states,{family:{"eligible_seen":x["eligible_seen"],"selected":len(x["states"])} for family,x in output.items()}


def build(source_json):
    # Historical partition reconstruction is an explicit, separately scoped
    # operation. Normal imports never load the legacy literals or L1 bounds.
    datasets = json.loads(Path(source_json).read_text(encoding='utf-8'))
    destination=ROOT/"data";destination.mkdir(parents=True,exist_ok=True)
    sets={k:{} for k in ("development","audit","heldout")};ids={}
    for family,data in datasets.items():
        names=sorted(data)
        rng=np.random.default_rng(PARTITION_SEED+(0 if family=="OR3" else 1));rng.shuffle(names)
        ndev,naudit=(12,4) if family=="OR3" else (3,1)
        split={"development":names[:ndev],"audit":names[ndev:ndev+naudit],"heldout":names[ndev+naudit:]}
        ids[family]=split
        for role,names_for_role in split.items():
            sets[role][family]={name:data[name] for name in sorted(names_for_role)}
    fingerprint,fp_stats=collect(sets["development"],STATE_SEED,64)
    audit,audit_stats=collect(sets["audit"],STATE_SEED+1,128)
    assert not ({s["state_id"] for s in fingerprint}&{s["state_id"] for s in audit})
    state_bank={"fingerprint":fingerprint,"audit":audit}
    research={"development":sets["development"],"audit":sets["audit"]}
    dump(destination/"research_data.json",research)
    dump(destination/"heldout.json",sets["heldout"])
    dump(destination/"states.json",state_bank)
    manifest={"partition_seed":PARTITION_SEED,"state_seed":STATE_SEED,
              "source_dataset_hashes":{k:content_hash(v) for k,v in datasets.items()},
              "instance_ids":ids,"partition_hashes":{k:content_hash(v) for k,v in sets.items()},
              "fingerprint_sizes":[16,64,128],"fingerprint_state_ids":[s["state_id"] for s in fingerprint],
              "audit_state_ids":[s["state_id"] for s in audit],"fingerprint_selection":fp_stats,
              "audit_selection":audit_stats,"state_bank_sha256":content_hash(state_bank),
              "selection_rule":"Nested interleaved family-balanced prefixes of fixed reservoirs; real trusted FF/BF prefix decisions where FF/BF disagree",
              "dataset_note":"Existing upstream OR3 and Weibull 5k literals; original Weibull generation seed not supplied. No new instance values generated.",
              "historical_exposure":"OR3 FF/BF aggregate infrastructure results predate this retrospective split; do not claim a historically untouched OR heldout set",
              "heldout_used_for_states_or_replay":False,
              "files_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.glob('*.json') if p.name!='manifest.json'}}
    dump(destination/"manifest.json",manifest)
    print(json.dumps({"partitions":{role:{f:len(x) for f,x in group.items()} for role,group in sets.items()},
                      "fingerprint_states":len(fingerprint),"audit_states":len(audit),
                      "state_bank_sha256":manifest["state_bank_sha256"]},indent=2))


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description='Historical rebuild only; requires separately authorized source data')
    parser.add_argument('--source-json',type=Path,required=True)
    build(parser.parse_args().source_json)
