"""Cloud Shell only: verify/create the single authorized pilot invitation."""
import json
import subprocess
import urllib.request
import urllib.error

PROJECT = 'signrush-login'
UID = 'F5lF7niFU8Oy6JMsMSEgKRAChKY2'
base = f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents'
token = subprocess.check_output(['gcloud', 'auth', 'print-access-token'], text=True).strip()

def request(path, payload=None):
    headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
    req = urllib.request.Request(base + path, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

try:
    invite = request('/pilotInvites/' + UID)
except urllib.error.HTTPError as exc:
    if exc.code != 404:
        raise SystemExit(f'Invitation lookup failed: HTTP {exc.code}')
    invite = request('/pilotInvites?documentId=' + UID, {'fields': {'active': {'booleanValue': True}}})
assert invite['fields']['active']['booleanValue'] is True
print('Authorized pilot invitation active: verified from cloud')
try:
    profile = request('/players/' + UID)
    print('Player profile:', json.dumps(profile.get('fields', {})))
except urllib.error.HTTPError as exc:
    print('Player profile HTTP:', exc.code)
try:
    with urllib.request.urlopen(base + '/pilotInvites/' + UID, timeout=30):
        raise SystemExit('FAIL: unauthenticated invitation read succeeded')
except urllib.error.HTTPError as exc:
    assert exc.code in (401, 403), exc.code
    print('Unauthenticated invitation read denied:', exc.code)
