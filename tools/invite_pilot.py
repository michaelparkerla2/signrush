"""Add an explicitly authorized pilot login; never accept consent for its owner."""
import argparse
import os
import firebase_admin
from firebase_admin import auth
from google.cloud import firestore
p=argparse.ArgumentParser()
p.add_argument('email');p.add_argument('--name',required=True);p.add_argument('--same-person-as')
a=p.parse_args()
os.environ['GOOGLE_CLOUD_QUOTA_PROJECT']='signrush-login'
firebase_admin.initialize_app(options={'projectId':'signrush-login'})
try:
 try:user=auth.get_user_by_email(a.email)
 except auth.UserNotFoundError:user=auth.create_user(email=a.email,display_name=a.name,email_verified=False)
 if user.disabled:raise RuntimeError('Account is disabled')
 db=firestore.Client(project='signrush-login');ref=db.document('pilotInvites/'+user.uid)
 values={'active':True,'testOnly':True}
 if a.same_person_as:values['samePersonAs']=a.same_person_as
 ref.set(values,merge=True)
 assert ref.get().to_dict()['active'] is True
 print('PASS: pilot access enabled for',a.email,'; consent remains user-controlled; test-only account.')
except Exception as exc:
 print('FAILED:',type(exc).__name__);raise SystemExit(1)
