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
    assess=commands.add_parser('assess-review',help='Record a fluent ASL adjudicator finding; does not bypass quorum')
    assess.add_argument('recording');assess.add_argument('review')
    assess.add_argument('--verdict',required=True,choices=('equivalent','different','unrelated'))
    assess.add_argument('--critical-dispute',required=True,choices=('resolved','unresolved'))
    assess.add_argument('--assessor',required=True,help='Auditable operator identity')
    assess.add_argument('--reason',required=True,help='Explain meaning, quality and negation/names/numbers/roles/timing checks')
    args=parser.parse_args()
    if hasattr(args,'reason') and not args.reason.strip():parser.error('A nonempty reason is required')
    if hasattr(args,'assessor') and not args.assessor.strip():parser.error('An assessor identity is required')
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
        elif args.command=='reject':
            ref=db.document('pilotRecordings/'+args.recording)
            record=ref.get(transaction=tx).to_dict() or {}
            if record.get('status')!='saved':raise ValueError('Only saved recordings can be adjudicated')
            if record.get('consensus',{}).get('status')=='approved':raise ValueError('Approved clips require a separate revocation and reward audit')
            tx.update(ref,{'corpusDisposition':'rejected','corpusRejectionReason':args.reason,'corpusAdjudicatedAt':datetime.now(timezone.utc)})
        else:
            from consensus import assessment_binding
            ref=db.document('pilotRecordings/'+args.recording)
            record=ref.get(transaction=tx).to_dict() or {}
            review=db.document('pilotReviews/'+args.review).get(transaction=tx).to_dict() or {}
            if record.get('status')!='saved' or review.get('status')!='pending':raise ValueError('Saved recording and submitted review required')
            if review.get('recordingId')!=args.recording or args.review not in [r['reviewId'] for r in record.get('reviewResults',[])]:raise ValueError('Review does not belong to recording')
            if record.get('consensus',{}).get('status')=='approved':raise ValueError('Approved clips require a separate revocation and reward audit')
            finding={'binding':assessment_binding(record,review),'verdict':args.verdict,
                     'criticalResolved':args.critical_dispute=='resolved','assessor':args.assessor.strip(),
                     'reason':args.reason.strip(),'createdAt':datetime.now(timezone.utc)}
            # Append-only private history; never overwrite the original interpretation.
            history=db.collection('meaningAssessmentHistory').document()
            tx.create(history,{'recordingId':args.recording,'reviewId':args.review,**finding})
            tx.update(ref,{'meaningAssessments':{**record.get('meaningAssessments',{}),args.review:finding}})
    apply(db.transaction())
    print('Private corpus policy updated. Worker will reconcile coverage on its next cycle.')

if __name__=='__main__':main()
