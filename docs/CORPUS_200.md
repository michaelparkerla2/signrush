> Current review policy: [Meaning consensus v2](consensus-pilot.md) supersedes older three-matches and 0.85-threshold descriptions below: 3/3 initially, then 4/5, with unresolved meaning disputes held for fluent adjudication.

# Daily-use corpus: 200 meanings, up to 20 approved people each

This supersedes the 30-prompt / 300-reservation policy in DAILY_STARTER_V1.md.
All DAILY-001–200 prompts retain version 1, category `daily_use`, and the natural-ASL instruction. The first 30 meanings and IDs are unchanged. The additional 170 are the owner's supplied original list.

## Collection behavior

- Initial target: 200 × 20 = 4,000 approved distinct signer/meaning pairs. Twenty is a collection policy, not a scientific guarantee of model quality.
- One known person gets a meaning only once, even after a failed or rejected submission. Pre-submit retakes stay within that assignment. The owner's final no-repeat instruction takes precedence over the pasted proposal for post-rejection retakes.
- One person may contribute to many different meanings; there is no 20-person account limit.
- Completed, assigned, or reviewed meanings remain in private exposure history. Existing self-review and linked-account exclusions continue to apply.
- Scheduling ranks by fewer approved people, then fewer pending people. Work awaiting technical/meaning review reserves space; it does not count as approved. Thus a phrase can temporarily stop receiving assignments while its last slots are pending.
- Each assignment queries actual records for the selected phrase inside a transaction. It derives unique identities through `samePersonAs`, rather than trusting upload counts or client data. Approval repeats the cap check transactionally, including for excess legacy assignments. A full phrase gets no new signers. Failed or operator-rejected clips release capacity for another person, never another task for the original person.
- A private scheduling cache is reconciled from all database records every 60 seconds; the old `promptCoverage` reservation map and 300-reservation ceiling are not used to determine availability. Historic counters are retained for audit only. History scans are not truncated at 4,000 uploads.
- The signer sees `approved unique signers / cap` on the assigned task. Counts are a snapshot at assignment and refreshed during qualification; no other signer identity or review answer is exposed.
- Unresolved quality/adjudication cases continue holding capacity until an operator resolves them. Abandoned assignments do not auto-expire; the operator must audit them rather than silently reissuing someone's task.

## Validation and privacy

Approval still requires the existing technical check and three independent, good-quality matching reviews. The conservative exact-English matcher does not verify every valid ASL paraphrase: unresolved natural variations require fluent human adjudication. A prompt is not a verified transcript merely because it was displayed.

Private Google storage, consent, video receipts, held-out references, test-only rewards, and `exportEligible=false` are preserved. These changes do not enable cash payouts or release training media. Existing Google-managed encryption at rest and HTTPS transport are unchanged; this is not end-to-end encryption.

## Signer-level evaluation separation

The private `corpusSigners/{canonicalPerson}` record freezes a deterministic cohort: 80% train, 10% validation, 10% test, by a versioned hash of the canonical identity. These percentages are a practical default, not an exact headcount guarantee. All prompts from that canonical person use the same cohort. If linked accounts already have conflicting cohorts, new assignment/qualification quarantines the canonical person instead of moving evaluation data into training. Evaluation contributors count toward the same 20-person cap.

Assignments and receipts carry `corpusSignerId` and `corpusSplit`. Qualification backfills legacy database records; original immutable receipts are not rewritten and may still say `quarantine`. The database signer cohort is authoritative. The `training_eligible` guard rejects evaluation contributors and all current test-mode recordings. There is no automatic training export in this worker.

Before any future training export, the hosting operator must reconcile newly discovered linked identities across ALL prior records/receipts and quarantine any conflicting cohort assignments. Unknown duplicate people cannot be detected merely from Google accounts. No claim is made that account IDs prove distinct humans. No existing dataset may be released by blindly trusting older receipt split fields. Separate unseen meanings will also be needed for broader translation evaluation.

## Operator controls (maintainer's host only)

Private Firestore collections are denied to browser clients by the existing catch-all rule. The worker uses its existing authorized server credentials.

After inspecting the first 10 approved contributors per phrase, continue toward 20. To reopen one reviewed phrase to 30:

```sh
PYTHONPATH=tools python tools/corpus_admin.py --project YOUR_PROJECT set-cap DAILY-117 30
```

To reject a saved, not-yet-approved clip after human review (with a recorded reason):

```sh
PYTHONPATH=tools python tools/corpus_admin.py --project YOUR_PROJECT reject RECORDING_ID --reason 'Human review: intended meaning not conveyed'
```

Approved clips cannot be revoked with this command; they require a separate audit of existing rewards and dataset eligibility. The CLI can reduce a cap to 20 but never deletes previous approvals; if 30 already exist, no new assignments are issued. Policy changes do not erase exposure history.

## Delivery

Local development and GitHub only. No production data migration, hosting restart, Cloud Shell deployment, new account, paid service, or billing upgrade is part of this change. maintainer should run the updated worker with its existing dependencies and deploy `web/` on her infrastructure. The first coverage reconciliation includes existing records without deleting them. Runtime memory/read cost now grows with corpus history; host operators should monitor quotas and migrate reconciliation to indexed aggregation before scaling materially beyond this first collection.

## Local verification

- Exact comparison: the original 30 objects are unchanged; all 170 new IDs/texts match the supplied attachment.
- Final local Firestore emulator + policy/unit run: 48 tests passed (synthetic users/media only).
- Full transaction/open-enrollment run before the final cohort-conflict safeguard: 47 passed; final run rechecked changed signing/qualification paths, including the new conflict test.
- Firestore browser access rules: 22 passed, including denied access to private corpus counts, policy and signer cohorts.
- Frontend controller tests: 37 passed.
- Contention tests model a subsequent worker tick after the Firestore SDK exhausts its transaction retries, then assert final capacity and independence. Only explicit transaction-aborted errors are retried; unrelated errors fail tests.
