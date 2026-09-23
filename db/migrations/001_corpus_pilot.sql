-- First vertical slice. Apply once to an empty PostgreSQL 16+ database.
-- Trusted backend/admin only: no browser connections or public role grants.
BEGIN;
CREATE SCHEMA signrush;
REVOKE ALL ON SCHEMA signrush FROM PUBLIC;
SET LOCAL search_path = signrush, pg_catalog;
ALTER DEFAULT PRIVILEGES IN SCHEMA signrush REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

CREATE TABLE accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_subject text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','closed')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE corpus_signers (
  account_id uuid PRIMARY KEY REFERENCES accounts,
  signer_number bigint GENERATED ALWAYS AS IDENTITY UNIQUE
);
CREATE TABLE consent_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id uuid NOT NULL REFERENCES accounts,
  action text NOT NULL CHECK (action IN ('accepted','withdrawn')),
  terms_version text NOT NULL,
  disclosure_version text NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON consent_events(account_id, id DESC);
CREATE TABLE phrase_collections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL UNIQUE
);
CREATE TABLE phrases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  collection_id uuid NOT NULL REFERENCES phrase_collections,
  active boolean NOT NULL DEFAULT true
);
CREATE TABLE phrase_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  phrase_id uuid NOT NULL REFERENCES phrases,
  version integer NOT NULL CHECK (version > 0),
  english_prompt text NOT NULL CHECK (length(trim(english_prompt)) > 0),
  intended_meaning text NOT NULL,
  required_details jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(required_details) = 'array'),
  acceptable_paraphrases jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(acceptable_paraphrases) = 'array'),
  source text NOT NULL, reuse_terms text NOT NULL,
  review_status text NOT NULL CHECK (review_status IN ('draft','reviewed')),
  UNIQUE (phrase_id, version)
);
CREATE TABLE phrase_exposures (
  account_id uuid NOT NULL REFERENCES accounts,
  phrase_id uuid NOT NULL REFERENCES phrases,
  first_shown_at timestamptz NOT NULL DEFAULT now(),
  reason text NOT NULL,
  PRIMARY KEY (account_id, phrase_id)
);
CREATE TABLE signing_assignments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  signer_id uuid NOT NULL REFERENCES accounts,
  phrase_version_id uuid NOT NULL REFERENCES phrase_versions,
  consent_event_id bigint NOT NULL REFERENCES consent_events,
  reward_points integer NOT NULL CHECK (reward_points >= 0),
  mode text NOT NULL DEFAULT 'test' CHECK (mode = 'test'),
  state text NOT NULL DEFAULT 'assigned' CHECK (state IN ('assigned','submitted','skipped')),
  assigned_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(id, signer_id)
);
CREATE TABLE submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assignment_id uuid NOT NULL UNIQUE,
  signer_id uuid NOT NULL REFERENCES accounts,
  state text NOT NULL DEFAULT 'processing'
    CHECK (state IN ('processing','awaiting_reviews','needs_review','approved','confirmed_failed','withdrawn')),
  review_limit smallint NOT NULL DEFAULT 3 CHECK (review_limit IN (3,5)),
  submitted_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (assignment_id, signer_id) REFERENCES signing_assignments(id, signer_id)
);
CREATE TABLE media_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id uuid NOT NULL REFERENCES submissions,
  kind text NOT NULL CHECK (kind IN ('original','silent_playback','export_source')),
  bucket text NOT NULL, object_key text NOT NULL, object_generation text NOT NULL,
  sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  byte_count bigint NOT NULL CHECK (byte_count > 0),
  mime_type text NOT NULL CHECK (mime_type IN ('video/mp4','video/webm')),
  duration_seconds numeric(12,4) NOT NULL CHECK (duration_seconds > 0),
  width integer NOT NULL CHECK (width > 0), height integer NOT NULL CHECK (height > 0),
  fps numeric(8,3) NOT NULL CHECK (fps > 0), audio_present boolean NOT NULL,
  derived_from_asset_id uuid,
  UNIQUE (id, submission_id), UNIQUE (bucket, object_key, object_generation),
  FOREIGN KEY (derived_from_asset_id, submission_id) REFERENCES media_assets(id, submission_id),
  CHECK (kind <> 'silent_playback' OR NOT audio_present),
  CHECK ((kind = 'original' AND derived_from_asset_id IS NULL) OR
         (kind <> 'original' AND derived_from_asset_id IS NOT NULL))
);
CREATE UNIQUE INDEX one_original ON media_assets(submission_id) WHERE kind = 'original';
CREATE TABLE clips (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), submission_id uuid NOT NULL REFERENCES submissions,
  source_asset_id uuid NOT NULL,
  start_seconds numeric(12,4) NOT NULL CHECK (start_seconds >= 0),
  end_seconds numeric(12,4) NOT NULL CHECK (end_seconds > start_seconds),
  boundary_status text NOT NULL CHECK (boundary_status IN ('draft','verified')),
  FOREIGN KEY (source_asset_id, submission_id) REFERENCES media_assets(id, submission_id)
);
CREATE TABLE quality_checks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), submission_id uuid NOT NULL REFERENCES submissions,
  rule text NOT NULL, outcome text NOT NULL CHECK (outcome IN ('pass','fail','uncertain')),
  checker_version text NOT NULL, evidence jsonb NOT NULL DEFAULT '{}',
  checked_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE validation_assignments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), submission_id uuid NOT NULL REFERENCES submissions,
  validator_id uuid NOT NULL REFERENCES accounts,
  slot smallint NOT NULL CHECK (slot BETWEEN 1 AND 5),
  state text NOT NULL DEFAULT 'assigned' CHECK (state IN ('assigned','completed','expired','skipped','reported')),
  reward_points integer NOT NULL CHECK (reward_points >= 0),
  mode text NOT NULL DEFAULT 'test' CHECK (mode = 'test'),
  assigned_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
  UNIQUE (submission_id, validator_id),
  CHECK (expires_at > assigned_at)
);
CREATE UNIQUE INDEX occupied_review_slots ON validation_assignments(submission_id, slot)
  WHERE state IN ('assigned','completed');
