"""Run in authorized Google Cloud Shell. Standard library only.

Writes synthetic fixtures only beneath smoke-tests/ in two fixed SignRush buckets.
Never changes IAM, billing, or held-out data. Never overwrites an existing object.
"""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API = "https://storage.googleapis.com"
RAW = "umi-signrush-raw"
EXPORTS = "umi-signrush-exports"
MAX_BYTES = 1_000_000


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Storage:
    def __init__(self):
        # Token remains inside Cloud Shell memory; never write or print it.
        self.token = subprocess.run(["gcloud","auth","print-access-token"],
            check=True,capture_output=True,text=True,timeout=60).stdout.strip()
        if not self.token:
            raise RuntimeError("Cloud Shell authorization required")

    def request(self, path, data=None, method="GET", headers=None, auth=True):
        if not path.startswith(("/storage/v1/", "/upload/storage/v1/")):
            raise ValueError("Only the Google Cloud Storage API is allowed")
        request_headers = dict(headers or {})
        if auth:
            request_headers["Authorization"] = "Bearer " + self.token
        with urlopen(Request(API+path,data=data,method=method,headers=request_headers),timeout=30) as response:
            content = response.read(MAX_BYTES+1)
            if len(content)>MAX_BYTES:
                raise RuntimeError("Response exceeds synthetic test bound")
            return response.status,content

    def object_path(self,bucket,key):
        if bucket not in (RAW,EXPORTS) or not key.startswith("smoke-tests/"):
            raise ValueError("Outside synthetic test scope")
        return f"/storage/v1/b/{bucket}/o/{quote(key,safe='')}"

    def metadata(self,bucket,key):
        return json.loads(self.request(self.object_path(bucket,key))[1])

    def read(self,bucket,key,generation):
        return self.request(self.object_path(bucket,key)+"?"+urlencode({"alt":"media","generation":generation}))[1]

    def put(self,bucket,key,data,mime):
        self.object_path(bucket,key)
        if len(data)>MAX_BYTES:
            raise ValueError("Synthetic upload too large")
        path=f"/upload/storage/v1/b/{bucket}/o?"+urlencode({"uploadType":"media","name":key,"ifGenerationMatch":0})
        try:
            metadata=json.loads(self.request(path,data,"POST",{"Content-Type":mime})[1])
        except HTTPError as error:
            if error.code!=412:
                raise
            metadata=self.metadata(bucket,key)
        remote=self.read(bucket,key,metadata["generation"])
        if digest(remote)!=digest(data):
            raise RuntimeError("Existing or uploaded object differs; refusing overwrite")
        return metadata,remote

    def copy(self,source_key,source_generation,target_key):
        source=self.object_path(RAW,source_key)
        target=self.object_path(EXPORTS,target_key).removeprefix("/storage/v1")
        path=source+"/rewriteTo"+target+"?"+urlencode({"ifGenerationMatch":0,"sourceGeneration":source_generation})
        try:
            response=json.loads(self.request(path,b"","POST")[1])
            if not response.get("done"):
                raise RuntimeError("Unexpected multi-step copy for a tiny fixture")
            return response["resource"]
        except HTTPError as error:
            if error.code!=412:
                raise
            return self.metadata(EXPORTS,target_key)


