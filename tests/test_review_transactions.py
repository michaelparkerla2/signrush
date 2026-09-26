"""Firestore emulator only; synthetic people, no real media or signed URLs."""
import os
if not os.environ.get('FIRESTORE_EMULATOR_HOST'):raise SystemExit('Emulator required')
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from transaction_retry import attempt
import secrets
from google.cloud import firestore
from google.auth.credentials import AnonymousCredentials
from review_worker import ReviewWorker
from signing_worker import PHRASES
class Reviews(unittest.TestCase):
 def setUp(self):
  self.w=ReviewWorker.__new__(ReviewWorker);self.w.fs=firestore
  self.w.db=firestore.Client(project='demo-review-'+secrets.token_hex(3),credentials=AnonymousCredentials());self.db=self.w.db
  self.player('signer');self.rid=secrets.token_hex(16)
  self.record=self.db.document('pilotRecordings/'+self.rid)
  self.record.set({'uid':'signer','assignmentId':self.rid,'status':'saved','phrase':PHRASES[0],'technicalCheck':{'passed':True},'reviewResults':[]})
 def player(self,uid):
  self.db.document('pilotInvites/'+uid).set({'active':True})
  self.db.document('players/'+uid).set({'status':'active','mode':'test','consentAccepted':True,'lastConsentId':'one'})
  self.db.document('players/'+uid+'/consents/one').set({'action':'accepted','termsVersion':'terms-2026-09-26-v1','disclosureVersion':'commercial-2026-09-26-v1','privacyVersion':'privacy-2026-09-26-v1','bundleHash':'93843951df66917913dd0f08de8dbcd9fca94214ee8be9cf7c6c663d0b8c2da7','adultConfirmed':True,'publicDisplayAllowed':False})
 def job(self,uid):
  self.player(uid);ref=self.db.document('reviewJobs/'+uid);ref.set({'uid':uid,'state':'requested','requestedAt':firestore.SERVER_TIMESTAMP});return ref
 def test_self_and_exposed_phrase_are_excluded(self):
  ref=self.job('signer');self.w.choose(ref);self.assertEqual(ref.get().to_dict()['state'],'empty')
  ref=self.job('exposed');self.db.document('pilotRecordings/earlier').set({'uid':'exposed','status':'assigned','phrase':PHRASES[0]})
  self.w.choose(ref);self.assertEqual(ref.get().to_dict()['state'],'empty')
 def test_three_distinct_slots_under_concurrency_and_sanitized_jobs(self):
  refs=[self.job('reviewer'+str(i)) for i in range(5)]
  with ThreadPoolExecutor(max_workers=5) as p:list(p.map(lambda ref:attempt(self.w.choose,ref),refs))
  for ref in refs:self.w.choose(ref)
  assigned=[r.get().to_dict() for r in refs if r.get().to_dict()['state']=='preparing']
  self.assertEqual(len(assigned),3);self.assertEqual(len(set(self.record.get().to_dict()['reviewerIds'])),3)
  for job in assigned:self.assertEqual(set(job),{'uid','state','reviewId','requestedAt'})
 def test_answer_saved_once_and_pending(self):
  ref=self.job('reviewer');self.w.choose(ref);self.w.choose(ref);job=ref.get().to_dict()
  ref.update({'state':'submitted','text':'  My independent meaning.  ','submittedAt':firestore.SERVER_TIMESTAMP})
  self.w.save_answer(ref);self.w.save_answer(ref)
  self.assertEqual(ref.get().to_dict()['state'],'pending')
  result=self.record.get().to_dict()['reviewResults'];self.assertEqual(len(result),1);self.assertEqual(result[0]['text'],'My independent meaning.')
  self.assertEqual(result[0]['rights']['consentPath'],'players/reviewer/consents/one')
  self.assertEqual(result[0]['rights']['rightsStatus'],'license_recorded')
  self.assertEqual(self.db.document('pilotReviews/'+job['reviewId']).get().to_dict()['status'],'pending')
  self.assertNotIn('phrase',ref.get().to_dict())
  self.assertEqual(ref.get().to_dict()['referencePrompt'],PHRASES[0]['text'])
 def test_consent_checked_before_media_access(self):
  ref=self.job('reviewer');self.w.choose(ref);self.db.document('players/reviewer').update({'consentAccepted':False})
  with patch.object(self.w,'playback',side_effect=AssertionError('should not read media')):self.w.grant_review(ref)
  self.assertEqual(ref.get().to_dict()['state'],'blocked')
 def test_original_signer_withdrawal_blocks_answer(self):
  ref=self.job('reviewer');self.w.choose(ref);self.db.document('players/signer').update({'consentAccepted':False})
  ref.update({'state':'submitted','text':'meaning','submittedAt':firestore.SERVER_TIMESTAMP});self.w.save_answer(ref)
  self.assertEqual(ref.get().to_dict()['state'],'blocked');self.assertEqual(self.record.get().to_dict()['reviewResults'],[])
 def test_reviewer_cannot_get_the_hidden_phrase_as_a_signing_task(self):
  ref=self.job('reviewer');self.w.choose(ref)
  sign=self.db.document('signingJobs/reviewer');sign.set({'uid':'reviewer','state':'requested','requestedAt':firestore.SERVER_TIMESTAMP})
  with patch('signing_worker.PHRASES',[PHRASES[0]]):self.w.assign(sign)
  self.assertEqual(sign.get().to_dict()['state'],'blocked')
if __name__=='__main__':unittest.main()
