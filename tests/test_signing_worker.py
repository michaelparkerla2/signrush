import unittest
import sys
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.signing_worker import eligible,valid_upload,technical_check
class Checks(unittest.TestCase):
 def test_current_consent(self):
  invite={'active':True};p={'status':'active','mode':'test','consentAccepted':True};e={'action':'accepted','termsVersion':'terms-2026-09-26-v1','disclosureVersion':'commercial-2026-09-26-v1','privacyVersion':'privacy-2026-09-26-v1','bundleHash':'93843951df66917913dd0f08de8dbcd9fca94214ee8be9cf7c6c663d0b8c2da7','adultConfirmed':True,'publicDisplayAllowed':False}
  self.assertTrue(eligible(invite,p,e))
  self.assertTrue(eligible({},p,e))
  self.assertFalse(eligible({'active':False},p,e))
  self.assertFalse(eligible({'testOnly':True},p,e))
  for bad in [{**p,'status':'suspended'},{**p,'consentAccepted':False},{**p,'mode':'cash'}]:self.assertFalse(eligible(invite,bad,e))
  self.assertFalse(eligible(invite,p,{**e,'disclosureVersion':'old'}))
 def test_upload_bounds(self):
  good={'size':100,'mime':'video/webm','sha256':'a'*64};self.assertTrue(valid_upload(good))
  for bad in [{'size':True},{'size':8388609},{'size':0},{'mime':'audio/mp3'},{'sha256':'X'*64}]:self.assertFalse(valid_upload({**good,**bad}))
 def check(self,data):
  import json
  with patch('tools.signing_worker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(data).encode())):return technical_check('synthetic')
 def test_media_checks(self):
  data={'streams':[{'codec_type':'video','width':1280,'height':720}],'packets':[{'pts_time':'0','duration_time':'0.04'},{'pts_time':'2','duration_time':'0.04'}]}
  self.assertTrue(self.check(data)['passed'])
  self.assertFalse(self.check({**data,'streams':data['streams']+[{'codec_type':'audio'}]})['passed'])
  self.assertFalse(self.check({**data,'packets':[{'pts_time':'0'},{'pts_time':'40'}]})['passed'])
if __name__=='__main__':unittest.main()
