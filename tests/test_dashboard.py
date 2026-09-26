import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from dashboard import summary
class Dashboard(unittest.TestCase):
 def test_counts_exclude_self_and_exposure_and_preserve_history(self):
  records=[{'assignmentId':'a','uid':'me','status':'saved','phrase':{'id':'one'},'consensus':{}},
           {'assignmentId':'b','uid':'other','status':'saved','phrase':{'id':'one'},'technicalCheck':{'passed':True}}]
  d=summary('me',records,[],{}, {},299)
  self.assertEqual(d['submitted'],1);self.assertEqual(d['pending'],1);self.assertEqual(d['reviewAvailable'],0);self.assertEqual(d['signAvailable'],200)
  self.assertNotIn('phrase',str(d));self.assertNotIn('uid',d)
 def test_historical_reservations_do_not_consume_approved_capacity(self):
  self.assertEqual(summary('me',[],[],{}, {},4000)['signAvailable'],200)
 def test_catalog_batch_is_marked_without_leaking_prompts(self):
  fresh=summary('me',[],[],{}, {},0,{})
  self.assertEqual(fresh['signAvailable'],200);self.assertEqual(fresh['catalogBatch'],'daily-use-v1');self.assertEqual(fresh['catalogSize'],200);self.assertNotIn('I need help',str(fresh))
if __name__=='__main__':unittest.main()
