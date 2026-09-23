//! Pure plan for the existing TEST points ledger; never a cash payment API.
//! Read existing event IDs and balances, re-run this plan, and atomically create
//! events/update balances in one transaction. A plan alone is not idempotent storage.
use crate::consensus::{Identities, Input, Review, VERSION, decide, person_key_checked};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, PartialEq, Eq)]
pub struct Award {
    pub event_id: String,
    pub uid: String,
    pub role: &'static str,
    pub points: u32,
    pub mode: &'static str,
    pub policy_version: &'static str,
}
#[derive(Debug, PartialEq, Eq)]
pub struct RewardPlan {
    pub awards: Vec<Award>,
    pub balances: BTreeMap<String, u64>,
}
#[derive(Debug, PartialEq, Eq)]
pub enum PlanError {
    InvalidIdentifier,
    DuplicateReview,
    TooManyReviews,
    InvalidBalance,
    CyclicIdentity,
    Overflow,
}
const MAX_SAFE_INTEGER: u64 = 9_007_199_254_740_991;
fn valid_uid(s: &str) -> bool {
    !s.is_empty() && s.len() <= 128 && !s.contains('/') && !s.chars().any(char::is_control)
}

pub fn plan_test_rewards(
    recording_id: &str,
    input: &Input<'_>,
    reviews: &[Review<'_>],
    identities: &Identities,
    existing_events: &BTreeSet<String>,
    balances: &BTreeMap<String, u64>,
) -> Result<RewardPlan, PlanError> {
    if recording_id.len() != 32
        || !recording_id
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        || !valid_uid(input.signer_uid)
    {
        return Err(PlanError::InvalidIdentifier);
    }
    if reviews.len() > 5 {
        return Err(PlanError::TooManyReviews);
    }
    let mut seen = BTreeSet::new();
    for r in reviews {
        if r.id.is_empty() || r.id.contains('/') || !valid_uid(r.uid) {
            return Err(PlanError::InvalidIdentifier);
        }
        if !seen.insert(r.id) {
            return Err(PlanError::DuplicateReview);
        }
    }
    for uid in std::iter::once(input.signer_uid).chain(reviews.iter().map(|r| r.uid)) {
        person_key_checked(uid, identities).map_err(|_| PlanError::CyclicIdentity)?;
    }
    let outcome = decide(input, reviews, identities);
    let mut candidates = Vec::new();
    if outcome.signer_points > 0 {
        candidates.push((input.signer_uid, "sign", outcome.signer_points));
    }
    for r in reviews {
        if outcome.reward_review_ids.iter().any(|id| id == r.id) {
            candidates.push((r.uid, "review", outcome.reviewer_points));
        }
    }
    let mut plan = RewardPlan {
        awards: Vec::new(),
        balances: BTreeMap::new(),
    };
    for (uid, role, points) in candidates {
        let event_id = format!("{recording_id}-{role}-{uid}");
        if existing_events.contains(&event_id) {
            continue;
        }
        let old = plan
            .balances
            .get(uid)
            .or_else(|| balances.get(uid))
            .copied()
            .unwrap_or(0);
        if old > MAX_SAFE_INTEGER {
            return Err(PlanError::InvalidBalance);
        }
        let new = old
            .checked_add(u64::from(points))
            .filter(|n| *n <= MAX_SAFE_INTEGER)
            .ok_or(PlanError::Overflow)?;
        plan.balances.insert(uid.to_owned(), new);
        plan.awards.push(Award {
            event_id,
            uid: uid.to_owned(),
            role,
            points,
            mode: "test",
            policy_version: VERSION,
        });
    }
    Ok(plan)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::consensus::Identity;
    const RECORD: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    #[test]
    fn retries_and_partial_existing_awards_never_increment_twice() {
        let input = Input {
            signer_uid: "s",
            normalized_reference: "hello",
            technical_passed: true,
            duration_seconds: Some(12.7),
        };
        let reviews: Vec<_> = ["a", "b", "c"]
            .iter()
            .map(|uid| Review {
                id: uid,
                uid,
                pending: true,
                text_present: true,
                normalized_text: "hello",
                quality_good: true,
            })
            .collect();
        let identities = ["s", "a", "b", "c"]
            .into_iter()
            .map(|uid| {
                (
                    uid.into(),
                    Identity {
                        active: true,
                        ..Default::default()
                    },
                )
            })
            .collect();
        let initial = plan_test_rewards(
            RECORD,
            &input,
            &reviews,
            &identities,
            &BTreeSet::new(),
            &BTreeMap::new(),
        )
        .unwrap();
        assert_eq!(initial.awards.len(), 4);
        assert_eq!(initial.balances["s"], 12);
        assert_eq!(initial.balances["a"], 5);
        assert!(initial.awards.iter().all(|a| a.mode == "test"));
        let existing = initial.awards.iter().map(|a| a.event_id.clone()).collect();
        let retry = plan_test_rewards(
            RECORD,
            &input,
            &reviews,
            &identities,
            &existing,
            &initial.balances,
        )
        .unwrap();
        assert!(retry.awards.is_empty());
        assert!(retry.balances.is_empty());
        let partial = BTreeSet::from([format!("{RECORD}-review-a")]);
        let next = plan_test_rewards(
            RECORD,
            &input,
            &reviews,
            &identities,
            &partial,
            &BTreeMap::from([("a".into(), 5)]),
        )
        .unwrap();
        assert_eq!(next.awards.len(), 3);
        assert!(!next.balances.contains_key("a"));
        let huge = BTreeMap::from([("s".into(), MAX_SAFE_INTEGER)]);
        assert_eq!(
            plan_test_rewards(
                RECORD,
                &input,
                &reviews,
                &identities,
                &BTreeSet::new(),
                &huge
            ),
            Err(PlanError::Overflow)
        );
    }
    #[test]
    fn invalid_records_and_duplicate_reviews_fail_closed() {
        let input = Input {
            signer_uid: "s",
            normalized_reference: "hi",
            technical_passed: true,
            duration_seconds: Some(10.0),
        };
        assert_eq!(
            plan_test_rewards(
                "../bad",
                &input,
                &[],
                &Identities::new(),
                &BTreeSet::new(),
                &BTreeMap::new()
            ),
            Err(PlanError::InvalidIdentifier)
        );
        let reviews: Vec<_> = ["a", "b"]
            .iter()
            .map(|uid| Review {
                id: "same",
                uid,
                pending: true,
                text_present: true,
                normalized_text: "hi",
                quality_good: true,
            })
            .collect();
        assert_eq!(
            plan_test_rewards(
                RECORD,
                &input,
                &reviews,
                &Identities::new(),
                &BTreeSet::new(),
                &BTreeMap::new()
            ),
            Err(PlanError::DuplicateReview)
        );
    }
}
