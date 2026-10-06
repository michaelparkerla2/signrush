# Upload diagnostic — 2026-10-06

## Production evidence

- Seven current signing jobs: six assigned, one upload_requested from September 27. The pending request has declared WebM bytes but no issued upload session. No participant document was changed during this investigation.
- Player dashboard updates stopped September 26 UTC (September 25 Pacific).
- Repository worker_runtime runs bounded operator sessions (30 minutes by default), not a durable service. Operator reports only Cloud Shell / no confirmed persistent host.
- Cloud Run API is disabled in both signrush-login and signrush. Cloud Functions API is disabled in signrush-login. This does not inventory unrelated external hosting.
- Authenticated isolated Cloud Storage resumable upload succeeded, including preflight and PUT CORS for https://signrush.io and identical readback. A 69-byte synthetic text object remains under smoke-tests/upload-diagnostic-1791327512076/synthetic.txt, outside corpus records. This tests transport with administrator authorization, not a participant or valid video.

## Browser repairs

- Failed upload releases its in-flight flag and offers an explicit retry while retaining the local recording.
- Delayed preparation/checking shows a message after 30 seconds instead of indefinite apparent progress.
- A reloaded unfinished upload explains that the local recording is unavailable. Videos held only in browser memory cannot be recovered from the server before upload.
- Late upload failures after signout cannot change the next session.

## Verification and remaining blocker

49 browser/controller tests and three Python upload/technical-validation unit tests passed. No real camera was activated and no synthetic clip was entered into participant rewards or corpus queues.

Reliable public submission remains blocked on a durable cloud worker deployment. Restarting Cloud Shell is temporary. No Mac-hosted service, paid upgrade, new cloud access grant, or claim of production readiness was made. Deploy the existing consent-checking worker and media tools on an approved persistent host, then test an isolated non-reward video through request, grant, PUT, technical verification, and saved state. Do not reset participant tasks or erase their evidence to manufacture a successful result.