def verify(bundle):
    if bundle.get("synthetic") is not True or not re.fullmatch(r"smoke-[a-zA-Z0-9-]+",bundle.get("run","")):
        raise ValueError("Only explicitly synthetic smoke-test bundles are accepted")
    blobs={}
    for label in ("source","playback"):
        entry=bundle[label]
        if not re.fullmatch(r"[0-9a-f-]{36}\.mp4",entry["filename"]):
            raise ValueError("Unexpected synthetic filename")
        data=base64.b64decode(entry["base64"],validate=True)
        if not 0<len(data)<=MAX_BYTES or digest(data)!=entry["sha256"]:
            raise ValueError("Invalid fixture checksum or size")
        blobs[label]=data
    records=bundle["records"]
    if not isinstance(records,list) or len(records)!=1:
        raise ValueError("Exactly one synthetic record required")
    row=records[0]
    if (row["source_path"]!="media/"+bundle["source"]["filename"] or
        row["source_sha256"]!=digest(blobs["source"]) or "SYNTHETIC" not in row["reference"]):
        raise ValueError("Manifest does not match the synthetic media")
    client=Storage()
    bucket_settings={}
    for bucket in (RAW,EXPORTS):
        metadata=json.loads(client.request(f"/storage/v1/b/{bucket}")[1])
        iam=metadata["iamConfiguration"]
        if iam.get("publicAccessPrevention")!="enforced" or not iam["uniformBucketLevelAccess"]["enabled"]:
            raise RuntimeError("Expected private uniform bucket settings; no settings were changed")
        bucket_settings[bucket]={"public_access_prevention":"enforced","uniform_access":True}
    prefix="smoke-tests/"+bundle["run"]
    uploaded={}
    for label in ("source","playback"):
        key=prefix+"/raw/"+bundle[label]["filename"]
        metadata,remote=client.put(RAW,key,blobs[label],"video/mp4")
        uploaded[label]={"bucket":RAW,"key":key,"generation":metadata["generation"],
                         "sha256":digest(remote),"bytes":len(remote)}
    release_prefix=prefix+"/synthetic-release/"
    export_key=release_prefix+row["source_path"]
    copied=client.copy(uploaded["source"]["key"],uploaded["source"]["generation"],export_key)
    if digest(client.read(EXPORTS,export_key,copied["generation"]))!=row["source_sha256"]:
        raise RuntimeError("Exported media checksum differs")
    manifest_bytes=(json.dumps(records,indent=2)+"\n").encode()
    manifest_meta,_=client.put(EXPORTS,release_prefix+"records.json",manifest_bytes,"application/json")
    client.put(EXPORTS,release_prefix+"README.txt",
        b"SYNTHETIC SMOKE TEST ONLY. Not ASL. Exclude from all training and evaluation releases.\n",
        "text/plain")
    playback=uploaded["playback"]
    media_path=client.object_path(RAW,playback["key"])+"?"+urlencode({"alt":"media","generation":playback["generation"]})
    status,partial=client.request(media_path,headers={"Range":"bytes=0-1023"})
    if status!=206 or partial!=blobs["playback"][:1024]:
        raise RuntimeError("Authenticated video range read failed")
    try:
        client.request(media_path,auth=False)
    except HTTPError as error:
        if error.code not in (401,403):
            raise
        denied=error.code
    else:
        raise RuntimeError("Anonymous access unexpectedly succeeded")
    receipt={"synthetic":True,"run":bundle["run"],"status":"CLOUD_STORAGE_CHECKS_PASS",
        "objects":uploaded,"export":{"bucket":EXPORTS,"prefix":release_prefix,
            "records_generation":manifest_meta["generation"],"media_generation":copied["generation"]},
        "bucket_settings":bucket_settings,"anonymous_read_status":denied,
        "authenticated_range_read":True,"whole_source_sha256_matches":True,
        "cloud_copy_sha256_matches":True,"browser_playback":"not yet observed",
        "participant_authentication":"not implemented","heldout_access_test":"not performed"}
    client.put(EXPORTS,release_prefix+"storage-receipt.json",
               (json.dumps(receipt,indent=2)+"\n").encode(),"application/json")
    print(json.dumps(receipt,indent=2),flush=True)
    return blobs["playback"],manifest_bytes


def serve(video,records):
    page=b'''<!doctype html><meta charset="utf-8"><title>SignRush private media check</title>
    <style>body{font:20px system-ui;max-width:720px;margin:40px auto;background:#f5f7fa;color:#15283b}
    video{width:100%;border-radius:16px}strong{color:#a32626}</style>
    <h1>SignRush private media check</h1><p><strong>Synthetic test pattern. Not ASL or training data.</strong></p>
    <video controls playsinline preload="metadata" src="/video.mp4"></video>
    <p>This preview serves bytes read back from private cloud storage.</p>
    <p><a href="/records.json">View synthetic export record</a></p>'''
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assets={"/":(page,"text/html; charset=utf-8"),"/video.mp4":(video,"video/mp4"),
                    "/records.json":(records,"application/json")}
            if self.path not in assets:
                self.send_error(404); return
            data,mime=assets[self.path]
            start,end=0,len(data)-1
            status=200
            requested=self.headers.get("Range")
            if requested:
                match=re.fullmatch(r"bytes=(\d+)-(\d*)",requested)
                if not match:
                    self.send_error(416); return
                start=int(match[1]); end=min(int(match[2]) if match[2] else end,end)
                if start>end:
                    self.send_error(416); return
                status=206
            self.send_response(status)
            self.send_header("Content-Type",mime)
            self.send_header("Cache-Control","no-store")
            self.send_header("Accept-Ranges","bytes")
            self.send_header("Content-Length",str(end-start+1))
            if status==206:
                self.send_header("Content-Range",f"bytes {start}-{end}/{len(data)}")
            self.end_headers(); self.wfile.write(data[start:end+1])
        def log_message(self,*_):
            pass
    print("PRIVATE PREVIEW READY: Cloud Shell Web Preview on port 8080. Ctrl-C stops it.",flush=True)
    HTTPServer(("127.0.0.1",8080),Handler).serve_forever()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("bundle",type=Path)
    parser.add_argument("--serve",action="store_true")
    args=parser.parse_args()
    if args.bundle.stat().st_size>3_000_000:
        raise ValueError("Bundle too large")
    video,records=verify(json.loads(args.bundle.read_text()))
    if args.serve:
        serve(video,records)
