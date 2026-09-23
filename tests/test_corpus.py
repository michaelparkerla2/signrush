"""Small, isolated PostgreSQL integration tests. No cloud or media downloads."""
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DB = None


def uid(number):
    return f"00000000-0000-0000-0000-{number:012d}"


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


class TemporaryPostgres:
    def __enter__(self):
        for executable in ("initdb", "pg_ctl", "psql"):
            if not shutil.which(executable):
                raise RuntimeError(f"{executable} is required; no software is installed automatically")
        self.tmp = tempfile.TemporaryDirectory(prefix="signrush-test-")
        self.root = Path(self.tmp.name)
        self.data = self.root / "pgdata"
        self.started = False
        try:
            subprocess.run(["initdb", "-D", str(self.data), "-U", "signrush_test", "-A", "trust", "--no-locale"],
                           check=True, capture_output=True, text=True)
            # Private temp directory, Unix socket only; never contacts the existing server.
            options = f"-F -k {self.root} -h '' -p 55439 -c shared_buffers=8MB -c max_connections=20"
            subprocess.run(["pg_ctl", "-D", str(self.data), "-l", str(self.root / "postgres.log"),
                            "-o", options, "-w", "start"], check=True, capture_output=True, text=True)
            self.started = True
            self.run((ROOT / "db/migrations/001_corpus_pilot.sql").read_text())
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def run(self, sql, check=True):
        command = ["psql", "-X", "--no-password", "-h", str(self.root), "-p", "55439",
                   "-U", "signrush_test", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-Atq"]
        result = subprocess.run(command, input="SET search_path=signrush,pg_catalog;\n" + sql,
                                capture_output=True, text=True, timeout=20)
        if check and result.returncode:
            raise AssertionError(result.stderr)
        return result

    def __exit__(self, *_):
        if self.started:
            # Do not delete the data directory if stopping the private server fails.
            subprocess.run(["pg_ctl", "-D", str(self.data), "-m", "immediate", "-w", "stop"],
                           check=True, capture_output=True, text=True)
        self.tmp.cleanup()


class CorpusTests(unittest.TestCase):
    def sql(self, sql):
        return DB.run(sql).stdout.strip()

    def reject(self, sql, message):
        result = DB.run(sql, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)

    def setUp(self):
        # Only operates on the private disposable database created by this script.
        self.sql("TRUNCATE accounts, phrase_collections RESTART IDENTITY CASCADE;")
        self.sql(f"""
            INSERT INTO accounts(id,auth_subject)
              SELECT ('00000000-0000-0000-0000-' || lpad(n::text,12,'0'))::uuid,
                     'synthetic-player-' || n FROM generate_series(1,14) n;
            INSERT INTO consent_events(account_id,action,terms_version,disclosure_version)
              SELECT id,'accepted','synthetic-terms-v1','synthetic-disclosure-v1' FROM accounts;
            INSERT INTO phrase_collections VALUES('{uid(90)}','Synthetic everyday');
            INSERT INTO phrases VALUES('{uid(100)}','{uid(90)}',true);
            INSERT INTO phrase_versions(id,phrase_id,version,english_prompt,intended_meaning,source,reuse_terms,review_status)
              VALUES('{uid(101)}','{uid(100)}',1,'I need to change my appointment to tomorrow.',
                     'Reschedule the appointment for tomorrow.','synthetic fixture','test only','draft');
            DO $$ DECLARE a uuid; BEGIN
              a := assign_signing('{uid(1)}','{uid(101)}',20);
              INSERT INTO submissions(id,assignment_id,signer_id,state)
                VALUES('{uid(201)}',a,'{uid(1)}','awaiting_reviews');
              UPDATE signing_assignments SET state='submitted' WHERE id=a;
            END $$;
            INSERT INTO media_assets(id,submission_id,kind,bucket,object_key,object_generation,sha256,
              byte_count,mime_type,duration_seconds,width,height,fps,audio_present,derived_from_asset_id)
              VALUES('{uid(301)}','{uid(201)}','original','synthetic-only','opaque-original.webm','1',
                     repeat('a',64),100,'video/webm',12,640,480,30,false,NULL),
                    ('{uid(302)}','{uid(201)}','silent_playback','synthetic-only','opaque-playback.mp4','1',
                     repeat('b',64),80,'video/mp4',12,640,480,30,false,'{uid(301)}');
            INSERT INTO clips VALUES('{uid(401)}','{uid(201)}','{uid(301)}',1,11,'verified');
        """)

    def claim(self, account):
        return self.sql(f"SELECT claim_validation('{uid(account)}','{uid(201)}',5);")

    def approve_fixture(self):
        # A synthetic human-review decision, deliberately NOT an ASL scoring model.
        self.sql(f"""
            INSERT INTO quality_checks(submission_id,rule,outcome,checker_version)
              VALUES('{uid(201)}','fixture_quality','pass','synthetic-reviewer-v1');
            INSERT INTO scoring_runs(submission_id,algorithm_version,input_snapshot,pairwise_scores,
              prompt_fidelity_scores,decision)
              VALUES('{uid(201)}','synthetic-reviewer-v1','{{"synthetic":true}}','[]','[]','approved');
            INSERT INTO annotations(id,clip_id,version,english_meaning,provenance,status,fingerspelling_status)
              VALUES('{uid(501)}','{uid(401)}',1,'Please reschedule my appointment for tomorrow.',
                     'Synthetic reviewed annotation v1','approved','unknown');
            UPDATE submissions SET state='approved' WHERE id='{uid(201)}';
            INSERT INTO corpus_membership(submission_id,status,reason)
              VALUES('{uid(201)}','approved','Synthetic reviewed fixture');
        """)

    def manifest(self):
        return json.loads(self.sql("SELECT training_manifest();"))

    def test_blind_round_to_compatible_export(self):
        for account in (2, 3, 4):
            assignment = self.claim(account)
            payload = json.loads(self.sql(f"SELECT validation_payload('{uid(account)}','{assignment}');"))
            self.assertEqual(set(payload), {"assignment_id", "reward_points", "mode", "media"})
            self.assertEqual(payload["media"]["object_key"], "opaque-playback.mp4")
            self.assertNotIn("appointment", json.dumps(payload))
            text = quote("Please reschedule my appointment for tomorrow.")
            self.sql(f"SELECT submit_interpretation('{uid(account)}','{assignment}',{text});")
        self.assertEqual(self.sql("SELECT count(*) FROM interpretations;"), "3")
        self.assertEqual(self.manifest(), [])  # Consensus alone cannot approve training truth.
        self.approve_fixture()
        records = self.manifest()
        self.assertEqual(len(records), 1)
        row = records[0]
        self.assertEqual(row["eng"], "Please reschedule my appointment for tomorrow.")
        self.assertEqual(row["reference"], row["eng"])
        self.assertEqual(row["source_sha256"], "a" * 64)
        self.assertEqual(row["source_path"], f"media/{uid(301)}.webm")
        self.assertEqual(row["end_time_sec"] - row["start_time_sec"], 10)
        self.assertEqual(row["signer"], 1)
        self.assertNotIn("partition", row)
        self.assertNotIn("lane", row)
        self.assertEqual(records, self.manifest())

    def test_self_and_exposed_validators_rejected(self):
        self.reject(f"SELECT claim_validation('{uid(1)}','{uid(201)}',5);", "self validation")
        self.sql(f"SELECT expose_phrase('{uid(2)}','{uid(100)}','skipped_signing_prompt');")
        self.reject(f"SELECT claim_validation('{uid(2)}','{uid(201)}',5);", "seen this phrase")

    def test_no_prompt_exposure_during_active_review(self):
        assignment = self.claim(2)
        self.reject(f"SELECT assign_signing('{uid(2)}','{uid(101)}',20);", "active blind review")
        self.reject(f"SELECT validation_payload('{uid(3)}','{assignment}');", "owned assignment")
        self.reject(f"SELECT submit_interpretation('{uid(3)}','{assignment}','guess');", "not owned")

    def test_answer_locks_and_retries(self):
        assignment = self.claim(2)
        sql = f"SELECT submit_interpretation('{uid(2)}','{assignment}','Tomorrow appointment.');"
        answer_id = self.sql(sql)
        self.assertEqual(self.sql(sql), answer_id)
        self.reject(f"SELECT submit_interpretation('{uid(2)}','{assignment}','Today appointment.');", "locked")
        self.reject(f"UPDATE interpretations SET english_text='different' WHERE id='{answer_id}';", "append-only")
        self.reject(f"SELECT claim_validation('{uid(2)}','{uid(201)}',5);", "unique constraint")

    def test_expired_review_cannot_submit_and_slot_reusable(self):
        assignment = self.claim(2)
        self.sql(f"UPDATE validation_assignments SET assigned_at=now()-interval '2 hours',"
                 f"expires_at=now()-interval '1 hour' WHERE id='{assignment}';")
        self.reject(f"SELECT submit_interpretation('{uid(2)}','{assignment}','answer');", "closed")
        self.claim(3)
        self.assertEqual(self.sql(f"SELECT state FROM validation_assignments WHERE id='{assignment}';"), "expired")

    def test_review_limit_under_concurrent_claims(self):
        def attempt(account):
            return DB.run(f"SELECT claim_validation('{uid(account)}','{uid(201)}',5);", check=False)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = list(pool.map(attempt, range(2,8)))
        self.assertEqual(sum(r.returncode == 0 for r in outcomes), 3)
        self.assertTrue(all(r.returncode == 0 or 'review limit reached' in r.stderr for r in outcomes))
        # Authorized extra review: three completed answers first, then two more slots.
        self.sql(f"UPDATE submissions SET review_limit=5 WHERE id='{uid(201)}';")
        self.claim(9)
        self.claim(10)
        self.reject(f"SELECT claim_validation('{uid(11)}','{uid(201)}',5);", "review limit")
        self.reject(f"UPDATE submissions SET review_limit=6 WHERE id='{uid(201)}';", "check constraint")
        self.assertEqual(self.sql("SELECT count(*) FROM validation_assignments WHERE state='assigned';"), "5")

    def test_holdouts_block_each_scope(self):
        self.approve_fixture()
        for column, value in (("submission_id",201),("phrase_id",100),("signer_id",1)):
            with self.subTest(scope=column):
                self.sql(f"INSERT INTO holdout_membership({column},policy_version) VALUES('{uid(value)}','test-v1');")
                self.assertEqual(self.manifest(), [])
                self.sql("DELETE FROM holdout_membership;")
                self.assertEqual(len(self.manifest()), 1)

    def test_failed_uncertain_and_withdrawn_excluded(self):
        self.approve_fixture()
        for state in ("confirmed_failed","uncertain","quarantined","withdrawn"):
            self.sql(f"UPDATE corpus_membership SET status='{state}';")
            self.assertEqual(self.manifest(), [])
        self.sql("UPDATE corpus_membership SET status='approved';")
        self.sql(f"INSERT INTO consent_events(account_id,action,terms_version,disclosure_version) "
                 f"VALUES('{uid(1)}','withdrawn','v1','v1');")
        self.assertEqual(self.manifest(), [])
        self.reject(f"SELECT assign_signing('{uid(1)}','{uid(101)}',20);", "consent required")

    def test_latest_unapproved_annotation_blocks_stale_export(self):
        self.approve_fixture()
        self.sql(f"INSERT INTO annotations(clip_id,version,english_meaning,provenance,status,fingerspelling_status) "
                 f"VALUES('{uid(401)}',2,'Meaning under review','Correction review','draft','unknown');")
        self.assertEqual(self.manifest(), [])

    def test_clip_source_integrity_and_no_real_rewards(self):
        self.reject(f"UPDATE clips SET end_seconds=13 WHERE id='{uid(401)}';", "exceeds source duration")
        self.reject(f"UPDATE clips SET start_seconds=-1 WHERE id='{uid(401)}';", "check constraint")
        self.reject("UPDATE signing_assignments SET mode='cash';", "check constraint")
        self.reject("UPDATE media_assets SET sha256=repeat('c',64);", "append-only")


if __name__ == "__main__":
    with TemporaryPostgres() as database:
        DB = database
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CorpusTests))
    print("Temporary PostgreSQL server stopped and test files removed.")
    raise SystemExit(0 if result.wasSuccessful() else 1)
