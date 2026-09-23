# SignRush developer handoff

Updated 2026-09-23. Audience: UMI’s authorized developers, including Sam and maintainer. Read this before using older dated notes. This document distinguishes the live implementation from reference code and future plans.

## 1. Ownership, environments and source

SignRush is a UMI asset. The owner operates the current cloud projects under `umi.vision`. The repository contains the complete source currently available in this workspace, documentation, test fixtures and deployment configuration. It does not contain participant videos, cloud database contents, credentials, dependency installations, Cloud Shell history or external FLEURS/UMI model repositories.

| Resource | Exact identifier / entry point |
|---|---|
| Public app | https://signrush-login.web.app/ |
| Firebase project | `signrush-login` (project number `886992538485`) |
| Firebase console | https://console.firebase.google.com/project/signrush-login/overview |
| Firestore database | `(default)`, Native Standard, `us-east1` |
| Media project | `signrush` |
| Cloud storage console | https://console.cloud.google.com/storage/browser?project=signrush |
| Original/derived media | `gs://umi-signrush-raw` |
| Hidden references | `gs://umi-signrush-heldout-answers` |
| Release storage | `gs://umi-signrush-exports` |
| Playback identity | `signrush-playback@signrush.iam.gserviceaccount.com` |
| Owner’s existing Cloud Shell checkout | `/home/michael/signrush-signing-pilot` |

A collaborator’s Cloud Shell home is separate from the owner’s. Clone the repository into your own Cloud Shell or developer checkout. Do not assume a process or file in the owner’s session exists in yours. Multiple worker instances can contend; coordinate one operator for the live pilot.

Hosting is public, but Firestore and media are private. Firebase is on Spark; media storage is in a separate billing-linked project originally operated under the trial. Check the actual account’s remaining trial/quota before provisioning resources. No paid plan upgrade or new paid service is authorized.

## 2. What is actually running

`web/login.js` connects Google Authentication, `firestore-registration.mjs`, `signing.mjs`, `review.mjs` and `home.mjs`. Firebase SDK web identifiers in `web/firebase-config.js` are public configuration, not server credentials. They do not grant data access.

The browser submits narrowly shaped requests into owner-only Firestore documents. `tools/consensus_worker.py` inherits `ReviewWorker`, which inherits the signing `Worker`. It polls every five seconds and updates sanitized dashboards roughly every ten seconds. Processing uses the operator’s Cloud Shell application-default credentials today, not a production runtime identity. FFmpeg/FFprobe run in Cloud Shell with temporary media files; browser uploads go directly to private Cloud Storage.

`backend/app.py` (FastAPI) and `db/migrations/` (PostgreSQL) are locally tested reference code. The live app does not call those HTTP routes. `.env.example`, `SIGNRUSH_PILOT_UIDS`, PostgreSQL limits and reference API invitation checks apply to that reference deployment, not live open registration. Do not deploy it as a drop-in replacement without adapting storage, identity and UI integration.

## 3. Player flow and privacy boundaries

1. A verified Google account registers a test profile. `web/pilot-disclosure.mjs` supplies rules and explicit training-use consent. Consent acceptance/withdrawal is an atomic profile-plus-immutable-event write.
2. A signing request reserves a phrase, saves exposure and creates an opaque recording ID. The three draft phrases are in `data/pilot-phrases.json`; do not silently change an existing phrase’s meaning/ID. Introduce versioned entries when expanding the corpus.
3. The user records without audio, reviews locally, confirms framing and submits. The worker issues a single create-only resumable upload session pinned to the declared size/type. Unsubmitted retakes stay in browser memory.
4. The worker pins the stored object generation, verifies whole-file SHA-256 and technical video properties, and stores private receipts and the prompt reference. Technical checks do not establish ASL meaning or framing quality.
5. Other eligible players receive silent playback copies through signed links (maximum five minutes; three grants per review). References and peer answers are never in the assigned review job. A signed URL is a bearer capability until expiry; stopping the worker does not instantly revoke it.
6. Review assignment, playback and submission recheck consent and independence. Same UID, known `samePersonAs` aliases, duplicate reviewers and known phrase exposure are excluded. Unknown multi-account abuse/collusion is not solved.
7. Three eligible exact normalized reference matches plus quality approval can qualify a recording. Additional evidence opens at most five review assignments. Unknown paraphrases are not scored as semantically wrong; unresolved cases require adjudication, whose operator UI is not built yet.
8. Deterministic reward-event identities prevent duplicate test-point awards. Original records remain even when the current job is replaced for another task.

