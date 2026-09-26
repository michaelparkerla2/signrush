"""Private operator controls; run by the hosting operator with existing ADC.
Never run this tool against production as part of a local development test.
"""
import argparse
from datetime import datetime, timezone


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    cap=commands.add_parser('set-cap')
    cap.add_argument('prompt');cap.add_argument('cap',type=int,choices=(20,30))
    reject=commands.add_parser('reject')
    reject.add_argument('recording');reject.add_argument('--reason',required=True)
    args=parser.parse_args()
    from google.cloud import firestore
    from signing_worker import PHRASES,BATCH
    db=firestore.Client(project=args.project)
    @firestore.transactional
    def apply(tx):
        if args.command=='set-cap':
            if args.prompt not in {p['id'] for p in PHRASES}:raise ValueError('Unknown prompt')
            ref=db.document('corpusPolicy/'+BATCH)
            policy=ref.get(transaction=tx).to_dict() or {}
            tx.set(ref,{**policy,'caps':{**policy.get('caps',{}),args.prompt:args.cap},'updatedAt':datetime.now(timezone.utc)})
        else:
            ref=db.document('pilotRecordings/'+args.recording)
            record=ref.get(transaction=tx).to_dict() or {}
            if record.get('status')!='saved':raise ValueError('Only saved recordings can be adjudicated')
            if record.get('consensus',{}).get('status')=='approved':raise ValueError('Approved clips require a separate revocation and reward audit')
            tx.update(ref,{'corpusDisposition':'rejected','corpusRejectionReason':args.reason,'corpusAdjudicatedAt':datetime.now(timezone.utc)})
    apply(db.transaction())
    print('Private corpus policy updated. Worker will reconcile coverage on its next cycle.')

if __name__=='__main__':main()
