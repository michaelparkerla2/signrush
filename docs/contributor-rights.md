> Current Terms release: `terms-2026-09-26-v2` adds the report/strike mechanism. Prior v1 documents and manifest are preserved verbatim in `web/legal/archive/terms-2026-09-26-v1/` and Git history.

# Contributor onboarding and rights evidence

This release implements one affirmative, unchecked checkbox for Terms, Contributor Data & AI License and acknowledgment of the Privacy Notice, including an explicit 18+ representation. Commercial AI training, third-party dataset licensing and derived face/hand/body features are visible beside the checkbox. Full documents are linked before acceptance; no required second checkbox or public-display grant exists.

Three optional single-choice questions collect ASL experience, hearing identity and ASL role. Skip/prefer-not-to-say is the default. Responses are private self-reports, not credential verification, and do not establish fluent-reviewer qualifications. They are stored in `contributorProfiles/{uid}` with a consent-event link and server timestamp. They are not included in the current media/review export or leaderboard.

## Enforced evidence

The active browser transport is `web/firestore-registration.mjs`. Its transaction writes the immutable `players/{uid}/consents/{event}` receipt, optional-background profile, and account pointer together. Firestore Rules independently verify authenticated UID/email, release IDs, document-bundle hash, server timestamp, age representation and `publicDisplayAllowed:false`. Old versions cannot unlock participation. Existing users must accept the new release to resume tasks; historical contributions are not retroactively given new commercial rights.

`web/legal/manifest.json` contains hashes of the exact published documents and a bundle hash. Tests verify all hashes and their correspondence with browser disclosure and Firestore Rules. Preserve every released document/manifest in Git. Any document edit requires new release IDs, recomputed hashes, coordinated Rules/worker/browser updates and renewed acceptance; never silently edit an accepted release.

The worker requires current consent for assignment, media access, submission and qualification. Newly assigned recordings and submitted reviews include `rights.consentPath`, versions, bundle hash, `rightsStatus:license_recorded` and `publicDisplayAllowed:false`. Media receipts preserve this evidence with source hashes and existing prompt, split and validation provenance. Review exports carry the reviewer's own evidence. The receipt links to the immutable server timestamp and authenticated account record; email and sensitive background answers are not added to corpus receipts.

`license_recorded` means an affirmative license record exists. It is not a guarantee of legal clearance, contributor identity/authority, or export qualification. The training-eligibility helper now also rejects missing license evidence and flagged rights restrictions; any future exporter must separately recheck authoritative current consent and restrictions. Existing test-only data remain `exportEligible:false`; no data sale, commercial export, cash integration or promotional display is enabled. Legacy material without these rights references remains `legacy_unverified` in new receipts, even if its owner accepts a newer agreement later.

## Privacy requests

Account includes a private request form for access, correction, deletion or restriction. `privacyRequests/{id}` stores requester UID, type, optional details, server timestamp and `requested` status. No email is sent. Users cannot mark requests completed or inspect other users' requests. Verified signed-in users can submit after withdrawing participation. Trusted operators must monitor and handle this collection; storing a request does not automatically delete or restrict historical data. Withdrawal separately stops participation and future eligible exports. Do not describe this as an automated deletion system.

## Delivery / operator coordination

Local development and GitHub only. maintainer must deploy the browser assets, Firestore Rules and Python workers together; new receipts fail closed against old Rules, and old workers cannot accept new versions. The separate FastAPI/reference transport is not the active site enrollment path and remains a legacy test reference, not an alternative commercial-consent endpoint. No new accounts or storage locations were introduced: all additions use the existing Firestore project and private media receipts.

Rules/worker checks and emulator tests cover immutable evidence, current-version and age gates, private background, post-withdrawal request submission and independent consent provenance. The release does not implement public promotion permission, a minors flow, automatic biometric processing or a commercial dataset exporter.
