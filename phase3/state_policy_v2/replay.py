"""Real upstream database lifecycle, with separate C1/F1 and state factors.

The only numerical candidate execution boundary is runner.run_task. Controllers
and offline recorded-result tests only parse source AST and register checked scores.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap3
from database_state import restore, snapshot
from replay3 import ScopedReplay
from replay import accepted_full
from filters import Representatives, exact_source
from static_policy import validate
from implementation import code_manipulation as cm
from trusted_cases import SPECIFICATION
from .states import digest
from .terminal_index import TerminalSources
from .worker_v2 import VERSION, valid_vector


def checked_terminal(record, task, states, groups):
    if record.get('cleanup_verified') is not True:
        raise RuntimeError('Cleanup uncertain')
    if record.get('status') == 'runtime_error':
        # Confirmed numerical validity rejection only. Timeouts/OOM/unknown
        # exceptions/transport errors never become a reusable terminal cache entry.
        errors = [m.get('error', {}) for m in record.get('worker_messages', []) if m.get('kind') == 'error']
        if errors and all(e.get('type') == 'ValueError' and e.get('message') in (
                'Priority scores must be finite real numbers under obp-validity-v1',
                'priority must return one score for each feasible bin.') for e in errors):
            return False
        raise RuntimeError('Unexpected worker exception: stop without retry')
    if record.get('status') != 'ok':
        raise RuntimeError('Resource/dispatch/protocol uncertainty')
    value = record['result']
    if (value.get('task') != task or value.get('worker_version') != VERSION
            or value.get('validity_policy') != 'obp-validity-v1'):
        raise RuntimeError('Task/version substitution')
    if task['action'] == 'full' and (value.get('fingerprint_valid') or value.get('fallback_used')):
        raise RuntimeError('Full-only task unexpectedly fingerprinted')
    if task['action'] == 'fingerprint' and (not value.get('fingerprint_valid') or value.get('fallback_used')
                                           or value.get('full_evaluation_performed')):
        raise RuntimeError('FP-only task requires a complete valid vector and no fitness/fallback')
    if not task['coverage_supported'] and value.get('fingerprint_valid'):
        raise RuntimeError('Unsupported coverage cannot authorize a behavioral skip')
    if value.get('fingerprint_valid'):
        if not states or not valid_vector(value, states):
            raise RuntimeError('Invalid fingerprint result')
        match = next((r['candidate_id'] for r in task['representatives'] if r['decisions'] == value['decisions']), None)
        if value.get('matched_representative_id') != match:
            raise RuntimeError('Worker/host match disagreement')
        if task['action'] == 'fused' and value.get('full_evaluation_performed') != (match is None):
            raise RuntimeError('Wrong fused branch')
    elif task['action'] == 'fused':
        if (task['fallback'] != 'F1' or not value.get('fallback_used')
                or value.get('matched_representative_id') is not None
                or value.get('decisions') is not None):
            raise RuntimeError('Unsupported fallback result')
    if value.get('full_evaluation_performed'):
        if not task['allow_full'] or not accepted_full(record, groups):
            raise RuntimeError('Incomplete or forbidden fitness')
    else:
        if any(k in value for k in ('score', 'scores_per_group', 'group_details')):
            raise RuntimeError('Skipped candidate has fabricated fitness')
        if task['action'] == 'full' or (task['action'] == 'fused' and value.get('matched_representative_id') is None):
            raise RuntimeError('Missing full evaluation')
    return True


class PolicyReplay(ScopedReplay):
    def __init__(self, runner, setting, logger, initial, states, bank_hash, coverage_supported):
        self.runner = runner; self.setting = deepcopy(setting); self.log = logger
        self.database = restore(initial)
        self.template = cm.text_to_program(SPECIFICATION)
        self.groups = runner.data['development']; self.records = []; self.executions = []
        self.states = states; self.reps = Representatives()
        self.context = dict(configuration=setting, state_bank_sha256=bank_hash,
                            image=runner.image, dataset=digest(self.groups), static_policy='shared-v2')
        self.terminal = TerminalSources(self.context)
        self.supported = coverage_supported
        self.best = max(self.database._best_score_per_island); self.final = self.best

    def register(self, candidate, parsed, prompt, candidate_id, record):
        outcome = super().register(candidate, parsed, prompt, candidate_id, record)
        if outcome['status'] == 'ok':
            self.runner.accept(candidate_id, record)
        return outcome

    def process(self, candidate, prompt, candidate_id):
        start = perf_counter(); name = candidate.response_metadata['expected_name']
        row = dict(candidate_id=candidate_id, island_id=int(prompt.island_id),
                   version_generated=prompt.version_generated, registered=False,
                   score=None, scores_per_group=None, matched_representative_id=None,
                   best_before=self.best, selected_island_best_before=self.database._best_score_per_island[prompt.island_id],
                   fingerprint=None, provenance=None, parse_seconds=0.0, filter_seconds=0.0)
        then = perf_counter()
        try:
            parsed, static = validate(candidate.text, name, candidate.finish_reason)
            row.update(static=static, parsed_body=parsed.body)
        except (ValueError, SyntaxError) as exc:
            row.update(status='static_rejected', reason=str(exc))
        else:
            row['parse_seconds'] = perf_counter()-then
            self.runner.check_candidate(candidate)
            key = exact_source(candidate.text, name)
            row['exact_source_key_sha256'] = hashlib.sha256(key.encode()).hexdigest()
            then = perf_counter(); rep = self.reps.exact(key)
            propagated = (self.terminal.exact_repeat(key, candidate_id, self.context)
                          if rep is None and self.setting['cache'] == 'C1' else None)
            row['filter_seconds'] += perf_counter()-then
            if rep:
                row.update(status='skipped_exact', matched_representative_id=rep['candidate_id'])
            elif propagated:
                row.update(status=propagated['status'], provenance=propagated['provenance'],
                           matched_representative_id=propagated['representative_id'], audit_required=True)
            else:
                action = 'fused' if self.setting['bank'] else 'full'
                record = self.runner.run_task(candidate, parsed, action, setting=self.setting,
                                               representatives=self.reps.wire(), coverage_supported=self.supported)
                self.executions.append(record)
                if not checked_terminal(record, record['bound_task'], self.states, self.groups):
                    row.update(status='runtime_rejected', reason='Complete validity required')
                else:
                    result = record['result']; fp = result.get('decisions') if result.get('fingerprint_valid') else None
                    row.update(fingerprint=fp, fallback_used=result.get('fallback_used', False))
                    if not result['full_evaluation_performed']:
                        if not self.supported:
                            raise RuntimeError('Unsupported state coverage skipped candidate')
                        match = self.reps.behavioral(fp)
                        if match is None or match['candidate_id'] != result['matched_representative_id']:
                            raise RuntimeError('Behavioral cache/match differs')
                        row.update(status='skipped_behavioral', matched_representative_id=match['candidate_id'],
                                   provenance=[candidate_id, match['candidate_id']], audit_required=True)
                        if self.setting['cache'] == 'C1':
                            self.terminal.retain_skip(key, candidate_id, match['candidate_id'], record)
                    else:
                        outcome = self.register(candidate, parsed, prompt, candidate_id, record)
                        if outcome['status'] != 'ok':
                            raise RuntimeError('Complete accepted result failed registration')
                        row.update(status='evaluated', evaluation=outcome, registered=True,
                                   score=outcome['score'], scores_per_group=outcome['scores_per_group'])
                        self.reps.retain(candidate_id, key, fp, deepcopy(outcome['scores_per_group']))
                        self.best = max(self.best, outcome['score']); self.final = outcome['score']
        row['parse_seconds'] = row['parse_seconds'] or perf_counter()-then
        row.update(best_after=self.best, processing_seconds=perf_counter()-start)
        if row['registered'] and row['status'] != 'evaluated':
            raise RuntimeError('Skipped/rejected candidate registered')
        self.records.append(row); self.log.emit('candidate_outcome', **row)
        return row
