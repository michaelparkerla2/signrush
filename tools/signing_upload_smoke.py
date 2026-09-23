"""One tiny synthetic Cloud Shell upload; tokens and session URI never printed."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
from urllib.request import Request,urlopen
from google.cloud import storage
from signing_worker import technical_check,ORIGIN
with tempfile.TemporaryDirectory(prefix='signrush-upload-smoke-') as folder:
 path=Path(folder)/'synthetic.mp4'
 subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=30','-t','2','-an','-c:v','libx264','-preset','ultrafast','-movflags','+faststart',str(path)],check=True,timeout=30)
 payload=path.read_bytes();assert len(payload)<500000
 import secrets
 blob=storage.Client(project='signrush').bucket('umi-signrush-raw').blob('smoke-tests/signing-upload-'+secrets.token_hex(6)+'/synthetic.mp4')
 uri=blob.create_resumable_upload_session(content_type='video/mp4',size=len(payload),origin=ORIGIN,if_generation_match=0,timeout=30)
 req=Request(uri,method='OPTIONS',headers={'Origin':ORIGIN,'Access-Control-Request-Method':'PUT','Access-Control-Request-Headers':'content-type'})
 with urlopen(req,timeout=30) as r:assert r.headers.get('Access-Control-Allow-Origin') in ('*',ORIGIN)
 with urlopen(Request(uri,data=payload,method='PUT',headers={'Origin':ORIGIN,'Content-Type':'video/mp4'}),timeout=30) as r:
  assert r.status in (200,201);assert r.headers.get('Access-Control-Allow-Origin') in ('*',ORIGIN)
 blob.reload(timeout=30);got=blob.download_as_bytes(if_generation_match=int(blob.generation),timeout=30)
 assert hashlib.sha256(got).digest()==hashlib.sha256(payload).digest()
 assert technical_check(path)['passed']
 print('PASS: synthetic bounded upload, browser CORS headers, cloud hash, silent-video technical checks; bytes:',len(payload))
 print('Synthetic object:',blob.name)
