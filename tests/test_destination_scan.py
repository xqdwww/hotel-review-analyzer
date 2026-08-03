"""Tests for Ctrip destination candidate ranking."""

import json

from hotel_review_analyzer.cli import main
from hotel_review_analyzer.destination import (
    rank_destination_candidates,
    validate_destination_scan_input,
)
from hotel_review_analyzer.profiles import get_preference_profile


def make_candidate(rank, rating, name=None, **signal_overrides):
    signals = {
        "hygiene_positive_count": 1,
        "quiet_positive_count": 1,
        "air_conditioning_positive_count": 1,
        "hot_water_positive_count": 1,
        "facility_stability_positive_count": 1,
        "transport_convenience_score": 3,
    }
    signals.update(signal_overrides)
    return {
        "name": name or f"Hotel {rank}",
        "url": f"https://hotels.ctrip.com/hotels/{rank}.html",
        "ctrip_rating": rating,
        "entry_rank": rank,
        "review_count": 500 + rank,
        "price_or_range": "CNY 600-900",
        "location": "Synthetic central area",
        "star_or_class": "Comfort",
        "family_tags": ["family room"],
        "recent_review_summary": ["Synthetic recent summary"],
        "visible_negative_risk_summary": ["Synthetic low-score summary"],
        "preference_signals": signals,
    }


def make_scan_input():
    candidates = [
        make_candidate(rank, round(4.91 - rank * 0.05, 2))
        for rank in range(1, 23)
    ]
    candidates[0] = make_candidate(
        1,
        4.9,
        "Highest rating with repeated hard issues",
        recent_air_conditioning_issue_count=2,
        recent_hot_water_issue_count=2,
        recent_noise_issue_count=2,
        recent_hygiene_issue_count=2,
        recent_specific_repeated_issue_count=4,
    )
    candidates[1] = make_candidate(
        2,
        4.8,
        "Strong candidate with low-priority caveats",
        hygiene_positive_count=3,
        quiet_positive_count=3,
        air_conditioning_positive_count=2,
        hot_water_positive_count=2,
        facility_stability_positive_count=2,
        transport_convenience_score=5,
        ordinary_breakfast_complaint_count=3,
        ordinary_service_complaint_count=2,
        parking_process_hassle_count=3,
    )
    candidates[11] = make_candidate(
        12,
        4.3,
        "Entry rank 12 preference match",
        hygiene_positive_count=4,
        quiet_positive_count=4,
        air_conditioning_positive_count=3,
        hot_water_positive_count=3,
        facility_stability_positive_count=3,
        transport_convenience_score=5,
        room_comfort_positive_count=3,
    )
    return {
        "platform": "ctrip",
        "mode": "destination_scan",
        "destination": "Synthetic City Center",
        "entry_sort_order": "rating_desc",
        "candidate_pool_target": 25,
        "final_candidate_limit": 10,
        "deep_screen_shortlist_size": 3,
        "preference_profile_id": "hotel_family_comfort_v1",
        "candidates": candidates,
    }


def test_family_comfort_profile_exists_with_expected_priority_tiers():
    profile = get_preference_profile("hotel_family_comfort_v1")

    assert profile["id"] == "hotel_family_comfort_v1"
    assert "hygiene" in profile["priority_groups"]["high"]
    assert "facility_stability" in profile["priority_groups"]["high"]
    assert "room_size_and_comfort" in profile["priority_groups"]["medium"]
    assert "ordinary_breakfast" in profile["priority_groups"]["low"]
    assert profile["destination_scan_weights"]["ctrip_rating_max_points"] == 10.0


def test_destination_input_is_valid_and_defaults_to_20_30_pool_target():
    data = make_scan_input()

    is_valid, issues = validate_destination_scan_input(data)

    assert is_valid, issues
    assert 20 <= data["candidate_pool_target"] <= 30


def test_destination_input_requires_at_least_20_candidates():
    data = make_scan_input()
    data["candidates"] = data["candidates"][:19]

    is_valid, issues = validate_destination_scan_input(data)

    assert not is_valid
    assert any("at least 20" in issue for issue in issues)


def test_rating_is_entry_only_and_entry_rank_12_can_rerank_first():
    report = rank_destination_candidates(make_scan_input())
    top = report["final_top10"]

    assert top[0]["name"] == "Entry rank 12 preference match"
    assert top[0]["entry_rank"] == 12
    assert top[0]["preference_rank"] == 1
    assert top[0]["ctrip_rating"] < 4.9
    assert any(item["entry_rank"] != item["preference_rank"] for item in top)


def test_highest_entry_rating_with_concentrated_recent_hard_issues_is_downranked():
    report = rank_destination_candidates(make_scan_input())
    names = {candidate["name"] for candidate in report["final_top10"]}

    assert "Highest rating with repeated hard issues" not in names
    assert report["final_top10"][0]["ctrip_rating"] != 4.9


def test_low_priority_caveats_do_not_significantly_reduce_strong_candidate():
    report = rank_destination_candidates(make_scan_input())
    candidate = next(
        item
        for item in report["final_top10"]
        if item["name"] == "Strong candidate with low-priority caveats"
    )

    assert candidate["preference_rank"] <= 4
    assert candidate["preference_score"] >= 80
    assert any("breakfast" in reason for reason in candidate["downrank_reasons"])
    assert any("parking" in reason for reason in candidate["downrank_reasons"])
    assert any("service" in reason for reason in candidate["downrank_reasons"])


def test_scan_output_is_top10_without_final_hotel_judgment_fields():
    report = rank_destination_candidates(make_scan_input())

    assert len(report["final_top10"]) == 10
    assert report["candidate_stage_only"] is True
    assert report["deep_screen_required"] is True
    assert "2-3 hotels" in report["next_step"]
    for forbidden in ["verdict", "risk_score", "confidence", "evidence_status"]:
        assert forbidden not in report
        assert all(forbidden not in candidate for candidate in report["final_top10"])
    assert sum(item["should_deep_screen"] for item in report["final_top10"]) == 3


def test_requested_deep_screen_shortlist_size_is_preserved():
    data = make_scan_input()
    data["deep_screen_shortlist_size"] = 2
    for candidate in data["candidates"]:
        candidate["preference_signals"]["recent_hygiene_issue_count"] = 3

    report = rank_destination_candidates(data)

    assert sum(item["should_deep_screen"] for item in report["final_top10"]) == 2


def test_destination_ranker_cli_writes_standalone_json(tmp_path):
    input_path = tmp_path / "candidates.json"
    output_path = tmp_path / "shortlist.json"
    input_path.write_text(json.dumps(make_scan_input()), encoding="utf-8")

    result = main(
        [
            "rank-destination",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )

    assert result == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(report["final_top10"]) == 10
    assert report["preference_profile_used"] == "hotel_family_comfort_v1"
