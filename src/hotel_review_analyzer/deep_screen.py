"""Evidence-gated single-hotel deep screening."""

from typing import Any, Dict, List, Tuple

from .profiles import get_preference_profile
from .schema import DEFAULT_HOTEL_WEIGHTS, extract_review_signals


def validate_deep_screen_input(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Require latest-sorted reviews and a separate low-score sample."""
    issues = []
    if not isinstance(data, dict):
        return False, ["Input root must be an object"]
    hotel = data.get("hotel")
    if not isinstance(hotel, dict) or not isinstance(hotel.get("name"), str):
        issues.append("hotel.name must be a non-empty string")

    collection = data.get("review_collection")
    if not isinstance(collection, dict):
        issues.append("review_collection must be an object")
    else:
        if collection.get("sort_order") != "latest":
            issues.append("review_collection.sort_order must be 'latest'")
        recent_count = collection.get("recent_reviews_collected_count")
        if isinstance(recent_count, bool) or not isinstance(recent_count, int) or recent_count < 1:
            issues.append("recent_reviews_collected_count must be greater than zero")
        negative_count = collection.get("negative_reviews_collected_count")
        if isinstance(negative_count, bool) or not isinstance(negative_count, int) or negative_count < 1:
            issues.append("negative_reviews_collected_count must be greater than zero")
        if collection.get("negative_reviews_collected_separately") is not True:
            issues.append("negative reviews must be collected separately")

    try:
        get_preference_profile(data.get("preference_profile_id", "hotel_family_comfort_v1"))
    except ValueError as exc:
        issues.append(str(exc))

    reviews = data.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        issues.append("reviews must be a non-empty array")
        return len(issues) == 0, issues

    bucket_counts = {"recent": 0, "negative": 0}
    for index, review in enumerate(reviews):
        if not isinstance(review, dict):
            issues.append(f"reviews[{index}] must be an object")
            continue
        if not isinstance(review.get("text"), str) or not review["text"].strip():
            issues.append(f"reviews[{index}].text must be a non-empty string")
        bucket = review.get("sample_bucket")
        if bucket not in bucket_counts:
            issues.append(f"reviews[{index}].sample_bucket must be recent or negative")
        else:
            bucket_counts[bucket] += 1
        if not isinstance(review.get("is_recent"), bool):
            issues.append(f"reviews[{index}].is_recent must be a boolean")
        if not isinstance(review.get("specific"), bool):
            issues.append(f"reviews[{index}].specific must be a boolean")

    if bucket_counts["recent"] == 0:
        issues.append("reviews must include the latest/recent sample")
    if bucket_counts["negative"] == 0:
        issues.append("reviews must include a separately collected negative sample")
    if isinstance(collection, dict):
        if collection.get("recent_reviews_collected_count") != bucket_counts["recent"]:
            issues.append("recent review count does not match the supplied sample")
        if collection.get("negative_reviews_collected_count") != bucket_counts["negative"]:
            issues.append("negative review count does not match the supplied sample")

    return len(issues) == 0, issues


def analyze_deep_screen(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a single hotel with explicit review-collection provenance."""
    is_valid, issues = validate_deep_screen_input(data)
    if not is_valid:
        raise ValueError("; ".join(issues))

    profile_id = data.get("preference_profile_id", "hotel_family_comfort_v1")
    profile = get_preference_profile(profile_id)
    adjusted_weights = {
        category: weight * profile["priorities"].get(category, 1.0)
        for category, weight in DEFAULT_HOTEL_WEIGHTS.items()
    }
    total_weight = sum(adjusted_weights.values())
    normalized_weights = {
        category: value / total_weight for category, value in adjusted_weights.items()
    }

    category_evidence = {}
    analyzed_reviews = len(data["reviews"])
    for index, review in enumerate(data["reviews"], start=1):
        signals = extract_review_signals(review["text"])
        multiplier = 1.0
        if review["is_recent"]:
            multiplier *= 1.5
        if review["specific"]:
            multiplier *= 1.4
        if review["sample_bucket"] == "negative":
            multiplier *= 1.1

        for category, keywords in signals.items():
            evidence = category_evidence.setdefault(
                category,
                {
                    "weighted_occurrences": 0.0,
                    "review_count": 0,
                    "recent_specific_count": 0,
                    "evidence": [],
                },
            )
            evidence["weighted_occurrences"] += multiplier
            evidence["review_count"] += 1
            if review["is_recent"] and review["specific"]:
                evidence["recent_specific_count"] += 1
            evidence["evidence"].append(
                {
                    "review_id": review.get("id", f"review_{index}"),
                    "sample_bucket": review["sample_bucket"],
                    "is_recent": review["is_recent"],
                    "specific": review["specific"],
                    "matched_keywords": keywords,
                }
            )

    category_scores = {}
    repeated_recent_specific_issues = []
    for category, evidence in category_evidence.items():
        repeated_count = evidence["recent_specific_count"]
        repeat_multiplier = 1.0
        if repeated_count >= 2:
            repeat_multiplier += min(0.75, (repeated_count - 1) * 0.25)
            repeated_recent_specific_issues.append(
                {"category": category, "guest_reports": repeated_count}
            )
        weighted_rate = min(1.0, evidence["weighted_occurrences"] / analyzed_reviews)
        raw_score = min(10.0, weighted_rate * 10.0 * repeat_multiplier)
        category_scores[category] = {
            "issue_review_count": evidence["review_count"],
            "weighted_occurrences": round(evidence["weighted_occurrences"], 3),
            "recent_specific_count": repeated_count,
            "repeat_multiplier": round(repeat_multiplier, 2),
            "raw_score": round(raw_score, 2),
            "normalized_profile_weight": round(normalized_weights[category], 4),
            "evidence": evidence["evidence"],
        }

    weighted_sum = sum(
        values["raw_score"] * normalized_weights[category]
        for category, values in category_scores.items()
    )
    overall_score = round(min(100.0, weighted_sum * 10.0), 1)
    if overall_score < 20:
        risk_level = "low"
    elif overall_score < 40:
        risk_level = "moderate"
    elif overall_score < 70:
        risk_level = "high"
    else:
        risk_level = "very_high"
    confidence = "high" if analyzed_reviews >= 20 else "medium" if analyzed_reviews >= 5 else "low"

    checklist = [
        "Confirm the exact room area, window, floor, view, and bed type.",
        "Confirm that air conditioning is individually controllable for the stay dates.",
        "Confirm stable hot water during peak family-use hours.",
        "Request a quiet room away from roads, lifts, plant rooms, and construction.",
        "Verify the actual walking route and parking process with luggage or children.",
        "Save the cancellation, deposit, fee, breakfast, and child-policy terms.",
    ]

    return {
        "hotel": {
            "name": data["hotel"]["name"],
            "location": data["hotel"].get("location", ""),
        },
        "preference_profile_used": profile_id,
        "evidence_status": "sufficient_evidence",
        "review_collection": data["review_collection"],
        "overall_risk_score": overall_score,
        "risk_level": risk_level,
        "confidence": confidence,
        "category_scores": category_scores,
        "repeated_recent_specific_issues": repeated_recent_specific_issues,
        "pre_booking_checklist": checklist,
        "explainability": {
            "evidence_multipliers": {
                "recent": 1.5,
                "specific": 1.4,
                "negative_sample": 1.1,
                "repeated_recent_specific": "1.25x to 1.75x by repeated guest count",
            },
            "profile_weights": normalized_weights,
        },
        "limitations": [
            "The analyzer uses supplied local review text and keyword matching only.",
            "A deep screen is decision support, not a booking guarantee.",
        ],
    }
