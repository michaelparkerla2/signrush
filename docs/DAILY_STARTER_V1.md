> Current review policy: [Meaning consensus v2](consensus-pilot.md) supersedes older three-matches and 0.85-threshold descriptions below: 3/3 initially, then 4/5, with unresolved meaning disputes held for fluent adjudication.

# Daily-use starter batch v1

The active backend catalog is `data/pilot-phrases.json`: exactly the owner's 30 meanings, `DAILY-001` through `DAILY-030`, version 1, category `daily_use`, batch `daily-use-v1`. The previous three prompts are archived in `data/legacy-phrases-v1.json`. Existing assignments keep their original prompt snapshot; no old recording, reference or exposure history is rewritten.

## Collection behavior

- The initial reservation ceiling is 10 known distinct people per meaning, 300 new assignments in total. It does not promise 300 accepted clips: abandoned/failed attempts still consume reservations until an operator reviews them. Do not reset counters to hide failed attempts.
- A transaction chooses among eligible meanings with the lowest reservation count. Counts include in-flight reservations so simultaneous arrivals spread across meanings. This is reservation balancing, not a validated-clip counter.
- A person is not assigned a meaning already signed or exposed through a blind-review assignment. Known linked accounts share a private exposure history. Identity chains are fully resolved; cycles/excessive chains fail closed. Undiscovered duplicate accounts remain an abuse-control limitation.
- `promptCoverage/daily-use-v1`, `promptParticipants/{canonical UID}` and `pilotLimits/daily-use-v1` are private server-only documents in the existing Firestore database. Browser access remains denied by the default rules. No new account, bucket, database service or paid plan is required.
- Prior `pilotLimits/signing-v1` reservations remain intact. Record scans cover the three legacy reservations plus the 300 new ones. Qualification rotates through pages of 25; dashboard publication is throttled to 60 seconds. Monitor existing free/trial quotas as traffic grows; this is bounded collection, not unlimited scale.

Signers see: “Express this meaning naturally in ASL, as you would in an everyday conversation. You do not need to follow the English word order. Use your own natural signing style.” They are not shown an example video to imitate. Short phrases need not be stretched to ten seconds; existing technical duration limits remain in force.

## Private provenance and validation

Each assignment snapshots the full prompt, stable meaning ID, prompt version, batch and a private canonical `corpusSignerId` derived from the existing pseudonymous Firebase UID. The receipt retains those fields with pinned object generation, source SHA-256 and technical checks. This ID is not a public leaderboard name; future identity corrections require explicit dataset reconciliation.

Original prompt references stay in the existing private held-out bucket. Recordings and evidence stay in the private raw bucket. Existing Google-managed encryption at rest and HTTPS transport apply; this is not end-to-end encryption from authorized cloud administrators. Prompts are not deployed as a public catalog, and the blind-review payload still exposes only an opaque review ID and short-lived silent playback, not source prompts or peer answers.

The existing 3-independent-review threshold, expansion to at most 5 when needed, consent checks and idempotent test-only rewards remain. Automatic scoring still uses exact normalized English matches; it is not semantic ASL verification. Natural paraphrases and meaningful deviations require fluent adjudication rather than changing a transcript to match the prompt. All live records remain `exportEligible: false`.

## Evaluation and capacity

Keep separate evaluation signers out of training when designing the release. Repeated meanings with unseen signers measure signer generalization; unseen-meaning evaluation needs held-out meaning families too. No evaluation cohort was automatically selected and no training release was produced by this change.

A person who has seen a prompt cannot blindly validate its recordings. Therefore the collection needs enough participants with unexposed meanings, not merely ten people signing all thirty meanings. Three reviews for every one of 300 clips would require at least 900 independent review completions, plus any extra review rounds. Existing failed/adjudication cases remain separate.

The current Cloud Shell worker must be running for assignment and processing. An eight-hour session is not durable always-on hosting. No payment program, referral bonus, prize selection or real USD ledger is activated by adding prompts.

## Validation

The isolated Firestore emulator passed 40 transaction test executions, including coverage balancing, filled-batch refusal, linked accounts, consent withdrawal, upload recovery and idempotent rewards. Local checks passed for the 30 stable catalog entries, dashboard counts, existing signing/consensus policy and all 37 frontend controller tests. Some emulator test classes are imported by multiple suites, so the execution count includes repeats. No synthetic participants were created in the live database.
