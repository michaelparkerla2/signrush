"""Open enrollment still preserves server-side eligibility and private summaries."""
from test_consensus_transactions import Qualification

class OpenEnrollment(Qualification):
 def test_uninvited_players_receive_dashboard_and_independent_test_rewards(self):
  self.answers()
  for uid in ['signer','r0','r1','r2']:
   self.db.document('pilotInvites/'+uid).delete()
  self.w.qualify(self.record)
  self.assertEqual(self.db.document('playerRewards/signer').get().to_dict()['points'],12)
  self.w.publish_dashboards()
  dashboard=self.db.document('playerDashboard/r0').get().to_dict()
  self.assertEqual(dashboard['approved'],1)
  self.assertNotIn('phrase',dashboard)
  self.assertNotIn('text',dashboard)
 def test_public_signer_can_receive_assignment_but_blocked_account_cannot(self):
  self.player('new-public')
  ref=self.db.document('signingJobs/new-public')
  ref.set({'uid':'new-public','state':'requested','requestedAt':self.w.fs.SERVER_TIMESTAMP})
  self.db.document('pilotInvites/new-public').delete()
  self.w.assign(ref)
  self.assertEqual(ref.get().to_dict()['state'],'assigned')
  self.player('blocked-public')
  blocked=self.db.document('signingJobs/blocked-public')
  blocked.set({'uid':'blocked-public','state':'requested','requestedAt':self.w.fs.SERVER_TIMESTAMP})
  self.db.document('pilotInvites/blocked-public').set({'active':False})
  self.w.assign(blocked)
  self.assertEqual(blocked.get().to_dict()['state'],'blocked')
