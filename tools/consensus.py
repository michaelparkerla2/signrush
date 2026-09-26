"""Meaning-panel qualification. Exact normalized text is the only automatic match.
Unrecognized paraphrases require adjudication; word overlap is never ASL accuracy.
"""
import hashlib
import json
import math
import re
import unicodedata
VERSION='meaning-panel-v3'
MAX_REVIEWS=5
REPORT_REASONS=('not_signing','unusable_quality')

def valid_report(review):
    return (review.get('reportReason') in REPORT_REASONS and not review.get('text','').strip()
            and review.get('quality')=='poor')

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
        if invites.get(uid,{}).get('testOnly') or invites.get(identity,{}).get('testOnly') or identity==owner:reason='owner_or_test_account'
        elif not active.get(uid):reason='participation_paused'
        elif identity in seen:reason='duplicate_person'
        elif r.get('status')!='pending' or (not valid_report(r) and (r.get('reportReason') or not r.get('text','').strip())):reason='incomplete'
        else:reason=None
        if reason:excluded[r['reviewId']]=reason
        else:accepted.append(r);seen.add(identity)
    reference=normalize(record.get('phrase',{}).get('text',''))
    matched=[];unresolved=[];outliers=[]
    reports=[r for r in accepted if valid_report(r)]
    spam=[r for r in reports if r['reportReason']=='not_signing']
    scores={}
    for r in accepted:
        rid=r['reviewId']
        if valid_report(r):
            scores[rid]=None;continue
        exact=bool(reference) and normalize(r['text'])==reference
        scores[rid]=1.0 if exact else None  # Text match only, never semantic accuracy.
        assessment=record.get('meaningAssessments',{}).get(rid,{})
        valid=(assessment.get('binding')==assessment_binding(record,r)
               and assessment.get('verdict') in ('equivalent','different','unrelated')
               and bool(assessment.get('assessor')) and bool(assessment.get('reason')))
        if valid:
            equivalent=assessment['verdict']=='equivalent'
            if assessment.get('criticalResolved') is not True:unresolved.append(rid)
            if assessment['verdict']=='unrelated':outliers.append(rid)
        else:
            equivalent=exact
            if not exact:unresolved.append(rid)
        if equivalent and r.get('quality')=='good':matched.append(r)
    # Expansion is sticky: later adjudication cannot shrink a five-person panel.
    expanded=(record.get('reviewLimit',3)==5 or len(reviews)>3
              or record.get('consensus',{}).get('reviewLimit')==5
              or bool(excluded) or (len(accepted)>=3 and (len(matched)<3 or unresolved)))
    panel=5 if expanded else 3
    required=4 if expanded else 3
    result={'version':VERSION,'threshold':required/panel,'status':'awaiting_reviews',
            'independentReviews':len(accepted),'excludedReviews':excluded,'referenceScores':scores,
            'reviewLimit':panel,'requiredAgreement':required,'agreementCount':len(matched),
            'agreementFraction':len(matched)/len(accepted) if accepted else 0,
            'unresolvedMeaningReviewIds':unresolved,'suspectedOutlierReviewIds':outliers,
            'rewardReviewIds':[],'signerPoints':0,'reviewerPoints':5,
            'unusableReportIds':[r['reviewId'] for r in reports],
            'spamReportIds':[r['reviewId'] for r in spam],
            'misconductConfirmed':False}
    if not active.get(signer):result['status']='participation_paused';return result
    if invites.get(signer,{}).get('testOnly') or invites.get(owner,{}).get('testOnly'):
        result['status']='test_only';return result
    # Reports are independent panel votes, never fabricated translations.
    # Never reverse an established meaning consensus through automatic flag handling.
    previous=record.get('consensus',{})
    if len(reports)>=3 and len(accepted)<=MAX_REVIEWS and len(matched)<3:
        if previous.get('status')=='approved' or previous.get('agreementCount',0)>=3:
            result['status']='adjudication_required';return result
        result.update(status='rejected',rejectionReason='unusable_video',misconductConfirmed=len(spam)>=3)
        return result
    if len(accepted)<panel:
        result['status']='needs_more_reviews' if expanded else 'awaiting_reviews'
        if len(reviews)>=MAX_REVIEWS:result['status']='adjudication_required'
        return result
    if len(accepted)!=panel or len(matched)<required or unresolved:
        result['status']='adjudication_required';return result
    seconds=record.get('technicalCheck',{}).get('durationSec')
    if (record.get('technicalCheck',{}).get('passed') is not True
        or isinstance(seconds,bool) or not isinstance(seconds,(int,float))
        or not math.isfinite(seconds) or not 0.5<=seconds<=31):
        result['status']='quality_check_required';return result
    result['status']='approved'
    result['signerPoints']=min(30,max(1,math.floor(seconds)))
    result['rewardReviewIds']=[r['reviewId'] for r in matched]
    return result


def assessment_binding(record, review):
    """Invalidate expert findings if the original answer, quality or prompt changes."""
    value={'phrase':record.get('phrase'), 'reviewId':review['reviewId'],
           'uid':review['uid'], 'text':review.get('text'), 'quality':review.get('quality')}
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
