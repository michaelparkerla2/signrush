//! Private stdin/stdout protocol for comparison only. No network or writes.
use serde_json::{Value, json};
use signrush_core::consensus::*;
use std::io::{self, Read};
fn str_field<'a>(v: &'a Value, key: &str) -> Result<&'a str, &'static str> {
    v.get(key).and_then(Value::as_str).ok_or("invalid string")
}
fn bool_field(v: &Value, key: &str) -> Result<bool, &'static str> {
    v.get(key).and_then(Value::as_bool).ok_or("invalid bool")
}
fn execute(v: &Value) -> Result<Value, &'static str> {
    if str_field(v, "protocol")? != "signrush-shadow-v1"
        || str_field(v, "normalization")? != "python-nfkc-casefold-word-v1"
    {
        return Err("unsupported protocol");
    }
    let input = v.get("input").ok_or("missing input")?;
    let duration = input.get("duration_seconds").ok_or("missing duration")?;
    let duration = if duration.is_null() {
        None
    } else {
        Some(duration.as_f64().ok_or("invalid duration")?)
    };
    let input = Input {
        signer_uid: str_field(input, "signer_uid")?,
        normalized_reference: str_field(input, "normalized_reference")?,
        technical_passed: bool_field(input, "technical_passed")?,
        duration_seconds: duration,
    };
    let mut identities = Identities::new();
    for (uid, p) in v
        .get("identities")
        .and_then(Value::as_object)
        .ok_or("missing identities")?
    {
        let link = p.get("same_person_as").ok_or("missing link")?;
        identities.insert(
            uid.clone(),
            Identity {
                same_person_as: if link.is_null() {
                    None
                } else {
                    Some(link.as_str().ok_or("invalid link")?.into())
                },
                test_only: bool_field(p, "test_only")?,
                active: bool_field(p, "active")?,
            },
        );
    }
    let mut reviews = Vec::new();
    for r in v
        .get("reviews")
        .and_then(Value::as_array)
        .ok_or("missing reviews")?
    {
        reviews.push(Review {
            id: str_field(r, "id")?,
            uid: str_field(r, "uid")?,
            pending: bool_field(r, "pending")?,
            text_present: bool_field(r, "text_present")?,
            normalized_text: str_field(r, "normalized_text")?,
            quality_good: bool_field(r, "quality_good")?,
        });
    }
    let d = decide(&input, &reviews, &identities);
    let status = match d.status {
        Status::AwaitingReviews => "awaiting_reviews",
        Status::NeedsMoreReviews => "needs_more_reviews",
        Status::AdjudicationRequired => "adjudication_required",
        Status::ParticipationPaused => "participation_paused",
        Status::TestOnly => "test_only",
        Status::QualityCheckRequired => "quality_check_required",
        Status::Approved => "approved",
    };
    let excluded: serde_json::Map<String, Value> = d
        .excluded
        .into_iter()
        .map(|(k, v)| {
            (
                k,
                json!(match v {
                    Exclusion::OwnerOrTestAccount => "owner_or_test_account",
                    Exclusion::ParticipationPaused => "participation_paused",
                    Exclusion::DuplicatePerson => "duplicate_person",
                    Exclusion::Incomplete => "incomplete",
                }),
            )
        })
        .collect();
    Ok(
        json!({"version":VERSION,"threshold":THRESHOLD,"status":status,"independentReviews":d.independent_reviews,"excludedReviews":excluded,"referenceScores":d.reference_scores,"reviewLimit":d.review_limit,"rewardReviewIds":d.reward_review_ids,"signerPoints":d.signer_points,"reviewerPoints":d.reviewer_points}),
    )
}
fn main() {
    let mut input = Vec::new();
    let result = io::stdin()
        .take(262145)
        .read_to_end(&mut input)
        .map_err(|_| "read error")
        .and({
            if input.len() > 262144 {
                Err("oversized input")
            } else {
                Ok(())
            }
        })
        .and_then(|_| serde_json::from_slice::<Value>(&input).map_err(|_| "invalid json"))
        .and_then(|v| execute(&v));
    match result {
        Ok(out) => println!("{out}"),
        Err(_) => {
            eprintln!("shadow input rejected");
            std::process::exit(2);
        }
    }
}
