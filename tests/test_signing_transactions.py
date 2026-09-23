"""Cloud Shell emulator only. No production credentials or cloud media writes."""
import os
if not os.environ.get('FIRESTORE_EMULATOR_HOST'):raise SystemExit('Firestore emulator required')
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from unittest.mock import patch
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
  self.db.document('players/'+uid+'/consents/one').set({'action':'accepted','termsVersion':'pilot-v1','disclosureVersion':'training-v1'})
  ref=self.db.document('signingJobs/'+uid);ref.set({'uid':uid,'state':'requested','requestedAt':firestore.SERVER_TIMESTAMP});return ref
 def test_concurrent_reservations_are_globally_capped(self):
  refs=[self.player('p'+str(i)) for i in range(6)]
  with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(self.w.assign,refs))
  self.assertEqual(sum(r.get().to_dict()['state']=='assigned' for r in refs),3)
  self.assertEqual(self.db.document('pilotLimits/signing-v1').get().to_dict()['reserved'],3)
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
  self.assertEqual(self.db.document('pilotLimits/signing-v1').get().to_dict()['reserved'],1)
 def test_consent_withdrawn_during_session_creation_blocks_publication(self):
  ref=self.player('p');self.w.assign(ref)
  ref.update({'state':'upload_requested','size':9,'mime':'video/webm','sha256':'a'*64})
  def withdraw(**kw):
   self.db.document('players/p').update({'consentAccepted':False})
   return 'private-capability'
  with patch.object(Blob,'create_resumable_upload_session',side_effect=withdraw):self.w.grant(ref)
  job=ref.get().to_dict();self.assertEqual(job['state'],'blocked');self.assertNotIn('uploadURL',job)
if __name__=='__main__':unittest.main()