CREATE TABLE interpretations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assignment_id uuid NOT NULL UNIQUE REFERENCES validation_assignments,
  english_text text NOT NULL CHECK (length(trim(english_text)) BETWEEN 1 AND 4000),
  submitted_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE recording_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assignment_id uuid NOT NULL UNIQUE REFERENCES validation_assignments,
  reason text NOT NULL, details text NOT NULL DEFAULT ''
);
CREATE TABLE scoring_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), submission_id uuid NOT NULL REFERENCES submissions,
  algorithm_version text NOT NULL, input_snapshot jsonb NOT NULL,
  pairwise_scores jsonb NOT NULL, prompt_fidelity_scores jsonb NOT NULL,
  decision text NOT NULL CHECK (decision IN ('approved','confirmed_failed','needs_review')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE annotations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), clip_id uuid NOT NULL REFERENCES clips,
  version integer NOT NULL CHECK (version > 0),
  english_meaning text NOT NULL CHECK (length(trim(english_meaning)) > 0),
  provenance text NOT NULL CHECK (length(trim(provenance)) > 0),
  status text NOT NULL CHECK (status IN ('draft','approved','rejected')),
  fingerspelling_status text NOT NULL CHECK (fingerspelling_status IN ('unknown','reviewed')),
  fs_terms jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(fs_terms) = 'array'),
  UNIQUE (clip_id, version),
  CHECK (fingerspelling_status <> 'unknown' OR fs_terms = '[]'::jsonb)
);
CREATE TABLE corpus_membership (
  submission_id uuid PRIMARY KEY REFERENCES submissions,
  status text NOT NULL CHECK (status IN ('approved','confirmed_failed','uncertain','quarantined','withdrawn')),
  reason text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
-- A holdout can exclude a recording, a whole phrase family, or a signer.
CREATE TABLE holdout_membership (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id uuid REFERENCES submissions, phrase_id uuid REFERENCES phrases,
  signer_id uuid REFERENCES accounts, policy_version text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  CHECK (num_nonnulls(submission_id, phrase_id, signer_id) = 1)
);

CREATE FUNCTION reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'append-only record; create a new version or use a controlled erasure process'; END $$;
CREATE TRIGGER immutable_phrase BEFORE UPDATE OR DELETE ON phrase_versions
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_answer BEFORE UPDATE OR DELETE ON interpretations
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_annotation BEFORE UPDATE OR DELETE ON annotations
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_consent BEFORE UPDATE OR DELETE ON consent_events
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_media BEFORE UPDATE OR DELETE ON media_assets
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();

CREATE FUNCTION check_clip() RETURNS trigger LANGUAGE plpgsql SET search_path = signrush, pg_catalog AS $$
BEGIN
  IF NEW.end_seconds > (SELECT duration_seconds FROM media_assets WHERE id = NEW.source_asset_id) THEN
    RAISE EXCEPTION 'clip exceeds source duration';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER clip_bounds BEFORE INSERT OR UPDATE ON clips FOR EACH ROW EXECUTE FUNCTION check_clip();

CREATE FUNCTION lock_active_account(p_account uuid) RETURNS void
LANGUAGE plpgsql SET search_path = signrush, pg_catalog AS $$
BEGIN
  PERFORM 1 FROM accounts WHERE id = p_account AND status = 'active' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'active account required'; END IF;
END $$;

-- This same account lock serializes prompt exposure against review claims/answers.
CREATE FUNCTION expose_phrase(p_account uuid, p_phrase uuid, p_reason text) RETURNS void
LANGUAGE plpgsql SET search_path = signrush, pg_catalog AS $$
BEGIN
  PERFORM lock_active_account(p_account);
  IF EXISTS (
    SELECT 1 FROM validation_assignments v JOIN submissions s ON s.id=v.submission_id
    JOIN signing_assignments a ON a.id=s.assignment_id JOIN phrase_versions p ON p.id=a.phrase_version_id
    WHERE v.validator_id=p_account AND p.phrase_id=p_phrase AND v.state='assigned'
      AND v.expires_at > clock_timestamp()
  ) THEN RAISE EXCEPTION 'cannot reveal phrase during an active blind review'; END IF;
  INSERT INTO phrase_exposures(account_id, phrase_id, reason) VALUES(p_account,p_phrase,p_reason)
    ON CONFLICT DO NOTHING;
END $$;

CREATE FUNCTION assign_signing(p_account uuid, p_version uuid, p_points integer) RETURNS uuid
LANGUAGE plpgsql SET search_path = signrush, pg_catalog AS $$
DECLARE consent_id bigint; consent_action text; phrase uuid; result uuid;
BEGIN
  PERFORM lock_active_account(p_account);
  SELECT id, action INTO consent_id,consent_action FROM consent_events
    WHERE account_id=p_account ORDER BY id DESC LIMIT 1;
  IF consent_action IS DISTINCT FROM 'accepted' THEN RAISE EXCEPTION 'current consent required'; END IF;
  SELECT p.phrase_id INTO phrase FROM phrase_versions p JOIN phrases f ON f.id=p.phrase_id
    WHERE p.id=p_version AND f.active;
  IF NOT FOUND THEN RAISE EXCEPTION 'active phrase required'; END IF;
  PERFORM expose_phrase(p_account, phrase, 'signing_challenge');
  INSERT INTO corpus_signers(account_id) VALUES(p_account) ON CONFLICT DO NOTHING;
  INSERT INTO signing_assignments(signer_id,phrase_version_id,consent_event_id,reward_points)
    VALUES(p_account,p_version,consent_id,p_points) RETURNING id INTO result;
  RETURN result;
END $$;

CREATE FUNCTION assert_review_eligible(p_account uuid, p_submission uuid) RETURNS void
LANGUAGE plpgsql SET search_path = signrush, pg_catalog AS $$
DECLARE signer uuid; phrase uuid; submission_state text;
BEGIN
  SELECT s.signer_id,p.phrase_id,s.state INTO signer,phrase,submission_state
    FROM submissions s JOIN signing_assignments a ON a.id=s.assignment_id
    JOIN phrase_versions p ON p.id=a.phrase_version_id WHERE s.id=p_submission;
  IF NOT FOUND OR submission_state <> 'awaiting_reviews' THEN RAISE EXCEPTION 'submission not open for review'; END IF;
  IF signer=p_account THEN RAISE EXCEPTION 'self validation prohibited'; END IF;
  IF EXISTS(SELECT 1 FROM phrase_exposures WHERE account_id=p_account AND phrase_id=phrase) THEN
    RAISE EXCEPTION 'validator has seen this phrase';
  END IF;
  IF (SELECT action FROM consent_events WHERE account_id=signer ORDER BY id DESC LIMIT 1)
     IS DISTINCT FROM 'accepted' THEN RAISE EXCEPTION 'signer consent no longer active'; END IF;
END $$;

CREATE FUNCTION claim_validation(p_account uuid, p_submission uuid, p_points integer) RETURNS uuid
LANGUAGE plpgsql SET search_path = signrush, pg_catalog AS $$
DECLARE max_slots integer; free_slot integer; result uuid;
BEGIN
  PERFORM lock_active_account(p_account);
  SELECT review_limit INTO max_slots FROM submissions WHERE id=p_submission FOR UPDATE;
  PERFORM assert_review_eligible(p_account,p_submission);
  UPDATE validation_assignments SET state='expired'
    WHERE submission_id=p_submission AND state='assigned' AND expires_at<=clock_timestamp();
  SELECT n INTO free_slot FROM generate_series(1,max_slots) n WHERE NOT EXISTS (
    SELECT 1 FROM validation_assignments WHERE submission_id=p_submission AND slot=n
      AND state IN ('assigned','completed')
  ) ORDER BY n LIMIT 1;
  IF free_slot IS NULL THEN RAISE EXCEPTION 'review limit reached'; END IF;
  INSERT INTO validation_assignments(submission_id,validator_id,slot,reward_points,expires_at)
    VALUES(p_submission,p_account,free_slot,p_points,clock_timestamp()+interval '20 minutes')
    RETURNING id INTO result;
  RETURN result;
END $$;

CREATE FUNCTION submit_interpretation(p_account uuid, p_assignment uuid, p_text text) RETURNS uuid
LANGUAGE plpgsql SET search_path = signrush, pg_catalog AS $$
DECLARE v validation_assignments; result uuid; prior_text text;
BEGIN
  PERFORM lock_active_account(p_account);
  SELECT * INTO v FROM validation_assignments WHERE id=p_assignment AND validator_id=p_account;
  IF NOT FOUND THEN RAISE EXCEPTION 'assignment not owned by account'; END IF;
  PERFORM 1 FROM submissions WHERE id=v.submission_id FOR UPDATE;
  SELECT * INTO v FROM validation_assignments WHERE id=p_assignment FOR UPDATE;
  SELECT id,english_text INTO result,prior_text FROM interpretations WHERE assignment_id=p_assignment;
  IF FOUND THEN
    IF prior_text IS DISTINCT FROM p_text THEN RAISE EXCEPTION 'answer already locked'; END IF;
    RETURN result; -- exact network retry, not a second answer
  END IF;
  IF v.state<>'assigned' OR v.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'assignment closed'; END IF;
  PERFORM assert_review_eligible(p_account,v.submission_id);
  INSERT INTO interpretations(assignment_id,english_text) VALUES(p_assignment,p_text) RETURNING id INTO result;
  UPDATE validation_assignments SET state='completed' WHERE id=p_assignment;
  RETURN result;
END $$;

-- Trusted backend payload: cloud object locator, never original prompt/answers.
-- Backend must turn the locator into temporary playback access after authentication.
CREATE FUNCTION validation_payload(p_account uuid, p_assignment uuid) RETURNS jsonb
LANGUAGE plpgsql SET search_path = signrush, pg_catalog AS $$
DECLARE v validation_assignments; asset media_assets;
BEGIN
  PERFORM lock_active_account(p_account);
  SELECT * INTO v FROM validation_assignments WHERE id=p_assignment AND validator_id=p_account;
  IF NOT FOUND OR v.state<>'assigned' OR v.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'active owned assignment required'; END IF;
  PERFORM assert_review_eligible(p_account,v.submission_id);
  SELECT * INTO asset FROM media_assets WHERE submission_id=v.submission_id AND kind='silent_playback'
    ORDER BY id LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'silent playback not ready'; END IF;
  RETURN jsonb_build_object('assignment_id',v.id,'reward_points',v.reward_points,'mode','test',
    'media',jsonb_build_object('bucket',asset.bucket,'object_key',asset.object_key,'generation',asset.object_generation));
END $$;

-- Latest annotation must be approved; never silently fall back to superseded truth.
CREATE FUNCTION training_manifest() RETURNS jsonb
LANGUAGE sql STABLE SET search_path = signrush, pg_catalog AS $$
  SELECT coalesce(jsonb_agg(jsonb_build_object(
    'example_id',c.id,'document_id',s.id,'sentence_id',a.phrase_version_id,
    'video_name',m.id::text || CASE m.mime_type WHEN 'video/mp4' THEN '.mp4' ELSE '.webm' END,
    'source_path','media/' || m.id::text || CASE m.mime_type WHEN 'video/mp4' THEN '.mp4' ELSE '.webm' END,
    'source_sha256',m.sha256,'start_time_sec',c.start_seconds,'end_time_sec',c.end_seconds,
    'eng',ann.english_meaning,'reference',ann.english_meaning,'reference_provenance',ann.provenance,
    'signer',cs.signer_number,'fs_terms',ann.fs_terms
  ) ORDER BY c.id), '[]'::jsonb)
  FROM clips c JOIN submissions s ON s.id=c.submission_id
  JOIN signing_assignments a ON a.id=s.assignment_id JOIN phrase_versions pv ON pv.id=a.phrase_version_id
  JOIN accounts ac ON ac.id=s.signer_id JOIN corpus_signers cs ON cs.account_id=s.signer_id
  JOIN media_assets m ON m.id=c.source_asset_id
  JOIN corpus_membership cm ON cm.submission_id=s.id
  JOIN LATERAL (SELECT * FROM annotations WHERE clip_id=c.id ORDER BY version DESC LIMIT 1) ann ON true
  WHERE s.state='approved' AND cm.status='approved' AND ann.status='approved'
    AND c.boundary_status='verified' AND ac.status='active'
    AND (SELECT action FROM consent_events WHERE account_id=s.signer_id ORDER BY id DESC LIMIT 1)='accepted'
    AND NOT EXISTS (SELECT 1 FROM holdout_membership h WHERE h.active AND
      (h.submission_id=s.id OR h.phrase_id=pv.phrase_id OR h.signer_id=s.signer_id));
$$;
REVOKE ALL ON ALL TABLES IN SCHEMA signrush FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA signrush FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA signrush FROM PUBLIC;
COMMIT;
