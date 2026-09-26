"""Synthetic emulator tests: irreversible-looking UI is backed by an auditable ledger."""
import os
if not os.environ.get('FIRESTORE_EMULATOR_HOST'):raise SystemExit('Emulator required')
import unittest,secrets
from concurrent.futures import ThreadPoolExecutor
from test_review_transactions import Reviews
from consensus_worker import ConsensusWorker
from google.cloud import firestore
from transaction_retry import attempt

class Moderation(unittest.TestCase):
 player=Reviews.player
 job=Reviews.job
 def setUp(self):
  Reviews.setUp(self);self.w.__class__=ConsensusWorker
  self.record.update({'technicalCheck':{'passed':True,'durationSec':12}})
 def reports(self,record,reason='not_signing'):
  results=[]
  for i in range(3):
   uid='flagger-'+secrets.token_hex(5);self.player(uid);rid=secrets.token_hex(16)
   r={'uid':uid,'reviewId':rid,'recordingId':record.id,'status':'pending','text':'','quality':'poor','reportReason':reason}
   self.db.document('pilotReviews/'+rid).set(r);results.append(r)
  record.update({'reviewResults':results});return results
 def next_record(self):
  rid=secrets.token_hex(16);ref=self.db.document('pilotRecordings/'+rid)
  ref.set({'uid':'signer','assignmentId':rid,'status':'saved','phrase':{'id':rid,'text':'Please wait.','version':1},'technicalCheck':{'passed':True,'durationSec':12}})
  return ref
 def test_first_strike_revokes_only_video_award_once(self):
  self.reports(self.record)
  self.db.document('playerRewards/signer').set({'points':100,'mode':'test'})
  self.db.document('rewardEvents/'+self.rid+'-sign-signer').set({'points':12,'uid':'signer','role':'sign','mode':'test'})
  with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:attempt(self.w.qualify,self.record),range(2)))
  self.w.qualify(self.record)
  self.assertEqual(self.db.document('playerRewards/signer').get().to_dict()['points'],88)
  self.assertEqual(self.db.document('playerModeration/signer').get().to_dict()['strikes'],1)
  self.assertEqual(len(list(self.db.collection('moderationEvents').stream())),1)
  self.assertEqual(self.db.document('rewardEvents/'+self.rid+'-sign-signer').get().to_dict()['points'],12)
  r=self.record.get().to_dict();self.assertEqual(r['corpusDisposition'],'rejected');self.assertFalse(r['exportEligible'])
  self.assertEqual(self.db.document('corpusCoverage/daily-use-v1').get().to_dict()[r['phrase']['id']],{'approved':0,'pending':0})
 def test_quality_rejection_never_adds_a_strike(self):
  self.reports(self.record,'unusable_quality');self.w.qualify(self.record)
  self.assertFalse(self.db.document('playerModeration/signer').get().exists)
  self.assertEqual(self.record.get().to_dict()['corpusRejectionReason'],'unusable_quality')
 def test_three_strikes_cancel_and_clear_all_known_linked_balances(self):
  self.player('alias');self.db.document('pilotInvites/alias').update({'samePersonAs':'signer'})
  for uid in ['signer','alias']:
   self.db.document('playerRewards/'+uid).set({'points':123,'mode':'test'})
   self.db.document('leaderboard/'+uid).set({'points':123})
  for n in range(3):
   ref=self.record if n==0 else self.next_record();self.reports(ref);self.w.qualify(ref);self.w.qualify(ref)
   self.assertEqual(self.db.document('playerModeration/signer').get().to_dict()['strikes'],n+1)
   if n<2:self.assertEqual(self.db.document('playerRewards/signer').get().to_dict()['points'],123)
  for uid in ['signer','alias']:
   self.assertEqual(self.db.document('players/'+uid).get().to_dict()['status'],'cancelled')
   self.assertEqual(self.db.document('playerRewards/'+uid).get().to_dict()['points'],0)
   self.assertFalse(self.db.document('leaderboard/'+uid).get().exists)
   self.assertFalse(self.w.consent(None,uid))
  self.assertEqual(len(list(self.db.collection('moderationEvents').stream())),3)
 def test_linked_account_cannot_bypass_ban_even_with_active_profile(self):
  self.player('alias');self.db.document('pilotInvites/alias').update({'samePersonAs':'signer'})
  self.db.document('accountModeration/signer').set({'blocked':True,'strikes':3})
  self.assertFalse(self.w.consent(None,'alias'))
 def test_report_saved_blind_once_and_late_reports_cannot_change_rejected_clip(self):
  ref=self.job('reporter');self.w.choose(ref)
  ref.update({'state':'submitted','text':'','quality':'poor','reportReason':'not_signing','submittedAt':firestore.SERVER_TIMESTAMP})
  self.w.save_answer(ref);self.w.save_answer(ref)
  answer=self.record.get().to_dict()['reviewResults'];self.assertEqual(len(answer),1);self.assertEqual(answer[0]['text'],'');self.assertEqual(answer[0]['reportReason'],'not_signing')
  self.assertEqual(ref.get().to_dict()['state'],'pending')
  late=self.job('late');self.w.choose(late);self.record.update({'corpusDisposition':'rejected'})
  late.update({'state':'submitted','text':'','quality':'poor','reportReason':'not_signing','submittedAt':firestore.SERVER_TIMESTAMP});self.w.save_answer(late)
  self.assertEqual(late.get().to_dict()['state'],'blocked');self.assertEqual(len(self.record.get().to_dict()['reviewResults']),1)
 def test_concurrent_different_incidents_reach_three_once(self):
  self.db.document('playerRewards/signer').set({'points':77,'mode':'test'})
  self.reports(self.record);self.w.qualify(self.record)
  refs=[self.next_record(),self.next_record()]
  for ref in refs:self.reports(ref)
  with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda ref:attempt(self.w.qualify,ref),refs))
  for ref in refs:self.w.qualify(ref)
  self.assertEqual(self.db.document('playerModeration/signer').get().to_dict()['strikes'],3)
  self.assertEqual(self.db.document('playerRewards/signer').get().to_dict()['points'],0)
  self.assertEqual(len(list(self.db.collection('moderationEvents').stream())),3)
 def test_rejected_clip_cannot_get_a_new_playback_grant(self):
  from unittest.mock import patch
  ref=self.job('reporter');self.w.choose(ref);self.record.update({'corpusDisposition':'rejected'})
  with patch.object(self.w,'playback',side_effect=AssertionError('must not access rejected media')):self.w.grant_review(ref)
  self.assertEqual(ref.get().to_dict()['state'],'blocked')
if __name__=='__main__':unittest.main()
