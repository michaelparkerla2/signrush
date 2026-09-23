# Signing pilot — 2026-09-14

## Scope

The registered player's screen requests a server-assigned phrase from `data/pilot-phrases.json`, an initial set of three UMI-authored everyday phrases. These are pilot drafts, not an externally licensed lexicon or expert-qualified ASL evaluation set. Phrases may be assigned to multiple players. Stable phrase IDs and provenance are retained.

The camera starts on explicit click, requests no microphone, targets 720p/30 FPS and 1.2 Mbps, and records at most 30 seconds/8 MiB. Preview is mirrored; recordings are not. A player reviews the take, confirms framing and submits explicitly. Retakes and unsent recordings stay in browser memory; sign-out stops tracks and releases blob URLs. Refreshing loses an unsent take.

## Cloud flow

- Browser creates one `signingJobs/{Firebase UID}` request. Rules require invitation and current consent. Only that player can read its assigned phrase and upload capability.
- `tools/signing_worker.py` runs temporarily in authorized Cloud Shell and rechecks consent server-side. Firestore transactions reserve at most three assignments globally, one per player. Reservations are not automatically refunded or recycled.
- The worker stores the assigned prompt snapshot in admin-only `pilotRecordings/{assignmentId}`. It issues one new-object-only Google Cloud Storage resumable session with the exact declared size and content type.
- Video bytes go directly from the browser to `umi-signrush-raw`, never through this Mac's filesystem. JSON API upload CORS requires no public bucket or IAM changes. The session URL is a bearer credential kept in the private job document and browser memory, never printed or exported. Google sessions can last up to a week; a stopped worker does not itself revoke an issued session. The pilot's fixed reservations bound exposure; prompt consent checks do not retroactively invalidate a previously issued capability.
- The worker polls for uploaded objects, pins their generation, verifies byte count and whole-file SHA-256, and runs bounded FFprobe checks on a temporary Cloud Shell file. It requires one video stream, no audio, at least 640×360, and a duration between 0.5 and 31 seconds. These checks do not establish good lighting, full hand visibility, ASL accuracy or human consensus.
- A saved result is unvalidated and has `exportEligible: false`, no translated reference, no review results, no points and no cash. Failed technical attempts go under `pilot/failed/{assignmentId}/`; regular recordings use `pilot/recordings/{assignmentId}/`. Receipts reference the raw video generation and hash. Raw original prompt snapshots are written separately to `umi-signrush-heldout-answers/pilot/references/{assignmentId}.json` and identified as unvalidated prompts.
- A future approved corpus exporter must check current consent, distinct reviewers, quality and qualification, and then produce the agreed JSON-array manifest. This pilot does not mark an original prompt as a verified translation.

The worker uses the authorized administrator's Cloud Shell credentials for this private test only. Production service-account isolation, App Check/rate limiting, durable hosting, grant expiry/cancellation, automatic recovery of a crash during upload-grant issuance, abandoned-session reconciliation, review queues and corpus release generation remain subsequent work. Browser rules do not constrain an administrator, so this worker must not be exposed as arbitrary database or storage CRUD. There is no public HTTP backend.

## Test evidence

- 11 Firestore Rules emulator tests passed in Cloud Shell; extended rules deployed successfully.
- 3 worker transaction tests passed against an isolated Firestore emulator: concurrent global cap, consent withdrawal, single upload grant and saved receipt. Storage was an explicit test double for these tests.
- 3 local worker validation unit tests, 6 recorder lifecycle tests and 8 registration controller tests passed.
- A real Cloud Storage smoke test uploaded a 475,403-byte synthetic MP4 through a resumable session, checked browser CORS response headers, matched the cloud read-back SHA-256, and passed FFprobe checks. It used a separate `smoke-tests/signing-upload-*` object, not a player task.
- Desktop layout inspected using a separate nonfunctional fixture with a synthetic phrase, not by forging a real player session. Real camera capture is the user's next test.

## Running the private test

Cloud directory: `/home/michael/signrush-signing-pilot`. Dependencies and FFmpeg live in Cloud Shell, not the Mac. From that directory:

```sh
.venv/bin/python tools/signing_worker.py --seconds 1800
```

The worker stops after 30 minutes and can stop earlier if Cloud Shell disconnects. Restart explicitly for later testing. The canonical phone preview is `https://signrush-login.web.app/`, deployed through Firebase Hosting on the existing Spark project. The worker now authorizes that HTTPS upload origin. Local `python3 tools/serve_login.py` remains useful for layout development, but use the hosted address for uploads. This is a temporary private pilot, not persistent public hosting. Keep signing job documents/session credentials out of logs and exports.

Useful source documentation: [Google resumable uploads](https://docs.cloud.google.com/storage/docs/resumable-uploads), [JSON API CORS behavior](https://docs.cloud.google.com/storage/docs/cross-origin).

## HTTPS phone preview

Firebase Hosting deploy succeeded on 2026-09-14. Published HTML and three core JavaScript assets matched local SHA-256 hashes. Backend script, pilot-identity file and Firestore rules URLs returned HTTP 404. HTTPS camera permission is limited to self; microphone is disabled through Permissions-Policy. The welcome page loaded successfully and was inspected at 390×844 CSS pixels; the temporary viewport override was reset.

The synthetic 475,403-byte upload passed again with the hosted HTTPS origin: preflight and upload CORS headers, whole-file hash and silent-video technical checks. This is not yet a real iPhone camera/browser-upload test. The temporary Cloud Shell worker was restarted for 30 minutes for the user test. Login and data access remain invitation-only, although the static welcome page itself is public and marked noindex. No billing-plan upgrade, public media access or new IAM grants were made.

## Phone UX correction

After the first real phone test, the user reported that the assigned phrase looked like an instruction and scrolled away from the camera. The updated UI labels it “Please sign this phrase,” adds explicit quotation marks, and keeps the colored phrase header with the camera preview in a sticky capture surface. Registered players enter the compact recording workspace directly; Account expands the registration/consent controls, and recording tips are collapsed. The prompt remains visible during review and recording.

Recording and review fixture layouts were inspected at 390×844 and 375×667 CSS pixels; real camera access was not triggered for these visual checks. All 15 recorder/onboarding tests passed, including prompt visibility in recording and review. The four changed assets matched the deployed HTTPS files. Cloud Shell’s active pilot worker reported `Recording finalized: saved` after the user phone test; this confirms the saved technical-check state, not ASL translation accuracy.

### Explicit completion state

The saved task now shows “Task submitted” and “Awaiting review,” explains that the recording is saved and reviews have not opened, and says another pilot task is not available. No points are invented or awarded. Terminal cloud state takes precedence over the local preview blob, so the completion screen appears immediately after saving as well as after reload. Eight recorder tests passed, including the just-saved transition. Changed assets matched the deployed files. No task, recording or quota was reset.

### Account-only agreement details

For registered players, the full rules, training disclosure, version labels and withdrawal action are now inside the collapsed Account → Rules & training agreement section. The registration-success paragraph and profile heading are not shown for accepted accounts. Signup/current-consent-required states still show the full disclosure and explicit agreement form; withdrawal remains available inside the expandable account section. Eight onboarding-controller tests passed.
