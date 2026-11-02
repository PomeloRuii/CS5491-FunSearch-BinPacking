"""Focused offline refusals against actual immutable batch artifacts; no worker/API."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import wave1_artifacts as artifacts
import evaluate_wave1_once as execution


@contextmanager
def workspace_temp():
    root = artifacts.HERE/'test_tmp'; root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as tmp:
        if not Path(tmp).resolve().is_relative_to(root.resolve()):
            raise PermissionError('Test cleanup must stay inside workspace test_tmp')
        yield tmp


class Wave1ScopeTests(unittest.TestCase):
    def test_actual_pool_and_manifest_provenance(self):
        pool, analysis, selected = artifacts.verify_pool()
        self.assertEqual(pool['api_attempts'], 8)
        self.assertEqual(selected, [2, 3, 5, 8])
        self.assertEqual(len({r['source_sha256'] for r in analysis}), 8)
        self.assertEqual(artifacts.verify_manifest()['maximum_full_evaluations'], 4)

    def test_substituted_source_refused_without_execution(self):
        with workspace_temp() as tmp:
            target = Path(tmp)/'wave1'
            shutil.copytree(artifacts.POOL.parent, target)
            source = target/'candidate_002/source.py.txt'
            source.write_bytes(source.read_bytes()+b'\n')
            with self.assertRaises((PermissionError, ValueError)):
                artifacts.verify_pool(target/'pool.json')

    def test_changed_generation_payload_refused(self):
        with workspace_temp() as tmp:
            target = Path(tmp)/'wave1'
            shutil.copytree(artifacts.POOL.parent, target)
            path = target/'candidate_002/request.json'
            value = json.loads(path.read_text()); value['payload']['seed'] += 1
            path.write_text(json.dumps(value))
            with self.assertRaises(PermissionError): artifacts.verify_pool(target/'pool.json')

    def test_incomplete_execution_scope_refused(self):
        with workspace_temp() as tmp:
            value = artifacts.read(artifacts.MANIFEST)
            value['dispatch_slots'].pop()
            path = Path(tmp)/'manifest.json'; artifacts.write(path, value)
            with self.assertRaises(PermissionError): artifacts.verify_manifest(path)

    def test_no_approval_never_constructs_worker(self):
        with workspace_temp() as tmp:
            with patch.object(execution, 'checked_runner', side_effect=AssertionError('Worker reached')) as worker:
                with self.assertRaises(FileNotFoundError):
                    execution.main(argparse.Namespace(approval=Path(tmp)/'missing_approval.json'))
                worker.assert_not_called()


if __name__ == '__main__': unittest.main(verbosity=2)

