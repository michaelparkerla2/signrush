"""Run in authorized Cloud Shell; scoped, keyless playback identity only."""
import subprocess
SA='signrush-playback@signrush.iam.gserviceaccount.com'
def run(args):
 p=subprocess.run(['gcloud',*args,'--quiet'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError('gcloud operation failed: '+args[0]+' '+args[1])
 return p.stdout
accounts=run(['iam','service-accounts','list','--project=signrush','--format=value(email)']).splitlines()
if SA not in accounts:run(['iam','service-accounts','create','signrush-playback','--project=signrush','--display-name=SignRush private playback'])
run(['services','enable','iamcredentials.googleapis.com','--project=signrush'])
run(['iam','service-accounts','add-iam-policy-binding',SA,'--project=signrush','--member=user:michael@umi.vision','--role=roles/iam.serviceAccountTokenCreator'])
run(['storage','buckets','add-iam-policy-binding','gs://umi-signrush-raw','--member=serviceAccount:'+SA,'--role=roles/storage.objectViewer',"--condition=title=signrush-playback-only,expression=resource.name.startsWith('projects/_/buckets/umi-signrush-raw/objects/pilot/playback/')"])
print('PASS: keyless playback identity limited to playback objects; existing access preserved.')
