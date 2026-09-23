# Blind review pilot

The Sign and Review tabs share account registration and consent. The newer [consensus pilot](consensus-pilot.md) supersedes the pending-only behavior described below, adds quality answers, up to five assignments, known-person exclusions and test rewards. Reviewers receive an opaque review ID, a silent playback copy, and a text field. Original prompts, signer IDs, and other answers remain in backend-only records. A submitted interpretation stays pending; semantic consensus, quality approval and points are not yet implemented.

The pilot reserves at most three distinct reviewers per recording, one review job per participant. The signer and anyone already assigned that phrase are excluded. A shared transactional activity record also prevents a reviewer from subsequently receiving the same phrase as a signing assignment. This limits known account-level exposure; it cannot prevent coordinated people or multiple accounts. Abandoned slots are not automatically recycled yet.

`tools/review_worker.py` extends the signing worker and runs in Cloud Shell for at most 30 minutes per explicit start. It checks current consent for both participants before issuing playback or accepting an answer. Playback copies are generated in temporary Cloud Shell storage, stripped of audio and metadata, and kept under `umi-signrush-raw/pilot/playback/`. The original is unchanged.

The keyless `signrush-playback` service account receives object-viewer access only for that playback prefix. The Cloud Shell operator can sign URLs using that identity. No cloud login or service credentials reach players. Each URL lasts five minutes; at most three grants are issued per review. Existing links remain usable until expiry, including after withdrawal. The worker itself still uses operator credentials and is a temporary pilot backend.

Independent answers are retained in protected `pilotReviews` records, attached to `pilotRecordings.reviewResults`, and copied to private `pilot/reviews/{reviewId}.json`. Original prompts stay separately stored in the heldout bucket. Exports remain ineligible pending future qualification.

Validation: browser controller tests, Firestore rules tests, concurrent emulator worker tests, and a synthetic cloud playback isolation check. Synthetic tests do not establish ASL accuracy. A distinct invited Google account is needed to review the current player's real recording.

Owner testing accounts can be provisioned with `tools/invite_pilot.py`. Their invite records carry `testOnly: true` and, when known, `samePersonAs` linking the owner's primary UID. These flags must be honored by future consensus/qualification/export code: a second account belonging to the signer is not an independent validator. The current pilot still blocks self-review by UID only and awards no approval or points; cross-account owner use is interface testing only. No consent is created by the invitation helper.
