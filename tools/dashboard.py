"""Sanitized, bounded pilot task summaries. No prompts or peer answers."""
from consensus import person_key
from review_worker import can_review
from signing_worker import PHRASES,MAX_TASKS,TARGET_SIGNERS

def summary(uid,records,reviews,invites,activity,reserved,coverage=None):
    own=[r for r in records if r.get('uid')==uid]
    mine=[r for r in reviews if r.get('uid')==uid and r.get('status')=='pending']
    exposed={r.get('phrase',{}).get('id') for r in own}|set(activity.get('signingPhraseIds',[]))|set(activity.get('reviewedPhraseIds',[]))
    available=[]
    for r in records:
        people={person_key(u,invites) for u in [r['uid'],*r.get('reviewerIds',[])]}
        if can_review(r,uid,exposed) and person_key(uid,invites) not in people:available.append(r)
    approved=sum(r.get('consensus',{}).get('status')=='approved' for r in own)
    pending=sum(r.get('status')=='saved' and r.get('consensus',{}).get('status') not in ('approved','test_only','participation_paused') for r in own)
    tests=0
    by_id={r['assignmentId']:r for r in records}
    for review in mine:
        decision=by_id.get(review.get('recordingId'),{}).get('consensus',{})
        if review['reviewId'] in decision.get('rewardReviewIds',[]):approved+=1
        elif review['reviewId'] in decision.get('excludedReviews',{}):tests+=1
        else:pending+=1
    return {'signAvailable':min(max(0,MAX_TASKS-reserved),sum(p['id'] not in exposed and (coverage or {}).get(p['id'],0)<TARGET_SIGNERS for p in PHRASES)),
            'reviewAvailable':len(available),'submitted':sum(r.get('status') in ('saved','failed') for r in own)+len(mine),
            'pending':pending,'approved':approved,'testTasks':tests,'mode':'test'}
