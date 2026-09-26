import json,unittest
from pathlib import Path
class DailyPrompts(unittest.TestCase):
 def test_stable_original_meanings_and_versions(self):
  rows=json.loads((Path(__file__).resolve().parents[1]/'data/pilot-phrases.json').read_text())
  self.assertEqual([r['id'] for r in rows],[f'DAILY-{i:03}' for i in range(1,201)])
  self.assertTrue(all(r['version']==1 and r['domain']=='daily_use' and r['meaningId']==r['id'] for r in rows))
  self.assertEqual(len({r['text'] for r in rows}),200)
  self.assertEqual(rows[8]['text'],'I understand.')
  self.assertEqual(rows[9]['text'],'I do not understand.')
  self.assertEqual(rows[29]['text'],'Thank you for helping me.')
if __name__=='__main__':unittest.main()
