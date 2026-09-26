> Current review policy: [Meaning consensus v2](consensus-pilot.md) supersedes older three-matches and 0.85-threshold descriptions below: 3/3 initially, then 4/5, with unresolved meaning disputes held for fluent adjudication.

# SignRush database draft

Status: target design. The first local PostgreSQL slice and ten synthetic integration tests are implemented; see `../README.md` for scope and limitations. No cloud database, app, scoring model, payment integration, or service-identity isolation has been deployed. Tables below describe the complete target, not a claim that every table is implemented.

## Purpose

Collect consented ASL recordings through a friendly game, independently review their meaning, and produce a traceable corpus. Preserve the requested phrase separately from what the recording actually means. Players interact only with SignRush; cloud credentials and hidden labels never enter player-facing responses.

## Records and relationships

All primary IDs are immutable UUIDs unless noted. Times use UTC. Repeated signing of a phrase creates new submissions, not new phrase identities.

| Table | Main fields | Purpose |
|---|---|---|
| accounts | id, authentication_subject, status, created_at | Player identity; separate from corpus exports. |
| corpus_signers | account_id, stable_signer_number | Stable pseudonymous integer for the existing training loader. One number per account, never reassigned. Does not prove two accounts are different humans. |
| consent_events | id, account_id, terms_version, training_disclosure_version, action, recorded_at | Versioned acceptance and withdrawal history. Preserve evidence; a terms checkbox alone is not an unlimited retention policy. |
| phrase_collections | id, name, domain, active | Everyday, medical, banking, and later collections. |
| phrases | id, collection_id, current_version_id, active | Stable phrase family identity. |
| phrase_versions | id, phrase_id, version, english_prompt, intended_meaning, required_details, acceptable_paraphrases, source, reuse_terms, review_status | Immutable prompt and meaning snapshot. Drafts require ASL review before paid use. |
| task_pools | id, phrase_version_id, target_distinct_signers, reward_points, expected_seconds, mode, active | Budgeted recording opportunities; fixed rewards shown before acceptance. |
| phrase_exposures | account_id, phrase_id, first_shown_at, reason | Records a prompt being shown, including skipped challenges. Used to exclude exposed players from reviewing that phrase. |
| signing_assignments | id, account_id, task_pool_id, phrase_version_id, reward_snapshot, consent_event_id, assigned_at, expires_at, state | Server-side allocation of a recording opportunity. |
| submissions | id, signing_assignment_id, signer_id, current_state, submitted_at | One submitted recording; retries before submission do not automatically become paid tasks or corpus records. |
| media_assets | id, submission_id, kind, bucket, object_key, object_generation, sha256, byte_count, mime_type, duration_seconds, fps, width, height, audio_present, derived_from_asset_id | Original file and derived playback/export copies with provenance. Store object keys, not expiring URLs. |
| clips | id, submission_id, source_asset_id, start_seconds, end_seconds, boundary_status | Time-bounded intervals inside an exact source asset. Each clip can become one exported example. |
| quality_checks | id, submission_id, rule, outcome, score, checker_type, checker_version, evidence, checked_at | Lighting, framing, playability, and other quality findings. Automated checks are evidence, not assumed perfect judgments. |
| validation_assignments | id, submission_id, validator_id, reward_snapshot, assigned_at, expires_at, state | Blind assignment and payment eligibility. Maximum five completed paid review slots per submission. |
| interpretations | id, validation_assignment_id, english_text, submitted_at | Exact independent answer, locked after submission. Reports and skips are not interpretations. |
| recording_reports | id, validation_assignment_id, reason, details, submitted_at | Poor framing, unusable media, or other problems. |
| scoring_runs | id, submission_id, input_snapshot, algorithm_version, pairwise_scores, prompt_fidelity_scores, decision, created_at | Reproducible review decisions, preserving previous runs. |
| adjudications | id, submission_id, reviewer_id, decision, rationale, created_at | Additional review for disputes and unresolved cases. |
| annotations | id, clip_id, version, english_meaning, provenance, status, fingerspelling_status, fs_terms, created_at | Meaning established for the actual signing, independently versioned from the requested prompt. |
| reward_events | id, account_id, task_id, kind, points, mode, idempotency_key, decision_id, created_at | Append-only pending, approval, rejection, redemption, and reversal events. Separate signer and validator decisions. |
| reward_reservations | id, task_pool_id, signing_assignment_id, reserved_points, mode, state | Transactional reservation for signer reward and up to five validator rewards. |
| payouts | id, account_id, amount_cents, provider_reference, state, idempotency_key | Future real payouts. Store provider references, not payment credentials, in this database. Disabled during pilot. |
| corpus_membership | submission_id, status, reason, annotation_id, updated_at | Approved, confirmed_failed, uncertain, quarantined, or withdrawn. Failure and uncertainty are different labels. |
| holdout_membership | id, submission_id, phrase_family_id, signer_id, policy_version, state | Controls exclusion from ordinary training exports; different from the downstream pipeline's qualification fields. |
| challenge_exposures | id, clip_id, recipient_reference, served_at, retired_at | Tracks distributed challenges because a recipient can retain a served video. |
| export_releases | id, version, manifest_asset, schema_version, selection_snapshot, created_at, state | Immutable export versions and checksum manifests. |
| export_items | release_id, clip_id, annotation_id, source_asset_id, relative_path | Exact records and versions included in a release. |
| audit_events | id, actor_id, action, target_id, occurred_at | Administrative access and changes; avoid copying hidden prompts or sensitive payloads into logs. |

