# Rust migration: comparison mode and rollback

## Current boundary

The website and authoritative backend remain Firebase/Google Cloud + Python. The Rust executable is an opt-in private local subprocess, not a public endpoint. It compares consensus output after Python's existing Firestore transaction commits. It cannot change approval, points, assignments, consent, exports, balances or payment status. No new cloud accounts, storage or services are required for preparation.

## Build and verify without cloud access

From the repository root, with the existing Rust toolchain:

```sh
cargo build --locked --offline --manifest-path backend/rust-core/Cargo.toml --bin signrush-shadow
cargo test --locked --offline --manifest-path backend/rust-core/Cargo.toml
cargo clippy --locked --offline --manifest-path backend/rust-core/Cargo.toml --all-targets -- -D warnings
python3 -m unittest discover -s tests -p test_rust_shadow.py
python3 -m unittest discover -s tests -p test_consensus.py
```

The JSON runner uses a pinned serde_json dependency, with a committed Cargo.lock. Offline builds need the locked crates cached; a fresh developer machine may need one normal Cargo dependency download (no account). Build on the target platform: a macOS binary cannot run in Linux Cloud Shell.

## Normalization contract

`rust_shadow.payload` uses the same Python `consensus.normalize` function as the authority: NFKC, Unicode casefold, curly apostrophe normalization and Python word extraction. Preserve negation, pronouns, numbers and order. The protocol identifies this algorithm and includes Python's Unicode data version. Boolean/nonfinite/missing durations become null rather than a valid signing duration.

This completes normalization for the hybrid comparison path, not a standalone Rust Unicode implementation. A future all-Rust service must implement and verify this exact contract or deliberately version a replacement. Do not substitute ASCII lowercase or a generic regex and assume parity. Re-run oracle cases when changing Python/Unicode versions.

## Isolated database checks using existing resources

Use the existing Cloud Shell and Python environment, or an already-configured local emulator. Copy code into an isolated temporary directory; do not patch a running worker's checkout. Run only with an emulator and demo project. The transaction tests refuse to run without FIRESTORE_EMULATOR_HOST and create synthetic demo projects using anonymous credentials. Never remove these guards.

```sh
# From the existing firestore directory, with tests in the repo root:
node_modules/.bin/firebase emulators:exec --only firestore --project demo-signrush-rules 'cd .. && PYTHONPATH=tools:tests .venv/bin/python -m unittest test_review_transactions test_consensus_transactions'
```

These cover concurrent review reservation, the 3-to-5 review ceiling, immutable reward events, qualification retries, withdrawn consent, linked accounts and safe participant summaries. Added shadow-failure/mismatch tests prove comparison cannot override the authoritative transaction. They validate the existing transaction adapter, not a future Rust database adapter.

## Optional shadow activation on an existing worker

1. Run the checks and build the binary on the worker's operating system.
2. Keep the current source revision and executable available for rollback.
3. Put the binary outside any public Hosting directory; use owner-only permissions.
4. For a bounded worker run, set `SIGNRUSH_RUST_SHADOW_BIN` to its absolute executable path. Use the existing worker command and existing credentials; do not add secrets or new buckets.
5. Watch only the aggregate log statuses: `Rust shadow: match`, `mismatch`, or `unavailable`. Do not log the subprocess input/output or a decision diff: those contain private reference/answer information.
6. Comparison has a one-second timeout and 256 KiB input ceiling. It runs after commit, so it can add worker-loop latency but does not hold a database transaction open. The original Python policy remains authoritative even if Rust is missing, slow, crashes, rejects input or disagrees.

This activation is NOT performed by the preparation commit. No production corpus was copied into the test fixtures.

## Rollback

Unset `SIGNRUSH_RUST_SHADOW_BIN` and restart the same worker using its normal bounded run command. Comparison is off by default. No schema rollback, reward reversal, media movement or database rewrite is required. If rolling back source, use the previously verified commit with the variable unset. Do not delete rewardEvents or recompute balances as part of rollback.

## Gates before authoritative Rust or Cloudflare cutover

- Sam provides the selected existing deployment account/access. Do not create a new account, storage location or paid plan automatically.
- Choose the runtime and authentication path to the current Firebase/Firestore/GCS resources; no D1/R2 migration is assumed.
- Implement and test Firebase token verification, consent and full identity-chain resolution from trusted transactional snapshots.
- Reject malformed/unknown states and cyclic linkage. The legacy Python cycle resolver has path-dependent behavior; the checked Rust resolver rejects cycles. Resolve that policy difference explicitly before cutover.
- Keep Unicode normalization/version parity, or approve a versioned policy change with regression cases.
- Prove atomic assignment reservation and reward-event deduplication under contention in the actual Rust database adapter. The pure Rust reward planner is not a transaction engine.
- Preserve private references, silent playback, URL expiry, consent/export exclusions, and separation of test rewards from real-money accounting.
- Test assignment and playback end-to-end, compare a bounded canary, then switch authority only with a verified rollback path. A Cloudflare HTTP wrapper alone would not satisfy these gates.
- Heavy FFmpeg processing remains separate; the later shared Python runtime permits bounded sessions up to 8 hours, but does not make processing always-on. See RELIABILITY_READINESS.md.

## Verified preparation checks (2026-09-23)

- Locked offline build and Clippy with warnings denied: passed.
- Rust: 9 unit tests and the 135-case Python-oracle integration test passed.
- Python bridge: 5 tests passed, including all 135 cases through the real Rust executable.
- Python consensus: 8 tests passed.
- Existing Cloud Shell Firestore emulator: 21 test executions passed in 34.947 seconds, using an isolated code copy and synthetic records. The imported review test class is executed by both modules, so this count includes repeated review tests.
- No live shadow activation, production database changes, new accounts, buckets or services were performed for this preparation.
