# Firestore registration pilot — 2026-09-14

## Live cloud configuration

- Project: `signrush-login`, owned under `umi.vision`; Firebase Spark.
- Database: `(default)`, Standard edition, Firestore Native, `us-east1`.
- Creation response confirmed `freeTier: true`. Billing inspection confirmed `billingEnabled: false` and an empty billing account name. No billing upgrade was made.
- `firestore/firestore.rules` compiled and was released successfully with Firebase CLI.
- The existing Google-authenticated UMI pilot UID has an administrator-created `pilotInvites/{uid}` document with `active: true`. A subsequent authenticated REST read independently verified this value. Anonymous REST access returned HTTP 403.
- After the user completed registration, independent cloud REST reads verified the active test-mode player profile and its matching accepted consent event. Profile creation: 2026-09-14 18:58:29.280 UTC. Consent recorded: 18:58:59.953 UTC, with terms `pilot-v1` and disclosure `training-v1`. The user submitted the agreement; the agent only read it back.

The console location picker stalled. Database creation instead used authorized Cloud Shell:

```sh
gcloud firestore databases create --project=signrush-login --location=us-east1 --type=firestore-native --edition=standard
npx firebase deploy --only firestore:rules --project signrush-login --non-interactive
```

## Browser persistence

`web/login.js` now activates `web/firestore-registration.mjs`. Google sign-in uses the existing Firebase project. Firestore transactions create invitation-only test-mode profiles and atomically save versioned consent events plus their latest-event pointer. The browser cannot set rewards, invitations, account privileges, prompts or held-out answers. All unspecified collections are denied.

Profile IDs are Firebase UIDs. They are not the PostgreSQL reference implementation's UUID account IDs or corpus signer numbers. A stable corpus identity mapping remains to be implemented before exports from this live backend.

The disclosure in `web/pilot-disclosure.mjs` matches the current backend notice; future changes must coordinate text and version IDs with Firestore rules and the reference API. Agreement is unchecked by default and saves only on explicit submission. Failed/ambiguous saves remain unconfirmed; refresh reconciles server state. Aborting a UI request cannot undo a Firestore transaction already committed.

## Verification

- Eight Firestore emulator security tests passed in Cloud Shell, using only synthetic identities in `demo-signrush-rules`. They cover verified invitations, account ownership, immutable consent events, atomic acceptance/withdrawal, stale terms, forged fields/timestamps, replay, suspension, revoked invitation and protected collections.
- Eight local onboarding-controller tests passed after the transport timeout change.
- Live rules compilation and deployment succeeded.
- Live invitation read-back and anonymous access denial passed.
- The user completed the browser flow, and independent cloud reads verified player creation and persisted consent with matching event pointer, versions and timestamp. Google login/sign-out had also passed previously.

Emulator dependencies and Java ran in Cloud Shell, not on the Mac. No real signing videos, FLEURS files, cash rewards or payout data were used. The Cloud Shell test directory contains logs and dependency lockfile. `tools/check_firestore_pilot.py` verifies the one authorized invitation, creates it only if absent, inspects the profile and tests anonymous denial. Its access token stays in process memory and is never printed.

## Scope and next step

Only registration/consent is connected to Firestore. PostgreSQL migrations and FastAPI game endpoints remain locally tested reference code, not a deployed game backend. Signing queues, blind-review assignment, media processing, scoring and corpus release/export need subsequent implementation against the chosen cloud architecture. Do not connect a generic browser CRUD interface to these collections.

Video storage remains in the private `signrush` project buckets, under the previously authorized trial; the unbilled Firebase project does not change that separate project's storage billing. No dataset sync to the Mac is required. Google Drive is optional for documents and selected copies.

## Verified registration milestone

Real Google login → player creation → explicit agreement → persisted Firestore profile and matching consent history passed. The next small build step is the signing screen: assigned phrase, recording guidance, camera preview and bounded private upload. Games remain unavailable until that flow and its server authorization are implemented.
