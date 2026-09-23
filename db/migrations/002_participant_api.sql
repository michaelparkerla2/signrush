-- Apply as migration owner, after 001. Runtime login receives membership in this
-- NOLOGIN role, never in the migration-owner role. No browser database access.
BEGIN;
SET LOCAL search_path = signrush, pg_catalog;
CREATE ROLE signrush_api NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA signrush TO signrush_api;

CREATE TABLE upload_tickets (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 assignment_id uuid NOT NULL UNIQUE REFERENCES signing_assignments,
 account_id uuid NOT NULL REFERENCES accounts,
 submission_id uuid NOT NULL UNIQUE REFERENCES submissions,
 object_key text NOT NULL UNIQUE,
 mime_type text NOT NULL CHECK(mime_type IN ('video/mp4','video/webm')),
 state text NOT NULL DEFAULT 'reserved' CHECK(state IN ('reserved','stored')),
 reserved_at timestamptz NOT NULL DEFAULT now(),
 generation text, sha256 text, byte_count bigint,
 CHECK(state <> 'stored' OR (generation IS NOT NULL AND sha256 ~ '^[0-9a-f]{64}$' AND byte_count BETWEEN 1 AND 20971520))
);
-- Deliberately conservative pilot budget: reservations, including abandoned ones,
-- count forever until an administrator explicitly reconciles them. No auto-reset.
CREATE TABLE pilot_upload_budget (id boolean PRIMARY KEY DEFAULT true CHECK(id), max_uploads integer NOT NULL CHECK(max_uploads BETWEEN 1 AND 100));
INSERT INTO pilot_upload_budget VALUES(true,100);

CREATE FUNCTION api_account(p_subject text, p_require_consent boolean DEFAULT true) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=signrush,pg_catalog AS $$
DECLARE a uuid;
BEGIN
 SELECT id INTO a FROM accounts WHERE auth_subject=p_subject AND status='active' FOR UPDATE;
 IF a IS NULL THEN RAISE EXCEPTION 'access denied'; END IF;
 IF p_require_consent AND NOT EXISTS (
   SELECT 1 FROM (SELECT * FROM consent_events WHERE account_id=a ORDER BY id DESC LIMIT 1) c
   WHERE action='accepted' AND terms_version='pilot-v1' AND disclosure_version='training-v1'
 ) THEN RAISE EXCEPTION 'current consent required'; END IF;
 RETURN a;
END $$;

