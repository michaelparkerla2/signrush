"""Emulator-only atomic rewards and linked-person enforcement."""
import os
if not os.environ.get('FIRESTORE_EMULATOR_HOST'):raise SystemExit('Emulator required')
import unittest
from concurrent.futures import ThreadPoolExecutor
from test_review_transactions import Reviews
from consensus_worker import ConsensusWorker
from google.cloud import firestore
class Qualification(unittest.TestCase):
 player=Reviews.player
 job=Reviews.job
 def setUp(self):
  Reviews.setUp(self)
  self.w.__class__=ConsensusWorker
  self.record.update({'technicalCheck':{'passed':True,'durationSec':12.7}})
  self.db.document('signingJobs/signer').set({'uid':'signer','state':'saved','assignmentId':self.rid})
 def answers(self,n=3):
  refs=[]
  for i in range(n):
   ref=self.job('r'+str(i));self.w.choose(ref)
   ref.update({'state':'submitted','text':self.record.get().to_dict()['phrase']['text'],'quality':'good','submittedAt':firestore.SERVER_TIMESTAMP})
   self.w.save_answer(ref);refs.append(ref)
  return refs
 def test_concurrent_retries_award_once_and_publish_no_reference(self):
  refs=self.answers()
  def attempt(_):
   try:self.w.qualify(self.record)
   except ValueError as exc:
    # The real worker retries its next tick after SDK transaction exhaustion.
    # Permit only the documented contention wrapper; other errors still fail.
    from google.api_core.exceptions import Aborted
    if not isinstance(exc.__cause__,Aborted):raise
  with ThreadPoolExecutor(max_workers=3) as p:list(p.map(attempt,range(3)))
  self.w.qualify(self.record)
  self.assertEqual(len(list(self.db.collection('rewardEvents').stream())),4)
  self.assertEqual(self.db.document('playerRewards/signer').get().to_dict()['points'],12)
  for i in range(3):self.assertEqual(self.db.document('playerRewards/r'+str(i)).get().to_dict()['points'],5)
  summary=refs[0].get().to_dict()['outcome'];self.assertEqual(set(summary),{'status','independentReviews','requiredReviews'});self.assertEqual(summary['status'],'approved')
  self.assertFalse(self.record.get().to_dict()['exportEligible'])
 def test_old_owner_review_saved_as_test_never_rewarded(self):
  refs=self.answers();self.db.document('pilotInvites/r0').update({'samePersonAs':'signer','testOnly':True})
  self.w.qualify(self.record)
  self.assertEqual(refs[0].get().to_dict()['outcome']['status'],'test_only')
  self.assertEqual(len(list(self.db.collection('rewardEvents').stream())),0)
 def test_withdrawal_before_qualification_blocks_award(self):
  self.answers();self.db.document('players/r0').update({'consentAccepted':False});self.w.qualify(self.record)
  self.assertEqual(len(list(self.db.collection('rewardEvents').stream())),0)
 def test_alias_cannot_get_own_signers_video(self):
  ref=self.job('alternate');self.db.document('pilotInvites/alternate').update({'samePersonAs':'signer'})
  self.w.choose(ref);self.assertEqual(ref.get().to_dict()['state'],'empty')
 def test_disagreement_opens_only_two_extra_slots(self):
  refs=self.answers()
  first=refs[0].get().to_dict()['reviewId'];self.db.document('pilotReviews/'+first).update({'text':'Different meaning'})
  self.w.qualify(self.record);self.assertEqual(self.record.get().to_dict()['reviewLimit'],5)
  self.w.choose(self.job('r3'));self.w.choose(self.job('r4'));last=self.job('r5');self.w.choose(last)
  self.assertEqual(last.get().to_dict()['state'],'empty')
 def test_next_review_keeps_original_review_and_qualifies_original(self):
  refs=self.answers()
  original=refs[0].get().to_dict()['reviewId']
  refs[0].set({'uid':'r0','state':'requested','requestedAt':firestore.SERVER_TIMESTAMP})
  self.w.qualify(self.record)
  self.assertEqual(refs[0].get().to_dict()['state'],'requested')
  self.assertNotIn('outcome',refs[0].get().to_dict())
  self.assertTrue(self.db.document('pilotReviews/'+original).get().exists)
  self.assertEqual(self.db.document('playerRewards/r0').get().to_dict()['points'],5)
 def test_repeated_signing_retains_both_assignment_records(self):
  ref=self.db.document('signingJobs/new-signer');self.player('new-signer')
  ref.set({'uid':'new-signer','state':'requested','requestedAt':firestore.SERVER_TIMESTAMP})
  self.w.assign(ref);first=ref.get().to_dict()['assignmentId']
  ref.set({'uid':'new-signer','state':'requested','requestedAt':firestore.SERVER_TIMESTAMP})
  self.w.assign(ref);second=ref.get().to_dict()['assignmentId']
  self.assertNotEqual(first,second)
  self.assertTrue(self.db.document('pilotRecordings/'+first).get().exists)
  self.assertTrue(self.db.document('pilotRecordings/'+second).get().exists)
 def test_shadow_failure_does_not_change_awards_or_duplicate_them(self):
  from unittest.mock import patch
  self.answers()
  with patch('rust_shadow.compare',return_value='unavailable') as shadow:
   self.w.qualify(self.record);self.w.qualify(self.record)
   self.assertEqual(shadow.call_count,2)
  self.assertEqual(len(list(self.db.collection('rewardEvents').stream())),4)
  self.assertEqual(self.db.document('playerRewards/signer').get().to_dict()['points'],12)
 def test_shadow_mismatch_never_overrides_python_qualification(self):
  from unittest.mock import patch
  self.answers()
  with patch('rust_shadow.compare',return_value='mismatch'):
   self.w.qualify(self.record)
  self.assertEqual(self.record.get().to_dict()['consensus']['status'],'approved')
  self.assertEqual(self.db.document('playerRewards/signer').get().to_dict()['points'],12)
 def test_concurrent_last_approval_slot_is_not_overfilled(self):
  from secrets import token_hex
  self.answers()
  phrase=self.record.get().to_dict()['phrase']
  for i in range(19):
   self.db.document('pilotRecordings/approved'+str(i)).set({'uid':'old'+str(i),'assignmentId':'approved'+str(i),'phrase':phrase,'status':'saved','technicalCheck':{'passed':True},'consensus':{'status':'approved'}})
  self.player('second')
  other_id=token_hex(16);other=self.db.document('pilotRecordings/'+other_id)
  answers=[]
  for i in range(3):
   uid='second-reviewer'+str(i);self.player(uid)
   answer={'uid':uid,'reviewId':'second-review'+str(i),'status':'pending','text':phrase['text'],'quality':'good'}
   self.db.document('pilotReviews/'+answer['reviewId']).set(answer);answers.append(answer)
  other.set({'uid':'second','assignmentId':other_id,'phrase':phrase,'status':'saved','technicalCheck':{'passed':True,'durationSec':2},'reviewResults':answers})
  from transaction_retry import attempt
  with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda ref:attempt(self.w.qualify,ref),[self.record,other]))
  for ref in [self.record,other]:self.w.qualify(ref)
  states=[r.get().to_dict()['consensus']['status'] for r in [self.record,other]]
  self.assertEqual(sorted(states),['approved','collection_full'])
  self.assertEqual(self.db.document('corpusCoverage/daily-use-v1').get().to_dict()[phrase['id']]['approved'],20)
 def test_operator_rejection_releases_slot_and_survives_requalification(self):
  self.answers();self.record.update({'corpusDisposition':'rejected'})
  self.w.qualify(self.record);self.w.qualify(self.record)
  self.assertEqual(self.record.get().to_dict()['consensus']['status'],'rejected')
  phrase=self.record.get().to_dict()['phrase']['id']
  self.assertEqual(self.db.document('corpusCoverage/daily-use-v1').get().to_dict()[phrase],{'approved':0,'pending':0})
  self.assertFalse(self.db.document('rewardEvents/'+self.rid+'-sign-signer').get().exists)
 def test_expanded_panel_audited_outlier_and_idempotent_rewards(self):
  import subprocess,sys
  from pathlib import Path
  refs=self.answers()
  first=refs[0].get().to_dict()['reviewId'];original='A completely unrelated meaning.'
  self.db.document('pilotReviews/'+first).update({'text':original})
  self.w.qualify(self.record)
  for i in [3,4]:
   ref=self.job('r'+str(i));self.w.choose(ref)
   ref.update({'state':'submitted','text':self.record.get().to_dict()['phrase']['text'],'quality':'good','submittedAt':firestore.SERVER_TIMESTAMP})
   self.w.save_answer(ref);self.w.qualify(self.record)
  self.assertEqual(self.record.get().to_dict()['consensus']['status'],'adjudication_required')
  self.assertEqual(len(list(self.db.collection('rewardEvents').stream())),0)
  subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'tools/corpus_admin.py'),'--project',self.db.project,'assess-review',self.rid,first,'--verdict','unrelated','--critical-dispute','resolved','--assessor','synthetic-expert','--reason','Synthetic unrelated response; critical meaning reviewed'],check=True,capture_output=True)
  self.w.qualify(self.record);self.w.qualify(self.record)
  d=self.record.get().to_dict()['consensus'];self.assertEqual(d['status'],'approved');self.assertEqual(d['independentReviews'],5)
  self.assertEqual(d['suspectedOutlierReviewIds'],[first]);self.assertEqual(len(list(self.db.collection('rewardEvents').stream())),5)
  self.assertEqual(len(list(self.db.collection('meaningAssessmentHistory').stream())),1)
  self.assertEqual(self.db.document('pilotReviews/'+first).get().to_dict()['text'],original)
  self.assertEqual(refs[0].get().to_dict()['outcome']['requiredReviews'],5)
if __name__=='__main__':unittest.main()
