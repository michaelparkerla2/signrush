"""Local synthetic normalization/IPC parity and failure isolation, no cloud."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from consensus import decide,normalize
from generate_rust_consensus_fixtures import cases,base
from rust_shadow import compare,payload
BIN=ROOT/'backend/rust-core/target/debug/signrush-shadow'
class Shadow(unittest.TestCase):
    def test_disabled_requires_no_process(self):
        r,rs,i,a=base()
        with patch.dict(os.environ,{},clear=True),patch('rust_shadow.subprocess.run',side_effect=AssertionError('must not run')):
            self.assertEqual(compare(r,rs,i,a,decide(r,rs,i,a)),'disabled')
    def test_python_unicode_normalization_contract(self):
        for raw,want in [('Straße','strasse'),('ＰＬＥＡＳＥ','please'),('I don’t feel well','i don\'t feel well'),('e\u0301cole','école'),('１２ apples','12 apples'),('İstanbul','i stanbul')]:
            self.assertEqual(normalize(raw),want)
        self.assertNotEqual(normalize('I feel well'),normalize('I do not feel well'))
        r,rs,i,a=base();r['technicalCheck']['durationSec']=True
        self.assertIsNone(payload(r,rs,i,a)['input']['duration_seconds'])
    def test_timeout_and_bad_output_are_isolated(self):
        r,rs,i,a=base();expected={**decide(r,rs,i,a),'version':'exact-pilot-v1'}
        for effect in [subprocess.TimeoutExpired('runner',1),ValueError('invalid'),OSError('missing')]:
            with patch('rust_shadow.subprocess.run',side_effect=effect):
                self.assertEqual(compare(r,rs,i,a,expected,executable='/synthetic/runner'),'unavailable')
        with patch('rust_shadow.subprocess.run',return_value=subprocess.CompletedProcess([],0,b'{}')):
            self.assertEqual(compare(r,rs,i,a,expected,executable='/synthetic/runner'),'mismatch')
    def test_new_policy_never_claims_parity_with_legacy_runner(self):
        for name,r,rs,i,a in cases:
            with self.subTest(name=name):self.assertEqual(compare(r,rs,i,a,decide(r,rs,i,a),executable=str(BIN)),'unsupported_policy')
    def test_runner_rejects_unknown_protocol_and_oversized_input_without_echo(self):
        for raw in [b'{"protocol":"bad"}',b'x'*262145]:
            out=subprocess.run([str(BIN)],input=raw,capture_output=True,timeout=2)
            self.assertEqual(out.returncode,2);self.assertEqual(out.stdout,b'');self.assertEqual(out.stderr,b'shadow input rejected\n')
if __name__=='__main__':unittest.main()
