# Reliability and readiness — 2026-09-23

## Existing-host worker operation

The three Python entry points share `tools/worker_runtime.py`. Sessions default to 30 minutes and can explicitly run for up to 8 hours on the existing host. SIGINT/SIGTERM stop new ticks and allow the current operation to finish. Tick failures log exception types only and back off up to 60 seconds. A filesystem lock prevents two upgraded workers on the same host/user from running together; it does not coordinate different hosts or legacy workers. Stop any legacy worker first. Never run all three entry points together; the consensus worker includes signing and reviews.

```sh
GOOGLE_CLOUD_QUOTA_PROJECT=signrush-login .venv/bin/python -u tools/consensus_worker.py --seconds 28800
```

Keep the existing Cloud Shell session available. This does not prevent Cloud Shell suspension, add durable hosting, bypass quotas, change the three-recording cap, or guarantee continuous service. After host termination, restart the command explicitly. Do not reset reservations or balances to recover a worker. No scheduler, new service, bucket, account or paid plan was created.

Upload grants now have a 90-second lease and per-attempt token. A crash or timeout while creating a resumable upload session can be retried without allocating a new recording. Publication rechecks consent and the attempt token transactionally. An obsolete attempt cannot replace the current grant. This does not yet reclaim abandoned uploads/reviews or reservation slots.

Dashboard queue timestamps refresh at most every 30 seconds when unchanged. The browser trusts an empty queue only while that summary is fresh; stale or missing timestamps trigger a server assignment request. A current empty response still returns immediately. Runtime timestamps are estimates of queue freshness, not promises that an eligible video is reserved.

## Read-only payment and export audit

```sh
.venv/bin/python tools/audit_readiness.py
```

Uses the existing `signrush-login` project, reads up to 1,000 documents per collection, and fails rather than silently truncating larger collections. Outputs aggregate counts only. Does not fetch payout destinations, write data, send payments or export recordings. Because reads are not a single snapshot, recheck a discrepancy while the worker is stopped before making any correction.

Verified live snapshot before starting the updated worker: 3 recordings; 0 reward events, 0 wallets and 0 saved payout preferences. No invalid reward events, balance mismatches, invalid payout metadata or unexpectedly export-eligible recordings were found. Zero records is not proof of a working cash-payment workflow.

Real cash accounting and withdrawal processing are not implemented. Test points cannot be treated as USD. Before manual payments, implement a separate integer-cent ledger, immutable earning IDs, transactional withdrawal reservation, confirmed payee snapshot, unique provider payment reference and reconciliation. An ambiguous provider response must remain pending until checked; never resend merely because a page timed out. Only a confirmed failed/cancelled transfer can release its reservation. Saving a PayPal/Venmo string does not verify ownership or authorize a payment. No payment was made or enabled during this work.

## Corpus privacy boundary

The live worker continues to mark recordings `exportEligible: false`. Private GCS receipts and interpretation snapshots are retained research evidence, not approved training releases. The reference PostgreSQL exporter is a separate implementation; its tests cover signer/phrase/recording holdouts, withdrawn consent, failed/uncertain records and newer unapproved annotations. Passing those tests does not install that exporter on the live Firebase data.

A production release exporter still needs current consent checks, reviewed annotations, stable signer mapping, holdout/split policy, pinned media provenance and release manifests. Existing exports cannot be recalled automatically. Do not bulk-download participant videos or payout details to a laptop or GitHub. No such downloads were performed for these checks.

## Phone/tablet review

`python3 tools/preview_layout.py` provides a loopback-only synthetic fixture with the real HTML/CSS and game/payout controllers. It loads no Firebase login and never writes participant data. It is outside the Hosting directory and must not be deployed. Open `http://localhost:8089/?width=390&mode=home`; supported widths include 320, 390, 768 and 1024. Modes cover landing, home, signing, decoding, ranks, payout, wallet and avatars.

The 32 screen/width combinations showed no page-wide horizontal overflow. The payout form and leaderboard were visually checked on phone widths and the recording layout on tablet width. These are desktop-browser responsive checks, not physical iOS/Android camera, virtual-keyboard or Google OAuth verification. Those device-specific checks remain necessary before claiming full device support.

## Rollback

Keep the previous worker files and frontend before replacement. Stop the updated worker, restore the previous files and restart it with its original 1800-second limit. Restore/redeploy the previous `web/review.mjs` if necessary. New lease fields and dashboard timestamps require no schema migration; do not delete recording, consent or reward history. A legacy worker will not recover `granting` jobs, so prefer fixing forward or reconcile those jobs deliberately.

## Validation results

- 37 frontend controller tests passed.
- 37 Firestore emulator transaction test executions passed, including interrupted grants and consent withdrawal during grant creation (imported test classes mean some cases repeat).
- 22 Firestore browser access-rule tests passed.
- 10 isolated PostgreSQL corpus tests passed; the temporary database was stopped and removed.
- 3 runtime tests, 2 aggregate-audit tests, 3 signing checks and 2 dashboard tests passed.
- Synthetic responsive layout checked at 320, 390, 768 and 1024 pixels.
