"""Versioned consent evidence. Older acceptance never grants this release retroactively."""
import json
from pathlib import Path
POLICY=json.loads((Path(__file__).resolve().parents[1]/'web/legal/manifest.json').read_text())

def current(event):
    return (event.get('action')=='accepted' and event.get('adultConfirmed') is True
            and all(event.get(k)==POLICY[k] for k in ('termsVersion','disclosureVersion','privacyVersion','bundleHash'))
            and event.get('publicDisplayAllowed') is False)

def evidence(event, uid, consent_id):
    return {'consentPath':f'players/{uid}/consents/{consent_id}',
            **{k:event[k] for k in ('termsVersion','disclosureVersion','privacyVersion','bundleHash')},
            'rightsStatus':'license_recorded','publicDisplayAllowed':False}