Current limits: three global recording reservations (including abandoned ones), 8 MiB, recorder limit 30 seconds, technical duration 0.5–31 seconds, minimum 640×360, one video stream and no audio. The reference API has different limits; do not confuse them. Do not reset counters to reopen slots without reconciling existing reservations. Worker queries also assume the three-recording cap: raising just one constant is insufficient.

## 4. Live Firestore collections

| Collection | Purpose / access |
|---|---|
| `players/{uid}` | Profile, status, test mode, current consent pointer; owner-only browser access |
| `players/{uid}/consents/{id}` | Immutable consent events and exact version IDs |
| `pilotInvites/{uid}` | Legacy name for admin-controlled active/block, `samePersonAs`, `testOnly`; browser denied |
| `signingJobs/{uid}` | Current request/phrase/upload capability/outcome; only participating owner |
| `reviewJobs/{uid}` | Current blind review/playback capability/answer/outcome; only participating owner |
| `pilotLimits/signing-v1` | Global `reserved` count; admin-only |
| `pilotActivity/{uid}` | Exposure history, including prior signing/reviewed phrase IDs |
| `pilotRecordings/{assignmentId}` | Prompt snapshot, signer UID, media provenance, technical checks, reviewer IDs and consensus |
| `pilotReviews/{reviewId}` | Independent answer, quality response, assignment/recording linkage |
| `rewardEvents/{id}` | Immutable, idempotent test awards |
| `payoutPreferences/{uid}` | Private, unverified PayPal/Venmo destination; see [payout setup](payout-preferences.md); never a payment authorization or corpus field |
| `playerRewards/{uid}` | Server-controlled, owner-readable balance |
| `playerDashboard/{uid}` | Sanitized counts; server controlled, owner-readable |

No invitation document is needed for new public enrollment. If an admin record exists it must have `active: true`; `active: false` blocks access. **Deleting a blocked record would reopen public enrollment.** `testOnly` records are excluded from qualifying rewards/reviews. Do not use `tools/invite_pilot.py` for ordinary public enrollment: it deliberately creates test-only accounts. Known owner-linked testing accounts retain their exclusions.

Never export entire signing/review job documents casually: they can contain live `uploadURL` or `playbackURL` capabilities. Keep them out of logs, GitHub and training manifests. Admin access bypasses Firestore browser rules; privileges are not proof that a bulk edit is safe.

## 5. Storage, corpus and held-out data

All three buckets use private access, uniform bucket-level access, public-access prevention and Google-managed encryption at rest. Transport uses HTTPS. Bucket separation does not restrict a project owner or other broad inherited role. Playback identity has conditional object read on `umi-signrush-raw/pilot/playback/` only; it must never gain raw/held-out read access. Keyless signing uses IAM Credentials; the current owner has Token Creator on that service account.

| Prefix | Content |
|---|---|
| `raw/pilot/recordings/{id}/` | Original submitted media and `receipt.json` (where `raw` denotes the raw bucket) |
| `raw/pilot/failed/{id}/` | Failed technical attempts and receipts |
| `raw/pilot/playback/{id}/silent-v1.mp4` | Silent normalized playback derivative |
| `raw/pilot/reviews/{reviewId}.json` | Private independent interpretation evidence |
| `raw/pilot/decisions/{id}/{digest}.json` | Versioned decision snapshot |
| `heldout/pilot/references/{id}.json` | Original prompt, explicitly not a verified translation |
| `smoke-tests/…` | Synthetic infrastructure tests; exclude from real corpus releases |

Use exact object keys/generations in the stored records instead of assuming file extensions. Retain raw prompts separately from verified meanings. A signer may produce a different meaning; majority agreement is evidence, not automatic ground truth. Failed/uncertain records remain distinct and are not automatically negative labels.

There are two separate concepts: (a) hide prompts during blind validation; (b) keep evaluation sources/phrases/signers out of training releases according to the eventual split policy. The production qualification/export pipeline and stable mapping from Firebase UIDs to corpus signer numbers are not implemented. Live records remain `exportEligible: false`.

