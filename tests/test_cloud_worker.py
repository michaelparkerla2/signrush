import unittest
from unittest.mock import Mock
from tools.cloud_worker import authorized, Runner

class CloudWorkerTests(unittest.TestCase):
    def test_only_verified_scheduler_identity_is_accepted(self):
        verify=Mock(return_value={'email_verified':True,'email':'scheduler@example.iam.gserviceaccount.com'})
        self.assertTrue(authorized('Bearer test','https://worker','scheduler@example.iam.gserviceaccount.com',verify))
        for header,aud,caller in [('', 'https://worker','scheduler@example.iam.gserviceaccount.com'),('Bearer test','','scheduler@example.iam.gserviceaccount.com'),('Bearer test','https://worker','wrong')]:
            self.assertFalse(authorized(header,aud,caller,verify))
        verify.return_value={'email_verified':False,'email':'scheduler@example.iam.gserviceaccount.com'}
        self.assertFalse(authorized('Bearer test','https://worker','scheduler@example.iam.gserviceaccount.com',verify))
        verify.side_effect=ValueError('invalid signature')
        self.assertFalse(authorized('Bearer test','https://worker','scheduler@example.iam.gserviceaccount.com',verify))

    def test_overlapping_local_request_does_not_run_worker(self):
        worker=Mock();runner=Runner(worker);runner.lock.acquire()
        self.assertEqual(runner.tick(),409)
        worker.tick.assert_not_called();worker.db.document.assert_not_called()
        runner.lock.release()
