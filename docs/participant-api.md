# Participant API: first tested slice

Status: implemented and tested locally against a disposable PostgreSQL database. **Not deployed and no player uploads have been accepted.** A separate browser login and sign-out has now been verified; this API has not yet received a real Firebase user token. The existing cloud smoke test remains an administrator-only test.

## Identity and access

The runtime verifies Firebase ID tokens using the official Admin SDK with `check_revoked=True`. Verified email and an explicit pilot UID allowlist are required. Tokens come from the `Authorization: Bearer …` header only. Account IDs supplied by a browser are never used as identity. Authentication outages fail closed. Firebase Authentication and Google sign-in are enabled in the separate UMI-owned `signrush-login` project on the no-cost Spark plan. Web app registration and a real Chrome sign-in/sign-out test are complete; the test UID is recorded in ignored local pilot data for deployment. The backend verifies tokens issued for `signrush-login`; storage remains in `signrush`. The deployed backend service identity will need narrowly scoped Firebase Authentication read access in the login project for revocation checks, in addition to its storage access in the media project.

Migration 002 creates a `signrush_api` group role with access only to eight narrowly scoped functions. The login service authenticates the subject before invoking them. It cannot directly read prompts, interpretations, hold-out membership, or training manifests, or edit tables. The startup check rejects migration-owner credentials. The database is never exposed to browsers. This restriction does not protect against a compromised trusted API impersonating subjects; cloud IAM and runtime isolation remain essential.

The API storage adapter uses only `umi-signrush-raw`. Upload objects have opaque names in `pilot/uploads/`. Playback requires an active owned validation assignment, current consent, an active signer, and a generation-pinned silent asset under `pilot/playback/`. No client-selectable bucket/path or held-out endpoint exists. Cloud IAM denial for a distinct runtime identity is still untested; application checks do not replace it.

Consent is explicit and versioned. The disclosure includes UMI's training/evaluation use and retention of failed attempts. The pilot does not accept older consent versions. Withdrawal blocks further participation and playback requests; bytes already delivered to a browser cannot be recalled.

## Endpoints

All `/v1/` routes require verified, invited identity. No permissive CORS is enabled; deploy behind the same web origin.

| Route | Result |
|---|---|
| `POST /v1/account` | Creates/loads the caller's account; returns consent state |
| `GET /v1/consent` | Current rules, training disclosure and version IDs |
| `POST /v1/consent` | Records acceptance or withdrawal with exact version IDs |
| `POST /v1/signing/next` | Resumes an assignment or randomly selects an active reviewed latest phrase |
| `PUT /v1/signing/{id}/video` | Accepts bounded MP4/WebM bytes for the caller's assignment; returns processing state |
| `POST /v1/reviews/next` | Resumes/claims an eligible blind review; returns only task/reward/playback endpoint |
| `GET /v1/reviews/{id}/video` | Authorized silent video bytes, optional single HTTP Range |
| `POST /v1/reviews/{id}/answer` | Locks interpretation; exact retries return the same pending answer |

Playback requests need the bearer header. A future browser UI should fetch the bounded video with that header and create a temporary blob URL, or use a properly authenticated same-origin media layer. Do not put ID tokens in video URLs. Responses are private and `no-store`.

## Upload quarantine and costs

Uploads are at most 20 MiB, five lifetime reservations per account, and 100 reservations globally in this pilot. Reservations count even when interrupted or malformed. The global budget row serializes reservations; these deliberately conservative limits require explicit administrative reconciliation. They bound this upload intake, not every possible cloud charge (playback/compute still need deployment rate limits and monitoring).

Incoming bytes are streamed to a bounded temporary file and uploaded with a create-only generation precondition. In a cloud deployment the temporary file is on cloud runtime disk; it is removed when the request finishes. Upload completion records the object generation, byte count and SHA-256. Object names and storage credentials never appear in the participant response. Only test points are returned; no rewards are paid.

An uploaded object **does not become playable automatically**. The next media-worker slice must probe file contents (never trust the MIME header), check duration/dimensions, strip all audio and metadata, record immutable media provenance, verify clip bounds, and assess quality before opening reviews. That worker must retain failed/uncertain attempts separately with the consent/retention policy, and reconcile abandoned tickets and orphaned objects. Currently uploaded objects remain quarantined in `processing`; there is no worker or retry/reconciliation UI yet. Review tests use explicitly prepared synthetic media records.

## Tests and running

`tests/test_api.py` runs HTTP requests against real functions through a restricted PostgreSQL login. Identity and object storage are explicitly injected test doubles: no cloud credentials, real players or videos are used. Ten API tests passed, plus eight browser registration-flow tests; the ten corpus tests passed in the earlier database slice. They cover identity spoofing, wrong-owner and expired playback, consent withdrawal, prompt exposure/self-review, locked answers, three-review capacity, upload ownership/caps/quarantine, and direct database access denial. The Firebase adapter test verifies the SDK revocation-check call; it is not a live Firebase integration test.

Dependencies tested with Python 3.11 are pinned in `backend/requirements.lock`. Install in an isolated environment; no global packages are needed. Apply migrations 001 and 002 to an empty dedicated PostgreSQL database as its migration owner. Create a separate LOGIN role inheriting `signrush_api`, with no other application privileges. Configure `.env.example` values securely in the runtime environment; this app does not automatically load `.env`. Never paste tokens or database passwords into chat.

```sh
python -m pip install -r backend/requirements.lock
python tests/test_corpus.py
python tests/test_api.py
uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8080
```

The test runner creates its own private PostgreSQL cluster and removes it afterward. Do not run the API under the migration-owner DSN. Production requires HTTPS, restricted network/database access, request rate limits, concurrency/timeouts, appropriate cloud service identity, and dependency/security maintenance. No cloud deployment or billing upgrade was performed for this slice.

## Next cloud step

Deploy and exercise the now-wired web login and enrollment/consent flow, using the recorded test UID as the initial allowlist. Choose a cloud PostgreSQL runtime within the user's free-only constraints before deploying; do not silently provision a billable managed database. Implement the media worker and actual service-account isolation tests before collecting participant videos. Queue counts, player UI, scoring/consensus, reward ledger, payments, export publishing, and controlled erasure remain later slices.
