import unittest,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from consent_policy import POLICY,current,evidence
class ConsentPolicy(unittest.TestCase):
 def test_release_hashes_match_exact_published_documents(self):
  for item in POLICY['documents'].values():
   self.assertEqual(hashlib.sha256((ROOT/'web'/item['path'].lstrip('/')).read_bytes()).hexdigest(),item['sha256'])
  manifest={k:v for k,v in POLICY.items() if k!='bundleHash'}
  self.assertEqual(hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest(),POLICY['bundleHash'])
  self.assertIn(POLICY['bundleHash'],(ROOT/'firestore/firestore.rules').read_text())
  self.assertIn(POLICY['bundleHash'],(ROOT/'web/pilot-disclosure.mjs').read_text())
 def test_explicit_current_license_required_and_old_consent_not_upgraded(self):
  event={**POLICY,'action':'accepted','adultConfirmed':True,'publicDisplayAllowed':False}
  self.assertTrue(current(event))
  for changes in [{'adultConfirmed':False},{'action':'withdrawn'},{'bundleHash':'old'},{'disclosureVersion':'training-v1'},{'publicDisplayAllowed':True}]:self.assertFalse(current({**event,**changes}))
  self.assertEqual(evidence(event,'person','event')['consentPath'],'players/person/consents/event')
