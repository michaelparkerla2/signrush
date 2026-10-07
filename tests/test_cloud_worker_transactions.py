import os
import secrets
import threading
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from google.cloud import firestore
from google.auth.credentials import AnonymousCredentials
from tools.cloud_worker import Runner

@unittest.skipUnless(os.environ.get('FIRESTORE_EMULATOR_HOST'), 'Firestore emulator required')
class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.db=firestore.Client(project='demo-cloud-worker-'+secrets.token_hex(3),credentials=AnonymousCredentials())
        self.ref=self.db.document('workerHealth/scheduled')
        self.worker=SimpleNamespace(db=self.db,fs=firestore,tick=Mock())

    def test_second_instance_cannot_process_during_first_cycle(self):
        entered=threading.Event();release=threading.Event()
        def tick():
            entered.set();release.wait(10)
        self.worker.tick.side_effect=tick
        first=Runner(self.worker);results=[]
        thread=threading.Thread(target=lambda:results.append(first.tick()))
        thread.start()
        try:
            self.assertTrue(entered.wait(10))
            self.assertEqual(Runner(self.worker).tick(),409)
        finally:
            release.set();thread.join(10)
        self.assertEqual(results,[200]);self.assertEqual(self.worker.tick.call_count,1)
        self.assertNotIn('leaseToken',self.ref.get().to_dict())

    def test_expired_lease_recovers_and_failure_is_recorded(self):
        self.ref.set({'leaseToken':'old','leaseUntil':datetime.now(timezone.utc)-timedelta(seconds=1)})
        self.worker.tick.side_effect=RuntimeError('sensitive text must not be logged')
        self.assertEqual(Runner(self.worker).tick(),503)
        state=self.ref.get().to_dict()
        self.assertEqual(state['state'],'failed');self.assertNotIn('leaseToken',state)
