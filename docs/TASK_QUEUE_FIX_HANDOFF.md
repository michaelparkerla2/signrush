# Task queue correction for maintainer

This change reconciles the browser fallback introduced in 607961b with the existing 200-phrase corpus. The original goal—letting a player request a task when the dashboard is missing or outdated—is retained.

## What changed

- Removed the separate 30-phrase browser catalog, 10-reservation limit and 300-request ceiling. The authoritative catalog remains `data/pilot-phrases.json`: DAILY-001 through DAILY-200.
- Browsers submit a task request. Only the worker assigns a phrase, using the existing transactional 20-approved-distinct-signer policy, pending reservations, canonical linked identities, prior signing/review exposure, immutable consent evidence and persistent signer evaluation split. Individual prompts may still be reopened to 30 by server policy.
- Firestore rules again reject browser writes to recordings, exposure histories and coverage counters. Merely increasing browser constants would not preserve these safeguards.
- Missing/legacy dashboards show an unknown count and allow an eligibility check; they do not claim 30 or 200 tasks are available to that individual. Current dashboard summaries include the catalog size and preserve a real zero count.
- An existing request stays pending without duplicate requests or client-side self-assignment. The UI explains that the request is saved while the worker processes it.

## Deployment

Deploy browser assets, Firestore rules and the updated worker/dashboard together. The signing, review and consensus workers need to run in the deployment environment; a static frontend cannot process their queues. This commit does not establish always-on hosting or run a worker on Michael's computer. No Supabase integration or deployment URL was found in this repository during review; if a separate deployment uses Supabase, apply the equivalent server-side checks there before using it as the active task service.

If the previous browser claim path ran in production, inspect its existing assignments: they may carry `consentVersion: training-v1` and lack `rights` and `corpusSplit`. Do not fabricate historical consent or infer an evaluation split. Existing export restrictions must remain in place; review or quarantine those records separately. This change does not mutate production records or delete contributions.

## Validation

Regression coverage verifies that DAILY-200 is assignable with consent provenance and a signer split even after 4,000 historical reservations. Existing emulator tests exercise concurrent caps, aliases, exhausted coverage, failed submissions, reopening to 30 and evaluation identity separation. Firestore tests reject the complete former browser claim transaction, including valid catalog wording.
