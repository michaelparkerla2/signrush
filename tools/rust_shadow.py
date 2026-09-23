"""Opt-in, comparison-only bridge; never makes or changes a production decision.

Private inputs travel only over local subprocess stdin. Never log payloads,
answers, identifiers, differences or subprocess output. Disabled by default.
"""
import json
import math
import os
from pathlib import Path
import subprocess
import unicodedata
from consensus import normalize

PROTOCOL='signrush-shadow-v1'
NORMALIZATION='python-nfkc-casefold-word-v1'

def payload(record,reviews,invites,active):
    seconds=record.get('technicalCheck',{}).get('durationSec')
    if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds):seconds=None
    uids=set(invites)|set(active)|{record['uid']}|{r['uid'] for r in reviews}
    return {'protocol':PROTOCOL,'normalization':NORMALIZATION,'unicode_version':unicodedata.unidata_version,
        'input':{'signer_uid':record['uid'],'normalized_reference':normalize(record.get('phrase',{}).get('text','')),
                 'technical_passed':record.get('technicalCheck',{}).get('passed') is True,'duration_seconds':seconds},
        'identities':{uid:{'same_person_as':invites.get(uid,{}).get('samePersonAs') or None,
                           'test_only':bool(invites.get(uid,{}).get('testOnly')),'active':bool(active.get(uid))} for uid in uids},
        'reviews':[{'id':r['reviewId'],'uid':r['uid'],'pending':r.get('status')=='pending','text_present':bool(r.get('text','').strip()),
                    'normalized_text':normalize(r.get('text','')),'quality_good':r.get('quality')=='good'} for r in reviews]}

def compare(record,reviews,invites,active,expected,*,executable=None,timeout=1.0):
    """Return only disabled/match/mismatch/unavailable; fail open to Python.

    A failed shadow is not an approval. Python's original result remains authoritative.
    """
    executable=executable or os.environ.get('SIGNRUSH_RUST_SHADOW_BIN')
    if not executable:return 'disabled'
    try:
        if not Path(executable).is_absolute():return 'unavailable'
        encoded=json.dumps(payload(record,reviews,invites,active),ensure_ascii=False,allow_nan=False).encode()
        if len(encoded)>262144:return 'unavailable'
        completed=subprocess.run([executable],input=encoded,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                 timeout=timeout,check=True)
        actual=json.loads(completed.stdout)
        return 'match' if actual==expected else 'mismatch'
    except Exception:
        return 'unavailable'
