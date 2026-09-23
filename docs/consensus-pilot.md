# Test consensus and points — first version

Run `tools/consensus_worker.py --seconds 1800` in Cloud Shell instead of the review worker. This includes signing, reviews, decision processing and private decision receipts. No paid service, cash redemption or automatic training export is enabled.

## Qualification

The first automatic scorer is **exact-pilot-v1**, not a calibrated semantic or ASL accuracy model. It normalizes Unicode, case, punctuation and whitespace, preserving word order, pronouns, negation and numbers. An exact normalized match to the heldout phrase gets a text-match score of 1.0; all other interpretations get an unknown score, never an invented low accuracy score. The configured threshold is 0.85, but intermediate similarity scores are not implemented. Valid paraphrases may therefore wait for adjudication. Human adjudication tooling and a calibrated semantic scorer remain future work.

Three eligible people must independently match the reference. That also guarantees their normalized answers match each other. Disagreement or excluded owner testing opens up to five total assignment slots per recording; no sixth review is assigned. Unresolved completed reviews are marked for adjudication. Abandoned slots remain reserved in this small pilot.

Three matching reviewers must also report clear lighting and framing before the signer qualifies. Missing quality answers, poor quality or uncertainty keep signer points pending for a human check. Technical checks still apply. Reviewers who match the reference as part of a three-person consensus can receive their test points even if the signer’s framing needs a check.

Known linked accounts are treated as one person. Assignment, playback and submission reject a known signer alias. Historical owner tests remain stored, but are excluded from independent counts and rewards. `testOnly` invitations never contribute qualifying reviews. Active invitation and current consent are rechecked transactionally before awards. This does not solve unknown multi-account abuse or collusion.

## Test rewards

Signers receive one test point per whole verified video second, with a minimum of one and maximum of 30. Each qualifying validator receives five test points. These values are provisional game testing units, not a promise of cash value or hourly pay.

Immutable `rewardEvents` use recording/role/player identities to prevent duplicate awards. The event, owner-only `playerRewards` balance and sanitized task outcome commit atomically. Repeated or concurrent worker runs do not duplicate points. Existing historical awards are not automatically clawed back after later consent withdrawal; export consent must be checked independently.

Original reviews are preserved. Versioned private decision snapshots in `pilot/decisions/{recordingId}/{digest}.json` retain the independent counts, exclusions and scoring policy separately. They do not turn an owner test into training-quality ground truth. All recording exports remain ineligible pending a separate corpus qualification process.
