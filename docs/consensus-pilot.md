# Meaning consensus and test rewards — current policy

`meaning-panel-v3` supersedes `exact-pilot-v1` and older three-matches/0.85 proposals. This is the authoritative implemented review policy. Delivery is local code and GitHub only; maintainer controls hosting. No new service, account, paid upgrade, cash integration or automatic training export is required by this change.

## Independent panels

| Panel outcome | Action |
| --- | --- |
| Three of three agree on intended meaning and usable quality | Approve if technical checks pass |
| Any initial meaning or quality disagreement | Expand to five reviewers |
| Four or five of five agree on intended meaning and usable quality | Approve only after all critical meaning questions are resolved and technical checks pass |
| Three or fewer of five agree | Hold for experienced ASL review |
| Unknown meaning, unresolved critical disagreement, or unanimous interpretation of a different meaning | Hold; never label the clip with the intended prompt |

Expansion is permanent for that recording. Four received answers in an expanded panel are not enough. Excluded invalid reviews do not shrink it back to three; if five assignment slots are exhausted without five eligible answers, the recording needs adjudication. Abandoned slots remain reserved. This implementation does not automatically replace exhausted slots or relabel clips.

80% means four people out of five, **not 80% English word similarity**. Automatic comparison recognizes only exact normalized text (Unicode, case, punctuation and whitespace normalization). It preserves word order, negation and numbers. `referenceScores` records text matches, not semantic accuracy. No arbitrary semantic-similarity cutoff or uncalibrated outlier classifier approves labels.

Natural paraphrases need a fluent ASL adjudicator's finding. Negation, names, numbers, who did what, and timing must be checked explicitly when resolving a nonmatching interpretation. Until resolved, even four exact matches plus one unknown answer remain on hold. An expert can also flag a critical dispute in an otherwise exact answer. The panel quorum still applies after expert review.

## Blind answers and outliers

Reviewers see neither the prompt nor other answers before submitting their original interpretation and quality assessment. The server saves that answer immutably, then reveals only the intended prompt to that reviewer for comparison. This reveal itself is not a new equivalence vote. Other reviewers' answers stay private. A phrase already exposed through signing or review cannot be assigned to that person again.

An adjudicator can mark an unrelated interpretation as a suspected outlier. It stays in the full valid panel and in review history. Different wording is not evidence of an outlier. Nothing deletes dissent or excludes it for disagreeing. Exclusions remain based on identity, participation or incomplete/invalid submission checks. Known linked accounts count as one person; self-review, known signer aliases and test-only identities cannot contribute. Unknown multi-account abuse/collusion still needs operational identity controls.

## Private adjudication command

maintainer or another trusted operator with existing backend credentials can run:

```sh
python tools/corpus_admin.py --project PROJECT assess-review RECORDING REVIEW \
  --verdict equivalent --critical-dispute resolved \
  --assessor OPERATOR_ID --reason 'Explain the ASL meaning and critical-detail checks'
```

Verdicts: `equivalent`, `different`, `unrelated`. Critical dispute: `resolved` or `unresolved`. The operator must be qualified to assess ASL; the assessor field is an audit identifier, not an automated competency verification. Credentials remain the authorization boundary. Use `unresolved` when a critical question remains; never mark it resolved merely because a majority agrees.

The command verifies record/review association, saves a private append-only `meaningAssessmentHistory` event, and updates the current finding on the recording. Each finding binds to the original text, quality, identity and prompt; changing them invalidates the finding. Original responses are never rewritten. Browser clients cannot read/write these private collections. See [unusable-video moderation](unusable-video-moderation.md) for the independently reported rejection and three-strike path.

The worker re-evaluates quorum on its next cycle. The command cannot override quorum or modify already-approved clips (those require separate revocation/reward audit). Rejection remains available through `reject RECORDING --reason ...`.

## Rewards, corpus and migration

Only a qualified panel with passing technical checks creates new rewards: the signer receives one test point per whole verified video second (minimum one, maximum 30); each agreeing good-quality reviewer receives five test points. Outlier/dissenting responses receive none. Technical failure, unresolved panels and rejected recordings create no new rewards. All remain test-only, with no cash value.

Reward events, balances and sanitized outcomes commit atomically and are idempotent. Historical awards are not automatically clawed back when a stricter policy re-evaluates a recording. Existing approvals may become held under v2; their old ledger events remain. Disputed clips do not count as approved corpus coverage. All records remain `exportEligible: false`; no training export is enabled. Consent is rechecked before qualification.

The Rust shadow runner still implements v1. It now returns `unsupported_policy` for v2 without running or claiming parity; Python remains authoritative. A future Rust port must implement the expanded panel and audited findings before comparison is re-enabled.

Tests cover quorum, sticky expansion, critical dissent, expert-resolved paraphrases, stale findings, outlier preservation, technical/quality gates, blinded assignment/post-submit reveal, transaction retries and immutable test rewards using local synthetic data.
