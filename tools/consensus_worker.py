"""Transactional test rewards; protected source answers never enter player views."""
import argparse
import time
from consensus import decide
from review_worker import ReviewWorker
from signing_worker import MAX_RECORDINGS,BATCH

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
            invites=self.identities(tx,uids)
            active={u:self.consent(tx,u) for u in uids}
            decision=decide(record,reviews,invites,active)
            if record.get('corpusDisposition')=='rejected':
                decision={**decision,'status':'rejected','signerPoints':0,'rewardReviewIds':[]}
            from corpus import counts, cap_for
            from google.cloud.firestore_v1.base_query import FieldFilter
            prompt=record.get('phrase',{}).get('id')
            coverage_ref=self.db.document('corpusCoverage/'+BATCH)
            coverage=coverage_ref.get(transaction=tx).to_dict() or {}
            policy=self.db.document('corpusPolicy/'+BATCH).get(transaction=tx).to_dict() or {}
            rows=[x.to_dict() for x in self.db.collection('pilotRecordings').where(filter=FieldFilter('phrase.id','==',prompt)).stream(transaction=tx)]
            self.identities(tx,[r['uid'] for r in rows],invites)
            from consensus import person_key
            person=person_key(record['uid'],invites)
            signer_ref=self.db.document('corpusSigners/'+person)
            signer=self.signer_cohort(tx,person,invites)
            # Existing approvals keep their place. New decisions cannot exceed the cap,
            # even when legacy data contains too many pending assignments.
            others=[r for r in rows if r.get('assignmentId')!=record.get('assignmentId')]
            if decision['status']=='approved' and record.get('consensus',{}).get('status')!='approved':
                duplicate=any(person_key(r['uid'],invites)==person and r.get('consensus',{}).get('status')=='approved' for r in others)
                if duplicate or counts(others,invites)['approved']>=cap_for(policy,prompt):
                    decision={**decision,'status':'collection_full','signerPoints':0}
            after=counts([*others,{**record,'consensus':decision}],invites)
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
            from moderation import prepare
            apply_moderation=prepare(self,tx,ref,record,decision,invites)
            # All reads precede all writes, including consent and reward deduplication.
            apply_moderation()
            if coverage.get(prompt)!=after:tx.set(coverage_ref,{**coverage,prompt:after})
            tx.set(signer_ref,signer)
            if record.get('corpusSplit')!=signer['split'] or record.get('corpusSignerId')!=person:
                tx.update(ref,{'corpusSplit':signer['split'],'corpusSignerId':person,'exportEligible':False})
            if record.get('consensus')!=decision:
                tx.update(ref,{'consensus':decision,'reviewLimit':decision['reviewLimit'],
                               'exportEligible':False,'consensusExported':False})
            if sj.get('assignmentId')==ref.id:
                tx.update(signer_job,{'approvedSigners':after['approved'],'signerCap':cap_for(policy,prompt)})
            summary={'status':decision['status'],'independentReviews':decision['independentReviews'],'requiredReviews':decision['reviewLimit']}
            if sj.get('assignmentId')==ref.id and sj.get('outcome')!=summary:tx.update(signer_job,{'outcome':summary})
            for job,j,r in jobs:
                if r['reviewId'] in decision['excludedReviews']:status='test_only' if decision['excludedReviews'][r['reviewId']]=='owner_or_test_account' else 'ineligible'
                elif r.get('reportReason') and decision['status']=='rejected':status='report_confirmed'
                elif r.get('reportReason') and decision['status']=='approved':status='report_not_upheld'
                elif r['reviewId'] in decision['rewardReviewIds']:status='approved'
                elif decision['status'] in ('approved','adjudication_required','quality_check_required'):status='adjudication_required'
                else:status='awaiting_reviews'
                outcome={'status':status,'independentReviews':decision['independentReviews'],'requiredReviews':decision['reviewLimit']}
                if j.get('outcome')!=outcome:tx.update(job,{'outcome':outcome})
            for event,uid,role,points in ledger:
                tx.create(event,{'uid':uid,'recordingId':ref.id,'role':role,'points':points,'mode':'test',
                                 'policyVersion':decision['version'],'createdAt':self.fs.SERVER_TIMESTAMP})
                wallet,value=wallets[uid]
                tx.set(wallet,{'points':value['points']+points,'mode':'test','updatedAt':self.fs.SERVER_TIMESTAMP})
            return record,reviews,invites,active,decision
        snapshot=commit(self.db.transaction())
        # Outside the transaction: shadow failures never change awards or cause retries.
        if snapshot:
            from rust_shadow import compare
            status=compare(*snapshot)
            if status!='disabled':print('Rust shadow:',status,flush=True)

    def export_decisions(self):
        from google.cloud.firestore_v1.base_query import FieldFilter
        import hashlib,json
        for snap in self.db.collection('pilotRecordings').where(filter=FieldFilter('consensusExported','==',False)).limit(MAX_RECORDINGS).stream():
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
        records=[s.to_dict() for s in self.db.collection('pilotRecordings').stream()]
        reviews=[s.to_dict() for s in self.db.collection('pilotReviews').stream()]
        # Page through registered players, including those without legacy invites.
        query=self.db.collection('players').order_by('__name__').limit(50)
        cursor=getattr(self,'_dashboard_cursor',None)
        if cursor:query=query.start_after(cursor)
        players=list(query.stream())
        self._dashboard_cursor=players[-1] if len(players)==50 else None
        uids={p.id for p in players}
        for record in records:uids.update([record['uid'],*record.get('reviewerIds',[])])
        invites=self.identities(None,uids)
        coverage=self.db.document('corpusCoverage/'+BATCH).get().to_dict() or {}
        policy=self.db.document('corpusPolicy/'+BATCH).get().to_dict() or {}
        reserved=(self.db.document('pilotLimits/'+BATCH).get().to_dict() or {}).get('reserved',0)
        for player in players:
            uid=player.id;profile=player.to_dict();invite=invites[uid]
            if (invite and invite.get('active') is not True) or profile.get('status')!='active' or profile.get('consentAccepted') is not True:continue
            activity=self.db.document('pilotActivity/'+uid).get().to_dict() or {}
            from consensus import person_key
            history=self.db.document('promptParticipants/'+person_key(uid,invites)).get().to_dict() or {}
            activity['signingPhraseIds']=list(set(activity.get('signingPhraseIds',[]))|set(history.get('meaningIds',[])))
            value=summary(uid,records,reviews,invites,activity,reserved,coverage,policy)
            sign=(self.db.document('signingJobs/'+uid).get().to_dict() or {}).get('state')
            review=(self.db.document('reviewJobs/'+uid).get().to_dict() or {}).get('state')
            value['signInProgress']=sign in ('requested','assigned','upload_requested','granting','uploading','submitted')
            value['reviewInProgress']=review in ('requested','preparing','assigned','refresh_requested','submitted')
            ref=self.db.document('playerDashboard/'+uid)
            previous=ref.get().to_dict() or {}
            from datetime import datetime,timezone
            updated=previous.pop('updatedAt',None)
            if previous!=value or updated is None or (datetime.now(timezone.utc)-updated).total_seconds()>=30:
                ref.set({**value,'updatedAt':self.fs.SERVER_TIMESTAMP})

    def tick(self):
        super().tick()
        from google.cloud.firestore_v1.base_query import FieldFilter
        query=self.db.collection('pilotRecordings').where(filter=FieldFilter('status','==','saved')).order_by('__name__').limit(25)
        if getattr(self,'_consensus_cursor',None):query=query.start_after(self._consensus_cursor)
        page=list(query.stream())
        self._consensus_cursor=page[-1] if len(page)==25 else None
        for snap in page:self.qualify(snap.reference)
        self.export_decisions()
        if time.monotonic()-getattr(self,'_dashboard_at',0)>60:
            self.publish_dashboards();self._dashboard_at=time.monotonic()

if __name__=='__main__':
    from worker_runtime import main
    main(ConsensusWorker)
