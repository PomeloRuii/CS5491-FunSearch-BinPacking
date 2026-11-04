"""Same acceptance/island/filter semantics, development-only initialization."""
import random
from time import perf_counter
import numpy as np
from .runner import bootstrap3
from replay3 import ScopedReplay
from filters import Representatives
from implementation import code_manipulation as cm, config
from implementation.programs_database import ProgramsDatabase
from trusted_cases import SPECIFICATION
from .protocol import DEV, read


class FusedReplayV1(ScopedReplay):
    def __init__(self,runner,mode,logger,seed=5491):
        if mode not in ('exact','behavioral'):raise ValueError('Only paired declared modes')
        self.runner,self.mode,self.size,self.architecture,self.log=runner,mode,16,'fused',logger
        random.seed(seed);np.random.seed(seed)
        self.template=cm.text_to_program(SPECIFICATION)
        self.database=ProgramsDatabase(config.ProgramsDatabaseConfig(),self.template,'priority')
        self.groups=runner.data['development'];self.states=read(DEV/'states.json')
        self.reps=Representatives();self.records=[];self.executions=[];self.seed_executions=[]
        self.counts={k:0 for k in ('candidates','static_rejections','runtime_rejections','full_attempted',
            'full_completed','exact_matches','behavioral_matches','skipped','registrations','blocked_generated')}
        self.best=None;self.final=None

    def register(self,candidate,parsed,prompt,candidate_id,record):
        started=perf_counter()
        outcome=super().register(candidate,parsed,prompt,candidate_id,record)
        if outcome['status']=='ok':self.runner.authority.accept(candidate_id,record)
        outcome['registration_and_acceptance_seconds']=perf_counter()-started
        return outcome
