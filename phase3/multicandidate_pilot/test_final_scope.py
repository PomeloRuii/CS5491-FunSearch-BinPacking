"""Focused real-receipt/RNG/scope checks; no worker, model call or source execution."""
import argparse
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import final_stream as f
import final_replay as execution
from common import read, digest
from database_state import restore, snapshot
from two_wave_guards import feedback_condition, same_database
from run_wave2_remaining import rng_neutral


class FinalScopeTests(unittest.TestCase):
    def test_actual_frozen_pool_and_diversity(self):
        pool = f.check_final_pool(); result = f.diversity(pool)
        self.assertEqual(result['static_valid_count'], 10)
        self.assertEqual(result['static_valid_exact_unique'], 9)
        self.assertEqual(result['static_valid_ast_unique'], 8)
        self.assertEqual(result['matching_groups']['raw'], [[14, 15]])
        self.assertEqual(result['matching_groups']['ast'], [[3, 14, 15]])

    def test_actual_feedback_verification_does_not_change_caller_rng(self):
        database = restore(read(f.LEARNING/'pilot_database_after.json'))
        before = snapshot(database)
        gate = rng_neutral(feedback_condition, read(f.REQUEST), f.REQUEST_SHA, f.LEARNING/'wave1_feedback_bundle.json')
        self.assertTrue(same_database(before, snapshot(database)))
        self.assertEqual(gate['successful_new_registrations'], 3)
        self.assertEqual([p['seed'] for p in gate['payloads']], list(range(549199021, 549199029)))

    def test_exact_finite_task_set_and_full_task_metadata(self):
        manifest, pool = f.verify_manifest()
        self.assertEqual(manifest['maximum_container_dispatches'], 220)
        self.assertEqual(manifest['maximum_full_evaluations'], 130)
        self.assertEqual(manifest['maximum_fingerprint_tasks'], 90)
        self.assertEqual(len({s['slot_id'] for s in manifest['dispatch_slots']}), 220)
        self.assertTrue(all(s['fingerprint_size'] == 16 for s in manifest['dispatch_slots'] if s['action'] == 'full'))
        self.assertEqual({s['fingerprint_size'] for s in manifest['dispatch_slots'] if s['role'] == 'normal' and s['action'] == 'fingerprint'}, {16, 64, 128})
        self.assertFalse(manifest['heldout_access'])

    def test_no_new_approval_stops_before_worker_construction(self):
        with patch.object(execution, 'checked_runner', side_effect=AssertionError('Worker reached')) as worker:
            with self.assertRaises(FileNotFoundError):
                execution.main(argparse.Namespace(approval=f.HERE/'missing_final_approval.json'))
            worker.assert_not_called()


if __name__ == '__main__': unittest.main(verbosity=2)
