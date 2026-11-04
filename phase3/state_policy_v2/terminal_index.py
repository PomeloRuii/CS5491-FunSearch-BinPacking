"""C1 v1: terminal behavioral decisions, separate from evaluated representatives."""
from copy import deepcopy
import hashlib
import json

VERSION = 'terminal-source-index-c1-v1'


class TerminalSources:
    def __init__(self, context):
        self.context = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
        self.entries = {}

    def retain_skip(self, source_key, candidate_id, representative_id, record):
        result = record.get('result', {})
        if (record.get('status') != 'ok' or record.get('cleanup_verified') is not True
                or result.get('full_evaluation_performed') is not False
                or result.get('matched_representative_id') != representative_id
                or result.get('fingerprint_valid') is not True
                or not result.get('decisions') or 'score' in result or 'scores_per_group' in result):
            raise ValueError('C1 requires a validated terminal skip, never uncertain/failed/full fitness')
        entry = dict(first_candidate_id=candidate_id, representative_id=representative_id,
                     provenance=[candidate_id, representative_id], suspected=True,
                     context=self.context, source_key_sha256=hashlib.sha256(source_key.encode()).hexdigest())
        self.entries.setdefault(source_key, entry)

    def exact_repeat(self, source_key, candidate_id, context):
        if hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest() != self.context:
            raise PermissionError('Terminal-source context changed')
        entry = self.entries.get(source_key)
        if entry is None:
            return None
        return dict(deepcopy(entry), candidate_id=candidate_id,
                    provenance=[candidate_id] + entry['provenance'],
                    status='exact_repeat_of_behavioral_skip', registered=False,
                    score=None, audit_required=True)
