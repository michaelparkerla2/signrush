"""Real PostgreSQL permissions and HTTP flows; cloud identity/storage are fakes."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend.app import create_app, Settings, Database, FirebaseIdentity, CloudStorage
from test_corpus import TemporaryPostgres, CorpusTests, uid

DB = None

class Identity:
    def verify(self,token):
        if not token.startswith('test-player-') or not token[12:].isdigit():
            raise HTTPException(401,'Invalid token')
        return 'synthetic-player-'+token[12:]

class Storage:
    def __init__(self):
        self.uploads=[]
        self.reads=[]
    def upload(self,key,file,mime):
        self.uploads.append((key,file.read(),mime))
        return '12'
    def metadata(self,media):
        CloudStorage._validate(media)
        return 10
    def read(self,media,start,end):
        self.reads.append(media)
        return b'0123456789'[start:end+1]

class ApiTests(unittest.TestCase):
    def sql(self,query):
        return DB.run(query).stdout.strip()

    def setUp(self):
        CorpusTests.setUp(self)
        # Append a current consent version instead of mutating immutable history.
        self.sql("INSERT INTO consent_events(account_id,action,terms_version,disclosure_version) SELECT id,'accepted','pilot-v1','training-v1' FROM accounts;")
        # Replace fixture media with approved-prefix locators before immutable insert.
        self.sql("ALTER TABLE media_assets DISABLE TRIGGER immutable_media;")
        self.sql("UPDATE media_assets SET bucket='umi-signrush-raw',object_key='pilot/playback/'||id WHERE kind='silent_playback';")
        self.sql("ALTER TABLE media_assets ENABLE TRIGGER immutable_media;")
        settings=Settings('', 'signrush-login',frozenset(f'synthetic-player-{n}' for n in range(1,15)))
        self.storage=Storage()
        self.db=Database(f'host={DB.root} port=55439 user=signrush_runtime dbname=postgres')
        self.client=TestClient(create_app(settings,identity=Identity(),database=self.db,storage=self.storage),raise_server_exceptions=False)

    def headers(self,n=2,**extra):
        return {'Authorization':f'Bearer test-player-{n}',**extra}
    def claim(self,n=2):
        response=self.client.post('/v1/reviews/next',headers=self.headers(n))
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['task']

    def test_authentication_and_identity_spoofing(self):
        for headers in ({},{'Authorization':'Bearer forged'},{'X-Account-ID':uid(2)},self.headers(99)):
            response=self.client.post('/v1/reviews/next',headers=headers)
            self.assertIn(response.status_code,(401,403))
        response=self.client.post('/v1/account',headers=self.headers(2),json={'account_id':uid(1)})
        self.assertEqual(response.json()['account_id'],uid(2))
        self.assertEqual(self.storage.reads,[])

    def test_new_registration_consent_versions_and_withdrawal(self):
        self.sql(f"UPDATE accounts SET auth_subject='previous-fixture' WHERE id='{uid(14)}';")
        response=self.client.post('/v1/account',headers=self.headers(14))
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['consent_required'])
        self.assertEqual(self.client.post('/v1/signing/next',headers=self.headers(14)).status_code,409)
        disclosure=self.client.get('/v1/consent',headers=self.headers(14)).json()
        self.assertIn('including failed attempts',disclosure['notice'])
        body={k:disclosure[k] for k in ('terms_version','disclosure_version')}
        body['accept']=True
        stale=dict(body,terms_version='old-version')
        self.assertEqual(self.client.post('/v1/consent',headers=self.headers(14),json=stale).status_code,422)
        self.assertTrue(self.client.post('/v1/account',headers=self.headers(14)).json()['consent_required'])
        self.assertEqual(self.client.post('/v1/consent',headers=self.headers(14),json=body).json(),{'accepted':True})
        self.assertFalse(self.client.post('/v1/account',headers=self.headers(14)).json()['consent_required'])
        body['accept']=False
        self.assertEqual(self.client.post('/v1/consent',headers=self.headers(14),json=body).json(),{'accepted':False})
        self.assertTrue(self.client.post('/v1/account',headers=self.headers(14)).json()['consent_required'])

    def test_same_origin_web_assets_do_not_expose_repository(self):
        for path in ('/','/login.js','/onboarding.mjs','/styles.css','/firebase-config.js'):
            result=self.client.get(path)
            self.assertEqual(result.status_code,200,path)
            self.assertIn('no-store',result.headers['cache-control'])
        for path in ('/.env','/local-data/pilot-login.json','/db/migrations/001_corpus_pilot.sql','/backend/app.py'):
            self.assertEqual(self.client.get(path).status_code,404,path)

    def test_blind_payload_and_owned_playback(self):
        task=self.claim()
        self.assertEqual(set(task),{'assignment_id','reward_points','mode','playback_path'})
        for secret in ('appointment','bucket','generation','prompt','object_key'):
            self.assertNotIn(secret,json.dumps(task))
        for n in (1,3):
            self.assertEqual(self.client.get(task['playback_path'],headers=self.headers(n)).status_code,409)
        self.assertEqual(self.storage.reads,[])
        response=self.client.get(task['playback_path'],headers=self.headers(2,Range='bytes=2-5'))
        self.assertEqual(response.status_code,206)
        self.assertEqual(response.content,b'2345')
        self.assertEqual(response.headers['content-range'],'bytes 2-5/10')
        self.assertIn('no-store',response.headers['cache-control'])
        self.assertEqual(self.client.get(task['playback_path'],headers=self.headers(2,Range='bytes=20-')).status_code,416)
        self.assertEqual(self.client.get('/v1/heldout-answers',headers=self.headers()).status_code,404)

    def test_self_exposure_and_consent(self):
        self.assertIsNone(self.claim(1))
        self.sql(f"SELECT expose_phrase('{uid(2)}','{uid(100)}','test');")
        self.assertIsNone(self.claim(2))
        task=self.claim(3)
        body={'accept':False,'terms_version':'pilot-v1','disclosure_version':'training-v1'}
        self.assertEqual(self.client.post('/v1/consent',headers=self.headers(3),json=body).status_code,200)
        self.assertEqual(self.client.get(task['playback_path'],headers=self.headers(3)).status_code,409)
        self.assertEqual(self.client.post('/v1/reviews/next',headers=self.headers(3)).status_code,409)

    def test_signer_withdrawal_and_expiry_revoke_playback(self):
        task=self.claim(2)
        self.sql(f"UPDATE accounts SET status='suspended' WHERE id='{uid(1)}';")
        self.assertEqual(self.client.get(task['playback_path'],headers=self.headers(2)).status_code,409)
        self.assertEqual(self.client.post(f"/v1/reviews/{task['assignment_id']}/answer",headers=self.headers(2),json={'text':'Answer'}).status_code,409)
        self.sql(f"UPDATE accounts SET status='active' WHERE id='{uid(1)}';")
        self.sql(f"INSERT INTO consent_events(account_id,action,terms_version,disclosure_version) VALUES('{uid(1)}','withdrawn','pilot-v1','training-v1');")
        self.assertEqual(self.client.get(task['playback_path'],headers=self.headers(2)).status_code,409)
        self.sql(f"INSERT INTO consent_events(account_id,action,terms_version,disclosure_version) VALUES('{uid(1)}','accepted','pilot-v1','training-v1');")
        self.sql(f"UPDATE validation_assignments SET assigned_at=now()-interval '2 hours',expires_at=now()-interval '1 hour' WHERE id='{task['assignment_id']}';")
        self.assertEqual(self.client.get(task['playback_path'],headers=self.headers(2)).status_code,409)

    def test_answer_lock_and_three_review_cap(self):
        for n in (2,3,4):
            task=self.claim(n)
            path=f"/v1/reviews/{task['assignment_id']}/answer"
            first=self.client.post(path,headers=self.headers(n),json={'text':'Change my appointment to tomorrow.'})
            self.assertEqual(first.status_code,200,first.text)
            retry=self.client.post(path,headers=self.headers(n),json={'text':'Change my appointment to tomorrow.'})
            self.assertEqual(first.json(),retry.json())
            self.assertEqual(self.client.post(path,headers=self.headers(n),json={'text':'Different answer'}).status_code,409)
            self.assertEqual(self.client.get(task['playback_path'],headers=self.headers(n)).status_code,409)
        self.assertIsNone(self.claim(5))
        self.assertEqual(self.sql('SELECT training_manifest();'),'[]')

    def reviewed_prompt(self):
        self.sql(f"INSERT INTO phrase_versions(phrase_id,version,english_prompt,intended_meaning,source,reuse_terms,review_status) VALUES('{uid(100)}',2,'A synthetic phrase.','Synthetic.','fixture','test only','reviewed');")

    def test_upload_ownership_limits_and_quarantine(self):
        self.reviewed_prompt()
        response=self.client.post('/v1/signing/next',headers=self.headers(1))
        self.assertEqual(response.status_code,200,response.text)
        task=response.json()['task']
        path=f"/v1/signing/{task['assignment_id']}/video"
        response=self.client.put(path,headers=self.headers(2,**{'Content-Type':'video/mp4'}),content=b'fake-video')
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.storage.uploads,[])
        response=self.client.put(path,headers=self.headers(1,**{'Content-Type':'video/mp4'}),content=b'fake-video')
        self.assertEqual(response.status_code,202,response.text)
        self.assertEqual(response.json()['state'],'processing')
        self.assertEqual(self.storage.uploads[0][1],b'fake-video')
        self.assertNotIn('object_key',response.text)
        self.assertEqual(self.sql("SELECT count(*) FROM media_assets WHERE submission_id=(SELECT submission_id FROM upload_tickets LIMIT 1);"),'0')
        self.assertEqual(self.client.put(path,headers=self.headers(1,**{'Content-Type':'video/mp4'}),content=b'fake-video').status_code,409)
        self.sql('UPDATE pilot_upload_budget SET max_uploads=1;')
        task=self.client.post('/v1/signing/next',headers=self.headers(1)).json()['task']
        path=f"/v1/signing/{task['assignment_id']}/video"
        self.assertEqual(self.client.put(path,headers=self.headers(1,**{'Content-Type':'video/mp4'}),content=b'fake-video').status_code,409)
        self.assertEqual(len(self.storage.uploads),1)
        self.sql('UPDATE pilot_upload_budget SET max_uploads=100;')

    def test_database_role_cannot_read_truth_or_export(self):
        with self.assertRaises(RuntimeError):
            Database(f'host={DB.root} port=55439 user=signrush_test dbname=postgres')
        for query in ('SELECT * FROM signrush.phrase_versions','SELECT * FROM signrush.interpretations',
                      'SELECT * FROM signrush.holdout_membership','SELECT signrush.training_manifest()',
                      'SELECT signrush.validation_payload(NULL,NULL)',
                      "UPDATE signrush.accounts SET status='active'"):
            result=DB.run('SET ROLE signrush_api; '+query,check=False)
            self.assertNotEqual(result.returncode,0,query)
            self.assertIn('permission denied',result.stderr)

    def test_default_auth_adapter_checks_revocation(self):
        identity=FirebaseIdentity.__new__(FirebaseIdentity)
        identity.app=object()
        identity.auth=Mock()
        identity.auth.verify_id_token.return_value={'uid':'real-uid','email_verified':True}
        self.assertEqual(identity.verify('token'),'real-uid')
        identity.auth.verify_id_token.assert_called_once_with('token',app=identity.app,check_revoked=True)
        identity.auth.verify_id_token.side_effect=ValueError('expired or revoked')
        with self.assertRaises(HTTPException): identity.verify('token')

if __name__=='__main__':
    with TemporaryPostgres() as database:
        DB=database
        DB.run((Path(__file__).resolve().parents[1]/'db/migrations/002_participant_api.sql').read_text())
        DB.run('CREATE ROLE signrush_runtime LOGIN; GRANT signrush_api TO signrush_runtime;')
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ApiTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
