"""Private corpus policy. Counts people, never uploads or reward points."""
import hashlib
from consensus import person_key

DEFAULT_CAP = 20
SPLITS = ('train', 'validation', 'test')


def split_for(person):
    # Fixed across prompts and runs. Never split clips from one person at random.
    bucket = int(hashlib.sha256(('signrush-signer-v1:' + person).encode()).hexdigest()[:8], 16) % 100
    return 'train' if bucket < 80 else ('validation' if bucket < 90 else 'test')


def cap_for(policy, prompt):
    value = policy.get('caps', {}).get(prompt, DEFAULT_CAP)
    if type(value) is not int or value not in (20, 30):
        raise ValueError('Corpus cap must be 20 or 30')
    return value


def counts(records, identities):
    approved, pending = set(), set()
    for r in records:
        uid = r['uid']; person = person_key(uid, identities)
        if identities.get(uid, {}).get('testOnly') or identities.get(person, {}).get('testOnly'):
            continue
        if r.get('corpusDisposition') == 'rejected':continue
        status = r.get('consensus', {}).get('status')
        if r.get('status') == 'saved' and status == 'approved' and r.get('technicalCheck', {}).get('passed') is True:
            approved.add(person)
        elif r.get('status') in ('assigned', 'reserved') or (r.get('status') == 'saved' and status not in ('rejected', 'test_only', 'participation_paused', 'collection_full')):
            # Unresolved human adjudication still holds a slot; it is NOT approval.
            pending.add(person)
    return {'approved': len(approved), 'pending': len(pending - approved)}


def available(value, cap):
    return value.get('approved', 0) + value.get('pending', 0) < cap


def training_eligible(record, signer):
    # Evidence is necessary, not sufficient: an exporter must also recheck current consent.
    from consent_policy import POLICY
    rights=record.get('rights') or {}
    licensed=(rights.get('rightsStatus')=='license_recorded'
              and rights.get('consentPath','').startswith('players/'+record.get('uid','')+'/consents/')
              and all(rights.get(k)==POLICY[k] for k in ('termsVersion','disclosureVersion','privacyVersion','bundleHash')))
    # All current test-mode records remain quarantined. Evaluation can NEVER train.
    return (licensed and not record.get('rightsRestricted',False) and signer.get('split') == 'train' and record.get('corpusSplit') == 'train'
            and record.get('mode') != 'test' and record.get('exportEligible') is True
            and record.get('consensus', {}).get('status') == 'approved')
