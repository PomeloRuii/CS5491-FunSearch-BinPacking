"""Candidate-independent reachable development states, state-policy-v2.0.

No legacy dataset imports, model source access, reserved audit input or workers.
The same trusted prefix iterator supplies collection, extraction and provenance.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct

import numpy as np

VERSION = 'state-policy-v2.0'
SEEDS = dict(split=54921000, construction=54921001, validation=54921002,
             audit_order=54921003, timing_order=54921004)
FAMILIES = ('OR3', 'Weibull 5k')
COLLECTORS = ('FF', 'BF', 'WF', 'random')
SIZES = (16, 64, 128)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def seed_for(*parts):
    return int(digest(list(parts))[:16], 16)


def input_identity(state):
    dtype = state['bins_dtype']
    if dtype not in ('int64', 'float64') or state['item_scalar_type'] not in ('int', 'float'):
        raise ValueError('Unsupported Linux interface types')
    bins = np.asarray(state['bins'], dtype='<' + ('i8' if dtype == 'int64' else 'f8'))
    indices = np.asarray(state['valid_bin_indices'], dtype='<i8')
    if bins.ndim != 1 or indices.shape != bins.shape or not len(bins):
        raise ValueError('Malformed feasible vector')
    if not np.all(np.isfinite(bins)) or not np.all(bins >= state['item']):
        raise ValueError('Invalid capacities')
    if not np.all(np.diff(indices) > 0) or indices[0] < 0:
        raise ValueError('Original feasible indices must be ascending')
    if type(state['item']).__name__ != state['item_scalar_type'] or state['item'] <= 0:
        raise ValueError('Scalar contract differs')
    # Original dtype/scalar are behavioral inputs too. Normalize byte order,
    # never decimal-round values or include collector/family labels in identity.
    header = (dtype + '|' + state['item_scalar_type'] + '|' + str(len(bins))).encode()
    scalar = struct.pack('<q' if state['item_scalar_type'] == 'int' else '<d', state['item'])
    return hashlib.sha256(header + scalar + bins.tobytes() + indices.tobytes()).hexdigest()


def region(item, capacity):
    if 4 * item <= capacity:
        return 0
    if 2 * item < capacity:
        return 1
    if 4 * item <= 3 * capacity:
        return 2
    return 3


def subdivision(groups):
    if set(groups) != set(FAMILIES):
        raise ValueError('Development family scope differs')
    result = {'construction': {}, 'validation': {}}
    for family, count in zip(FAMILIES, (8, 2)):
        ids = sorted(groups[family], key=lambda name: hashlib.sha256(
            f'{VERSION}|{SEEDS["split"]}|{family}|{name}'.encode()).hexdigest())
        if len(ids) != (12 if family == 'OR3' else 3):
            raise ValueError('Frozen development instance coverage differs')
        result['construction'][family] = ids[:count]
        result['validation'][family] = ids[count:]
    return result


def prefixes(groups, ids, seed, permuted=False):
    for family in FAMILIES:
        for name in ids[family]:
            instance = groups[family][name]
            capacity = instance['capacity']
            items = instance['items']
            if instance['num_items'] != len(items):
                raise ValueError('Incomplete trusted instance')
            order = np.arange(len(items))
            if permuted:
                np.random.default_rng(seed_for(seed, family, name, 'order')).shuffle(order)
            for collector in COLLECTORS:
                rng = np.random.default_rng(seed_for(seed, family, name, collector))
                bins = np.full(len(items), capacity,
                               dtype='int64' if type(capacity) is int else 'float64')
                for position, item_index in enumerate(order):
                    item = items[int(item_index)]
                    valid = np.nonzero((bins - item) >= 0)[0]
                    feasible = bins[valid]
                    if not len(valid):
                        raise ValueError('Unpackable development item')
                    occupied = feasible[feasible < capacity]
                    layout = ('A' if len(occupied) == 1 else
                              'B' if len(np.unique(occupied)) >= 2 else None)
                    if layout is not None and np.any(feasible == capacity):
                        origin = dict(family=family, instance_id=name, collector=collector,
                                      seed=seed, permuted=permuted, item_index=position,
                                      original_item_index=int(item_index))
                        state = dict(origin, item=item, bins=feasible,
                                     bins_dtype=bins.dtype.name, item_scalar_type=type(item).__name__,
                                     valid_bin_indices=valid, original_bin_count=len(bins))
                        identity = input_identity(state)
                        yield dict(origin, origin_id=digest(origin), state_id=identity,
                                   region=region(item, capacity), layout=layout,
                                   exact_fit=bool(np.any(feasible == item)),
                                   equal_capacity=bool(len(np.unique(feasible)) < len(feasible)),
                                   occupied_tie=bool(len(np.unique(occupied)) < len(occupied)),
                                   large=bool(2 * item >= capacity),
                                   boundary_flags=[f'{a}/{b}' for a, b in ((1,4),(1,3),(1,2),(2,3),(3,4))
                                                   if b * item == a * capacity]), state
                    if collector == 'FF':
                        selected = 0
                    elif collector == 'BF':
                        selected = int(np.argmin(feasible))
                    elif collector == 'WF':
                        selected = int(np.argmax(feasible))
                    else:
                        selected = int(rng.integers(len(valid)))
                    bins[int(valid[selected])] -= item


def candidates(groups, ids, seed, permuted=False, exclude=()):
    excluded = set(exclude); unique = {}; occurrences = Counter()
    for meta, _ in prefixes(groups, ids, seed, permuted):
        occurrences[(meta['family'], meta['region'], meta['layout'])] += 1
        if meta['state_id'] in excluded:
            continue
        # Origin representative independent of iteration labels; input identity
        # is the primary uniqueness key, origin identity is provenance only.
        old = unique.get(meta['state_id'])
        if old is None or meta['origin_id'] < old['origin_id']:
            unique[meta['state_id']] = meta
    return list(unique.values()), occurrences


def select(pool, size):
    cells = defaultdict(list)
    for meta in pool:
        cells[(meta['family'], meta['region'], meta['layout'])].append(meta)
    for rows in cells.values():
        rows.sort(key=lambda row: row['state_id'])
    available = {family: {feature: any(m['family'] == family and m[feature] for m in pool)
                          for feature in ('exact_fit', 'equal_capacity')}
                 for family in FAMILIES}
    selected = []; used = set(); transfers = []; gaps = []
    for family in FAMILIES:
        for reg in range(4):
            for layout in ('A', 'B'):
                if not cells[(family, reg, layout)]:
                    gaps.append(dict(family=family, region=reg, layout=layout, support='absent'))
    # Each round adds 8/family, giving exactly nested 16/64/128 prefixes.
    for round_index in range(size // 16):
        for reg in range(4):
            for layout in ('A', 'B'):
                for family in FAMILIES:
                    requested = (family, reg, layout)
                    options = [m for m in cells[requested] if m['state_id'] not in used]
                    actual = requested
                    if not options:
                        for alt in range(4):
                            alternate = (family, alt, layout)
                            options = [m for m in cells[alternate] if m['state_id'] not in used]
                            if options:
                                actual = alternate
                                break
                    if not options:
                        return selected, dict(supported=False, reason='Unique same-family/layout support exhausted',
                                              gaps=gaps, redistribution=transfers, available=available)
                    existing = [m for m in selected if m['family'] == family]
                    need_fit = available[family]['exact_fit'] and not any(m['exact_fit'] for m in existing)
                    need_tie = available[family]['equal_capacity'] and not any(m['equal_capacity'] for m in existing)
                    # Only candidate-independent features guide guard satisfaction.
                    chosen = min(options, key=lambda m: (-int(need_fit and m['exact_fit']),
                                                        -int(need_tie and m['equal_capacity']), m['state_id']))
                    selected.append(chosen); used.add(chosen['state_id'])
                    if actual != requested:
                        transfers.append(dict(position=len(selected), round=round_index,
                                              requested=list(requested), actual=list(actual)))
    return selected, dict(supported=True, gaps=gaps, redistribution=transfers, available=available)


def coverage(selected, support, expected_size=None):
    counts = Counter((m['family'], m['region'], m['layout']) for m in selected)
    guards = {}
    for family in FAMILIES:
        rows = [m for m in selected if m['family'] == family]
        guards[family] = dict(states=len(rows), large=sum(m['large'] for m in rows),
                              configurations=sorted({m['layout'] for m in rows}),
                              exact_fit=sum(m['exact_fit'] for m in rows),
                              equal_capacity=sum(m['equal_capacity'] for m in rows))
    ok = (support['supported'] and (expected_size is None or len(selected) == expected_size)
          and len({m['state_id'] for m in selected}) == len(selected)
          and all(g['large'] >= 2 and g['configurations'] == ['A', 'B']
                  and (not support['available'][family]['exact_fit'] or g['exact_fit'] > 0)
                  and (not support['available'][family]['equal_capacity'] or g['equal_capacity'] > 0)
                  for family, g in guards.items()))
    return dict(behavioral_skipping_supported=ok, unique_inputs=len({m['state_id'] for m in selected}),
                guards=guards, cells=[dict(family=k[0], region=k[1], layout=k[2], count=v)
                                      for k, v in sorted(counts.items())])


def extract(groups, ids, seed, selected, permuted=False):
    wanted = {m['origin_id']: m for m in selected}; found = {}
    for meta, state in prefixes(groups, ids, seed, permuted):
        if meta['origin_id'] in wanted:
            if meta != wanted[meta['origin_id']]:
                raise RuntimeError('Reachability/identity changed during extraction')
            row = dict(state, **{k: v for k, v in meta.items() if k not in state})
            row['bins'] = state['bins'].tolist(); row['valid_bin_indices'] = state['valid_bin_indices'].tolist()
            found[meta['origin_id']] = row
    if len(found) != len(wanted):
        raise RuntimeError('Missing reachable selected states')
    return [found[m['origin_id']] for m in selected]


def construct(groups, historical_states, historical_challenges):
    split = subdivision(groups)
    pool, occurrences = candidates(groups, split['construction'], SEEDS['construction'])
    selected, support = select(pool, 128)
    states = extract(groups, split['construction'], SEEDS['construction'], selected)
    # S0/challenges are approved development inputs, never old reserved audit values.
    excluded = {input_identity(s) for s in historical_states + historical_challenges + states}
    validation_pool, validation_occurrences = candidates(groups, split['validation'], SEEDS['validation'], True, excluded)
    validation_selected, validation_support = select(validation_pool, 256)
    validation_states = extract(groups, split['validation'], SEEDS['validation'], validation_selected, True)
    return dict(fingerprint=states), dict(validation=validation_states), dict(
        version=VERSION, seeds=SEEDS, subdivision=split,
        construction=dict(eligible_unique_inputs=len(pool), eligible_occurrences=sum(occurrences.values()),
                          support=support, sizes={str(n): coverage(selected[:n], support, n) for n in SIZES}),
        validation=dict(eligible_unique_inputs=len(validation_pool), eligible_occurrences=sum(validation_occurrences.values()),
                        support=validation_support, coverage=coverage(validation_selected, validation_support, 256),
                        excluded_input_count=len(excluded), overlap=0,
                        independence='Prospective access/selection separation on historically exposed development; not pristine held-out evidence'),
        historical_challenges_role='regression only; no model decisions used',
        validation_used_to_select_or_tune_construction=False)
