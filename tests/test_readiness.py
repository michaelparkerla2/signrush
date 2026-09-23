import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_readiness import assess
class Audit(unittest.TestCase):
 def test_reconciles_and_never_echoes_private_fields(self):
  event={'uid':'private-user','recordingId':'record','role':'sign','mode':'test','points':12}
  result=assess({'record-sign-private-user':event},{'private-user':{'points':12,'mode':'test'}},{'record':{'exportEligible':False,'phrase':'PRIVATE ANSWER'}},{'private-user':{'destination':'PRIVATE PAYEE'}})
  self.assertEqual(result['walletLedgerMismatches'],0)
  self.assertNotIn('PRIVATE',str(result));self.assertNotIn('private-user',str(result))
 def test_unbacked_balance_and_cash_mode_are_flagged(self):
  result=assess({}, {'u':{'points':5000,'mode':'cash'}},{'r':{'exportEligible':True}}, {'u':{'verified':True}})
  self.assertEqual(result['walletLedgerMismatches'],1)
  self.assertEqual(result['invalidTestWallets'],1)
  self.assertEqual(result['unexpectedExportEligible'],1)
  self.assertEqual(result['unexpectedPayoutFields'],1)
if __name__=='__main__':unittest.main()