## Assignment rules enforced by the backend

1. Select active, reviewed phrases from task pools with remaining capacity. Keep phrase diversity and distinct signer targets; repeated phrases across different signers are intentional.
2. Record phrase exposure before returning a prompt to a signer. Skip still counts as exposure.
3. Assign reviews only to a different account with no exposure to that phrase and no previous review of the submission. Also record exposure when a prior review receives reference-based feedback.
4. Use a transaction to check eligibility, reserve a review slot, and create the assignment. Recheck when accepting an answer. Coordinate phrase assignment and review assignment so concurrent requests cannot expose a phrase during a blind review.
5. Start with three distinct completed interpretations. Request up to two additional reviews when needed. An expired uncompleted assignment can be replaced; completed paid slots cannot exceed five.
6. A failed signer submission does not automatically invalidate an accurate validator answer. Judge each reward separately.
7. Enforce no-self-review and uniqueness in database constraints where possible; cross-table exposure and role rules require transactional database functions or equivalent server logic. Do not rely on browser checks.
8. Account uniqueness is not human uniqueness. Identity abuse and collusion need separate controls and pilot evaluation.

Public queue counts are the tasks available to the current player, not raw global record counts. A player with no eligible reviews sees zero even if the global queue is nonempty. Small phrase libraries plus exposure exclusions can exhaust eligibility; monitor this before increasing recording targets.

## Submission and corpus states

Submission flow: assigned → uploaded → processing → awaiting_reviews → scoring → approved / confirmed_failed / needs_review.

Quality problems can stop routine review and enter failure or manual review directly. Three matching answers do not prove correctness; scoring considers both independent agreement and hidden prompt fidelity. The proposed 0.85 threshold must be calibrated on reviewed ASL examples and must not accept meaning-changing errors merely because sentences are similar.

After five reviews, unresolved cases enter needs_review and the uncertain collection. They do not become confirmed wrong-ASL labels. Corrections create new annotations and decisions; they do not overwrite history.

Confirmed failed and uncertain records are retained as separate logical collections and separate export manifests. Original video bytes need not be duplicated merely because their classification changes. Unsubmitted recordings, retention periods, consent withdrawal, and deletion propagation still need explicit policies before real participant collection.

## Rewards

- Proposed real mode: one point represents one cent; 5,000 approved unredeemed points reaches the $50 payout threshold.
- Pilot mode: test points have no cash value and cannot be converted silently into a payable balance.
- A phrase has a fixed reward based on expected duration, not uploaded duration. Longer recordings cannot inflate earnings.
- Pending points are separate from approved points. Balance is derived from ledger events; no client can set it.
- Scoring retries and repeated submission requests use unique idempotency keys to prevent duplicate awards.
- Reserve the maximum review budget before opening a paid recording task; release unused reservations after resolution.

## Storage and access boundary

