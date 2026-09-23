# Player registration and consent flow

Updated on 2026-09-14: the port-8088 preview now uses deployed Firestore registration in the free Spark project. The original same-origin API design described below remains a locally tested reference; it is not the active browser transport. See [live Firestore setup and verification status](firestore-setup-20260914.md).

In the reference API transport, after Firebase login, `web/onboarding.mjs` obtains an ID token from the current user and sends it in an Authorization header to the same-origin participant API. It never puts credentials in URLs or persists them. API requests reject redirects. `/v1/account` determines whether current consent is needed; `/v1/consent` supplies the rules, training disclosure and exact version IDs.

The page renders server text as text, displays the full training notice including failed attempts, and requires an unchecked agreement checkbox and an explicit submit action. It displays success only after the server confirms acceptance. Previously accepted players can withdraw; withdrawal restores the consent requirement. It does not award points, create signing tasks or access the camera.

Sign-out resets the registration state, aborts in-flight requests, and ignores late responses. Failed or ambiguous saves are not represented as completed consent; Refresh registration reads the account again to reconcile a response that may have been lost. An expired or uninvited identity stays blocked. Duplicate button clicks cannot submit multiple concurrent agreements.

The FastAPI app now serves an explicit list of public web assets alongside its API. It never mounts the repository, `.env`, local pilot UID file or database migration files. Deployment uses the same origin for the web page and API; do not add a cross-origin endpoint that can receive tokens without an explicit security review.

## Verification

- `node --test tests/test_onboarding.mjs`: 8 passed (explicit versioned agreement, unavailable server, failed save, withdrawal, sign-out races, unverified/uninvited users, duplicate submission).
- `python tests/test_api.py`: 10 passed against an isolated PostgreSQL cluster and restricted runtime role. Added a new-account consent lifecycle, rejection of stale terms, and public-asset/repository isolation checks. Identity/storage adapters were test doubles; this was not a live cloud API verification.
- JavaScript syntax check passed. Standalone preview serves the new module successfully.
- Temporary Python dependencies and disposable PostgreSQL data were removed after tests.

## Next deployment dependency

Firestore was selected and provisioned within the free-only constraint for registration. The real browser → Firestore player/consent flow passed; independent cloud reads verified the user-submitted agreement and matching profile on 2026-09-14. Media collection and game workflows still require their own cloud implementation and narrowly scoped service identities. Do not substitute a fake success state, production test token, or localStorage consent flag while deployment is pending.
