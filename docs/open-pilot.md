# Open registration — 2026-09-23

The hosted pilot now permits verified Google accounts to register without an invitation. Consent is still required for task requests. Existing `pilotInvites` remain server-only account controls: an existing record must have `active: true`; inactive or malformed records block access. `samePersonAs` and `testOnly` retain their existing meanings. Do not delete a revoked record to unblock it accidentally.

Cloud Shell eligibility accepts registered, consenting players without legacy invitations. Dashboard publication pages through player profiles, instead of only invited accounts. Browsers cannot read other profiles, choose review videos, inspect raw recordings, read hidden references, or award points. Self-review and known linked-account checks remain in assignment, playback, submission and consensus.

This opens registration, not unlimited production capacity. The three-recording global reservation cap, 8 MiB/30-second limits, five-review maximum and 30-minute worker sessions remain. No cash payments or paid infrastructure were enabled. Unknown multi-account abuse and collusion are not solved by Google sign-in.

Sam’s architecture preference is Rust for future backend work and Cloudflare Workers where practical. The current worker remains Python until an incremental migration is built and tested. Wrangler authentication is not needed for this registration change. Long-running video conversion must be evaluated separately from request handling.

Validation: 24 browser/controller tests, 13 pure worker/scoring/dashboard tests, 19 Firestore rules tests, nine open-enrollment/consensus transaction tests and six review transaction tests passed. The new fixture was corrected after an initial setup error. Cloud Shell source hashes match local deployed code. Hosting content was fetched successfully over HTTPS; the production dashboard publication check passed. A new real Google account still needs to exercise the live sign-in flow.
