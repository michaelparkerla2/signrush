//! Pure backend policy. No credentials, network, database or media access.
//! The adapter must supply trusted transaction snapshots and canonical person IDs.

/// An identity resolved by the trusted backend, never supplied by the browser.
#[derive(Clone, Copy, Debug)]
pub struct Participant<'a> {
    pub uid: &'a str,
    pub person_id: &'a str,
    pub consent_active: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Decision {
    AwaitingReviews,
    NeedsMoreReviews,
    Approved,
    AdjudicationRequired,
    QualityCheckRequired,
    TestOnly,
    ParticipationPaused,
}

pub struct Recording<'a> {
    pub saved: bool,
    pub signer: Participant<'a>,
    pub phrase_id: &'a str,
    pub technical_check_passed: bool,
    pub reviewers: &'a [Participant<'a>],
    pub review_limit: usize,
    pub decision: Decision,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Ineligible {
    MissingIdentity,
    ParticipationPaused,
    RecordingNotReady,
    SamePerson,
    PhraseExposed,
    AlreadyReviewed,
    Closed,
    ReviewLimitReached,
}

/// Match the Python worker's assignment gates, failing closed for incomplete data.
/// This is a decision only: callers must recheck and reserve in one transaction.
/// It neither reveals a prompt nor issues a playback URL or reward.
pub fn review_eligibility(
    recording: &Recording<'_>,
    reviewer: Participant<'_>,
    exposed_phrase_ids: &[&str],
) -> Result<(), Ineligible> {
    let valid = |p: Participant<'_>| !p.uid.is_empty() && !p.person_id.is_empty();
    if !valid(reviewer)
        || !valid(recording.signer)
        || recording.phrase_id.is_empty()
        || recording.reviewers.iter().any(|p| !valid(*p))
    {
        return Err(Ineligible::MissingIdentity);
    }
    if !reviewer.consent_active
        || !recording.signer.consent_active
        || recording.decision == Decision::ParticipationPaused
    {
        return Err(Ineligible::ParticipationPaused);
    }
    if !recording.saved || !recording.technical_check_passed {
        return Err(Ineligible::RecordingNotReady);
    }
    if reviewer.uid == recording.signer.uid || reviewer.person_id == recording.signer.person_id {
        return Err(Ineligible::SamePerson);
    }
    if exposed_phrase_ids.contains(&recording.phrase_id) {
        return Err(Ineligible::PhraseExposed);
    }
    if recording
        .reviewers
        .iter()
        .any(|p| p.uid == reviewer.uid || p.person_id == reviewer.person_id)
    {
        return Err(Ineligible::AlreadyReviewed);
    }
    if !matches!(
        recording.decision,
        Decision::AwaitingReviews | Decision::NeedsMoreReviews
    ) {
        return Err(Ineligible::Closed);
    }
    if recording.reviewers.len() >= recording.review_limit.min(5) {
        return Err(Ineligible::ReviewLimitReached);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn player(uid: &str) -> Participant<'_> {
        Participant {
            uid,
            person_id: uid,
            consent_active: true,
        }
    }
    fn recording() -> Recording<'static> {
        Recording {
            saved: true,
            signer: player("signer"),
            phrase_id: "phrase-1",
            technical_check_passed: true,
            reviewers: &[],
            review_limit: 3,
            decision: Decision::AwaitingReviews,
        }
    }
    #[test]
    fn independent_unexposed_reviewer_is_eligible() {
        assert_eq!(
            review_eligibility(&recording(), player("reviewer"), &[]),
            Ok(())
        );
    }
    #[test]
    fn rejects_self_and_linked_accounts() {
        let r = recording();
        assert_eq!(
            review_eligibility(&r, player("signer"), &[]),
            Err(Ineligible::SamePerson)
        );
        let linked = Participant {
            uid: "other-login",
            person_id: "signer",
            consent_active: true,
        };
        assert_eq!(
            review_eligibility(&r, linked, &[]),
            Err(Ineligible::SamePerson)
        );
    }
    #[test]
    fn exposure_and_duplicate_people_are_excluded() {
        let mut r = recording();
        assert_eq!(
            review_eligibility(&r, player("reviewer"), &["phrase-1"]),
            Err(Ineligible::PhraseExposed)
        );
        let previous = [player("first")];
        r.reviewers = &previous;
        let linked = Participant {
            uid: "second-login",
            person_id: "first",
            consent_active: true,
        };
        assert_eq!(
            review_eligibility(&r, linked, &[]),
            Err(Ineligible::AlreadyReviewed)
        );
    }
    #[test]
    fn consent_and_quality_fail_closed() {
        let mut r = recording();
        r.signer.consent_active = false;
        assert_eq!(
            review_eligibility(&r, player("reviewer"), &[]),
            Err(Ineligible::ParticipationPaused)
        );
        r.signer.consent_active = true;
        r.technical_check_passed = false;
        assert_eq!(
            review_eligibility(&r, player("reviewer"), &[]),
            Err(Ineligible::RecordingNotReady)
        );
        r.technical_check_passed = true;
        r.phrase_id = "";
        assert_eq!(
            review_eligibility(&r, player("reviewer"), &[]),
            Err(Ineligible::MissingIdentity)
        );
    }
    #[test]
    fn three_reviews_can_expand_to_five_but_not_beyond() {
        let people = [
            player("a"),
            player("b"),
            player("c"),
            player("d"),
            player("e"),
        ];
        let mut r = recording();
        r.reviewers = &people[..3];
        assert_eq!(
            review_eligibility(&r, player("reviewer"), &[]),
            Err(Ineligible::ReviewLimitReached)
        );
        r.review_limit = 5;
        r.decision = Decision::NeedsMoreReviews;
        assert_eq!(review_eligibility(&r, player("reviewer"), &[]), Ok(()));
        r.reviewers = &people;
        r.review_limit = 999;
        assert_eq!(
            review_eligibility(&r, player("reviewer"), &[]),
            Err(Ineligible::ReviewLimitReached)
        );
    }
    #[test]
    fn finalized_records_are_closed() {
        for decision in [
            Decision::Approved,
            Decision::AdjudicationRequired,
            Decision::QualityCheckRequired,
            Decision::TestOnly,
        ] {
            let mut r = recording();
            r.decision = decision;
            assert_eq!(
                review_eligibility(&r, player("reviewer"), &[]),
                Err(Ineligible::Closed)
            );
        }
    }
}

pub mod consensus;
pub mod rewards;
