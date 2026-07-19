"""Tests for evidence-gated single-hotel deep screening."""

import copy
import json

import pytest

from hotel_review_analyzer.cli import main
from hotel_review_analyzer.deep_screen import (
    analyze_deep_screen,
    validate_deep_screen_input,
)


def make_deep_screen_input():
    return {
        "hotel": {"name": "Synthetic Family Hotel", "location": "Synthetic Center"},
        "preference_profile_id": "hotel_family_comfort_v1",
        "review_collection": {
            "sort_order": "latest",
            "recent_reviews_collected_count": 3,
            "negative_reviews_collected_count": 3,
            "negative_reviews_collected_separately": True,
        },
        "reviews": [
            {
                "id": "recent-1",
                "sample_bucket": "recent",
                "is_recent": True,
                "specific": True,
                "text": "The room was quiet and comfortable.",
            },
            {
                "id": "recent-2",
                "sample_bucket": "recent",
                "is_recent": True,
                "specific": True,
                "text": "Bathroom was clean and hot water was stable.",
            },
            {
                "id": "recent-3",
                "sample_bucket": "recent",
                "is_recent": True,
                "specific": False,
                "text": "Good family stay.",
            },
            {
                "id": "negative-1",
                "sample_bucket": "negative",
                "is_recent": True,
                "specific": True,
                "text": "AC did not work during the night.",
            },
            {
                "id": "negative-2",
                "sample_bucket": "negative",
                "is_recent": True,
                "specific": True,
                "text": "Air conditioning broken again in the family room.",
            },
            {
                "id": "negative-3",
                "sample_bucket": "negative",
                "is_recent": False,
                "specific": False,
                "text": "Breakfast was ordinary and service was average.",
            },
        ],
    }


def test_deep_screen_requires_latest_sort_and_separate_negative_reviews():
    data = make_deep_screen_input()
    is_valid, issues = validate_deep_screen_input(data)

    assert is_valid, issues

    missing_latest = copy.deepcopy(data)
    missing_latest["review_collection"]["sort_order"] = "default"
    is_valid, issues = validate_deep_screen_input(missing_latest)
    assert not is_valid
    assert any("sort_order" in issue for issue in issues)

    missing_negative = copy.deepcopy(data)
    missing_negative["review_collection"]["negative_reviews_collected_count"] = 0
    missing_negative["review_collection"]["negative_reviews_collected_separately"] = False
    missing_negative["reviews"] = [
        review for review in missing_negative["reviews"] if review["sample_bucket"] == "recent"
    ]
    is_valid, issues = validate_deep_screen_input(missing_negative)
    assert not is_valid
    assert any("negative" in issue for issue in issues)


def test_recent_specific_repeated_problem_has_more_weight_than_old_vague_problem():
    recent_specific = make_deep_screen_input()
    old_vague = copy.deepcopy(recent_specific)
    for review in old_vague["reviews"]:
        if "conditioning" in review["text"].lower() or "AC did" in review["text"]:
            review["is_recent"] = False
            review["specific"] = False

    recent_report = analyze_deep_screen(recent_specific)
    old_report = analyze_deep_screen(old_vague)

    assert recent_report["overall_risk_score"] > old_report["overall_risk_score"]
    assert recent_report["category_scores"]["air_conditioning"]["repeat_multiplier"] > 1
    assert recent_report["repeated_recent_specific_issues"] == [
        {"category": "air_conditioning", "guest_reports": 2}
    ]
    assert old_report["repeated_recent_specific_issues"] == []


def test_deep_screen_uses_family_comfort_profile_and_reports_collection_counts():
    report = analyze_deep_screen(make_deep_screen_input())

    assert report["preference_profile_used"] == "hotel_family_comfort_v1"
    assert report["evidence_status"] == "sufficient_evidence"
    assert report["review_collection"]["sort_order"] == "latest"
    assert report["review_collection"]["recent_reviews_collected_count"] == 3
    assert report["review_collection"]["negative_reviews_collected_count"] == 3
    assert report["pre_booking_checklist"]


def test_price_alone_is_not_material_but_hidden_fee_is():
    price_only = make_deep_screen_input()
    price_only["reviews"][3]["text"] = "The price was expensive."
    price_only["reviews"][4]["text"] = "The price was higher than usual."
    hidden_fee = copy.deepcopy(price_only)
    hidden_fee["reviews"][3]["text"] = "An unexpected fee was added at check-in."
    hidden_fee["reviews"][4]["text"] = "The room price included a hidden fee."

    price_report = analyze_deep_screen(price_only)
    fee_report = analyze_deep_screen(hidden_fee)

    assert "hidden_fees" not in price_report["category_scores"]
    assert fee_report["category_scores"]["hidden_fees"]["recent_specific_count"] == 2
    assert fee_report["overall_risk_score"] > price_report["overall_risk_score"]


def test_deep_screen_rejects_count_mismatch():
    data = make_deep_screen_input()
    data["review_collection"]["recent_reviews_collected_count"] = 10

    with pytest.raises(ValueError, match="count does not match"):
        analyze_deep_screen(data)


def test_deep_screen_cli_writes_report(tmp_path):
    input_path = tmp_path / "deep-screen.json"
    output_path = tmp_path / "report.json"
    input_path.write_text(json.dumps(make_deep_screen_input()), encoding="utf-8")

    result = main(
        [
            "deep-screen",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )

    assert result == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["review_collection"]["sort_order"] == "latest"
    assert report["repeated_recent_specific_issues"]
