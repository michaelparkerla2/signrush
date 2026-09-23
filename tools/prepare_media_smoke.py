"""Generate a tiny non-ASL media fixture and exercise the real DB export function.

Does not authenticate, upload, run training, or inspect participant recordings.
Use an explicit installed FFmpeg path; no dependencies are downloaded.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run(argv):
    return subprocess.run([str(x) for x in argv], check=True, capture_output=True, text=True, timeout=60).stdout


def quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def probe(binary, path):
    return json.loads(run([binary, "-v", "error", "-show_format", "-show_streams", "-of", "json", path]))


def fingerprints(path):
    content = path.read_bytes()  # This generator bounds all media to <1 MB.
    return {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
            "md5_base64": base64.b64encode(hashlib.md5(content).digest()).decode()}


def prepare(ffmpeg, output):
    ffprobe = ffmpeg.with_name("ffprobe")
    output.mkdir(parents=True, exist_ok=False)
    raw = output / "raw"
    release = output / "synthetic-release"
    raw.mkdir()
    (release / "media").mkdir(parents=True)
    source_id, playback_id, clip_id = [str(uuid.uuid4()) for _ in range(3)]
    source = raw / f"{source_id}.mp4"
    playback = raw / f"{playback_id}.mp4"
    run([ffmpeg,"-v","error","-nostdin","-f","lavfi","-i","testsrc2=size=320x180:rate=30",
         "-t","3","-an","-c:v","libx264","-crf","30","-pix_fmt","yuv420p",
         "-metadata","comment=SYNTHETIC TEST PATTERN - NOT ASL - NOT TRAINING DATA",
         "-movflags","+faststart",source])
    run([ffmpeg,"-v","error","-nostdin","-i",source,"-an","-map_metadata","-1",
         "-c:v","copy","-movflags","+faststart",playback])
    for path in (source,playback):
        if path.stat().st_size > 1_000_000:
            raise RuntimeError("synthetic video exceeded size bound")
    info = probe(ffprobe,source)
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert not any(s["codec_type"] == "audio" for s in probe(ffprobe,playback)["streams"])
    source_hash = fingerprints(source)
    playback_hash = fingerprints(playback)

    spec = importlib.util.spec_from_file_location("signrush_smoke_db",ROOT / "tests/test_corpus.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ids = {key:str(uuid.uuid4()) for key in ("signer","collection","phrase","version","submission")}
    with module.TemporaryPostgres() as db:
        db.run(f"""
          INSERT INTO accounts(id,auth_subject) VALUES('{ids['signer']}','synthetic-smoke-only');
          INSERT INTO consent_events(account_id,action,terms_version,disclosure_version)
            VALUES('{ids['signer']}','accepted','synthetic-no-person','synthetic-no-person');
          INSERT INTO phrase_collections VALUES('{ids['collection']}','Synthetic smoke test');
          INSERT INTO phrases VALUES('{ids['phrase']}','{ids['collection']}',true);
          INSERT INTO phrase_versions(id,phrase_id,version,english_prompt,intended_meaning,source,reuse_terms,review_status)
            VALUES('{ids['version']}','{ids['phrase']}',1,'Show a moving test pattern.',
                   'Technical media fixture, not ASL.','generated test pattern','synthetic test only','draft');
          DO $$ DECLARE a uuid; BEGIN
            a := assign_signing('{ids['signer']}','{ids['version']}',0);
            INSERT INTO submissions(id,assignment_id,signer_id,state)
              VALUES('{ids['submission']}',a,'{ids['signer']}','approved');
          END $$;
          INSERT INTO media_assets(id,submission_id,kind,bucket,object_key,object_generation,sha256,
            byte_count,mime_type,duration_seconds,width,height,fps,audio_present)
            VALUES('{source_id}','{ids['submission']}','original','umi-signrush-raw',
              {quote('smoke-tests/' + output.name + '/raw/' + source.name)},'staged-not-yet-uploaded',
              '{source_hash['sha256']}',{source_hash['bytes']},'video/mp4',3,320,180,30,false);
          INSERT INTO clips VALUES('{clip_id}','{ids['submission']}','{source_id}',0.5,2.5,'verified');
          INSERT INTO annotations(clip_id,version,english_meaning,provenance,status,fingerspelling_status)
            VALUES('{clip_id}',1,'SYNTHETIC TEST PATTERN — NOT ASL.',
              'Synthetic media smoke test; not a linguistic annotation','approved','reviewed');
          INSERT INTO corpus_membership(submission_id,status,reason)
            VALUES('{ids['submission']}','approved','Synthetic plumbing fixture only');
        """)
        records = json.loads(db.run("SELECT training_manifest();").stdout)
        assert len(records) == 1
    # Hardlink the tiny generated file, avoiding duplicate local media bytes.
    os.link(source,release / records[0]["source_path"])
    (release / "records.json").write_text(json.dumps(records,indent=2) + "\n")
    (release / "README.txt").write_text(
        "SYNTHETIC SMOKE TEST ONLY. Not ASL, not training/evaluation data.\n"
        "No partition, lane, or generalization has been assigned.\n"
        "The source_path is relative to this release directory.\n")
    # Exercise the precise FFmpeg clip settings found in the user's extractor.
    # Do not import that extractor: importing it starts the model-training workflow.
    with tempfile.TemporaryDirectory(prefix="signrush-clip-") as temp:
        extracted = Path(temp) / "interval.mp4"
        row = records[0]
        run([ffmpeg,"-v","error","-nostdin","-ss",str(row["start_time_sec"]),"-i",source,
             "-t",str(row["end_time_sec"]-row["start_time_sec"]),
             "-vf",r"fps=30,scale=-2:min(720\,ih)","-an","-c:v","libx264","-crf","23",
             "-pix_fmt","yuv420p",extracted])
        extracted_info = probe(ffprobe,extracted)
        video = next(s for s in extracted_info["streams"] if s["codec_type"] == "video")
        assert video["r_frame_rate"] == "30/1" and video["height"] <= 720
        assert abs(float(extracted_info["format"]["duration"])-2) < 0.1
        assert all(s["codec_type"] != "audio" for s in extracted_info["streams"])
    receipt = {"synthetic":True,"status":"LOCAL_PREPARED_CLOUD_NOT_YET_VERIFIED", "run":output.name,
        "source": {"filename":source.name,**source_hash},
        "playback": {"filename":playback.name,**playback_hash},
        "local_checks":{"postgres_manifest":True,"source_path_resolves":True,
            "whole_source_sha256_matches":True,"interval_extraction":True,
            "output_30fps":True,"output_height_lte_720":True,"output_silent":True},
        "source_dimensions":[stream["width"],stream["height"]],"source_duration_seconds":3,
        "cloud_checks":{},"cloud_generation":"must be read from uploaded object before cloud verification"}
    (output / "local-receipt.json").write_text(json.dumps(receipt,indent=2) + "\n")
    print(json.dumps({"output":str(output),**receipt},indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args = parser.parse_args()
    prepare(args.ffmpeg.resolve(),args.output.resolve())
