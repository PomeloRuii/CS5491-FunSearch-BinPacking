"""Focused offline authorization/dependency tests, not experimental results."""
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from two_wave_guards import TwoWaveBudget,feedback_condition,same_database,ROOT,PROJECT
from common import write,read,file_hash,digest


class TwoWaveTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'test_tmp').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test_tmp');self.base=Path(self.temp.name)
        self.request=self.base/'request.json';self.approval=self.base/'approval.json'
        self.payloads=[{'seed':549199013+i,'unit_only':True} for i in range(8)]
        self.plan={'max_new_generation_requests':16,'per_wave_cap':8,'per_slot_max_attempts':1,
            'candidate_execution_authorized':False,'main_calls':0,'control_sha256':{},
            'wave1':{'draws':[{'payload_sha256':digest(p)} for p in self.payloads]}}
        write(self.request,self.plan);self.approve()

    def tearDown(self):self.temp.cleanup()

    def approve(self,**changes):
        write(self.approval,{'approved':True,'kind':'finite_two_wave_generation_only',
            'manifest_sha256':file_hash(self.request),'user_authorization_verbatim':'UNIT FIXTURE, NOT A REAL GRANT',
            'recorded_at_utc':'unit-only','conditional_wave2_acknowledged':True,**changes})

    def budget(self):return TwoWaveBudget(self.request,self.approval,self.base/'state')

    def test_missing_old_inactive_and_wrong_hash_grants_refused(self):
        for change in ({'approved':False},{'kind':'finite_generation_batch_only'},
                       {'manifest_sha256':'old-eight-call-hash'},
                       {'conditional_wave2_acknowledged':False}):
            self.approve(**change)
            with self.assertRaises(PermissionError):self.budget()
        self.assertFalse((self.base/'state').exists())

    def test_declared_cap_execution_and_main_scope_cannot_expand(self):
        for change in ({'max_new_generation_requests':17},{'per_wave_cap':16},
                       {'candidate_execution_authorized':True},{'main_calls':1},
                       {'per_slot_max_attempts':2}):
            write(self.request,{**self.plan,**change});self.approve()
            with self.assertRaises(PermissionError):self.budget()

    def test_wave1_order_exact_payload_and_one_use(self):
        budget=self.budget()
        with self.assertRaises(PermissionError):budget.reserve(1,2,self.payloads[1])
        with self.assertRaises(PermissionError):budget.reserve(1,1,{'seed':549199013,'changed':True})
        path,record=budget.reserve(1,1,self.payloads[0]);self.assertEqual(record['wave'],1)
        with self.assertRaises(PermissionError):budget.reserve(1,1,self.payloads[0])
        write(path/'outcome.json',{'unit_only':True})
        second,_=budget.reserve(1,2,self.payloads[1]);self.assertTrue(second.exists())

    def test_no_transfer_third_wave_or_extra_slot(self):
        budget=self.budget()
        for wave,index in ((1,9),(2,9),(3,1),(0,1),(True,1),(1,0)):
            with self.subTest(wave=wave,index=index),self.assertRaises(PermissionError):
                budget.reserve(wave,index,{'seed':549199029})
        self.assertFalse(list(budget.root.glob('call_*')))

    def test_existing_slot12_actual_feedback_alone_cannot_unlock_wave2(self):
        budget=self.budget()
        old=ROOT/'feedback_runs/20261102T060406746432Z_07113903/registration_verification.json'
        with self.assertRaises(PermissionError):budget.reserve(2,1,{'seed':549199021},old)
        with self.assertRaises(PermissionError):budget.reserve(2,1,{'seed':549199021})
        self.assertFalse((budget.root/'call_009').exists())
        self.assertFalse((budget.root/'wave2_feedback_binding.json').exists())

    def test_cached_or_prior_pool_cannot_be_renamed_into_wave1(self):
        budget=self.budget()
        oldpool=ROOT/'feedback_generated/20261102T052500617671Z_74cc148e/pool.json'
        bundle=self.base/'bundle.json'
        write(bundle,{'generation_request_sha256':budget.hash,'wave':1,
            'wave1_pool':{'path':oldpool.relative_to(PROJECT).as_posix(),'sha256':file_hash(oldpool)}})
        with self.assertRaises(PermissionError):feedback_condition(self.plan,budget.hash,bundle)
        self.assertFalse((budget.root/'call_009').exists())

    def test_database_time_adjustment_does_not_allow_state_substitution(self):
        self.assertTrue(same_database({'programs':['unit'],'reset_age_seconds':1},
                                     {'programs':['unit'],'reset_age_seconds':2}))
        self.assertFalse(same_database({'programs':['unit'],'reset_age_seconds':1},
                                      {'programs':['substituted'],'reset_age_seconds':1}))


if __name__=='__main__':unittest.main()
