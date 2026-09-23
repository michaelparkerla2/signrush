"""Conservative pilot qualification. Exact normalized meaning is the only auto-score.
Unrecognized paraphrases require adjudication; word overlap is never ASL accuracy.
"""
import math
import re
import unicodedata
VERSION='exact-pilot-v1'
THRESHOLD=0.85
MAX_REVIEWS=5

def normalize(text):
    text=unicodedata.normalize('NFKC',text).casefold().replace('’',"'")
    # Preserve word order, negation, pronouns and numbers.
    return ' '.join(re.findall(r"\w+(?:'\w+)*",text))

def person_key(uid, invites):
    seen=set()
    while uid in invites and invites[uid].get('samePersonAs'):
        if uid in seen:return 'linked-cycle:'+min(seen)
        seen.add(uid);uid=invites[uid]['samePersonAs']
    return uid

def decide(record, reviews, invites, active):
    signer=record['uid'];owner=person_key(signer,invites)
    accepted=[];excluded={};seen={owner}
    for r in sorted(reviews,key=lambda x:x['reviewId']):
        uid=r['uid'];identity=person_key(uid,invites)
        if invites.get(uid,{}).get('testOnly') or identity==owner:reason='owner_or_test_account'
        elif not active.get(uid):reason='participation_paused'
        elif identity in seen:reason='duplicate_person'
        elif r.get('status')!='pending' or not r.get('text','').strip():reason='incomplete'
        else:reason=None
        if reason:excluded[r['reviewId']]=reason
        else:accepted.append(r);seen.add(identity)
    reference=normalize(record.get('phrase',{}).get('text',''))
    matched=[r for r in accepted if reference and normalize(r['text'])==reference]
    # Three exact matches also agree with each other. Unknown meanings get no score.
    scores={r['reviewId']:(1.0 if r in matched else None) for r in accepted}
    result={'version':VERSION,'threshold':THRESHOLD,'status':'awaiting_reviews',
            'independentReviews':len(accepted),'excludedReviews':excluded,'referenceScores':scores,
            'reviewLimit':3,'rewardReviewIds':[],'signerPoints':0,'reviewerPoints':5}
    if not active.get(signer):result['status']='participation_paused';return result
    if invites.get(signer,{}).get('testOnly'):result['status']='test_only';return result
    if len(matched)>=3:
        result['rewardReviewIds']=[r['reviewId'] for r in matched]
        quality=[r.get('quality') for r in matched]
        if record.get('technicalCheck',{}).get('passed') is not True:
            result['status']='quality_check_required'
        elif quality.count('good')>=3:
            seconds=record['technicalCheck'].get('durationSec')
            if isinstance(seconds,(int,float)) and not isinstance(seconds,bool) and math.isfinite(seconds) and 0.5<=seconds<=31:
                result['status']='approved';result['signerPoints']=min(30,max(1,math.floor(seconds)))
            else:result['status']='quality_check_required'
        else:result['status']='quality_check_required'
    elif len(accepted)>=3 or excluded:
        result['reviewLimit']=MAX_REVIEWS
        result['status']='needs_more_reviews'
        if len(reviews)>=MAX_REVIEWS:result['status']='adjudication_required'
    return result
