"""Input and output schemas for Hotel Review Analyzer."""

from typing import Any, Dict, List, Optional
from datetime import datetime


# Default weights for hotel scoring
DEFAULT_HOTEL_WEIGHTS = {
    "hygiene": 25,
    "noise": 25,
    "room_accuracy": 20,
    "location_truthfulness": 15,
    "recent_stability": 10,
    "policy_clarity": 5,
}

# Risk category definitions
RISK_CATEGORIES = {
    "hygiene": {
        "description": "Cleanliness and hygiene issues",
        "keywords": ["脏", "不干净", "有异味", "霉味", "虫子", "头发", "灰尘", "污渍"],
    },
    "noise": {
        "description": "Noise and soundproofing issues",
        "keywords": ["吵", " noisy", "隔音", "街道", "施工", "凌晨"],
    },
    "air_conditioning": {
        "description": "Air conditioning problems",
        "keywords": ["空调", "不冷", "不制冷", "无法控制", "中央空调"],
    },
    "hot_water": {
        "description": "Hot water stability issues",
        "keywords": ["热水", "不稳定", "忽冷忽热", "冷水", "洗澡"],
    },
    "room_mismatch": {
        "description": "Room type or facility mismatch",
        "keywords": ["房型不符", "面积小", "窗户", "视野", "设施损坏"],
    },
    "location": {
        "description": "Location or transit description mismatch",
        "keywords": ["位置", "地铁", "距离", "步行", "交通"],
    },
    "hidden_fees": {
        "description": "Hidden or unexpected fees",
        "keywords": ["额外收费", "押金", "押金", "取消", "退订"],
    },
    "service": {
        "description": "Service quality issues",
        "keywords": ["服务", "态度", "前台", "响应慢"],
    },
}

# Default traveler profile (neutral)
DEFAULT_TRAVELER_PROFILE = {
    "trip_type": "general",
    "priorities": {
        "hygiene": 1.0,
        "quiet_sleep": 1.0,
        "temperature_stability": 0.8,
        "location_accuracy": 0.8,
        "value_for_money": 0.7,
    },
    "tolerances": {
        "minor_hygiene": 3,
        "minor_noise": 2,
        "long_walking_distance": 3,
        "ordinary_breakfast": 5,
    },
}


def validate_input_schema(data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Validate input JSON schema.
    
    Args:
        data: Input data dictionary
        
    Returns:
        (is_valid, list_of_issues)
    """
    issues = []
    
    # Required fields
    if "hotel" not in data:
        issues.append("Missing required field: hotel")
    elif not isinstance(data["hotel"], dict):
        issues.append("'hotel' must be an object")
    elif "name" not in data["hotel"]:
        issues.append("Missing required field: hotel.name")
    
    if "reviews" not in data:
        issues.append("Missing required field: reviews")
    elif not isinstance(data["reviews"], list):
        issues.append("'reviews' must be an array")
    
    # Optional fields with validation
    if "traveler_profile" in data:
        profile = data["traveler_profile"]
        if not isinstance(profile, dict):
            issues.append("'traveler_profile' must be an object")
        elif "priorities" in profile and not isinstance(profile["priorities"], dict):
            issues.append("'traveler_profile.priorities' must be an object")
    
    # Validate reviews
    if "reviews" in data and isinstance(data["reviews"], list):
        for idx, review in enumerate(data["reviews"]):
            if not isinstance(review, dict):
                issues.append(f"reviews[{idx}] must be an object")
                continue
            if "text" in review and not isinstance(review["text"], str):
                issues.append(f"reviews[{idx}].text must be a string")
            if "rating" in review:
                try:
                    rating = float(review["rating"])
                    if not (0 <= rating <= 5):
                        issues.append(f"reviews[{idx}].rating must be between 0 and 5")
                except (TypeError, ValueError):
                    issues.append(f"reviews[{idx}].rating must be a number")
    
    return len(issues) == 0, issues


def normalize_review_text(text: str) -> str:
    """Normalize review text for consistent analysis."""
    return text.strip().lower()


def extract_review_signals(text: str) -> Dict[str, List[str]]:
    """Extract risk signals from review text.
    
    Args:
        text: Normalized review text
        
    Returns:
        Dictionary mapping risk categories to matching keywords
    """
    signals = {}
    text_lower = text.lower()
    
    for category, info in RISK_CATEGORIES.items():
        matches = []
        for keyword in info["keywords"]:
            if keyword.lower() in text_lower:
                matches.append(keyword)
        if matches:
            signals[category] = list(set(matches))  # Deduplicate
    
    return signals
