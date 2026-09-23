//! Conservative exact-match policy, matching Python `exact-pilot-v1`.
//! Text normalization remains a trusted adapter responsibility (Python NFKC +
//! casefold + word extraction). Never use client-provided normalized text.
use std::collections::{BTreeMap, BTreeSet};

pub const VERSION: &str = "exact-pilot-v1";
pub const THRESHOLD: f64 = 0.85;

#[derive(Default, Debug, Clone)]
pub struct Identity {
    pub same_person_as: Option<String>,
    pub test_only: bool,
    pub active: bool,
}
pub type Identities = BTreeMap<String, Identity>;

/// Preserves the existing Python identity-chain behavior, including cycles.
/// Callers must load the complete relevant chain from trusted records.
pub fn person_key(uid: &str, identities: &Identities) -> String {
    let mut current = uid;
    let mut seen = BTreeSet::new();
    while let Some(next) = identities
        .get(current)
        .and_then(|p| p.same_person_as.as_deref())
        .filter(|s| !s.is_empty())
    {
        if seen.contains(current) {
            return format!("linked-cycle:{}", seen.first().unwrap());
        }
        seen.insert(current);
        current = next;
    }
    current.to_owned()
}

/// Reject cyclic identity linkage before authorizing an assignment or reward.
/// `person_key` is retained for legacy decision parity, not safe cycle handling.
pub fn person_key_checked(uid: &str, identities: &Identities) -> Result<String, &'static str> {
    let mut current = uid;
    let mut seen = BTreeSet::new();
    loop {
        if !seen.insert(current) {
            return Err("cyclic identity linkage");
        }
        match identities
            .get(current)
            .and_then(|p| p.same_person_as.as_deref())
            .filter(|s| !s.is_empty())
        {
            Some(next) => current = next,
            None => return Ok(current.to_owned()),
        }
    }
}

pub struct Input<'a> {
    pub signer_uid: &'a str,
    pub normalized_reference: &'a str,
    pub technical_passed: bool,
    /// Invalid, missing or boolean Python durations must be mapped to None.
    pub duration_seconds: Option<f64>,
}
pub struct Review<'a> {
    pub id: &'a str,
    pub uid: &'a str,
    pub pending: bool,
    /// Whether the original text is nonempty after Python str.strip().
    pub text_present: bool,
    pub normalized_text: &'a str,
    pub quality_good: bool,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    AwaitingReviews,
    NeedsMoreReviews,
    AdjudicationRequired,
    ParticipationPaused,
    TestOnly,
    QualityCheckRequired,
    Approved,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Exclusion {
    OwnerOrTestAccount,
    ParticipationPaused,
    DuplicatePerson,
    Incomplete,
}
#[derive(Debug, PartialEq)]
pub struct Outcome {
    pub status: Status,
    pub independent_reviews: usize,
    pub excluded: BTreeMap<String, Exclusion>,
    /// Exact normalized match => Some(1.0); unknown similarity => None.
    pub reference_scores: BTreeMap<String, Option<f64>>,
    pub review_limit: usize,
    pub reward_review_ids: Vec<String>,
    pub signer_points: u32,
    pub reviewer_points: u32,
}

pub fn decide(input: &Input<'_>, reviews: &[Review<'_>], identities: &Identities) -> Outcome {
    let owner = person_key(input.signer_uid, identities);
    let mut seen = BTreeSet::from([owner.clone()]);
    let mut sorted: Vec<_> = reviews.iter().collect();
    sorted.sort_by_key(|r| r.id);
    let mut accepted = Vec::new();
    let mut result = Outcome {
        status: Status::AwaitingReviews,
        independent_reviews: 0,
        excluded: BTreeMap::new(),
        reference_scores: BTreeMap::new(),
        review_limit: 3,
        reward_review_ids: Vec::new(),
        signer_points: 0,
        reviewer_points: 5,
    };
    for r in sorted {
        let identity = person_key(r.uid, identities);
        let account = identities.get(r.uid);
        let reason = if account.is_some_and(|p| p.test_only) || identity == owner {
            Some(Exclusion::OwnerOrTestAccount)
        } else if !account.is_some_and(|p| p.active) {
            Some(Exclusion::ParticipationPaused)
        } else if seen.contains(&identity) {
            Some(Exclusion::DuplicatePerson)
        } else if !r.pending || !r.text_present {
            Some(Exclusion::Incomplete)
        } else {
            None
        };
        if let Some(reason) = reason {
            result.excluded.insert(r.id.to_owned(), reason);
        } else {
            accepted.push(r);
            seen.insert(identity);
        }
    }
    result.independent_reviews = accepted.len();
    let mut matched = Vec::new();
    for r in &accepted {
        let exact = !input.normalized_reference.is_empty()
            && r.normalized_text == input.normalized_reference;
        result
            .reference_scores
            .insert(r.id.to_owned(), exact.then_some(1.0));
        if exact {
            matched.push(*r);
        }
    }
    if !identities.get(input.signer_uid).is_some_and(|p| p.active) {
        result.status = Status::ParticipationPaused;
        return result;
    }
    if identities
        .get(input.signer_uid)
        .is_some_and(|p| p.test_only)
    {
        result.status = Status::TestOnly;
        return result;
    }
    if matched.len() >= 3 {
        // Existing policy can reward matching reviewers while the signer awaits quality review.
        result.reward_review_ids = matched.iter().map(|r| r.id.to_owned()).collect();
        result.status = Status::QualityCheckRequired;
        if input.technical_passed
            && matched.iter().filter(|r| r.quality_good).count() >= 3
            && let Some(seconds) = input
                .duration_seconds
                .filter(|s| s.is_finite() && (0.5..=31.0).contains(s))
        {
            result.status = Status::Approved;
            result.signer_points = (seconds.floor() as u32).clamp(1, 30);
        }
    } else if accepted.len() >= 3 || !result.excluded.is_empty() {
        result.review_limit = 5;
        result.status = if reviews.len() >= 5 {
            Status::AdjudicationRequired
        } else {
            Status::NeedsMoreReviews
        };
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn chains_and_cycles_match_current_policy() {
        let mut ids = Identities::new();
        for (a, b) in [("a", "b"), ("b", "c"), ("c", "b")] {
            ids.insert(
                a.into(),
                Identity {
                    same_person_as: Some(b.into()),
                    ..Default::default()
                },
            );
        }
        assert_eq!(person_key("a", &ids), "linked-cycle:a");
        assert!(person_key_checked("a", &ids).is_err());
        assert_eq!(person_key("b", &ids), "linked-cycle:b");
        ids.get_mut("c").unwrap().same_person_as = None;
        assert_eq!(person_key("a", &ids), "c");
    }
}