CREATE FUNCTION api_enroll(p_subject text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=signrush,pg_catalog AS $$
DECLARE a uuid;
BEGIN
 IF length(p_subject) NOT BETWEEN 1 AND 128 THEN RAISE EXCEPTION 'invalid identity'; END IF;
 INSERT INTO accounts(auth_subject) VALUES(p_subject) ON CONFLICT DO NOTHING;
 a := api_account(p_subject,false);
 RETURN jsonb_build_object('account_id',a,'mode','test','consent_required',NOT EXISTS (
 SELECT 1 FROM (SELECT * FROM consent_events WHERE account_id=a ORDER BY id DESC LIMIT 1) c
 WHERE action='accepted' AND terms_version='pilot-v1' AND disclosure_version='training-v1'));
END $$;
CREATE FUNCTION api_consent(p_subject text,p_accept boolean) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=signrush,pg_catalog AS $$
DECLARE a uuid;
BEGIN
 a := api_account(p_subject,false);
 INSERT INTO consent_events(account_id,action,terms_version,disclosure_version)
 VALUES(a,CASE WHEN p_accept THEN 'accepted' ELSE 'withdrawn' END,'pilot-v1','training-v1');
END $$;

CREATE FUNCTION api_signing_next(p_subject text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=signrush,pg_catalog AS $$
DECLARE a uuid; task signing_assignments; pv uuid;
BEGIN
 a := api_account(p_subject);
 SELECT * INTO task FROM signing_assignments WHERE signer_id=a AND state='assigned' ORDER BY assigned_at LIMIT 1;
 IF NOT FOUND THEN
  SELECT v.id INTO pv FROM phrase_versions v JOIN phrases f ON f.id=v.phrase_id
   WHERE f.active AND v.review_status='reviewed'
    AND v.version=(SELECT max(version) FROM phrase_versions WHERE phrase_id=f.id)
    AND NOT EXISTS (SELECT 1 FROM validation_assignments r JOIN submissions s ON s.id=r.submission_id
     JOIN signing_assignments sa ON sa.id=s.assignment_id JOIN phrase_versions rv ON rv.id=sa.phrase_version_id
     WHERE r.validator_id=a AND r.state='assigned' AND r.expires_at>clock_timestamp() AND rv.phrase_id=f.id)
   ORDER BY random() LIMIT 1;
  IF pv IS NULL THEN RETURN NULL; END IF;
  pv := assign_signing(a,pv,20);
  SELECT * INTO task FROM signing_assignments WHERE id=pv;
 END IF;
 RETURN jsonb_build_object('assignment_id',task.id,'prompt',(SELECT english_prompt FROM phrase_versions WHERE id=task.phrase_version_id),
  'reward_points',task.reward_points,'mode','test');
END $$;

CREATE FUNCTION api_reserve_upload(p_subject text,p_assignment uuid,p_mime text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=signrush,pg_catalog AS $$
DECLARE a uuid; s uuid; t upload_tickets; maximum integer;
BEGIN
 a := api_account(p_subject);
 PERFORM 1 FROM signing_assignments WHERE id=p_assignment AND signer_id=a AND state='assigned' FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'assignment unavailable'; END IF;
 SELECT * INTO t FROM upload_tickets WHERE assignment_id=p_assignment;
 IF FOUND THEN RAISE EXCEPTION 'upload already reserved'; END IF;
 SELECT max_uploads INTO maximum FROM pilot_upload_budget WHERE id FOR UPDATE;
 IF (SELECT count(*) FROM upload_tickets)>=maximum OR
    (SELECT count(*) FROM upload_tickets WHERE account_id=a)>=5 THEN RAISE EXCEPTION 'pilot upload limit reached'; END IF;
 INSERT INTO submissions(assignment_id,signer_id) VALUES(p_assignment,a) RETURNING id INTO s;
 INSERT INTO upload_tickets(assignment_id,account_id,submission_id,object_key,mime_type)
 VALUES(p_assignment,a,s,'pilot/uploads/'||gen_random_uuid()::text,p_mime) RETURNING * INTO t;
 UPDATE signing_assignments SET state='submitted' WHERE id=p_assignment;
 RETURN jsonb_build_object('ticket_id',t.id,'submission_id',s,'object_key',t.object_key,'mime_type',t.mime_type);
END $$;
CREATE FUNCTION api_finish_upload(p_subject text,p_ticket uuid,p_generation text,p_sha text,p_bytes bigint) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=signrush,pg_catalog AS $$
DECLARE a uuid; t upload_tickets;
BEGIN
 a := api_account(p_subject,false);
 SELECT * INTO t FROM upload_tickets WHERE id=p_ticket AND account_id=a FOR UPDATE;
 IF NOT FOUND OR t.state<>'reserved' THEN RAISE EXCEPTION 'upload unavailable'; END IF;
 UPDATE upload_tickets SET state='stored',generation=p_generation,sha256=p_sha,byte_count=p_bytes WHERE id=t.id;
 -- Processing stays closed to reviewers until a trusted media worker records
 -- a probed original, a stripped silent derivative, quality evidence and clips.
 RETURN jsonb_build_object('submission_id',t.submission_id,'state','processing','mode','test');
END $$;

CREATE FUNCTION api_review_next(p_subject text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=signrush,pg_catalog AS $$
DECLARE a uuid; task uuid; candidate uuid; result jsonb;
BEGIN
 a := api_account(p_subject);
 SELECT id INTO task FROM validation_assignments WHERE validator_id=a AND state='assigned'
  AND expires_at>clock_timestamp() ORDER BY assigned_at LIMIT 1;
 IF task IS NULL THEN
  SELECT s.id INTO candidate FROM submissions s
   JOIN signing_assignments sa ON sa.id=s.assignment_id JOIN phrase_versions pv ON pv.id=sa.phrase_version_id
   JOIN accounts signer ON signer.id=s.signer_id
   WHERE s.state='awaiting_reviews' AND s.signer_id<>a AND signer.status='active'
   AND (SELECT action FROM consent_events WHERE account_id=signer.id ORDER BY id DESC LIMIT 1)='accepted'
   AND EXISTS(SELECT 1 FROM media_assets WHERE submission_id=s.id AND kind='silent_playback')
   AND NOT EXISTS(SELECT 1 FROM phrase_exposures WHERE account_id=a AND phrase_id=pv.phrase_id)
   AND NOT EXISTS(SELECT 1 FROM validation_assignments WHERE submission_id=s.id AND validator_id=a)
   AND (SELECT count(*) FROM validation_assignments WHERE submission_id=s.id AND
     (state='completed' OR (state='assigned' AND expires_at>clock_timestamp())))<s.review_limit
   ORDER BY s.submitted_at LIMIT 1 FOR UPDATE OF s SKIP LOCKED;
  IF candidate IS NULL THEN RETURN NULL; END IF;
  task := claim_validation(a,candidate,5);
 END IF;
 result := validation_payload(a,task);
 RETURN result-'media';
END $$;
CREATE FUNCTION api_review_media(p_subject text,p_assignment uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=signrush,pg_catalog AS $$
DECLARE a uuid; result jsonb;
BEGIN
 a := api_account(p_subject);
 result := validation_payload(a,p_assignment);
 IF NOT EXISTS(SELECT 1 FROM validation_assignments v JOIN submissions s ON s.id=v.submission_id
 JOIN accounts ac ON ac.id=s.signer_id WHERE v.id=p_assignment AND ac.status='active')
 THEN RAISE EXCEPTION 'review unavailable'; END IF;
 RETURN result->'media';
END $$;
CREATE FUNCTION api_answer(p_subject text,p_assignment uuid,p_text text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=signrush,pg_catalog AS $$
DECLARE a uuid; answer uuid;
BEGIN
 a := api_account(p_subject);
 IF NOT EXISTS(SELECT 1 FROM validation_assignments v JOIN submissions s ON s.id=v.submission_id
 JOIN accounts ac ON ac.id=s.signer_id WHERE v.id=p_assignment AND ac.status='active')
 THEN RAISE EXCEPTION 'review unavailable'; END IF;
 answer := submit_interpretation(a,p_assignment,p_text);
 RETURN jsonb_build_object('answer_id',answer,'state','pending','mode','test');
END $$;

REVOKE ALL ON ALL TABLES IN SCHEMA signrush FROM PUBLIC,signrush_api;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA signrush FROM PUBLIC,signrush_api;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA signrush FROM PUBLIC,signrush_api;
GRANT EXECUTE ON FUNCTION api_enroll(text),api_consent(text,boolean),api_signing_next(text),
 api_reserve_upload(text,uuid,text),api_finish_upload(text,uuid,text,text,bigint),
 api_review_next(text),api_review_media(text,uuid),api_answer(text,uuid,text) TO signrush_api;
COMMIT;
