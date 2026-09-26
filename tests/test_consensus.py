import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from consensus import decide,normalize,assessment_binding
class Consensus(unittest.TestCase):
 def setUp(self):
  self.record={'uid':'signer','phrase':{'text':'Please close the window.'},'technicalCheck':{'passed':True,'durationSec':12.7}}
  self.reviews=[{'reviewId':str(i),'uid':'r'+str(i),'text':'Please close the window.','status':'pending','quality':'good'} for i in range(5)]
  self.invites={u:{} for u in ['signer',*[r['uid'] for r in self.reviews]]};self.active={u:True for u in self.invites}
 def decide(self,n=3):return decide(self.record,self.reviews[:n],self.invites,self.active)
 def test_three_matches_and_quality_award_bounded_points(self):
  d=self.decide();self.assertEqual(d['status'],'approved');self.assertEqual(d['signerPoints'],12);self.assertEqual(len(d['rewardReviewIds']),3)
 def test_negation_pronouns_numbers_order_not_erased(self):
  for text in ['Please do not close the window.','Please open the window.','Close two windows.','The window closes me.']:
   self.reviews[0]['text']=text;d=self.decide();self.assertEqual(d['status'],'needs_more_reviews');self.assertIsNone(d['referenceScores']['0'])
 def test_punctuation_case_equivalent_but_unknown_paraphrase_held(self):
  self.reviews[0]['text']='PLEASE close the window!';self.assertEqual(self.decide()['status'],'approved')
  self.reviews[0]['text']='Would you shut the window?';self.assertEqual(self.decide()['status'],'needs_more_reviews')
 def test_five_disagreements_stop(self):
  for r in self.reviews:r['text']='Different interpretation.'
  d=self.decide(5);self.assertEqual(d['status'],'adjudication_required');self.assertEqual(d['reviewLimit'],5);self.assertFalse(d['rewardReviewIds'])
 def test_known_owner_alias_and_test_accounts_never_count(self):
  self.invites['r0']={'samePersonAs':'signer'};self.invites['r1']={'testOnly':True}
  d=self.decide();self.assertEqual(d['independentReviews'],1);self.assertEqual(d['signerPoints'],0)
 def test_duplicate_people_and_withdrawal(self):
  self.invites['r0']={'samePersonAs':'r1'};self.assertEqual(self.decide()['independentReviews'],2)
  self.invites['r0']={};self.active['r0']=False;self.assertEqual(self.decide()['independentReviews'],2)
  self.active['signer']=False;self.assertEqual(self.decide()['status'],'participation_paused')
 def test_quality_missing_or_poor_prevents_signer_reward(self):
  for quality in [None,'poor','not_sure']:
   self.reviews[0]['quality']=quality;d=self.decide();self.assertEqual(d['signerPoints'],0);self.assertEqual(d['status'],'needs_more_reviews')
 def test_test_signer_no_rewards(self):
  self.invites['signer']={'testOnly':True};d=self.decide();self.assertEqual(d['status'],'test_only');self.assertFalse(d['rewardReviewIds'])
 def assess(self,i,verdict='equivalent',resolved=True):
  r=self.reviews[i]
  self.record.setdefault('meaningAssessments',{})[r['reviewId']]={'binding':assessment_binding(self.record,r),'verdict':verdict,'criticalResolved':resolved,'assessor':'expert','reason':'Fluent review of meaning and critical details'}
 def test_expanded_panel_needs_all_five_and_four_agreeing(self):
  self.record['reviewLimit']=5
  self.assertEqual(self.decide(3)['status'],'needs_more_reviews')
  self.assertEqual(self.decide(4)['status'],'needs_more_reviews')
  self.reviews[0]['text']='Unrelated response';self.assess(0,'unrelated')
  d=self.decide(5);self.assertEqual(d['status'],'approved');self.assertEqual(d['agreementCount'],4)
  self.assertEqual(d['threshold'],.8);self.assertEqual(d['independentReviews'],5)
  self.assertEqual(d['suspectedOutlierReviewIds'],['0']);self.assertFalse(d['excludedReviews'])
  self.assertNotIn('0',d['rewardReviewIds'])
 def test_three_of_five_never_approves(self):
  for i in [0,1]:self.reviews[i]['text']='Other meaning';self.assess(i,'different')
  self.assertEqual(self.decide(5)['status'],'adjudication_required')
 def test_four_matches_do_not_override_unresolved_critical_dissent(self):
  self.reviews[0]['text']='Please do not close the window.'
  self.assertEqual(self.decide(5)['status'],'adjudication_required')
  self.assess(0,'different',False)
  self.assertEqual(self.decide(5)['status'],'adjudication_required')
  self.assess(0,'different',True)
  self.assertEqual(self.decide(5)['status'],'approved')
 def test_human_verified_paraphrase_and_stale_finding(self):
  self.reviews[0]['text']='Shut the window, please.';self.assess(0)
  self.assertEqual(self.decide()['status'],'approved')
  self.reviews[0]['text']='Do not shut the window.'
  self.assertEqual(self.decide()['status'],'needs_more_reviews')
 def test_no_manufactured_consensus_after_excluding_review(self):
  self.record['reviewLimit']=5;self.invites['r0']={'testOnly':True}
  d=self.decide(5);self.assertEqual(d['status'],'adjudication_required');self.assertEqual(d['independentReviews'],4)
 def test_exact_text_critical_finding_blocks(self):
  self.assess(0,'equivalent',False)
  self.assertEqual(self.decide(5)['status'],'adjudication_required')
 def test_technical_failure_and_quality_do_not_earn_rewards(self):
  self.record['technicalCheck']['passed']=False
  d=self.decide();self.assertEqual(d['status'],'quality_check_required');self.assertFalse(d['rewardReviewIds'])
 def report(self,i,reason='not_signing'):
  self.reviews[i].update(text='',quality='poor',reportReason=reason)
 def test_three_spam_reports_reject_without_rewards(self):
  for i in range(3):self.report(i)
  d=self.decide();self.assertEqual(d['status'],'rejected');self.assertTrue(d['misconductConfirmed']);self.assertEqual(len(d['spamReportIds']),3);self.assertFalse(d['rewardReviewIds'])
 def test_quality_and_mixed_reports_reject_without_strikes(self):
  for i in range(3):self.report(i,'unusable_quality')
  self.assertFalse(self.decide()['misconductConfirmed']);self.assertEqual(self.decide()['status'],'rejected')
  self.report(0);self.report(1);self.assertFalse(self.decide()['misconductConfirmed'])
 def test_one_flag_cannot_reject_and_four_meanings_win(self):
  self.report(0)
  self.assertEqual(self.decide()['status'],'needs_more_reviews')
  self.assertEqual(self.decide(5)['status'],'approved')
 def test_self_alias_and_test_reports_cannot_create_strikes(self):
  for i in range(3):self.report(i)
  for identity in [{'samePersonAs':'signer'},{'testOnly':True},{'samePersonAs':'r1'}]:
   self.invites['r0']=identity;self.assertNotEqual(self.decide()['status'],'rejected')
 def test_established_three_meaning_consensus_prevents_automatic_reversal(self):
  for i in range(3):self.report(i)
  self.record['consensus']={'agreementCount':3,'status':'adjudication_required'}
  self.assertEqual(self.decide()['status'],'adjudication_required')
 def test_report_and_translation_cannot_be_mixed(self):
  for i in range(3):self.reviews[i]['reportReason']='not_signing'
  self.assertEqual(self.decide()['independentReviews'],0)
if __name__=='__main__':unittest.main()
