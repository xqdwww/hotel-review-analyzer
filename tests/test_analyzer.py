"""Tests for Hotel Review Analyzer."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotel_review_analyzer.schema import (
    validate_input_schema,
    extract_review_signals,
)
from hotel_review_analyzer.classify import classify_reviews, calculate_risk_score
from hotel_review_analyzer.cli import get_traveler_profile, main, merge_traveler_profile


class TestInputValidation:
    """Test input schema validation."""
    
    def test_valid_input(self):
        data = {
            "hotel": {"name": "Test Hotel"},
            "reviews": [{"text": "Good hotel"}],
        }
        is_valid, issues = validate_input_schema(data)
        assert is_valid
    
    def test_missing_hotel(self):
        data = {"reviews": []}
        is_valid, issues = validate_input_schema(data)
        assert not is_valid
        assert any("hotel" in issue for issue in issues)
    
    def test_missing_reviews(self):
        data = {"hotel": {"name": "Test"}}
        is_valid, issues = validate_input_schema(data)
        assert not is_valid
    
    def test_empty_reviews(self):
        data = {"hotel": {"name": "Test"}, "reviews": []}
        is_valid, issues = validate_input_schema(data)
        assert is_valid  # Empty reviews is valid

    def test_review_text_is_required(self):
        is_valid, issues = validate_input_schema({"hotel": {"name": "Test"}, "reviews": [{}]})
        assert not is_valid
        assert any("text" in issue for issue in issues)

    def test_unknown_profile_priority_is_rejected(self):
        is_valid, issues = validate_input_schema({
            "hotel": {"name": "Test"},
            "reviews": [],
            "traveler_profile": {"priorities": {"quiet_sleep": 2}},
        })
        assert not is_valid
        assert any("Unknown" in issue for issue in issues)


class TestSignalExtraction:
    """Test keyword-based signal extraction."""
    
    def test_hygiene_keywords(self):
        signals = extract_review_signals("房间很脏，有异味和虫子")
        assert "hygiene" in signals
    
    def test_noise_keywords(self):
        signals = extract_review_signals("太吵了，隔音不好")
        assert "noise" in signals
    
    def test_no_signals(self):
        signals = extract_review_signals("Everything was perfect")
        assert signals == {}

    def test_positive_mentions_are_not_risk_signals(self):
        signals = extract_review_signals("房间不吵，空调很好，热水充足，前台服务热情")
        assert signals == {}

    def test_english_negative_signals(self):
        signals = extract_review_signals("The room was filthy, noisy, and had no hot water")
        assert set(signals) == {"hygiene", "noise", "hot_water"}


class TestClassification:
    """Test review classification."""
    
    def test_empty_reviews(self):
        result = classify_reviews([])
        assert result["total_reviews"] == 0
        assert result["analyzed_reviews"] == 0
    
    def test_single_review(self):
        reviews = [{"text": "Room was clean"}]
        result = classify_reviews(reviews)
        assert result["total_reviews"] == 1
        assert result["analyzed_reviews"] == 1
    
    def test_multiple_categories(self):
        reviews = [
            {"text": "脏，不干净"},
            {"text": "太吵了"},
        ]
        result = classify_reviews(reviews)
        categories = result["categories"]
        assert "hygiene" in categories
        assert "noise" in categories


class TestRiskScoring:
    """Test risk score calculation."""
    
    def test_no_issues_low_score(self):
        classification = {
            "total_reviews": 10,
            "analyzed_reviews": 10,
            "categories": {},
            "positive_signals": [],
            "negative_signals": [],
            "evidence": [],
        }
        scoring = calculate_risk_score(classification)
        assert scoring["overall_risk_score"] < 30
        assert scoring["risk_level"] == "low"

    def test_no_reviews_is_insufficient_data(self):
        scoring = calculate_risk_score({"total_reviews": 0, "analyzed_reviews": 0, "categories": {}})
        assert scoring["overall_risk_score"] is None
        assert scoring["risk_level"] == "insufficient_data"
        assert scoring["confidence"] == "low"
    
    def test_many_issues_high_score(self):
        classification = {
            "total_reviews": 20,
            "analyzed_reviews": 20,
            "categories": {
                "hygiene": {"count": 20, "keywords_found": [], "review_ids": []},
                "noise": {"count": 20, "keywords_found": [], "review_ids": []},
                "hot_water": {"count": 20, "keywords_found": [], "review_ids": []},
            },
            "negative_signals": [],
            "evidence": [],
        }
        scoring = calculate_risk_score(classification)
        assert scoring["overall_risk_score"] == 50
        assert scoring["risk_level"] == "high"
    
    def test_traveler_profile_affects_weights(self):
        classification = {
            "total_reviews": 10,
            "analyzed_reviews": 10,
            "categories": {"noise": {"count": 3}},
            "negative_signals": [],
            "evidence": [],
        }
        
        # Family profile weights noise higher
        family_scoring = calculate_risk_score(classification, traveler_profile=get_traveler_profile("family"))
        general_scoring = calculate_risk_score(classification, traveler_profile=get_traveler_profile("general"))

        assert family_scoring["rule_trace"]["weights_used"]["noise"] > general_scoring["rule_trace"]["weights_used"]["noise"]
        assert family_scoring["overall_risk_score"] > general_scoring["overall_risk_score"]

    def test_scoring_is_deterministic(self):
        classification = classify_reviews([{"id": "r1", "text": "太吵，房间很脏"}])
        assert calculate_risk_score(classification) == calculate_risk_score(classification)


class TestProfilesAndCLI:
    def test_custom_profile_merges_supported_priorities(self):
        merged = merge_traveler_profile(
            get_traveler_profile("general"),
            {"trip_type": "custom", "priorities": {"noise": 2.0}},
        )
        assert merged["trip_type"] == "custom"
        assert merged["priorities"]["noise"] == 2.0
        assert "hygiene" in merged["priorities"]

    def test_sample_fixture_cli_reports_detected_risk(self, tmp_path):
        fixture = Path(__file__).parent / "fixtures" / "sample_hotel.json"
        output = tmp_path / "report.json"

        result = main(["analyze", "--input", str(fixture), "--output", str(output)])

        assert result == 0
        report = json.loads(output.read_text())
        assert report["overall_risk_score"] > 0
        assert report["risk_level"] in {"low", "moderate", "high", "very_high"}
        assert "recommendation" not in report
        assert report["evidence"]
        assert report["traveler_profile"]["trip_type"] == "general"
        assert output.stat().st_mode & 0o777 == 0o600

    def test_markdown_cli_smoke(self, tmp_path):
        fixture = Path(__file__).parent / "fixtures" / "sample_hotel.json"
        output = tmp_path / "report.md"

        result = main(["analyze", "--input", str(fixture), "--output", str(output), "--format", "markdown"])

        assert result == 0
        markdown = output.read_text()
        assert "## Risk Assessment" in markdown
        assert "## Limitations" in markdown
        assert "Recommendation" not in markdown

    def test_output_overwrite_requires_force(self, tmp_path):
        fixture = Path(__file__).parent / "fixtures" / "sample_hotel.json"
        output = tmp_path / "report.json"
        output.write_text("keep")

        assert main(["analyze", "--input", str(fixture), "--output", str(output)]) == 1
        assert output.read_text() == "keep"
        assert main(["analyze", "--input", str(fixture), "--output", str(output), "--force"]) == 0

    def test_output_symlink_is_refused_even_with_force(self, tmp_path):
        fixture = Path(__file__).parent / "fixtures" / "sample_hotel.json"
        protected = tmp_path / "protected.json"
        output = tmp_path / "report.json"
        protected.write_text("protected")
        output.symlink_to(protected)

        result = main(["analyze", "--input", str(fixture), "--output", str(output), "--force"])

        assert result == 1
        assert output.is_symlink()
        assert protected.read_text() == "protected"
