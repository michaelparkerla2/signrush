# Unusable videos and account strikes

Implemented by `meaning-panel-v3` and the transactional `three-strikes-v1` moderation ledger. This is executable backend behavior, not only player guidance. No new hosting service or account is required.

## Reporting

An assigned reviewer can choose **This video is not translatable**, then select **No signing / obvious spam or fake attempt** or **Too dark, obscured or unclear to translate**. This is a separate response type: no invented English translation is required or allowed alongside a flag. A quality selection alone on an ordinary translation is not a misconduct report. Unfamiliar ASL, dialect/style differences and disagreement are not reasons to claim non-signing.

Reports use the same consent, self-review, known-linked-person and unique-review safeguards as interpretations. One or two reports cannot independently remove a clip or penalize anyone. An initial mixed panel expands from three to five as before. Three valid independent unusable reports reject a clip when fewer than three reviewers agree on meaning. Automatic reports never overturn previously established three-person meaning agreement: such a conflict needs adjudication. With four meaningful, good-quality interpretations and one report, the normal 4/5 policy can approve; the original report remains stored.

Three poor-quality reports, or a mix with fewer than three spam/non-signing reports, reject the recording without a strike. A strike requires three independent spam/non-signing reports. Every original response remains private and auditable; reporting earns no automatic points. This does not establish intent by an AI classifier and does not prevent unknown multi-account collusion.

## Consequences

- Confirmed unusable clips leave task circulation and approved corpus coverage, release their pending collection slot, receive no new rewards, and are marked rejected, rights-restricted and export-ineligible.
- First and second misconduct incidents revoke only existing signer points attributable to that video. Other points remain. Usually an unapproved clip has earned zero, so the deduction is zero.
- The third confirmed incident forfeits the remaining current test-point balances, removes leaderboard entries and cancels signing/validation access. Known linked accounts share enforcement. Current rewards are test points; no cash ledger or external payment reversal is implemented or claimed.
- A red warning with the strike count appears on the next login and while the session is open. Cancellation blocks browser task writes through player status and is independently checked by the worker, including linked identities. An active alias profile cannot bypass a blocked canonical identity.

`moderationEvents/{recordingId}` is an immutable adjustment/evidence event. Original positive `rewardEvents` are never deleted or rewritten. Per-person `accountModeration` stores incident IDs and the block; owner-readable `playerModeration` exposes only the warning summary. The strike, balance adjustment, cancellation and recording quarantine commit together. Repeated qualification, concurrent workers and repeated clicks cannot charge the same recording twice. Clients cannot edit enforcement documents or restore their own account status.

Private raw video and review evidence are retained for audit; “removed” means removed from task circulation/training eligibility, not silently erased. Already-issued playback URLs retain their existing short expiry. New assignment, replay grants and late submissions are blocked after rejection. Operators must inspect any disputed enforcement before making an audited correction; automatic restoration is not implemented. Private account/privacy requests remain available to cancelled users.

## Deployment

GitHub delivery only. maintainer must deploy the matching browser, Firestore Rules and worker code. Deploy the updated legal release and renew agreement acceptance as documented in `contributor-rights.md`. The legacy Rust shadow remains disabled for the newer decision policy. No live users, balances or recordings were changed during local testing.
