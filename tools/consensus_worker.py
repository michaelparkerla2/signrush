"""Transactional test rewards; protected source answers never enter player views."""
import argparse
import time
from consensus import decide
from review_worker import ReviewWorker

class ConsensusWorker(ReviewWorker):
    def qualify(self, ref):
        @self.fs.transactional
        def commit(tx):
            record=ref.get(transaction=tx).to_dict() or {}
            if record.get('status')!='saved':return
            reviews=[]
            for answer in record.get('reviewResults',[]):
                r=self.db.document('pilotReviews/'+answer['reviewId']).get(transaction=tx).to_dict()
                if r:reviews.append(r)
            uids={record['uid']}|{r['uid'] for r in reviews}
            invites={u:(self.db.document('pilotInvites/'+u).get(transaction=tx).to_dict() or {}) for u in uids}
            active={u:self.consent(tx,u) for u in uids}
            decision=decide(record,reviews,invites,active)
            # Existing awards are immutable. Never manufacture a second award on retries.
            rewards=[]
            if decision['signerPoints']:
                rewards.append((record['uid'],'sign',decision['signerPoints']))
            for r in reviews:
                if r['reviewId'] in decision['rewardReviewIds']:rewards.append((r['uid'],'review',5))
            ledger=[];wallets={}
            for uid,role,points in rewards:
                event=self.db.document(f'rewardEvents/{ref.id}-{role}-{uid}')
                exists=event.get(transaction=tx).exists
                wallet=self.db.document('playerRewards/'+uid)
                value=wallet.get(transaction=tx).to_dict() or {'points':0,'mode':'test'}
                wallets[uid]=(wallet,value)
                if not exists:ledger.append((event,uid,role,points))
            signer_job=self.db.document('signingJobs/'+record['uid'])
            sj=signer_job.get(transaction=tx).to_dict() or {}
            jobs=[]
            for r in reviews:
                job=self.db.document('reviewJobs/'+r['uid']);j=job.get(transaction=tx).to_dict() or {}
                if j.get('reviewId')==r['reviewId']:jobs.append((job,j,r))
            # All reads precede all writes, including consent and reward deduplication.
            if record.get('consensus')!=decision:
                tx.update(ref,{'consensus':decision,'reviewLimit':decision['reviewLimit'],
                               'exportEligible':False,'consensusExported':False})
            summary={'status':decision['status'],'independentReviews':decision['independentReviews'],'requiredReviews':3}
            if sj.get('assignmentId')==ref.id and sj.get('outcome')!=summary:tx.update(signer_job,{'outcome':summary})
            for job,j,r in jobs:
                if r['reviewId'] in decision['excludedReviews']:status='test_only' if decision['excludedReviews'][r['reviewId']]=='owner_or_test_account' else 'ineligible'
                elif r['reviewId'] in decision['rewardReviewIds']:status='approved'
                elif decision['status'] in ('approved','adjudication_required','quality_check_required'):status='adjudication_required'
                else:status='awaiting_reviews'
                outcome={'status':status,'independentReviews':decision['independentReviews'],'requiredReviews':3}
                if j.get('outcome')!=outcome:tx.update(job,{'outcome':outcome})
            for event,uid,role,points in ledger:
                tx.create(event,{'uid':uid,'recordingId':ref.id,'role':role,'points':points,'mode':'test',
                                 'policyVersion':decision['version'],'createdAt':self.fs.SERVER_TIMESTAMP})
                wallet,value=wallets[uid]
                tx.set(wallet,{'points':value['points']+points,'mode':'test','updatedAt':self.fs.SERVER_TIMESTAMP})
        commit(self.db.transaction())

    def export_decisions(self):
        from google.cloud.firestore_v1.base_query import FieldFilter
        import hashlib,json
        for snap in self.db.collection('pilotRecordings').where(filter=FieldFilter('consensusExported','==',False)).limit(3).stream():
            record=snap.to_dict();decision=record['consensus']
            digest=hashlib.sha256(json.dumps(decision,sort_keys=True).encode()).hexdigest()[:24]
            self.put_json(self.raw,f'pilot/decisions/{snap.id}/{digest}.json',
                          {'recordingId':snap.id,'decision':decision,'exportEligible':False,'mode':'test'})
            @self.fs.transactional
            def mark(tx):
                fresh=snap.reference.get(transaction=tx).to_dict() or {}
                if fresh.get('consensus')==decision:tx.update(snap.reference,{'consensusExported':True})
            mark(self.db.transaction())

    def publish_dashboards(self):
        from dashboard import summary
        records=[s.to_dict() for s in self.db.collection('pilotRecordings').limit(3).stream()]
        reviews=[s.to_dict() for s in self.db.collection('pilotReviews').limit(15).stream()]
        # Page through registered players, including those without legacy invites.
        query=self.db.collection('players').order_by('__name__').limit(50)
        cursor=getattr(self,'_dashboard_cursor',None)
        if cursor:query=query.start_after(cursor)
        players=list(query.stream())
        self._dashboard_cursor=players[-1] if len(players)==50 else None
        uids={p.id for p in players}
        for record in records:uids.update([record['uid'],*record.get('reviewerIds',[])])
        invites={u:self.db.document('pilotInvites/'+u).get().to_dict() or {} for u in uids}
        reserved=(self.db.document('pilotLimits/signing-v1').get().to_dict() or {}).get('reserved',0)
        for player in players:
            uid=player.id;profile=player.to_dict();invite=invites[uid]
            if (invite and invite.get('active') is not True) or profile.get('status')!='active' or profile.get('consentAccepted') is not True:continue
            activity=self.db.document('pilotActivity/'+uid).get().to_dict() or {}
            value=summary(uid,records,reviews,invites,activity,reserved)
            sign=(self.db.document('signingJobs/'+uid).get().to_dict() or {}).get('state')
            review=(self.db.document('reviewJobs/'+uid).get().to_dict() or {}).get('state')
            value['signInProgress']=sign in ('requested','assigned','upload_requested','granting','uploading','submitted')
            value['reviewInProgress']=review in ('requested','preparing','assigned','refresh_requested','submitted')
            ref=self.db.document('playerDashboard/'+uid)
            if ref.get().to_dict()!=value:ref.set(value)

    def tick(self):
        super().tick()
        from google.cloud.firestore_v1.base_query import FieldFilter
        for snap in self.db.collection('pilotRecordings').where(filter=FieldFilter('status','==','saved')).limit(3).stream():
            self.qualify(snap.reference)
        self.export_decisions()
        if time.monotonic()-getattr(self,'_dashboard_at',0)>10:
            self.publish_dashboards();self._dashboard_at=time.monotonic()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=1800);a=p.parse_args()
    if not 1<=a.seconds<=1800:raise SystemExit('Maximum run is 1800 seconds')
    worker=ConsensusWorker();end=time.monotonic()+a.seconds
    print('Private signing, review and test-consensus worker ready.',flush=True)
    while time.monotonic()<end:
        try:worker.tick()
        except Exception as exc:print('Worker needs retry:',type(exc).__name__,flush=True)
        time.sleep(5)
    print('Pilot worker stopped.',flush=True)
