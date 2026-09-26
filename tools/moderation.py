"""Transactional report consequences. Evidence and original rewards stay immutable."""
from consensus import person_key
VERSION='three-strikes-v1'


def prepare(worker, tx, ref, record, decision, identities):
    """Read all dependencies before the caller starts writing; return a write closure."""
    if decision.get('rejectionReason')!='unusable_video' or decision['status']!='rejected':return lambda:None
    event_ref=worker.db.document('moderationEvents/'+ref.id)
    if event_ref.get(transaction=tx).exists:return lambda:None
    uid=record['uid'];person=person_key(uid,identities)
    strike=decision.get('misconductConfirmed') is True
    members={uid};previous=set();moderation_ref=worker.db.document('accountModeration/'+person)
    if strike:
        # Include known reverse aliases, not just the account used for this upload.
        known={**identities,**{s.id:s.to_dict() for s in worker.db.collection('pilotInvites').stream(transaction=tx)}}
        members|={p for p in {*known,person} if person_key(p,known)==person}
        for member in members|{person}:
            state=worker.db.document('accountModeration/'+member).get(transaction=tx).to_dict() or {}
            previous.update(state.get('incidentIds',[]))
    incidents=previous|{ref.id} if strike else previous
    strikes=min(3,len(incidents)) if strike else 0
    cancelled=strike and strikes>=3
    award=worker.db.document(f'rewardEvents/{ref.id}-sign-{uid}').get(transaction=tx).to_dict() or {}
    accounts={};wallets={};deductions={}
    for member in members:
        player_ref=worker.db.document('players/'+member)
        player=player_ref.get(transaction=tx)
        accounts[member]=(player_ref,player.exists)
        wallet_ref=worker.db.document('playerRewards/'+member)
        wallet=wallet_ref.get(transaction=tx).to_dict() or {'points':0,'mode':'test'}
        if wallet.get('mode')!='test':raise ValueError('Non-test wallet requires a separate audited payout adapter')
        balance=wallet.get('points',0)
        if type(balance) is not int or balance<0:raise ValueError('Invalid reward balance')
        amount=balance if cancelled else min(balance,award.get('points',0)) if member==uid else 0
        deductions[member]=amount;wallets[member]=(wallet_ref,balance)
    evidence={'uid':uid,'person':person,'recordingId':ref.id,'policyVersion':VERSION,
              'mode':'test','kind':'misconduct_strike' if strike else 'quality_rejection','strikes':strikes,
              'reportIds':decision['unusableReportIds'],'spamReportIds':decision['spamReportIds'],
              'deductions':deductions,'cancelled':cancelled,'createdAt':worker.fs.SERVER_TIMESTAMP}
    def write():
        tx.create(event_ref,evidence)
        tx.update(ref,{'corpusDisposition':'rejected','corpusRejectionReason':'spam_not_signing' if strike else 'unusable_quality',
                       'corpusRejectedAt':worker.fs.SERVER_TIMESTAMP,'rightsRestricted':True,'exportEligible':False})
        if strike:
            tx.set(moderation_ref,{'incidentIds':sorted(incidents),'strikes':strikes,'blocked':cancelled,
                                   'updatedAt':worker.fs.SERVER_TIMESTAMP})
        for member in members:
            amount=deductions[member];wallet_ref,balance=wallets[member]
            if amount or cancelled:
                tx.set(wallet_ref,{'points':balance-amount,'mode':'test','updatedAt':worker.fs.SERVER_TIMESTAMP},merge=True)
                tx.delete(worker.db.document('leaderboard/'+member))
            if strike:
                tx.set(worker.db.document('playerModeration/'+member),{'strikes':strikes,'blocked':cancelled,
                        'lastRecordingId':ref.id,'lastDeduction':amount,'updatedAt':worker.fs.SERVER_TIMESTAMP})
            if cancelled:
                player_ref,exists=accounts[member]
                if exists:tx.update(player_ref,{'status':'cancelled','updatedAt':worker.fs.SERVER_TIMESTAMP})
    return write
