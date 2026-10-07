# Private scheduled upload worker

Status: cloud deployment and production-path verification completed on 2026-10-07; see `worker-rollout-20261007.md` for evidence and limits.

The existing `signrush` storage project has billing enabled; `signrush-login` does not. Do not upgrade Firebase or attach billing to it. The user explicitly approved metered cloud worker deployment on 2026-10-07; this is an exception for this deployment to the repository's free/trial-only default. No zero-cost guarantee is possible from a free allowance; other account usage can consume that allowance.

## Design

Run the existing Python ConsensusWorker (including signing and reviews) in a private Cloud Run service. Cloud Scheduler calls POST /tick every minute using a dedicated service account and OIDC token. Each request checks for queued work; full cycles run for pending work or at least every 15 minutes for maintenance; there is no background thread that depends on idle CPU. Leave minimum instances at zero. Keep request-based billing, concurrency 1, maximum instances 1, CPU 1, memory 512MiB, request timeout 480 seconds, and startup CPU boost disabled. The FFmpeg tools run inside the cloud container, never on the operator's computer.

The service also checks the verified caller email and token audience. Cloud Run IAM must require authentication; never grant allUsers or allAuthenticatedUsers. The Firestore `workerHealth/scheduled` lease prevents concurrent cycles across revisions; a process watchdog kills a stuck container before its 10-minute lease expires. Existing transactional upload grants recover after interruption. A finished cycle is not proof every job succeeded: existing worker per-job retry logs and actual job progression must also be checked.

Existing corpus, privacy, consent, independent-review and reward logic is retained. No participant request bodies or media are accepted by the trigger endpoint.

## Deployment inputs and permissions

Build with `deploy/worker.Dockerfile` from the repository root. Its Docker-specific ignore file excludes credentials, Git metadata, client assets and local exports. Upload only the same allowlisted source files when building through Cloud Build; Docker ignore rules do not control the source archive sent to Cloud Build.

Create dedicated runtime and scheduler identities in signrush. Runtime needs Firestore data access (`roles/datastore.user`) in signrush-login, object read/create/delete permissions only on umi-signrush-raw, and object read/create permissions only on umi-signrush-heldout-answers. Review playback requires signBlob on the existing signrush-playback service account; grant that permission only on that account and verify its existing bucket read access. Do not issue service-account keys. Scheduler needs only run.invoker on this service. The deployer needs permission to act as the two service accounts; don't use Owner as a workaround.

Enable Cloud Run, Cloud Build, Artifact Registry and Cloud Scheduler in the existing billed project only after approval. Use a private container repository in us-east1, close to the media bucket. Build, deploy privately, then set WORKER_AUDIENCE to the exact service URL and WORKER_CALLER to the scheduler service-account email. The service fails closed without both variables. Bootstrap with a placeholder HTTPS audience, obtain the assigned service URL, update the environment, and only then enable the schedule.

Configure Scheduler with the service URL plus /tick, POST with no body, the runtime's exact service URL as OIDC audience, UTC schedule `* * * * *`, and a 480-second attempt deadline. Do not point Scheduler directly at participant data. Budget alerts are notifications, not a hard spending cap.

## Required rollout verification

1. Run the unit and Firestore emulator tests. Build the actual container and confirm FFprobe/FFmpeg and Python imports.
2. Verify anonymous requests cannot invoke the cloud service; a wrong caller or audience must fail.
3. Trigger an authenticated cycle, check workerHealth and retry logs without printing signed URLs. Confirm no Cloud Shell/local process is needed.
4. Use an explicitly isolated test identity and synthetic video, excluded from training/rewards, to exercise assignment, upload authorization, browser-origin CORS/PUT, hash and technical checks, and saved state. Check reviewer playback authorization separately.
5. Close Cloud Shell and verify scheduled cycles continue. Check signrush.io and the Firebase domain.
6. Inspect the old September 27 task without inventing its missing video. A clip never uploaded and lost from browser memory cannot be recovered; arrange a controlled retry that preserves the historical request.

Pause the scheduler to stop processing. Roll back the Cloud Run revision for code regressions. Do not roll back by deleting participant records, widening bucket visibility or resetting balances.
