# SignRush Rust core

Account-free first step toward Sam's Rust preference. This is a tested policy library, not a deployed backend or an HTTP service. No external Rust dependencies, cloud resources, credentials, new databases, or copied corpus data are required.

Run from the repository root:

```sh
cargo test --offline --manifest-path backend/rust-core/Cargo.toml
cargo clippy --offline --manifest-path backend/rust-core/Cargo.toml --all-targets -- -D warnings
```

## Included

Review assignment eligibility derived from `tools/review_worker.py`: saved and technically checked video, active signer/reviewer consent, exclusion of self/linked identities, previous phrase exposure, duplicate reviewers, finalized decisions, and the three-to-five review ceiling. Empty identity/phrase fields and explicit paused decisions additionally fail closed. No scoring, payments, media or database operations are implemented here.

## Adapter contract before live use

- Resolve canonical person IDs from trusted identity linkage records. Never accept them or consent/quality flags from clients. The Python `person_key` resolution is not ported yet.
- Read identity, consent, exposure and current recording/reviewer state inside the assignment transaction. Recheck eligibility and reserve the slot atomically; this pure function cannot prevent concurrent double assignment alone.
- Decode persisted statuses explicitly. Unknown statuses/malformed data must fail closed, not default to an open state.
- Preserve Firebase ID-token verification, private Firestore/GCS access and short-lived silent playback links. Return only opaque task IDs to participants, never hidden prompts or others' answers.
- Compare decisions against existing Python integration fixtures before a canary cutover. These unit tests are not end-to-end parity verification.

## No-account migration boundary

Keep the current Firebase projects and GCS buckets. Sam can later supply an existing Cloudflare account and narrowly scoped deployment access if Workers is selected. Do not create another account, database or storage location by default. Cloudflare integration still needs runtime/SDK selection, an authenticated Firebase/GCS adapter, secure configuration, transactional concurrency tests, deployment and rollback verification. Heavy FFmpeg processing remains on an appropriate existing compute service until a tested replacement is selected.

The live Python worker is unchanged; this library does not make task processing always-on. No Cloudflare Worker, Wrangler project or Rust endpoint has been deployed.
