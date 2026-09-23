"""Cloud-only synthetic access test; never print bearer links or credentials."""
from datetime import timedelta
import secrets,subprocess,tempfile,time,hashlib
from pathlib import Path
import requests,google.auth
from google.auth.transport.requests import Request
from review_worker import ReviewWorker,PLAYBACK_SIGNER
from google.cloud import storage

def main():
 client=storage.Client(project='signrush');raw=client.bucket('umi-signrush-raw');held=client.bucket('umi-signrush-heldout-answers')
 rid=secrets.token_hex(16);key=f'pilot/playback/{rid}/silent-v1.mp4'
 with tempfile.TemporaryDirectory() as folder:
  path=Path(folder)/'test.mp4'
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=30','-t','2','-an','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True,capture_output=True)
  data=path.read_bytes()
 objects=[]
 try:
  for bucket,name,payload in [(raw,key,data),(raw,f'smoke-tests/review-{rid}/raw.mp4',data),(held,f'smoke-tests/review-{rid}/answer.json',b'{"synthetic":true}')]:
   blob=bucket.blob(name);blob.upload_from_string(payload,if_generation_match=0);objects.append(blob)
  w=ReviewWorker.__new__(ReviewWorker);w.raw=raw
  uri=w.signed_playback({'objectKey':key,'generation':str(objects[0].generation)})
  response=requests.get(uri,timeout=30);assert response.status_code==200 and hashlib.sha256(response.content).digest()==hashlib.sha256(data).digest()
  assert requests.get(uri,headers={'Range':'bytes=0-99'},timeout=20).status_code==206
  assert requests.get('https://storage.googleapis.com/umi-signrush-raw/'+key,timeout=20).status_code==403
  creds,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform']);creds.refresh(Request())
  def sign(blob,seconds):return blob.generate_signed_url(version='v4',expiration=timedelta(seconds=seconds),service_account_email=PLAYBACK_SIGNER,access_token=creds.token,method='GET')
  for blob in objects[1:]:assert requests.get(sign(blob,300),timeout=20).status_code==403
  expired=sign(objects[0],1);time.sleep(3);denied=requests.get(expired,timeout=20)
  assert denied.status_code==400 and '<Code>ExpiredToken</Code>' in denied.text
  print('PASS: private synthetic playback, range streaming, unsigned denial, raw/heldout isolation, expired-link denial; bytes:',len(data))
 finally:
  for blob in objects:blob.delete(if_generation_match=blob.generation)
try:main()
except Exception as exc:print('FAIL:',type(exc).__name__);raise SystemExit(1)
