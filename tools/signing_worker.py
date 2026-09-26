"""Bounded Cloud Shell pilot worker; no public HTTP server or local media sync.

Use authorized Cloud Shell ADC. One current job per player, bounded daily batch. Browser
rules permit requests only; every persisted decision is rechecked here. Not an
always-on production worker: explicitly bounded sessions, default 30 minutes.
"""
from consent_policy import current as current_consent_event, evidence, POLICY
import argparse
import hashlib
import json
import math
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from datetime import datetime, timezone

MAX_BYTES = 8 * 1024 * 1024
MAX_TASKS = 4000
MAX_RECORDINGS = 4003  # Work-page bound, never used to truncate corpus accounting
BATCH = 'daily-use-v1'
TARGET_SIGNERS = 20
PROJECT = 'signrush-login'
RAW = 'umi-signrush-raw'
HELDOUT = 'umi-signrush-heldout-answers'
ORIGIN = 'https://signrush-login.web.app'
PHRASES = json.loads((Path(__file__).resolve().parents[1] / 'data/pilot-phrases.json').read_text())


def eligible(invite, player, event):
    return ((not invite or invite.get('active') is True) and player.get('status') == 'active'
            and player.get('mode') == 'test' and player.get('consentAccepted') is True
            and current_consent_event(event))


def valid_upload(job):
    return (type(job.get('size')) is int and 0 < job['size'] <= MAX_BYTES
            and job.get('mime') in ('video/webm', 'video/mp4')
            and isinstance(job.get('sha256'), str) and len(job['sha256']) == 64
            and all(c in '0123456789abcdef' for c in job['sha256']))


def technical_check(path):
    result = subprocess.run(['ffprobe','-v','error','-protocol_whitelist','file,pipe',
        '-max_alloc','16777216','-show_entries','stream=codec_type,width,height:packet=pts_time,duration_time',
        '-of','json',str(path)], capture_output=True, timeout=20)
    if result.returncode or len(result.stdout)>1_000_000:
        return {'passed':False,'reason':'unreadable_video'}
    data = json.loads(result.stdout)
    streams=data.get('streams',[])
    if len(streams)!=1 or streams[0].get('codec_type')!='video':
        return {'passed':False,'reason':'video_only_required'}
    stream=streams[0]
    if stream.get('width',0)<640 or stream.get('height',0)<360:
        return {'passed':False,'reason':'resolution_too_low'}
    packets=data.get('packets',[])
    if not packets:return {'passed':False,'reason':'empty_video'}
    start=min(float(p['pts_time']) for p in packets)
    end=max(float(p['pts_time'])+float(p.get('duration_time',0)) for p in packets)
    duration=end-start
    if not math.isfinite(duration) or not 0.5<=duration<=31:
        return {'passed':False,'reason':'duration_out_of_range'}
    return {'passed':True,'durationSec':duration,'width':stream['width'],'height':stream['height'],
            'qualityReview':'pending','translationReview':'pending'}


