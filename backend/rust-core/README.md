# SignRush Rust core

Account-free preparation toward Sam's Rust preference. This is a tested policy library, not a deployed backend or an HTTP service. The policy modules use the Rust standard library; the comparison executable uses pinned serde_json with a committed lockfile. No cloud resources, credentials, new databases or copied corpus data are required.

Run from the repository root:

```sh
cargo test --offline --manifest-path backend/rust-core/Cargo.toml
cargo clippy --offline --manifest-path backend/rust-core/Cargo.toml --all-targets -- -D warnings
```

## Included

Review assignment eligibility derived from `tools/review_worker.py`: saved and technically checked video, active signer/reviewer consent, exclusion of self/linked identities, previous phrase exposure, duplicate reviewers, finalized decisions, and the three-to-five review ceiling. Empty identity/phrase fields and explicit paused decisions additionally fail closed.

`consensus` ports the existing exact-normalized-match decision logic, exclusion reasons, 3-to-5 review escalation, quality gates and bounded signer test points. Unknown paraphrases still receive no similarity score; this is not an 85% semantic scorer. `rewards` produces test-point award intents and new balances, skips existing immutable events, and rejects unsafe balances, duplicate review IDs, cyclic identities and oversized review batches. It does not process cash payments or write data.

The Python oracle generates 135 deterministic synthetic decision cases. Run `python3 tools/generate_rust_consensus_fixtures.py`, then `cargo fmt` and the commands above to refresh/recheck them. This validates decision parity after normalization, not Unicode-normalizer parity or live database concurrency.

## Adapter contract before live use

- Resolve canonical person IDs from trusted identity linkage records. Never accept them or consent/quality flags from clients. The legacy `person_key` behavior is ported for parity. Production adapters must use `person_key_checked`, which rejects cycles; legacy resolution can produce different keys for paths entering the same cycle. The new reward planner rejects these inputs.
- Normalize raw reference/review text on the trusted backend using the existing Python `normalize` (NFKC, casefold and word extraction). A Rust Unicode normalizer is deliberately not approximated with lowercase/ASCII rules. The current hybrid adapter must supply normalized text and original-text presence; a standalone Rust text-normalization implementation remains outstanding.
- Read identity, consent, exposure and current recording/reviewer state inside the assignment transaction. Recheck eligibility and reserve the slot atomically; this pure function cannot prevent concurrent double assignment alone.
- Decode persisted statuses explicitly. Unknown statuses/malformed data must fail closed, not default to an open state.
- Preserve Firebase ID-token verification, private Firestore/GCS access and short-lived silent playback links. Return only opaque task IDs to participants, never hidden prompts or others' answers.
- For rewards, supply existing event IDs and safe nonnegative test-point balances from transactional reads. Create only returned events, update their affected balances and commit atomically; retries must reread the ledger. Reject cash-mode wallets. Pure planning cannot guarantee atomicity or idempotence without this adapter.
- Decision parity fixtures pass; authenticated integration, storage concurrency and canary/rollback checks remain required before live use.

## No-account migration boundary

Keep the current Firebase projects and GCS buckets. Sam can later supply an existing Cloudflare account and narrowly scoped deployment access if Workers is selected. Do not create another account, database or storage location by default. Cloudflare integration still needs runtime/SDK selection, an authenticated Firebase/GCS adapter, secure configuration, transactional concurrency tests, deployment and rollback verification. Heavy FFmpeg processing remains on an appropriate existing compute service until a tested replacement is selected.

The live Python worker is unchanged; this library does not make task processing always-on. No Cloudflare Worker, Wrangler project or Rust endpoint has been deployed.

## Comparison-only worker integration

`src/bin/signrush-shadow.rs` accepts a bounded private JSON payload over stdin and returns the Python-shaped decision. `tools/rust_shadow.py` supplies the existing authoritative Unicode normalization and invokes the executable only when `SIGNRUSH_RUST_SHADOW_BIN` is configured. `ConsensusWorker.qualify` compares after committing; only match/mismatch/unavailable statuses are logged. This is disabled by default and not activated on the live worker. See [the migration runbook](../../docs/RUST_MIGRATION_RUNBOOK.md) for builds, emulator tests, activation gates and rollback.
