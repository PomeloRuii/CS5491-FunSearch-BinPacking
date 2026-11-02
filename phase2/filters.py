"""Post-validity, pre-evaluation filters retaining fully evaluated representatives only."""
import re
import math


def exact_source(source,name):
    code=source.strip()
    if code.startswith('```'):
        match=re.fullmatch(r'```(?:python|py)?\s*\n([\s\S]*?)\n```',code)
        if not match:raise ValueError('Malformed source fence')
        code=match.group(1)
    # Only transport/version naming is normalized; internal whitespace, comments,
    # expressions, annotations and identifiers remain byte-for-byte significant.
    needle='def '+name+'('
    if code.count(needle)!=1:raise ValueError('Unexpected function header')
    return code.replace(needle,'def priority(',1)


class Representatives:
    def __init__(self):
        self.sources={};self.behaviors={};self.all=[]

    def retain(self,candidate_id,source,fingerprint,scores):
        if not scores or any(type(x) not in (int,float) or not math.isfinite(x) for x in scores.values()):
            raise ValueError('Only complete finite evaluated representatives may be retained')
        rep={'candidate_id':candidate_id,'source':source,'fingerprint':fingerprint,'scores':scores,
             'score':sum(scores.values())/len(scores)}
        self.all.append(rep)
        self.sources.setdefault(source,rep)
        if fingerprint is not None:self.behaviors.setdefault(tuple(fingerprint),rep)
        return rep

    def exact(self,source):return self.sources.get(source)
    def behavioral(self,decisions):return self.behaviors.get(tuple(decisions))
    def wire(self):return [{'candidate_id':r['candidate_id'],'decisions':r['fingerprint']}
                          for r in self.behaviors.values()]