The tested reference PostgreSQL exporter emits a **JSON array**, one record per time-bounded clip, with `example_id`, `document_id`, `sentence_id`, `video_name`, relative `source_path`, whole-source `source_sha256`, `start_time_sec`, `end_time_sec`, `eng`, `reference`, `reference_provenance`, stable `signer` and `fs_terms`. Downstream qualification assigns `partition`, `lane` and `generalization`. This is the user’s local loader contract, not an official subnet submission standard. Clip times are relative to the complete source video; hash the full file, not the extracted clip. Existing extraction normalizes to 30 FPS, height at most 720 and no audio.

Consent and approved annotation/split membership must be rechecked at release time. Previously exported copies cannot automatically be recalled. Retention/deletion propagation and an audited corpus publisher remain future work.

## 6. Developer setup and checks

Use Node 22 or 24, Python 3.12, Java 21 for the Firestore emulator, and FFmpeg/FFprobe. The reference PostgreSQL tests need PostgreSQL 16+ tools on PATH. Keep media work in cloud; the owner’s Mac has limited storage.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r tools/signing-requirements.txt
(cd firestore && npm ci)
node --test tests/*.mjs
.venv/bin/python -m unittest discover -s tests -p 'test_signing_worker.py'
.venv/bin/python -m unittest discover -s tests -p 'test_consensus.py'
.venv/bin/python -m unittest discover -s tests -p 'test_dashboard.py'
(cd firestore && npm test)
(cd firestore && node_modules/.bin/firebase emulators:exec --only firestore --project demo-signrush-rules 'cd .. && PYTHONPATH=tools:tests .venv/bin/python -m unittest test_signing_transactions test_review_transactions test_consensus_transactions test_open_transactions.OpenEnrollment')
```

Transaction tests require `FIRESTORE_EMULATOR_HOST` and use synthetic demo projects/anonymous credentials. Do not point them at production. The local reference tests create isolated PostgreSQL clusters; see `docs/participant-api.md` for their separate dependency installation and scope.

`python3 tools/serve_login.py` serves only `web/` at localhost:8088. It still uses the configured live Firebase project, so it is not an isolated database sandbox. Use the hosted HTTPS origin for real phone uploads; the worker’s allowed upload origin is fixed to that address. For a staging environment, create and configure separate authorized resources first; no staging project exists today.

## 7. Deploy and operate

Authenticate using your own granted Google account (Cloud Shell uses its signed-in identity). Never copy the owner’s ADC files or tokens. For local SDKs use `gcloud auth application-default login` and the appropriate quota project, after receiving permissions. Firebase CLI login is separate. No service-account key files are required.

From the repo root, after tests:

```sh
(cd firestore && node_modules/.bin/firebase deploy --only firestore:rules --project signrush-login --non-interactive)
firestore/node_modules/.bin/firebase deploy --only hosting --project signrush-login --non-interactive
GOOGLE_CLOUD_QUOTA_PROJECT=signrush-login .venv/bin/python -u tools/consensus_worker.py --seconds 1800
```

Run one worker in the foreground while testing; keep that terminal open. It stops after 30 minutes. A Cloud Shell VM may terminate sooner. Restart only when needed and check its output; “ready” is not proof that every operation succeeded. On a newly restored Cloud Shell VM, FFmpeg may need reinstalling even though the home directory and virtual environment survive. Use the official OS package manager for FFmpeg.

The website/login remain available without the worker, but task assignment, media processing, reviews and queue updates stall. Do not tell players it is an always-on public game yet. No GitHub auto-deployment is configured: a git push backs up code; explicit Firebase deployment and worker update are still required.

`tools/setup_review_playback.py` mutates IAM and hardcodes the original owner; read it before use. Do not rerun it as a generic bootstrap for new developers. `tools/check_firestore_pilot.py` can create an old owner invitation and prints profile metadata. It is a historical diagnostic, not a general health command.

## 8. Retrieve data without exposing it

Developers need explicit IAM in addition to repository membership. Browse the bucket Console or use Google Cloud CLI in a cloud/training environment. List a narrow prefix first; then copy selected exact objects. Do not sync full buckets to the owner’s Mac.

```sh
gcloud storage ls gs://umi-signrush-raw/pilot/recordings/
gcloud storage ls gs://umi-signrush-raw/pilot/failed/
gcloud storage ls gs://umi-signrush-heldout-answers/pilot/references/
gcloud storage ls gs://umi-signrush-exports/
```

Use Firestore Console or the Python Firestore SDK with `project='signrush-login'` to look up a recording by its stable assignment ID. `pilotRecordings/{id}` supplies exact media location/generation/hash, signer, original prompt and review linkage. Fetch its listed `pilotReviews` and decision snapshots, and the private held-out reference. Check the signer’s current consent event before any proposed training export. These are raw research evidence, not an approved training release.

Example selected copy (replace placeholders; run in a private cloud workspace):

```sh
mkdir -p private-exports/selected-recording
gcloud storage cp 'gs://umi-signrush-raw/pilot/recordings/RECORDING_ID/EXACT_FILENAME#GENERATION' private-exports/selected-recording/
gcloud storage cp 'gs://umi-signrush-heldout-answers/pilot/references/RECORDING_ID.json' private-exports/selected-recording/
```

Validate the copied whole-file SHA-256 against the pinned receipt before using clip times. Keep source provenance and independent review evidence together; never replace the prompt with a guessed translation. Private exports and cloud inventory output are ignored by Git. The repository is a source backup, not a media/database backup.

## 9. Collaborator access checklist

The owner must identify each collaborator’s **GitHub username and Google account email**. GitHub accounts and Google accounts are separate identities. Cloudflare uses a third identity/membership when introduced.

- Private repository **Write** access permits clone, push, branches and pull requests. Repository **Admin** is a separate privilege for settings, collaborator management and destructive operations; grant intentionally if needed.
- Firebase project access must cover Hosting deployment, Firestore data/rules management and Authentication administration according to the person’s operational role. Reading the repository alone grants none of these.
- Media access must cover the exact raw, failed, reference and export buckets required. A developer trusted with held-out references may inspect them; ordinary training identities must remain limited to qualified releases.
- Running the current worker requires Firestore read/write, relevant private object operations and keyless signing permission on the playback service account. Give each operator their own identity; do not share passwords or download owner keys.
- IAM administration and billing ownership are separate from building and retrieving data. Record actual grants when the owner supplies the recipients; no collaborator cloud grants are implied by this document.
- Cloudflare membership/Workers deployment permissions will be needed for the future Rust/Workers backend. No Worker, R2/D1 database, Wrangler project or Cloudflare migration has been set up yet.

Sam and maintainer’s configured identities, exact role grants, GitHub invitation status and access boundaries are recorded in [the collaborator access register](COLLABORATOR_ACCESS.md). Consult it for the current access setup; verify their own sessions at first use.

## 10. Known gaps and recovery

Priorities: durable worker hosting; scalable task/budget limits; curated phrase expansion; calibrated semantic scoring and ASL adjudication; identity abuse controls; reliable abandoned-job recovery; corpus signer mapping, split policy and release exporter; backup/restore and consent erasure workflows; then funded payments/referrals/prizes. Use Rust for new backend services and Cloudflare Workers where suitable; evaluate heavy video conversion separately.

Before changing production rules/worker state, record the deployed commit and keep a known-good checkout. To roll back code, deploy a previous known-good Git revision using the same explicit project IDs and restart the matching worker. Git rollback does not undo Firestore writes, consent, upload grants, ledger events or media changes. Cloud soft delete alone is not a tested whole-system backup. There is no automated production database backup/restore workflow in this repo yet.

Logs may identify failures by exception type without the full cause. Diagnose with targeted privileged reads in the cloud; do not print credentials, full job documents or hidden responses into shared tickets. Keep failed data and uncertainty intact rather than editing history to make tests pass.

## Account-free Rust preparation (2026-09-23)

The owner requests no new accounts or storage locations. Continue preparation locally using existing resources; obtain required deployment accounts/access from Sam later. `backend/rust-core` now contains a dependency-free Rust review-eligibility library with offline unit tests. It is not integrated or deployed. See its README for transaction/identity adapter requirements and deliberate fail-closed differences from Python. Current Python/Firebase/GCS behavior stays in place. Cloudflare access, authenticated adapters, parity/concurrency validation and deployment remain outstanding; do not describe the migration as complete.

### Rust consensus and reward preparation

The Rust core now includes the exact-match consensus decision stage, legacy/checked identity resolution, and a pure test-reward planner. Python-generated synthetic fixtures cover 135 cases; see `tools/generate_rust_consensus_fixtures.py`. Full Rust normalization, authenticated Firebase/Firestore adapters, transactional reservations/ledger writes and Cloudflare deployment are still outstanding. No cash activation or production cutover occurred. Identity cycles are a known legacy ambiguity: new reward planning rejects them; adapters must use the checked resolver. Existing Python/live behavior was not changed.
