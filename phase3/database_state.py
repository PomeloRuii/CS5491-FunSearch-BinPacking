"""JSON checkpoint of actual upstream islands, clusters and RNG; never pickle."""
import random
import time
import copy
import numpy as np
import bootstrap3
from common import digest
from implementation import code_manipulation as cm, config
from implementation.programs_database import ProgramsDatabase, Cluster
from trusted_cases import SPECIFICATION

OWNERSHIP_VERSION = 'checkpoint-owned-json-v2'

def snapshot(database):
    state=np.random.get_state()
    islands=[]
    for island in database._islands:
        clusters=[]
        for signature,cluster in island._clusters.items():
            clusters.append({'signature':list(signature),'score':cluster.score,
                'programs':[str(p) for p in cluster._programs],'lengths':list(cluster._lengths)})
        islands.append({'num_programs':island._num_programs,'clusters':clusters})
    value={'schema':'upstream-islands-json-v1','islands':islands,
        'config':__import__('dataclasses').asdict(database._config),
        'best_scores':database._best_score_per_island,
        'best_programs':[str(p) if p else None for p in database._best_program_per_island],
        'best_scores_per_test':database._best_scores_per_test_per_island,
        'reset_age_seconds':max(0,time.time()-database._last_reset_time),
        'numpy_rng':[state[0],state[1].tolist(),state[2],state[3],state[4]],
        'python_rng':random.getstate(), 'proposal_fitness_unchanged':True}
    # Exported best-score lists/nested per-test dictionaries must not provide a
    # mutable back door into the live database either.
    return copy.deepcopy(value)

def restore(value):
    # One ownership boundary covers lengths, best scores, nested per-test score
    # dictionaries, config and RNG containers. Values/order/semantics unchanged.
    value=copy.deepcopy(value)
    if value['schema']!='upstream-islands-json-v1':raise ValueError('Unknown checkpoint schema')
    database=ProgramsDatabase(config.ProgramsDatabaseConfig(**value['config']),cm.text_to_program(SPECIFICATION),'priority')
    if len(value['islands'])!=len(database._islands):raise ValueError('Island count changed')
    for island, saved in zip(database._islands,value['islands']):
        for row in saved['clusters']:
            programs=[cm.text_to_function(p) for p in row['programs']]
            if not programs or any(p.name!='priority' for p in programs):raise ValueError('Invalid saved program')
            cluster=Cluster(row['score'],programs[0]);cluster._programs=programs;cluster._lengths=row['lengths']
            if cluster._lengths!=[len(str(p)) for p in programs]:raise ValueError('Program length metadata differs')
            island._clusters[tuple(row['signature'])]=cluster
        island._num_programs=saved['num_programs']
        if island._num_programs!=sum(len(c._programs) for c in island._clusters.values()):raise ValueError('Program counts differ')
    database._best_score_per_island=value['best_scores']
    database._best_program_per_island=[cm.text_to_function(p) if p else None for p in value['best_programs']]
    database._best_scores_per_test_per_island=value['best_scores_per_test']
    # Operator approval pauses do not consume the four-hour active search timer.
    database._last_reset_time=time.time()-value['reset_age_seconds']
    n=value['numpy_rng'];np.random.set_state((n[0],np.asarray(n[1],dtype=np.uint32),n[2],n[3],n[4]))
    def tuples(x):return tuple(tuples(v) for v in x) if isinstance(x,list) else x
    random.setstate(tuples(value['python_rng']))
    return database

