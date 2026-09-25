import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from dashboard import summary
class Dashboard(unittest.TestCase):
 def test_counts_exclude_self_and_exposure_and_preserve_history(self):
  records=[{'assignmentId':'a','uid':'me','status':'saved','phrase':{'id':'one'},'consensus':{}},
           {'assignmentId':'b','uid':'other','status':'saved','phrase':{'id':'one'},'technicalCheck':{'passed':True}}]
  d=summary('me',records,[],{}, {},299)
  self.assertEqual(d['submitted'],1);self.assertEqual(d['pending'],1);self.assertEqual(d['reviewAvailable'],0);self.assertEqual(d['signAvailable'],1)
  self.assertNotIn('phrase',str(d));self.assertNotIn('uid',d)
 def test_full_storage_reservations_show_no_signing_tasks(self):
  self.assertEqual(summary('me',[],[],{}, {},300)['signAvailable'],0)
if __name__=='__main__':unittest.main()
