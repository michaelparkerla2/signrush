"""Private blind-review pilot. Browser jobs never contain prompts or peer answers."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time

from signing_worker import Worker, MAX_BYTES, RAW, MAX_RECORDINGS
from consensus import person_key

PLAYBACK_SIGNER = 'signrush-playback@signrush.iam.gserviceaccount.com'
REVIEW_LIMIT = 3
URL_SECONDS = 300
MAX_REFRESHES = 3


def can_review(record, uid, exposed):
    return (record.get('status') == 'saved' and record.get('uid') != uid
            and record.get('phrase', {}).get('id') not in exposed
            and record.get('technicalCheck', {}).get('passed') is True
            and uid not in record.get('reviewerIds', [])
            and record.get('consensus',{}).get('status') not in ('approved','adjudication_required','quality_check_required','test_only','rejected','collection_full')
            and len(record.get('reviewerIds', [])) < min(5,record.get('reviewLimit',REVIEW_LIMIT)))


class ReviewWorker(Worker):
    def independent(self, tx, signer, reviewer):
        invites=self.identities(tx,{signer,reviewer})
        return person_key(signer,invites)!=person_key(reviewer,invites)

    def choose(self, ref):
        from google.cloud.firestore_v1.base_query import FieldFilter
        # Failed attempts do not consume approved capacity; never truncate history.
        candidates=list(self.db.collection('pilotRecordings').where(filter=FieldFilter('status','==','saved')).stream())
        secrets.SystemRandom().shuffle(candidates)
        @self.fs.transactional
        def commit(tx):
            job=ref.get(transaction=tx).to_dict()
            if not job or job['state']!='requested':return
            uid=job['uid']
            if not self.consent(tx,uid):tx.update(ref,{'state':'blocked'});return
            activity_ref=self.db.document('pilotActivity/'+uid)
            activity=activity_ref.get(transaction=tx).to_dict() or {}
            invites=self.identities(tx,[uid])
            person=person_key(uid,invites)
            person_ref=self.db.document('promptParticipants/'+person)
            history=person_ref.get(transaction=tx).to_dict() or {}
            own=list(self.db.collection('pilotRecordings').where(filter=FieldFilter('uid','==',uid)).stream(transaction=tx))
            exposed={s.to_dict().get('phrase',{}).get('id') for s in own} | set(activity.get('signingPhraseIds',[])) | set(activity.get('reviewedPhraseIds',[])) | set(history.get('meaningIds',[]))
            chosen=None
            for candidate in candidates:
                record=candidate.reference.get(transaction=tx).to_dict() or {}
                self.identities(tx,[other for other in [record.get('uid'),*record.get('reviewerIds',[])] if other],invites)
                independent=person_key(uid,invites) not in {person_key(other,invites) for other in [record.get('uid'),*record.get('reviewerIds',[])] if other}
                if independent and can_review(record,uid,exposed) and self.consent(tx,record['uid']):
                    chosen=(candidate.reference,record);break
            if chosen is None:tx.update(ref,{'state':'empty'});return
            recording,record=chosen
            rid=secrets.token_hex(16)
            review={'uid':uid,'recordingId':recording.id,'phraseId':record['phrase']['id'],'status':'assigned',
                    'createdAt':self.fs.SERVER_TIMESTAMP,'mode':'test','refreshCount':0}
            tx.set(activity_ref,{**activity,'reviewedPhraseIds':list(set(activity.get('reviewedPhraseIds',[])+[record['phrase']['id']]))})
            tx.set(person_ref,{'meaningIds':list(set(history.get('meaningIds',[]))|{record['phrase']['id']})})
            tx.create(self.db.document('pilotReviews/'+rid),review)
            tx.update(recording,{'reviewerIds':record.get('reviewerIds',[])+[uid]})
            # Only opaque review identity crosses into the participant document.
            tx.set(ref,{'uid':uid,'reviewId':rid,'state':'preparing','requestedAt':job['requestedAt']})
        commit(self.db.transaction())

    def playback(self, record):
        from google.api_core.exceptions import PreconditionFailed
        rid=record['assignmentId']
        if not re.fullmatch('[a-f0-9]{32}',rid):raise ValueError('invalid recording')
        if record.get('bucket')!=RAW or not record.get('objectKey','').startswith('pilot/recordings/'+rid+'/'):
            raise ValueError('invalid source')
        playback=record.get('playback')
        key=f'pilot/playback/{rid}/silent-v1.mp4'
        if playback:
            if playback.get('objectKey')!=key or not str(playback.get('generation','')).isdigit():raise ValueError('invalid playback')
            return playback
        blob=self.raw.blob(record['objectKey'],generation=int(record['generation']))
        blob.reload(timeout=15)
        if not 0<blob.size<=MAX_BYTES:raise ValueError('invalid media size')
        payload=blob.download_as_bytes(start=0,end=blob.size-1,if_generation_match=int(record['generation']),timeout=30)
        if hashlib.sha256(payload).hexdigest()!=record['sourceSha256']:raise ValueError('source mismatch')
        with tempfile.TemporaryDirectory(prefix='signrush-review-') as folder:
            source=Path(folder)/'input';target=Path(folder)/'silent.mp4';source.write_bytes(payload)
            subprocess.run(['ffmpeg','-v','error','-nostdin','-protocol_whitelist','file,pipe',
                '-i',str(source),'-map','0:v:0','-map_metadata','-1','-map_chapters','-1','-an',
                '-t','31','-vf',"scale=w='min(1280,iw)':h='min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
                '-r','30','-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p',
                '-movflags','+faststart',str(target)],check=True,capture_output=True,timeout=60)
            if not 0<target.stat().st_size<=MAX_BYTES:raise ValueError('playback too large')
            normalized=target.read_bytes()
        out=self.raw.blob(key)
        try:out.upload_from_string(normalized,content_type='video/mp4',if_generation_match=0,timeout=30)
        except PreconditionFailed:out.reload(timeout=15)
        result={'objectKey':key,'generation':str(out.generation),'mime':'video/mp4'}
        self.db.document('pilotRecordings/'+rid).update({'playback':result})
        return result

    def signed_playback(self, playback):
        import google.auth
        from google.auth.transport.requests import Request
        creds,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        creds.refresh(Request())
        blob=self.raw.blob(playback['objectKey'],generation=int(playback['generation']))
        return blob.generate_signed_url(version='v4',expiration=timedelta(seconds=URL_SECONDS),method='GET',
            service_account_email=PLAYBACK_SIGNER,access_token=creds.token,
            response_disposition='inline; filename="signrush-review.mp4"',
            query_parameters={'generation':playback['generation']})

    def grant_review(self, ref):
        job=ref.get().to_dict()
        if not job or job['state'] not in ('preparing','refresh_requested'):return
        review_ref=self.db.document('pilotReviews/'+job['reviewId'])
        review=review_ref.get().to_dict() or {}
        record_ref=self.db.document('pilotRecordings/'+review.get('recordingId','missing'))
        record=record_ref.get().to_dict() or {}
        if review.get('uid')!=job['uid'] or review.get('status')!='assigned':ref.update({'state':'blocked'});return
        # Check eligibility before reading or converting any private media.
        @self.fs.transactional
        def allowed(tx):
            fresh=record_ref.get(transaction=tx).to_dict() or {}
            return (fresh.get('status')=='saved' and fresh.get('uid')!=job['uid']
                    and self.consent(tx,job['uid']) and self.consent(tx,fresh['uid'])
                    and self.independent(tx,fresh['uid'],job['uid']))
        if not allowed(self.db.transaction()):ref.update({'state':'blocked','playbackURL':self.fs.DELETE_FIELD});return
        if review.get('refreshCount',0)>=MAX_REFRESHES:ref.update({'state':'blocked','playbackURL':self.fs.DELETE_FIELD});return
        media=self.playback(record)
        uri=self.signed_playback(media)
        @self.fs.transactional
        def publish(tx):
            current=ref.get(transaction=tx).to_dict() or {}
            r=review_ref.get(transaction=tx).to_dict() or {}
            fresh=record_ref.get(transaction=tx).to_dict() or {}
            okay=(self.consent(tx,job['uid']) and self.consent(tx,record['uid']) and self.independent(tx,record['uid'],job['uid']))
            if current.get('state') not in ('preparing','refresh_requested') or r.get('status')!='assigned':return
            if not okay or fresh.get('status')!='saved' or r.get('refreshCount',0)>=MAX_REFRESHES:
                tx.update(ref,{'state':'blocked','playbackURL':self.fs.DELETE_FIELD});return
            tx.update(review_ref,{'refreshCount':r.get('refreshCount',0)+1})
            tx.update(ref,{'state':'assigned','playbackURL':uri,'expiresAt':datetime.now(timezone.utc)+timedelta(seconds=URL_SECONDS)})
        publish(self.db.transaction())

    def save_answer(self, ref):
        @self.fs.transactional
        def commit(tx):
            job=ref.get(transaction=tx).to_dict() or {}
            if job.get('state')!='submitted':return
            review_ref=self.db.document('pilotReviews/'+job['reviewId'])
            review=review_ref.get(transaction=tx).to_dict() or {}
            record_ref=self.db.document('pilotRecordings/'+review.get('recordingId','missing'))
            record=record_ref.get(transaction=tx).to_dict() or {}
            okay=self.consent(tx,job['uid']) and self.consent(tx,record.get('uid','missing')) and self.independent(tx,record.get('uid','missing'),job['uid'])
            text=job.get('text','').strip()
            if not okay or review.get('uid')!=job['uid'] or review.get('status')!='assigned' or record.get('uid')==job['uid'] or record.get('status')!='saved' or not 1<=len(text)<=1000:
                tx.update(ref,{'state':'blocked','playbackURL':self.fs.DELETE_FIELD});return
            answer={'reviewId':job['reviewId'],'uid':job['uid'],'text':text,'submittedAt':job['submittedAt'],
                    'status':'pending','mode':'test','quality':job.get('quality','not_sure')}
            tx.update(review_ref,{**answer,'exported':False})
            tx.update(record_ref,{'reviewResults':record.get('reviewResults',[])+[answer]})
            tx.update(ref,{'state':'pending','playbackURL':self.fs.DELETE_FIELD})
        commit(self.db.transaction())

    def export_answers(self):
        from google.cloud.firestore_v1.base_query import FieldFilter
        for snap in self.db.collection('pilotReviews').where(filter=FieldFilter('exported','==',False)).limit(9).stream():
            review=snap.to_dict()
            data={k:review[k] for k in ['reviewId','recordingId','uid','text','status','mode']}
            data['quality']=review.get('quality','not_sure')
            data['submittedAt']=review['submittedAt'].isoformat()
            self.put_json(self.raw,f"pilot/reviews/{snap.id}.json",data)
            snap.reference.update({'exported':True})

    def tick(self):
        super().tick()
        from google.cloud.firestore_v1.base_query import FieldFilter
        for snap in self.db.collection('reviewJobs').where(filter=FieldFilter('state','in',
                ['requested','preparing','refresh_requested','submitted'])).limit(9).stream():
            try:
                state=snap.to_dict()['state']
                if state=='requested':self.choose(snap.reference)
                elif state=='submitted':self.save_answer(snap.reference)
                else:self.grant_review(snap.reference)
            except Exception as exc:print('Review operation needs retry:',type(exc).__name__,flush=True)
        self.export_answers()

if __name__=='__main__':
    from worker_runtime import main
    main(ReviewWorker)
