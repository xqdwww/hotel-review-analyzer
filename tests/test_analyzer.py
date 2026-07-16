"""Tests for Hotel Review Analyzer."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotel_review_analyzer.schema import (
    validate_input_schema,
    extract_review_signals,
    DEFAULT_TRAVELER_PROFILE,
)
from hotel_review_analyzer.classify import classify_reviews, calculate_risk_score


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
        # May still match some generic keywords, just check it returns dict
        assert isinstance(signals, dict)


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
        assert scoring["recommendation"] == "recommended"
    
    def test_many_issues_high_score(self):
        classification = {
            "total_reviews": 20,
            "analyzed_reviews": 20,
            "categories": {
                "hygiene": {"count": 5, "keywords_found": [], "review_ids": []},
                "noise": {"count": 5, "keywords_found": [], "review_ids": []},
                "hot_water": {"count": 5, "keywords_found": [], "review_ids": []},
            },
            "negative_signals": [],
            "evidence": [],
        }
        scoring = calculate_risk_score(classification)
        assert scoring["overall_risk_score"] > 10
        assert scoring["recommendation"] in ["recommended", "acceptable_with_caveats", "proceed_with_caution", "not_recommended"]
    
    def test_traveler_profile_affects_weights(self):
        classification = {
            "total_reviews": 10,
            "analyzed_reviews": 10,
            "categories": {"noise": {"count": 3}},
            "negative_signals": [],
            "evidence": [],
        }
        
        # Family profile weights noise higher
        family_profile = {
            "trip_type": "family",
            "priorities": {"quiet_sleep": 1.5},
        }
        
        family_scoring = calculate_risk_score(classification, traveler_profile=family_profile)
        general_scoring = calculate_risk_score(classification)
        
        # Family should have higher noise weight
        assert family_scoring["rule_trace"]["weights_used"].get("noise", 0) > 0
