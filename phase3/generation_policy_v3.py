"""Versioned prompts and independent scheduled LLM seeds; no model calls or exec."""
from dataclasses import replace
import json
from pathlib import Path

import bootstrap3
from bootstrap3 import ROOT
from common import read, digest, file_hash
from generation3 import fixed_config
from interface import expected_name

POLICY_PATH = ROOT/'generation_policy_v3.json'

def policy():
    value = read(POLICY_PATH)
    if (value['model'] != fixed_config().model or value['digest'] != fixed_config().expected_digest
        or value['quantization'] != 'Q4_K_M' or value['max_attempts'] != 1
        or value['additional_call_allocation'] != 0 or value['main_dispatch_enabled'] is not False
        or value['seed_base']!=549100000 or value['seed_stream_stride']!=1000
        or value['pilot_stream_id']!=99 or value['reserved_feedback_slots']!=[11,12]
        or value['reserved_feedback_seeds']!=[549199011,549199012]):
        raise PermissionError('Policy identity, budget or main-dispatch guard differs')
    return value

def sampling_seed(stream_id, ordinal):
    value = policy()
    if (type(stream_id) is not int or type(ordinal) is not int or stream_id not in (0,1,2,99)
        or not 1 <= ordinal <= 60 or (stream_id == 99 and ordinal not in (11,12))):
        raise ValueError('Only declared main schedule or two reserved pilot ordinals')
    return value['seed_base'] + value['seed_stream_stride']*stream_id + ordinal

def feedback_config(slot):
    value = policy()
    if slot not in value['reserved_feedback_slots']:raise PermissionError('No additional pilot allocation')
    cfg = fixed_config()
    for name in ('model','temperature','top_p','max_tokens','reasoning_effort','max_attempts','request_timeout_seconds'):
        if getattr(cfg,name) != value[name]:raise PermissionError('Non-seed sampling control changed: '+name)
    return replace(cfg,seed=sampling_seed(value['pilot_stream_id'],slot))

def messages_for(prompt, verified_feedback):
    """Keep original DB code verbatim; instructions/real feedback are separate wrappers."""
    value = policy();name = expected_name(prompt)
    if not isinstance(verified_feedback,dict) or not verified_feedback.get('verified_real_model_feedback'):
        raise PermissionError('Real evaluated/registered model feedback required')
    system = (
        'Improve a numerical online-bin-packing heuristic. The optimization objective is to '
        'minimize bins used: maximize the negative mean used-bin count in each development '
        'family, then the equal mean of the complete family scores. Preserve this objective. '
        'Each positive arriving item sees only feasible residual capacities: '
        'valid_bin_indices = np.nonzero((bins - item) >= 0)[0], followed by '
        'priority(item, bins[valid_bin_indices]). Empty unused bins are included. '
        'Return a one-dimensional finite real NumPy score array in the same length/order. '
        'The original packer chooses valid_bin_indices[np.argmax(scores)] and the first '
        'maximum wins ties. Return scores, never a chosen index or a packing. '
        'Seek a substantively different, potentially better decision rule from supplied '
        'versions; copying, renaming locals, constant score shifts or positive scaling '
        'alone is not a meaningful improvement. Consider how item size and residual space '
        'interact to reduce future bin openings. No claim of novelty or improvement is '
        'assumed: unchanged/worse candidates are still recorded. '
        'NumPy is already imported as np. Use direct numerical np functions, ordinary '
        'arithmetic, local variables, slices, comparisons, np.where and if/else. '
        'Use np.asarray(..., dtype=float), np.max(...) or np.where(...) instead of ndarray '
        'methods or subscript assignment. No imports, helpers, input mutation, randomness, '
        'file/network/process access or calls to previous versions. '
        'Return exactly one complete function with the requested signature, concise '
        f'numerical code (target at most {value["soft_maximum_code_lines"]} lines), '
        'no comments, docstrings, reasoning, Markdown or prose. End with a score-array return.'
    )
    feedback = {key:verified_feedback[key] for key in (
        'candidate_id','source_sha256','evaluated_island_id','score','scores_per_group',
        'selected_next_island_id','feedback_receipt_sha256')}
    user = (
        'ACTUAL UPSTREAM DATABASE PROMPT (verbatim; no inserted or invented versions):\n'
        + prompt.code
        + '\n\nMOST RECENT ACTUAL AUTHORIZED MODEL EVALUATION:\n'
        + json.dumps(feedback,sort_keys=True,allow_nan=False)
        + '\nThis receipt belongs to the stated candidate/island. It is not an invented '
        'score for other prompt functions. The next island is the upstream database selection. '
        'Improve the final requested version using the objective above.\n'
        + f'def {name}(item: float, bins: np.ndarray) -> np.ndarray:\n'
        + 'Return the complete function only.'
    )
    return [{'role':'system','content':system},{'role':'user','content':user}]

def export_schedule(destination):
    value = policy()
    main = [{'run':run,'generation_ordinal':ordinal,'sampling_seed':sampling_seed(run,ordinal),
             'shared_at_matched_index_by':['standard','exact','behavioral']}
            for run in value['main_run_stream_ids'] for ordinal in range(1,61)]
    return {'policy_sha256':file_hash(POLICY_PATH),
        'pilot':[{'budget_slot':n,'sampling_seed':sampling_seed(99,n),'requires_real_feedback':True} for n in (11,12)],
        'main_seed_schedule_only':main,'main_generation_calls_authorized':0,
        'note':'The 180 distinct main indices are paired across three configurations, not an extra allocation.'}
