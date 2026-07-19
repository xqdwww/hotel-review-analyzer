"""Built-in traveler preference profiles."""

from copy import deepcopy
from typing import Any, Dict


HOTEL_FAMILY_COMFORT_V1: Dict[str, Any] = {
    "id": "hotel_family_comfort_v1",
    "description": (
        "Family hotel profile prioritizing hygiene, quiet sleep, stable air "
        "conditioning and hot water, reliable facilities, and truthful location."
    ),
    "priorities": {
        "hygiene": 1.5,
        "noise": 1.5,
        "air_conditioning": 1.4,
        "hot_water": 1.4,
        "facility": 1.4,
        "room_mismatch": 1.1,
        "location": 1.25,
        "hidden_fees": 0.8,
        "service": 0.5,
    },
    "priority_groups": {
        "high": [
            "hygiene",
            "quiet_sleep",
            "air_conditioning",
            "hot_water",
            "facility_stability",
            "transport_location",
        ],
        "medium": [
            "room_size_and_comfort",
            "decor_age",
            "location_truthfulness",
        ],
        "low": [
            "ordinary_breakfast",
            "ordinary_service_attitude",
            "parking_process_hassle",
            "price_alone",
        ],
    },
    "review_credibility_order": [
        "latest_specific_repeated_by_multiple_guests",
        "latest_specific_single_report",
        "older_specific_report",
        "long_but_vague_review",
    ],
    "tolerances": {
        "small_room": 4,
        "old_decor": 3,
        "ordinary_breakfast": 5,
        "ordinary_service": 3,
        "metro_walk_10_15_minutes": 3,
        "street_facing_but_quiet_with_window_closed": 4,
        "windowless_room": 3,
        "central_air_conditioning_not_individually_controllable": 2,
        "price_30_percent_above_normal": 2,
        "free_parking_with_cumbersome_process": 5,
    },
    "destination_scan_weights": {
        "base_points": 45.0,
        "ctrip_rating_max_points": 10.0,
        "positive_points": {
            "hygiene": 2.0,
            "quiet": 2.5,
            "air_conditioning": 2.0,
            "hot_water": 2.0,
            "facility_stability": 1.5,
            "transport_per_score": 2.0,
            "room_comfort": 1.0,
            "family_tag": 0.75,
        },
        "hard_risk_penalty_per_issue": {
            "hygiene": 8.0,
            "air_conditioning": 8.0,
            "hot_water": 8.0,
            "noise": 7.0,
            "facility": 3.0,
            "room_mismatch": 3.0,
            "location_mismatch": 4.0,
            "price_mismatch_or_broken_promise": 4.0,
        },
        "recent_specific_repeated_penalty_per_signal": 5.0,
        "recent_specific_repeated_penalty_cap": 15.0,
        "low_priority_penalty_per_issue": {
            "ordinary_breakfast": 0.4,
            "ordinary_service": 0.3,
            "parking_process_hassle": 0.3,
            "price_alone": 0.2,
        },
        "low_priority_penalty_cap": 3.0,
        "missing_recent_summary_penalty": 3.0,
        "missing_visible_negative_summary_penalty": 2.0,
    },
}


BUILT_IN_PROFILES = {
    HOTEL_FAMILY_COMFORT_V1["id"]: HOTEL_FAMILY_COMFORT_V1,
}


def get_preference_profile(profile_id: str = "hotel_family_comfort_v1") -> Dict[str, Any]:
    """Return an isolated copy of a built-in preference profile."""
    if profile_id not in BUILT_IN_PROFILES:
        raise ValueError(f"Unknown preference profile: {profile_id}")
    return deepcopy(BUILT_IN_PROFILES[profile_id])
