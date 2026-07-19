"""Input and output schemas for Hotel Review Analyzer."""

import math
from typing import Any, Dict, List


# Default weights for hotel scoring
DEFAULT_HOTEL_WEIGHTS = {
    "hygiene": 20,
    "noise": 20,
    "air_conditioning": 10,
    "hot_water": 10,
    "facility": 10,
    "room_mismatch": 12,
    "location": 8,
    "hidden_fees": 7,
    "service": 3,
}

# Risk category definitions
RISK_CATEGORIES = {
    "hygiene": {
        "description": "Cleanliness and hygiene issues",
        "keywords": ["脏", "不干净", "有异味", "霉味", "虫子", "污渍", "dirty", "filthy", "unclean", "not clean", "mold", "mould", "bedbug", "cockroach", "hair on"],
    },
    "noise": {
        "description": "Noise and soundproofing issues",
        "keywords": ["太吵", "很吵", "噪音", "隔音差", "隔音不好", "施工噪音", "noisy", "traffic noise", "construction noise", "poor soundproofing"],
    },
    "air_conditioning": {
        "description": "Air conditioning problems",
        "keywords": ["空调不冷", "空调不制冷", "空调坏", "空调无法控制", "air conditioning broken", "ac broken", "ac did not work", "air conditioning did not work"],
    },
    "hot_water": {
        "description": "Hot water stability issues",
        "keywords": ["热水不稳定", "没有热水", "忽冷忽热", "no hot water", "hot water was unstable", "hot water unstable"],
    },
    "facility": {
        "description": "Facility stability issues",
        "keywords": [
            "电梯坏",
            "电梯故障",
            "门锁坏",
            "网络不稳定",
            "设施老旧损坏",
            "lift broken",
            "elevator broken",
            "door lock broken",
            "unstable wifi",
            "broken facility",
        ],
    },
    "room_mismatch": {
        "description": "Room type or facility mismatch",
        "keywords": ["房型不符", "房间比描述小", "没有窗户", "设施损坏", "room did not match", "smaller than advertised", "no window", "broken facilities"],
    },
    "location": {
        "description": "Location or transit description mismatch",
        "keywords": ["位置描述不符", "离地铁很远", "距离不实", "交通不便", "location was misleading", "far from the subway", "distance was inaccurate"],
    },
    "hidden_fees": {
        "description": "Hidden or unexpected fees",
        "keywords": ["额外收费", "隐形收费", "未说明押金", "无法退款", "unexpected fee", "hidden fee", "undisclosed deposit", "refund refused"],
    },
    "service": {
        "description": "Service quality issues",
        "keywords": ["服务态度差", "前台态度差", "响应慢", "无人处理", "rude staff", "unhelpful staff", "slow response"],
    },
}

# Default traveler profile (neutral)
DEFAULT_TRAVELER_PROFILE = {
    "trip_type": "general",
    "priorities": {
        "hygiene": 1.0,
        "noise": 1.0,
        "air_conditioning": 1.0,
        "hot_water": 1.0,
        "facility": 1.0,
        "room_mismatch": 1.0,
        "location": 1.0,
        "hidden_fees": 1.0,
        "service": 1.0,
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

    if not isinstance(data, dict):
        return False, ["Input root must be an object"]
    
    # Required fields
    if "hotel" not in data:
        issues.append("Missing required field: hotel")
    elif not isinstance(data["hotel"], dict):
        issues.append("'hotel' must be an object")
    elif not isinstance(data["hotel"].get("name"), str) or not data["hotel"]["name"].strip():
        issues.append("'hotel.name' must be a non-empty string")
    
    if "reviews" not in data:
        issues.append("Missing required field: reviews")
    elif not isinstance(data["reviews"], list):
        issues.append("'reviews' must be an array")
    
    # Optional fields with validation
    if "traveler_profile" in data:
        profile = data["traveler_profile"]
        if not isinstance(profile, dict):
            issues.append("'traveler_profile' must be an object")
        elif "priorities" in profile:
            priorities = profile["priorities"]
            if not isinstance(priorities, dict):
                issues.append("'traveler_profile.priorities' must be an object")
            else:
                for category, value in priorities.items():
                    if category not in RISK_CATEGORIES:
                        issues.append(f"Unknown traveler priority category: {category}")
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                        issues.append(f"traveler_profile.priorities.{category} must be a finite non-negative number")
    
    # Validate reviews
    if "reviews" in data and isinstance(data["reviews"], list):
        for idx, review in enumerate(data["reviews"]):
            if not isinstance(review, dict):
                issues.append(f"reviews[{idx}] must be an object")
                continue
            if not isinstance(review.get("text"), str) or not review["text"].strip():
                issues.append(f"reviews[{idx}].text must be a non-empty string")
            if "rating" in review:
                try:
                    rating = float(review["rating"])
                    if not math.isfinite(rating) or not (0 <= rating <= 5):
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
            signals[category] = list(dict.fromkeys(matches))
    
    return signals
