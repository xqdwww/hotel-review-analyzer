"""Ctrip destination candidate-pool ranking."""

import math
from typing import Any, Dict, List, Mapping, Tuple

from .profiles import get_preference_profile


VALID_ENTRY_SORT_ORDERS = {"rating_desc", "positive_review_first", "unknown"}
FINAL_CANDIDATE_LIMIT = 10


def _as_int(values: Mapping[str, Any], key: str) -> int:
    value = values.get(key, 0)
    if isinstance(value, bool):
        return int(value)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _as_float(values: Mapping[str, Any], key: str) -> float:
    try:
        value = float(values.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, value) if math.isfinite(value) else 0.0


def _as_string_list(values: Mapping[str, Any], key: str) -> List[str]:
    value = values.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def validate_destination_scan_input(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a local Ctrip destination candidate pool."""
    issues = []
    if not isinstance(data, dict):
        return False, ["Input root must be an object"]
    if data.get("platform") != "ctrip":
        issues.append("platform must be 'ctrip'")
    if data.get("mode") != "destination_scan":
        issues.append("mode must be 'destination_scan'")
    if not isinstance(data.get("destination"), str) or not data["destination"].strip():
        issues.append("destination must be a non-empty string")
    if data.get("entry_sort_order") not in VALID_ENTRY_SORT_ORDERS:
        issues.append("entry_sort_order must be rating_desc, positive_review_first, or unknown")

    pool_target = data.get("candidate_pool_target", 25)
    if isinstance(pool_target, bool) or not isinstance(pool_target, int) or not 20 <= pool_target <= 30:
        issues.append("candidate_pool_target must be an integer between 20 and 30")
    if data.get("final_candidate_limit", FINAL_CANDIDATE_LIMIT) != FINAL_CANDIDATE_LIMIT:
        issues.append("final_candidate_limit must be 10")
    deep_screen_count = data.get("deep_screen_shortlist_size", 3)
    if isinstance(deep_screen_count, bool) or deep_screen_count not in {2, 3}:
        issues.append("deep_screen_shortlist_size must be 2 or 3")

    try:
        get_preference_profile(data.get("preference_profile_id", "hotel_family_comfort_v1"))
    except ValueError as exc:
        issues.append(str(exc))

    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        issues.append("candidates must be an array")
        return len(issues) == 0, issues
    if len(candidates) < FINAL_CANDIDATE_LIMIT:
        issues.append("candidates must contain at least 10 hotels to emit Top 10")
    if len(candidates) > 30:
        issues.append("candidates must not exceed 30 hotels")

    seen_names = set()
    seen_ranks = set()
    required_lists = {
        "family_tags",
        "recent_review_summary",
        "visible_negative_risk_summary",
    }
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            issues.append(f"candidates[{index}] must be an object")
            continue
        name = candidate.get("name")
        if not isinstance(name, str) or not name.strip():
            issues.append(f"candidates[{index}].name must be a non-empty string")
            name = f"candidate {index}"
        elif name in seen_names:
            issues.append(f"duplicate candidate name: {name}")
        seen_names.add(name)

        if not isinstance(candidate.get("url"), str) or not candidate["url"].strip():
            issues.append(f"candidates[{index}].url must be a non-empty string")
        rating = candidate.get("ctrip_rating")
        if (
            isinstance(rating, bool)
            or not isinstance(rating, (int, float))
            or not math.isfinite(rating)
            or not 0 <= rating <= 5
        ):
            issues.append(f"candidates[{index}].ctrip_rating must be between 0 and 5")
        entry_rank = candidate.get("entry_rank")
        if isinstance(entry_rank, bool) or not isinstance(entry_rank, int) or entry_rank < 1:
            issues.append(f"candidates[{index}].entry_rank must be a positive integer")
        elif entry_rank in seen_ranks:
            issues.append(f"duplicate entry_rank: {entry_rank}")
        seen_ranks.add(entry_rank)
        review_count = candidate.get("review_count")
        if isinstance(review_count, bool) or not isinstance(review_count, int) or review_count < 0:
            issues.append(f"candidates[{index}].review_count must be a non-negative integer")
        for field in required_lists:
            if not isinstance(candidate.get(field), list):
                issues.append(f"candidates[{index}].{field} must be an array")
        if not isinstance(candidate.get("preference_signals"), dict):
            issues.append(f"candidates[{index}].preference_signals must be an object")

    return len(issues) == 0, issues


def _score_candidate(
    candidate: Mapping[str, Any],
    weights: Mapping[str, Any],
) -> Tuple[int, List[str], List[str], int]:
    signals = candidate["preference_signals"]
    positive_weights = weights["positive_points"]
    hard_weights = weights["hard_risk_penalty_per_issue"]
    low_weights = weights["low_priority_penalty_per_issue"]
    rating = float(candidate["ctrip_rating"])
    score = float(weights["base_points"])
    score += rating / 5.0 * float(weights["ctrip_rating_max_points"])
    keep_reasons = [f"Ctrip rating {rating:.1f} used as an entry signal only"]
    downrank_reasons = []

    positive_fields = {
        "hygiene": ("hygiene_positive_count", "specific recent hygiene evidence"),
        "quiet": ("quiet_positive_count", "specific quiet-sleep evidence"),
        "air_conditioning": (
            "air_conditioning_positive_count",
            "stable or controllable air-conditioning evidence",
        ),
        "hot_water": ("hot_water_positive_count", "stable hot-water evidence"),
        "facility_stability": (
            "facility_stability_positive_count",
            "stable facility evidence",
        ),
        "room_comfort": ("room_comfort_positive_count", "room-comfort evidence"),
    }
    for category, (field, label) in positive_fields.items():
        count = _as_int(signals, field)
        if count:
            score += min(8.0, count * float(positive_weights[category]))
            keep_reasons.append(label)

    transport_score = min(5.0, _as_float(signals, "transport_convenience_score"))
    if transport_score:
        score += transport_score * float(positive_weights["transport_per_score"])
        keep_reasons.append(f"visible transport/location fit {transport_score:.1f}/5")
    family_tags = _as_string_list(candidate, "family_tags")
    if family_tags:
        score += min(3.0, len(family_tags) * float(positive_weights["family_tag"]))
        keep_reasons.append("family tags: " + ", ".join(family_tags[:3]))

    hard_fields = {
        "hygiene": ("recent_hygiene_issue_count", "recent hygiene issues"),
        "air_conditioning": (
            "recent_air_conditioning_issue_count",
            "recent air-conditioning issues",
        ),
        "hot_water": ("recent_hot_water_issue_count", "recent hot-water issues"),
        "noise": ("recent_noise_issue_count", "recent noise/soundproofing issues"),
        "facility": ("facility_issue_count", "facility-stability issues"),
        "room_mismatch": ("room_mismatch_count", "room/listing mismatch"),
        "location_mismatch": ("location_mismatch_count", "location mismatch"),
        "price_mismatch_or_broken_promise": (
            "price_mismatch_or_broken_promise_count",
            "price tied to mismatch, hidden fee, or broken promise",
        ),
    }
    hard_issue_total = 0
    for category, (field, label) in hard_fields.items():
        count = _as_int(signals, field)
        if count:
            hard_issue_total += count
            score -= count * float(hard_weights[category])
            downrank_reasons.append(f"{label} x {count}")

    repeated_count = _as_int(signals, "recent_specific_repeated_issue_count")
    if repeated_count:
        repeated_penalty = repeated_count * float(
            weights["recent_specific_repeated_penalty_per_signal"]
        )
        score -= min(float(weights["recent_specific_repeated_penalty_cap"]), repeated_penalty)
        downrank_reasons.append(
            f"specific recent issue repeated by multiple guests x {repeated_count}"
        )

    low_fields = {
        "ordinary_breakfast": (
            "ordinary_breakfast_complaint_count",
            "ordinary breakfast (low weight)",
        ),
        "ordinary_service": (
            "ordinary_service_complaint_count",
            "ordinary service (low weight)",
        ),
        "parking_process_hassle": (
            "parking_process_hassle_count",
            "parking-process hassle (low weight)",
        ),
        "price_alone": ("price_only_complaint_count", "price alone (low weight)"),
    }
    low_penalty = 0.0
    for category, (field, label) in low_fields.items():
        count = _as_int(signals, field)
        if count:
            low_penalty += count * float(low_weights[category])
            downrank_reasons.append(label)
    score -= min(float(weights["low_priority_penalty_cap"]), low_penalty)

    if not _as_string_list(candidate, "recent_review_summary"):
        score -= float(weights["missing_recent_summary_penalty"])
        downrank_reasons.append("recent-review summary missing; deep screen required")
    if not _as_string_list(candidate, "visible_negative_risk_summary"):
        score -= float(weights["missing_visible_negative_summary_penalty"])
        downrank_reasons.append("visible negative summary missing; absence is not positive evidence")
    if len(keep_reasons) == 1:
        keep_reasons.append("only list-level entry evidence is currently available")

    return round(max(0.0, min(100.0, score))), keep_reasons, downrank_reasons, hard_issue_total


def rank_destination_candidates(data: Dict[str, Any]) -> Dict[str, Any]:
    """Rerank a Ctrip entry pool by family-comfort preference fit."""
    is_valid, issues = validate_destination_scan_input(data)
    if not is_valid:
        raise ValueError("; ".join(issues))

    profile_id = data.get("preference_profile_id", "hotel_family_comfort_v1")
    profile = get_preference_profile(profile_id)
    weights = profile["destination_scan_weights"]
    ranked = []
    for candidate in data["candidates"]:
        preference_score, keep_reasons, downrank_reasons, hard_issue_total = _score_candidate(
            candidate,
            weights,
        )
        ranked.append(
            {
                "candidate": candidate,
                "preference_score": preference_score,
                "keep_reasons": keep_reasons,
                "downrank_reasons": downrank_reasons,
                "hard_issue_total": hard_issue_total,
            }
        )

    ranked.sort(
        key=lambda item: (
            -item["preference_score"],
            item["candidate"]["entry_rank"],
            item["candidate"]["name"],
        )
    )
    deep_screen_count = data.get("deep_screen_shortlist_size", 3)
    final_top10 = []
    for preference_rank, item in enumerate(ranked[:FINAL_CANDIDATE_LIMIT], start=1):
        candidate = item["candidate"]
        final_top10.append(
            {
                "name": candidate["name"],
                "url": candidate["url"],
                "ctrip_rating": float(candidate["ctrip_rating"]),
                "review_count": candidate["review_count"],
                "price_or_range": candidate.get("price_or_range"),
                "location": candidate.get("location"),
                "star_or_class": candidate.get("star_or_class"),
                "family_tags": _as_string_list(candidate, "family_tags"),
                "recent_review_summary": _as_string_list(candidate, "recent_review_summary"),
                "visible_negative_risk_summary": _as_string_list(
                    candidate,
                    "visible_negative_risk_summary",
                ),
                "entry_rank": candidate["entry_rank"],
                "preference_rank": preference_rank,
                "preference_score": item["preference_score"],
                "keep_reasons": item["keep_reasons"],
                "downrank_reasons": item["downrank_reasons"],
                "should_deep_screen": (
                    preference_rank <= deep_screen_count and item["hard_issue_total"] < 2
                ),
            }
        )

    caveats = [
        "Ctrip overall rating is an entry-pool signal, not the final judgment.",
        "List-page summaries are not a substitute for latest and low-score review screening.",
        "This candidate-stage output intentionally has no final hotel verdict or confidence.",
    ]
    if len(data["candidates"]) < 20:
        caveats.append("The supplied fixture has fewer than the default 20-30 entry candidates.")

    return {
        "scan_status": "candidate_shortlist",
        "platform": "ctrip",
        "mode": "destination_scan",
        "destination": data["destination"],
        "entry_sort_order": data["entry_sort_order"],
        "candidate_pool_size": len(data["candidates"]),
        "candidate_pool_target": data.get("candidate_pool_target", 25),
        "preference_profile_used": profile_id,
        "candidate_stage_only": True,
        "deep_screen_required": True,
        "final_top10": final_top10,
        "next_step": (
            "Select 2-3 hotels, then run deep-screen with latest reviews and a separately "
            "collected low-score/negative sample."
        ),
        "caveats": caveats,
    }
