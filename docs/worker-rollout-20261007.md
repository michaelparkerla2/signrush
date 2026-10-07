# Durable upload worker rollout — 2026-10-07

## Outcome

The upload worker now runs in Google Cloud independently of Cloud Shell and the developer computer. The user explicitly approved metered deployment to the existing billed `signrush` project. `signrush-login` remains on its existing unbilled configuration; no Firebase plan upgrade was performed.

- Service: `signrush-worker`, project `signrush`, region `us-east1`.
- Worker source revision: `e9c294f`.
- Container: `us-east1-docker.pkg.dev/signrush/signrush-worker/worker:e9c294f`.
- Ready revision: `signrush-worker-00003-lbj`.
- Scheduler: `signrush-worker-minute`, every minute, authenticated OIDC.
- Zero minimum instances, maximum one instance, concurrency one, 1 CPU, 512 MiB, request-based CPU allocation, no startup CPU boost.
- Pending work runs on the next scheduled cycle, so granting an upload or checking a submitted clip can take roughly a minute, plus processing time. This is not an instant synchronous endpoint.
- Idle checks do not scan the whole corpus. Full maintenance runs at least every 15 minutes. Firestore remains subject to the existing project's quota; this deployment is not a guarantee of capacity for the full 4,000-clip collection.

The service, scheduler and build settings are recorded under `deploy/`. The build source archive was explicitly allowlisted: Python worker sources, pinned requirements, prompt catalog, legal version manifest and Docker build files. No credentials, user exports, repository metadata or private corpus media were included. The staging bucket is private with seven-day source retention.

## Production-path tests

Two artificial, non-human clips completed the actual cloud pipeline:

1. Backend phrase assignment.
2. Exact-byte-count and content-type resumable upload grant.
3. Origin-constrained direct upload to the private storage bucket.
4. Cloud hash and FFprobe validation.
5. `saved` state and private receipt/reference persistence.
6. Explicit `test_only` consensus status, no reward eligibility and `exportEligible: false`.

MP4: 475,403 bytes, two seconds, 640×360, uploaded using the `https://signrush.io` origin. WebM: two seconds, 640×360, uploaded using `https://www.signrush.io`. Both passed technical checks.

An isolated reviewer fixture exercised cloud playback conversion and signed URL issuance. Signed playback returned HTTP 200 with MP4 media; unsigned access returned HTTP 403. Refreshing playback succeeded on the final deployed worker revision. Anonymous invocation of the worker returned HTTP 403. The service has no public invoker binding.

These were administrator-seeded test fixtures, not impersonated real users or actual legal acceptances. No Firebase Authentication accounts were created. Test identities are explicitly marked diagnostic/test-only; their clips were excluded from public review assignment before uploading. They remain as private audit evidence, not training examples, winners, participant signups or earnings.

The test used synthetic video and direct HTTP transport, not a physical phone camera. Browser camera lifecycle and submission behavior are covered by the existing controller tests; this report does not claim testing every phone/browser or real ASL quality.

## Recovery

The September 27 request had never uploaded a storage object. Its newly issued but unused session was cancelled, and the same job and phrase were restored to `assigned` with an administrative recovery event. The participant can record again. Missing video bytes from a closed browser cannot be recovered; no completed video was overwritten.

## Automated checks

- 77 worker transaction tests passed against the Firestore emulator.
- 31 Firestore permission-rule tests passed.
- Five final scheduled-worker authentication/lease/idle-work tests passed.
- Earlier upload-controller changes passed all 49 browser/controller tests.
- Multiple scheduled production cycles succeeded with no Cloud Shell process. Final-revision playback refresh was processed automatically.

## Operations

Inspect `workerHealth/scheduled` in Firestore and Cloud Run / Scheduler logs. `cycle_finished` means the cycle finished; per-job retry logs and task progression must also be checked because individual task errors are retried. Never print signed upload or playback URLs into logs.

To stop processing, pause the scheduler. To roll back, route the service to a known-good revision. Do not delete participant history or make buckets public. Keep the runtime, scheduler and builder service accounts separate. Resource manifests contain no private keys.

Google Cloud free allowances are not a hard cost cap. The user approved possible usage charges; scaling and queue checks reduce idle consumption but do not guarantee a zero bill. No cash payout integration, reward policy or public winner content was changed by this repair.
