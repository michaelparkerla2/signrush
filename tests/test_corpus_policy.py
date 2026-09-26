import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from corpus import counts,cap_for,available,split_for,training_eligible
class CorpusPolicy(unittest.TestCase):
 def row(self,uid,status='approved'):
  return {'uid':uid,'status':'saved','technicalCheck':{'passed':True},'consensus':{'status':status}}
 def test_unique_approved_not_uploads(self):
  rows=[self.row('a'),self.row('a'),self.row('alias'),self.row('b','rejected'),self.row('c','awaiting_reviews')]
  self.assertEqual(counts(rows,{'alias':{'samePersonAs':'a'}}),{'approved':1,'pending':1})
 def test_unresolved_quality_is_not_approval(self):
  self.assertEqual(counts([self.row('a','quality_check_required'),self.row('b','adjudication_required')],{}),{'approved':0,'pending':2})
 def test_failed_rejected_test_accounts_never_fill_approved(self):
  rows=[{**self.row('a'),'status':'failed'},{**self.row('b'),'corpusDisposition':'rejected'},self.row('test')]
  self.assertEqual(counts(rows,{'test':{'testOnly':True}}),{'approved':0,'pending':0})
 def test_caps_and_pending_slots(self):
  self.assertEqual(cap_for({},'a'),20)
  self.assertFalse(available({'approved':19,'pending':1},20))
  self.assertTrue(available({'approved':20},cap_for({'caps':{'a':30}},'a')))
  for value in [True,0,21,500]:
   with self.assertRaises(ValueError):cap_for({'caps':{'a':value}},'a')
 def test_evaluation_cannot_train_and_current_test_mode_is_quarantined(self):
  from consent_policy import POLICY,evidence
  r={'uid':'person','rights':evidence(POLICY,'person','consent'),'corpusSplit':'train','exportEligible':True,'mode':'production','consensus':{'status':'approved'}}
  for split in ['validation','test']:self.assertFalse(training_eligible(r,{'split':split}))
  self.assertFalse(training_eligible({**r,'mode':'test'},{'split':'train'}))
  self.assertTrue(training_eligible(r,{'split':'train'}))
  self.assertFalse(training_eligible({**r,'rights':{}},{'split':'train'}))
  self.assertFalse(training_eligible({**r,'rightsRestricted':True},{'split':'train'}))
  self.assertEqual(split_for('person'),split_for('person'))
if __name__=='__main__':unittest.main()
