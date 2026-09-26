"""Cloud Shell emulator only. No production credentials or cloud media writes."""
import os
if not os.environ.get('FIRESTORE_EMULATOR_HOST'):raise SystemExit('Firestore emulator required')
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from unittest.mock import patch
from transaction_retry import attempt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from google.cloud import firestore
from google.auth.credentials import AnonymousCredentials
from tools.signing_worker import Worker,MAX_BYTES

class Blob:
 def __init__(self,name):self.name=name;self.calls=[];self.generation=1;self.content_type='video/webm';self.payload=b'synthetic';self.size=len(self.payload)
 def create_resumable_upload_session(self,**kw):self.calls.append(kw);return 'https://storage.googleapis.com/upload/storage/v1/b/umi-signrush-raw/o?upload_id=synthetic'
 def reload(self,**kw):pass
 def download_as_bytes(self,**kw):return self.payload
 def upload_from_string(self,payload,**kw):self.payload=payload.encode();self.size=len(self.payload)
class Bucket:
 def __init__(self):self.blobs={}
 def blob(self,key):return self.blobs.setdefault(key,Blob(key))

class Transactions(unittest.TestCase):
 def setUp(self):
  import secrets
  self.db=firestore.Client(project='demo-signrush-worker-'+secrets.token_hex(3),credentials=AnonymousCredentials())
  self.w=Worker.__new__(Worker);self.w.fs=firestore;self.w.db=self.db;self.w.raw=Bucket();self.w.heldout=Bucket()
 def player(self,uid):
  self.db.document('pilotInvites/'+uid).set({'active':True})
  self.db.document('players/'+uid).set({'status':'active','mode':'test','consentAccepted':True,'lastConsentId':'one'})
  self.db.document('players/'+uid+'/consents/one').set({'action':'accepted','termsVersion':'terms-2026-09-26-v3','disclosureVersion':'commercial-2026-09-26-v2','privacyVersion':'privacy-2026-09-26-v2','bundleHash':'3cd7079cf5b9a988b9480309dee50f633061ef8235865e504b9d82b0a3b33fde','adultConfirmed':True,'publicDisplayAllowed':False})
  ref=self.db.document('signingJobs/'+uid);ref.set({'uid':uid,'state':'requested','requestedAt':firestore.SERVER_TIMESTAMP});return ref
 def test_concurrent_reservations_are_capped_per_prompt(self):
  from tools.signing_worker import PHRASES
  for i in range(18):
   self.db.document('pilotRecordings/existing'+str(i)).set({'uid':'old'+str(i),'assignmentId':'existing'+str(i),'phrase':PHRASES[0],'status':'saved','technicalCheck':{'passed':True},'consensus':{'status':'approved'}})
  refs=[self.player('p'+str(i)) for i in range(4)]
  with patch('tools.signing_worker.PHRASES',PHRASES[:1]):
   with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda ref:attempt(self.w.assign,ref),refs))
   for ref in refs:self.w.assign(ref)
  self.assertEqual(sum(r.get().to_dict()['state']=='assigned' for r in refs),2)
  self.assertEqual(self.db.document('corpusCoverage/daily-use-v1').get().to_dict()['DAILY-001'],{'approved':18,'pending':2})
 def test_withdrawn_player_is_blocked_server_side(self):
  ref=self.player('p');self.db.document('players/p').update({'consentAccepted':False});self.w.assign(ref)
  self.assertEqual(ref.get().to_dict()['state'],'blocked')
 def test_one_grant_pinned_to_size_and_new_object(self):
  import hashlib
  ref=self.player('p');self.w.assign(ref);self.w.assign(ref)
  ref.update({'state':'upload_requested','size':9,'mime':'video/webm','sha256':hashlib.sha256(b'synthetic').hexdigest()})
  self.w.grant(ref);self.w.grant(ref)
  job=ref.get().to_dict();self.assertEqual(job['state'],'uploading')
  calls=[c for b in self.w.raw.blobs.values() for c in b.calls];self.assertEqual(len(calls),1)
  self.assertEqual(calls[0]['size'],9);self.assertEqual(calls[0]['if_generation_match'],0)
  with patch('tools.signing_worker.technical_check',return_value={'passed':True,'durationSec':2,'translationReview':'pending'}):self.w.finish(ref,job)
  saved=ref.get().to_dict();self.assertEqual(saved['state'],'saved');self.assertNotIn('uploadURL',saved)
  record=self.db.document('pilotRecordings/'+job['assignmentId']).get().to_dict()
  self.assertEqual(record['sourceSha256'],hashlib.sha256(b'synthetic').hexdigest());self.assertFalse(record['exportEligible']);self.assertIsNone(record['translation'])
  self.assertEqual(len(self.w.heldout.blobs),1)
  self.assertEqual(record['rights']['consentPath'],'players/p/consents/one')
  self.assertEqual(record['rights']['rightsStatus'],'license_recorded')
  self.assertFalse(record['rights']['publicDisplayAllowed'])
 def test_interrupted_grant_recovers_after_lease_without_new_reservation(self):
  from datetime import datetime,timedelta,timezone
  ref=self.player('p');self.w.assign(ref)
  ref.update({'state':'upload_requested','size':9,'mime':'video/webm','sha256':'a'*64})
  with patch.object(Blob,'create_resumable_upload_session',side_effect=TimeoutError):
   with self.assertRaises(TimeoutError):self.w.grant(ref)
  self.assertEqual(ref.get().to_dict()['state'],'granting')
  self.w.grant(ref)
  self.assertEqual(ref.get().to_dict()['state'],'granting')
  ref.update({'grantStartedAt':datetime.now(timezone.utc)-timedelta(seconds=91)})
  self.w.grant(ref)
  self.assertEqual(ref.get().to_dict()['state'],'uploading')
  self.assertEqual(self.db.document('pilotLimits/daily-use-v1').get().to_dict()['reserved'],1)
 def test_consent_withdrawn_during_session_creation_blocks_publication(self):
  ref=self.player('p');self.w.assign(ref)
  ref.update({'state':'upload_requested','size':9,'mime':'video/webm','sha256':'a'*64})
  def withdraw(**kw):
   self.db.document('players/p').update({'consentAccepted':False})
   return 'private-capability'
  with patch.object(Blob,'create_resumable_upload_session',side_effect=withdraw):self.w.grant(ref)
  job=ref.get().to_dict();self.assertEqual(job['state'],'blocked');self.assertNotIn('uploadURL',job)
 def test_daily_batch_balances_coverage_and_preserves_prompt_provenance(self):
  for i in range(4):self.w.assign(self.player('daily'+str(i)))
  rows=[x.to_dict() for x in self.db.collection('pilotRecordings').stream()]
  self.assertEqual(len({r['phrase']['id'] for r in rows}),4)
  self.assertTrue(all(r['promptVersion']==1 and r['batch']=='daily-use-v1' and r['corpusSignerId']==r['uid'] for r in rows))
  self.assertEqual(sum(v['pending'] for v in self.db.document('corpusCoverage/daily-use-v1').get().to_dict().values()),4)
 def test_last_of_all_200_phrases_is_assignable_with_full_rights_and_split(self):
  from tools.signing_worker import PHRASES
  self.assertEqual(len(PHRASES),200)
  self.db.document('corpusCoverage/daily-use-v1').set({p['id']:{'approved':20,'pending':0} for p in PHRASES[:-1]})
  # Old lifetime reservations must not impose the removed 300-task limit.
  self.db.document('pilotLimits/daily-use-v1').set({'reserved':4000,'limit':300})
  ref=self.player('last');self.w.assign(ref);job=ref.get().to_dict()
  self.assertEqual(job['promptId'],'DAILY-200');self.assertEqual(job['signerCap'],20)
  row=self.db.document('pilotRecordings/'+job['assignmentId']).get().to_dict()
  self.assertEqual(row['rights']['consentPath'],'players/last/consents/one')
  self.assertIn(row['corpusSplit'],['train','validation','test'])
  self.assertEqual(row['corpusSignerId'],'last')
 def test_aliases_cannot_reserve_same_meaning_twice(self):
  ref=self.player('first');self.w.assign(ref);first=ref.get().to_dict()['promptId']
  second=self.player('second');self.db.document('pilotInvites/second').update({'samePersonAs':'first'})
  self.w.assign(second);self.assertNotEqual(second.get().to_dict()['promptId'],first)
 def test_filled_batch_returns_blocked_without_increment(self):
  from tools.signing_worker import PHRASES
  self.db.document('corpusCoverage/daily-use-v1').set({p['id']:{'approved':20,'pending':0} for p in PHRASES})
  ref=self.player('p');self.w.assign(ref)
  self.assertEqual(ref.get().to_dict()['state'],'blocked')
  self.assertFalse(self.db.document('pilotLimits/daily-use-v1').get().exists)
 def test_failed_clip_releases_capacity_but_never_repeats_for_signer(self):
  from tools.signing_worker import PHRASES
  with patch('tools.signing_worker.PHRASES',PHRASES[:1]):
   ref=self.player('p');self.w.assign(ref)
   rid=ref.get().to_dict()['assignmentId']
   self.db.document('pilotRecordings/'+rid).update({'status':'failed'})
   self.w.refresh_coverage()
   ref.set({'uid':'p','state':'requested'});self.w.assign(ref)
   self.assertEqual(ref.get().to_dict()['state'],'blocked')
   other=self.player('other');self.w.assign(other)
   self.assertEqual(other.get().to_dict()['state'],'assigned')
 def test_reopen_to_thirty_and_persistent_signer_split(self):
  from tools.signing_worker import PHRASES
  for i in range(20):
   self.db.document('pilotRecordings/old'+str(i)).set({'uid':'old'+str(i),'assignmentId':'old'+str(i),'phrase':PHRASES[0],'status':'saved','technicalCheck':{'passed':True},'consensus':{'status':'approved'}})
  self.w.refresh_coverage()
  with patch('tools.signing_worker.PHRASES',PHRASES[:1]):
   ref=self.player('new');self.w.assign(ref);self.assertEqual(ref.get().to_dict()['state'],'blocked')
   self.db.document('corpusPolicy/daily-use-v1').set({'caps':{'DAILY-001':30}})
   ref.set({'uid':'new','state':'requested'});self.w.assign(ref)
   self.assertEqual(ref.get().to_dict()['state'],'assigned')
   first=self.db.document('pilotRecordings/'+ref.get().to_dict()['assignmentId']).get().to_dict()
  ref.set({'uid':'new','state':'requested'});self.w.assign(ref)
  second=self.db.document('pilotRecordings/'+ref.get().to_dict()['assignmentId']).get().to_dict()
  self.assertEqual(first['corpusSplit'],second['corpusSplit'])
 def test_actual_database_overrides_stale_empty_coverage(self):
  from tools.signing_worker import PHRASES
  for i in range(20):
   self.db.document('pilotRecordings/full'+str(i)).set({'uid':'full'+str(i),'phrase':PHRASES[0],'status':'saved','technicalCheck':{'passed':True},'consensus':{'status':'approved'}})
  with patch('tools.signing_worker.PHRASES',PHRASES[:1]):
   ref=self.player('new');self.w.assign(ref);self.w.assign(ref)
  self.assertEqual(ref.get().to_dict()['state'],'blocked')
 def test_linked_evaluation_identity_cannot_move_to_training(self):
  self.player('first');ref=self.player('alias')
  self.db.document('pilotInvites/alias').update({'samePersonAs':'first'})
  self.db.document('corpusSigners/first').set({'split':'train'})
  self.db.document('corpusSigners/alias').set({'split':'test'})
  self.w.assign(ref)
  row=self.db.document('pilotRecordings/'+ref.get().to_dict()['assignmentId']).get().to_dict()
  self.assertEqual(row['corpusSplit'],'quarantine')
  self.assertEqual(self.db.document('corpusSigners/first').get().to_dict()['split'],'quarantine')
if __name__=='__main__':unittest.main()
