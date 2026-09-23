"""Read-only aggregate audit. Never prints identities, answers or payout destinations.

Run with existing authorized ADC. Reads bounded snapshots, so a concurrent worker
can cause transient ledger mismatches; recheck while the worker is stopped.
"""
from collections import Counter
import json
MAX_DOCUMENTS=1000

def assess(events,wallets,records,preferences):
    totals=Counter();bad_events=0
    for key,event in events.items():
        uid=event.get('uid');points=event.get('points')
        expected=f"{event.get('recordingId')}-{event.get('role')}-{uid}"
        valid=(event.get('mode')=='test' and event.get('role') in ('sign','review') and isinstance(uid,str)
               and type(points) is int and points>0 and key==expected)
        if not valid:bad_events+=1;continue
        totals[uid]+=points
    mismatch=sum(wallets.get(uid,{}).get('points',0)!=totals[uid] for uid in set(wallets)|set(totals))
    unsafe_wallets=sum(w.get('mode')!='test' or type(w.get('points')) is not int or w.get('points',-1)<0 for w in wallets.values())
    return {'rewardEvents':len(events),'wallets':len(wallets),'invalidRewardEvents':bad_events,
            'walletLedgerMismatches':mismatch,'invalidTestWallets':unsafe_wallets,
            'recordings':len(records),'unexpectedExportEligible':sum(r.get('exportEligible') is True for r in records.values()),
            'savedPayoutPreferences':len(preferences),
            'unexpectedPayoutFields':sum(bool(set(p)-{'method','destination','usResident','version','updatedAt'}) for p in preferences.values()),
            'cashWorkflow':'not_implemented','auditIsReadOnly':True}

def main():
    from google.cloud import firestore
    db=firestore.Client(project='signrush-login')
    def read(name,fields):
        rows=list(db.collection(name).select(fields).limit(MAX_DOCUMENTS+1).stream())
        if len(rows)>MAX_DOCUMENTS:raise RuntimeError('Audit exceeds bounded sample; add pagination before claiming completeness')
        return {r.id:r.to_dict() for r in rows}
    # Avoid fetching payout destinations; count only non-sensitive metadata.
    report=assess(read('rewardEvents',['uid','recordingId','role','points','mode']),
                  read('playerRewards',['points','mode']),read('pilotRecordings',['exportEligible']),{})
    preferences=read('payoutPreferences',['method','version'])
    report['savedPayoutPreferences']=len(preferences)
    report.pop('unexpectedPayoutFields') # Projection cannot audit extra fields; rules tests cover this.
    report['invalidPayoutMetadata']=sum(p.get('method') not in ('paypal','venmo') or p.get('version')!=1 for p in preferences.values())
    print(json.dumps(report,sort_keys=True,indent=2))
if __name__=='__main__':main()