Local storage is limited. Use cloud-first storage: keep production videos, derived media, dataset releases, and backups in private cloud storage. Keep only code, documentation, and small synthetic fixtures locally. Process production media in cloud jobs; avoid downloading or syncing entire buckets to the local machine. Training systems should read from cloud storage or copy directly to their own training environment. Any local media cache must be explicitly bounded and temporary. Cloud processing must remain within the authorized trial; no paid billing upgrade is authorized. Google Drive may hold selected planning documents or export copies, but is not the live video backend and must not receive held-out answers through an automatic sync.

Existing project: `signrush`, organization: `umi.vision`. Account remains on its free trial; no paid upgrade authorized.

| Bucket | Purpose | Current setup |
|---|---|---|
| umi-signrush-raw | Original recordings; derived copies identified separately | Created, nonpublic, Google-managed encryption, Standard storage, us-east1, soft delete enabled. |
| umi-signrush-exports | Versioned training releases and separately selected failed/uncertain exports | Same baseline settings. |
| umi-signrush-heldout-answers | Private reference answers for challenge scoring | Same baseline settings; default project-editor and project-viewer bucket grants removed. Project-owner bucket grants retained. |

These are bucket settings, not a completed isolation test. Inherited IAM and future service roles must be checked. No service identities, signed upload/playback flow, database, or training integration have been configured yet.

Proposed service boundaries:

- Player app: no cloud credentials, no bucket listing, no database connection. Authenticated backend issues short-lived, assignment-specific upload/playback access.
- Game service: accesses authorized submission media and game records; never exposes hidden prompt fields through validation responses, logs, captions, filenames, or media metadata.
- Corpus publisher: privileged, audited selection of approved annotations, train exclusions, release creation, and held-out answer writing.
- Training reader: reads explicitly approved training release paths only. Do not grant access to the entire exports bucket if it also contains failed or research-restricted collections.
- Challenge delivery service: serves selected video inputs only. No held-out answers.
- Challenge scorer: reads held-out answers; no player-facing endpoint that reveals them.

Permission grants and key management will be implemented when the execution environment is selected. Prefer service identities without downloadable long-lived keys. Separate buckets alone do not defeat broad inherited access.

## Existing training-loader export contract

The compatibility export is a JSON array, not JSONL. Each record represents one time-bounded clip. Rich archive tables may additionally use JSONL or Parquet.

| Loader field | Source |
|---|---|
| example_id | Stable clip ID |
| document_id | Stable submission/source recording ID |
| sentence_id | Stable phrase-version ID |
| video_name | Exported source filename |
| source_path | Media path relative to the configured dataset root |
| source_sha256 | SHA-256 of the exact whole file at source_path, not the extracted interval |
| start_time_sec / end_time_sec | Clip boundaries relative to that exact file |
| eng / reference | Same approved annotation meaning; never automatically copied from the prompt |
| reference_provenance | Annotation method and version |
| signer | Stable integer from corpus_signers |
| fs_terms | Annotated fingerspelling terms; retain unknown-versus-none status in the rich archive |

Require 0 ≤ start < end ≤ source duration. If media is transcoded or trimmed, use a new asset hash and boundaries in that new file's timeline. Preserve the original asset independently. The existing extractor handles 30 FPS, maximum 720-pixel height, and audio removal.

Do not invent `partition`, `lane`, `generalization`, `zs_split`, `si_split`, or `sd_split`. The downstream qualification process assigns its fields. Confirm whether the real loader requires them before running a compatibility test. The supplied example is a local pipeline schema, not an official subnet submission standard.

Release structure:

```text
release-0001/
  manifest.json
  records.json
  media/
  archive/
    prompts.jsonl
    interpretations.jsonl
    quality_checks.jsonl
    scoring_runs.jsonl
    annotations.jsonl
```

The rich archive is an admin artifact; do not ship it to blind challenge recipients. Export failed and uncertain records in separately named releases/manifests with explicit status and provenance. Keep held-out references in their restricted bucket. A signer/phrase-family split policy is selected before release; repeated recordings of the same phrase must not accidentally leak evaluation meaning into training.

## Next implementation step

The first migration and transactional assignment functions now pass a metadata-only synthetic blind-review-to-JSON-export test. Next, implement a cloud upload/playback/export integration with a small synthetic video and verified file checksums. Before real recordings: select authentication and hosting, complete budget/queue and reward workflows, implement consent/retention rules, calibrate scoring, configure service permissions, and test denied access to held-out answers.