class Worker:
    def __init__(self):
        from google.cloud import firestore, storage
        self.fs=firestore
        self.db=firestore.Client(project=PROJECT)
        self.storage=storage.Client(project='signrush')
        self.raw=self.storage.bucket(RAW)
        self.heldout=self.storage.bucket(HELDOUT)

    def consent(self,tx,uid):
        invite=self.db.document('pilotInvites/'+uid).get(transaction=tx).to_dict() or {}
        player=self.db.document('players/'+uid).get(transaction=tx).to_dict() or {}
        event={}
        if player.get('lastConsentId'):
            event=self.db.document('players/'+uid+'/consents/'+player['lastConsentId']).get(transaction=tx).to_dict() or {}
        return eligible(invite,player,event)

    def consent_evidence(self,tx,uid):
        player=self.db.document('players/'+uid).get(transaction=tx).to_dict() or {}
        consent_id=player.get('lastConsentId')
        if not consent_id:return None
        event=self.db.document(f'players/{uid}/consents/{consent_id}').get(transaction=tx).to_dict() or {}
        return evidence(event,uid,consent_id) if current_consent_event(event) else None

    def identities(self,tx,uids,known=None):
        values={} if known is None else known
        for uid in uids:
            person=uid;seen=set()
            while True:
                if person in seen or len(seen)>=32:raise ValueError('cyclic or excessive linked identity')
                seen.add(person)
                if person not in values:values[person]=self.db.document('pilotInvites/'+person).get(transaction=tx).to_dict() or {}
                linked=values[person].get('samePersonAs')
                if not linked:break
                if not isinstance(linked,str) or not linked or '/' in linked:raise ValueError('invalid linked identity')
                person=linked
        return values

    def signer_cohort(self,tx,person,identities):
        from consensus import person_key
        from corpus import split_for
        values=set()
        for uid in {person,*identities}:
            if person_key(uid,identities)!=person:continue
            profile=self.db.document('corpusSigners/'+uid).get(transaction=tx).to_dict() or {}
            if profile.get('split'):values.add(profile['split'])
        if not values:return {'split':split_for(person)}
        if not values.issubset({'train','validation','test','quarantine'}):raise ValueError('Invalid signer split')
        # Linking people from different cohorts can never move evaluation into training.
        return {'split':next(iter(values)) if len(values)==1 else 'quarantine'}

    def assign(self,ref):
        rid=secrets.token_hex(16)
        @self.fs.transactional
        def commit(tx):
            job=ref.get(transaction=tx).to_dict()
            if not job or job['state']!='requested':return
            uid=job['uid']
            ok=self.consent(tx,uid)
            rights=self.consent_evidence(tx,uid)
            activity_ref=self.db.document('pilotActivity/'+uid)
            activity=activity_ref.get(transaction=tx).to_dict() or {}
            # Canonical linked identity: one reservation per meaning per known person.
            from consensus import person_key
            identity_chain=self.identities(tx,[uid])
            person=person_key(uid,identity_chain)
            from corpus import counts, available, cap_for
            from google.cloud.firestore_v1.base_query import FieldFilter
            coverage_ref=self.db.document('corpusCoverage/'+BATCH)
            coverage=coverage_ref.get(transaction=tx).to_dict() or {}
            policy=self.db.document('corpusPolicy/'+BATCH).get(transaction=tx).to_dict() or {}
            person_ref=self.db.document('promptParticipants/'+person)
            history=person_ref.get(transaction=tx).to_dict() or {}
            signer_ref=self.db.document('corpusSigners/'+person)
            signer=self.signer_cohort(tx,person,identity_chain)
            exposed=set(activity.get('reviewedPhraseIds',[]))|set(activity.get('signingPhraseIds',[]))|set(history.get('meaningIds',[]))
            options=[p for p in PHRASES if p['id'] not in exposed and available(coverage.get(p['id'],{}),cap_for(policy,p['id']))]
            counter=self.db.document('pilotLimits/'+BATCH)
            count=(counter.get(transaction=tx).to_dict() or {}).get('reserved',0)
            if not ok or not options:
                tx.update(ref,{'state':'blocked'});return
            rank=lambda p:(coverage.get(p['id'],{}).get('approved',0),coverage.get(p['id'],{}).get('pending',0))
            lowest=min(map(rank,options))
            phrase=secrets.choice([p for p in options if rank(p)==lowest])
            rows=[x.to_dict() for x in self.db.collection('pilotRecordings').where(filter=FieldFilter('phrase.id','==',phrase['id'])).stream(transaction=tx)]
            identities=self.identities(tx,[r['uid'] for r in rows]+[uid])
            actual=counts(rows,identities)
            # Authoritative query + shared transaction lock prevent concurrent overbooking.
            if not available(actual,cap_for(policy,phrase['id'])):
                tx.set(coverage_ref,{**coverage,phrase['id']:actual});return
            if any(person_key(r['uid'],identities)==person for r in rows):
                tx.set(person_ref,{'meaningIds':list(set(history.get('meaningIds',[]))|{phrase['id']})});return
            tx.set(coverage_ref,{**coverage,phrase['id']:{**actual,'pending':actual['pending']+1}})
            tx.set(signer_ref,signer)
            tx.set(person_ref,{'meaningIds':list(set(history.get('meaningIds',[]))|{phrase['id']})})
            tx.set(activity_ref,{**activity,'signingPhraseIds':list(set(activity.get('signingPhraseIds',[])+[phrase['id']]))})
            record={'uid':uid,'assignmentId':rid,'phrase':phrase,'status':'assigned',
                    'createdAt':self.fs.SERVER_TIMESTAMP,'consentVersion':POLICY['disclosureVersion'],'rights':rights,'mode':'test',
                    'promptVersion':phrase['version'],'batch':BATCH,'corpusSignerId':person,'corpusSplit':signer['split']}
            tx.create(self.db.document('pilotRecordings/'+rid),record)
            tx.set(counter,{'reserved':count+1,'acceptedTarget':MAX_TASKS})
            tx.update(ref,{'state':'assigned','assignmentId':rid,'promptId':phrase['id'],
                           'approvedSigners':actual['approved'],'signerCap':cap_for(policy,phrase['id']),
                           'prompt':phrase['text'],'promptVersion':phrase['version'],'signerInstruction':phrase['signerInstruction'],'maxBytes':MAX_BYTES,'maxSeconds':30})
        commit(self.db.transaction())

    def grant(self,ref):
        @self.fs.transactional
        def reserve(tx):
            j=ref.get(transaction=tx).to_dict()
            if not j or j['state'] not in ('upload_requested','granting'):return None
            now=datetime.now(timezone.utc)
            if j['state']=='granting' and j.get('grantStartedAt') and (now-j['grantStartedAt']).total_seconds()<90:return None
            ok=self.consent(tx,j['uid'])
            record=self.db.document('pilotRecordings/'+j['assignmentId'])
            r=record.get(transaction=tx).to_dict() or {}
            if not ok or not valid_upload(j) or r.get('uid')!=j['uid'] or r.get('status')!=('reserved' if j['state']=='granting' else 'assigned'):
                tx.update(ref,{'state':'blocked'});return None
            j['grantToken']=secrets.token_hex(16)
            tx.update(ref,{'state':'granting','grantStartedAt':now,'grantToken':j['grantToken']})
            tx.update(record,{'status':'reserved','size':j['size'],'mime':j['mime'],'expectedSha256':j['sha256']})
            return j
        job=reserve(self.db.transaction())
        if not job:return
        ext='webm' if job['mime']=='video/webm' else 'mp4'
        key=f"pilot/recordings/{job['assignmentId']}/raw.{ext}"
        blob=self.raw.blob(key)
        # Session is a bearer capability; never print it or copy it into exports.
        uri=blob.create_resumable_upload_session(content_type=job['mime'],size=job['size'],
                    origin=ORIGIN,if_generation_match=0,timeout=30)
        now=datetime.now(timezone.utc)
        @self.fs.transactional
        def publish(tx):
            current=ref.get(transaction=tx).to_dict() or {}
            record_ref=self.db.document('pilotRecordings/'+job['assignmentId'])
            record=record_ref.get(transaction=tx).to_dict() or {}
            okay=self.consent(tx,job['uid'])
            if current.get('state')!='granting' or current.get('grantToken')!=job['grantToken']:return
            if not okay or record.get('status')!='reserved' or record.get('uid')!=job['uid']:
                tx.update(ref,{'state':'blocked','uploadURL':self.fs.DELETE_FIELD});return
            tx.update(record_ref,{'objectKey':key,'uploadIssuedAt':now})
            tx.update(ref,{'state':'uploading','uploadURL':uri,'uploadIssuedAt':now,
                           'grantToken':self.fs.DELETE_FIELD,'grantStartedAt':self.fs.DELETE_FIELD})
        publish(self.db.transaction())

    def finish(self,ref,job):
        from google.api_core.exceptions import NotFound
        record_ref=self.db.document('pilotRecordings/'+job['assignmentId'])
        record=record_ref.get().to_dict()
        if not record or not record.get('objectKey'):return
        blob=self.raw.blob(record['objectKey'])
        try:blob.reload(timeout=15)
        except NotFound:
            ext=record['objectKey'].rsplit('.',1)[-1]
            blob=self.raw.blob(f"pilot/failed/{job['assignmentId']}/raw.{ext}")
            try:blob.reload(timeout=15)
            except NotFound:return
        generation=int(blob.generation)
        if blob.size!=record['size'] or blob.size>MAX_BYTES or blob.content_type!=record['mime']:
            ref.update({'state':'failed','uploadURL':self.fs.DELETE_FIELD})
            record_ref.update({'status':'failed','failure':'unexpected_object_metadata','generation':str(generation)})
            return
        with tempfile.TemporaryDirectory(prefix='signrush-clip-') as folder:
            path=Path(folder)/'clip'
            # No unbounded download; generation pinned and read bounded to declared size.
            payload=blob.download_as_bytes(start=0,end=blob.size-1,if_generation_match=generation,timeout=30)
            digest=hashlib.sha256(payload).hexdigest()
            path.write_bytes(payload)
            try:quality=technical_check(path)
            except (ValueError,KeyError,subprocess.TimeoutExpired):quality={'passed':False,'reason':'unreadable_video'}
        if digest!=record['expectedSha256']:quality={'passed':False,'reason':'hash_mismatch'}
        tx=self.db.transaction()
        @self.fs.transactional
        def current_consent(transaction):return self.consent(transaction,job['uid'])
        consent_ok=current_consent(tx)
        if not consent_ok:quality={'passed':False,'reason':'consent_withdrawn'}
        state='saved' if quality['passed'] else 'failed'
        source_key=blob.name
        if state=='failed' and not source_key.startswith('pilot/failed/'):
            target=f"pilot/failed/{job['assignmentId']}/raw.{source_key.rsplit('.',1)[-1]}"
            from google.api_core.exceptions import PreconditionFailed
            try:copied=self.raw.copy_blob(blob,self.raw,new_name=target,source_generation=generation,if_generation_match=0,timeout=30)
            except PreconditionFailed:
                copied=self.raw.blob(target);copied.reload(timeout=15)
                if copied.size!=blob.size:raise ValueError('conflicting failed object')
            blob.delete(if_generation_match=generation,timeout=30)
            source_key=target;generation=int(copied.generation)
        receipt={'assignmentId':job['assignmentId'],'uid':job['uid'],'status':state,'bucket':RAW,
            'objectKey':source_key,'generation':str(generation),'sourceSha256':digest,'size':len(payload),
            'phraseId':record['phrase']['id'],'promptVersion':record['phrase'].get('version',1),
            'corpusSplit':record.get('corpusSplit','quarantine'),'batch':record.get('batch','legacy-v1'),'corpusSignerId':record.get('corpusSignerId',record['uid']),'technicalCheck':quality,'reviewResults':[],
            'translation':None,'mode':'test','exportEligible':False,'rights':record.get('rights',{'rightsStatus':'legacy_unverified'})}
        answer={'assignmentId':job['assignmentId'],'originalPrompt':record['phrase'],
                'consentVersion':record['consentVersion'],'referenceStatus':'unvalidated_prompt'}
        self.put_json(self.heldout,f"pilot/references/{job['assignmentId']}.json",answer)
        self.put_json(self.raw,f"pilot/{'failed' if state=='failed' else 'recordings'}/{job['assignmentId']}/receipt.json",receipt)
        batch=self.db.batch()
        batch.update(record_ref,{**receipt,'completedAt':self.fs.SERVER_TIMESTAMP})
        batch.update(ref,{'state':state,'uploadURL':self.fs.DELETE_FIELD})
        batch.commit()
        print('Recording finalized:',state,flush=True)

    def put_json(self,bucket,key,data):
        from google.api_core.exceptions import PreconditionFailed
        blob=bucket.blob(key)
        try:blob.upload_from_string(json.dumps(data),content_type='application/json',if_generation_match=0,timeout=30)
        except PreconditionFailed:
            if json.loads(blob.download_as_bytes(timeout=15))!=data:raise ValueError('conflicting receipt')

    def refresh_coverage(self):
        """Reconcile cached scheduling counts from ALL actual records (including legacy)."""
        from corpus import counts
        records=[x.to_dict() for x in self.db.collection('pilotRecordings').stream()]
        identities=self.identities(None,{r['uid'] for r in records})
        grouped={p['id']:[] for p in PHRASES}
        for r in records:
            key=r.get('phrase',{}).get('id')
            if key in grouped:grouped[key].append(r)
        value={key:counts(rows,identities) for key,rows in grouped.items()}
        ref=self.db.document('corpusCoverage/'+BATCH)
        # This is a scheduling cache only: assignment/approval recheck actual rows
        # transactionally. Stale reconciliation can never authorize an excess clip.
        if (ref.get().to_dict() or {})!=value:ref.set(value)

    def tick(self):
        if time.monotonic()-getattr(self,'_coverage_at',0)>60:
            self.refresh_coverage();self._coverage_at=time.monotonic()
        from google.cloud.firestore_v1.base_query import FieldFilter
        jobs=self.db.collection('signingJobs').where(filter=FieldFilter('state','in',
            ['requested','upload_requested','granting','uploading','submitted'])).limit(MAX_RECORDINGS).stream()
        for snap in jobs:
            job=snap.to_dict()
            try:
                if job['state']=='requested':self.assign(snap.reference)
                elif job['state'] in ('upload_requested','granting'):self.grant(snap.reference)
                else:self.finish(snap.reference,job)
            except Exception as exc:
                # Never serialize SDK exceptions: a storage exception may contain a session URI.
                print('Task check needs retry:',type(exc).__name__,flush=True)

if __name__=='__main__':
    from worker_runtime import main
    main(Worker)
