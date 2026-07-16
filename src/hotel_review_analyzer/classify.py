"""Review classification and scoring engine."""

import math
from typing import Any, Dict, List
from .schema import (
    DEFAULT_HOTEL_WEIGHTS,
    DEFAULT_TRAVELER_PROFILE,
    RISK_CATEGORIES,
    extract_review_signals,
    normalize_review_text,
)


def classify_reviews(reviews: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Classify reviews into risk categories.
    
    Args:
        reviews: List of review dictionaries with 'text' field
        
    Returns:
        Dictionary with risk category analysis
    """
    classification = {
        "total_reviews": len(reviews),
        "analyzed_reviews": 0,
        "categories": {},
        "positive_signals": [],
        "negative_signals": [],
        "evidence": [],
    }
    
    for review in reviews:
        if not isinstance(review, dict) or "text" not in review:
            continue
        
        classification["analyzed_reviews"] += 1
        text = review.get("text", "")
        normalized = normalize_review_text(text)
        
        signals = extract_review_signals(normalized)
        
        for category, matches in signals.items():
            if category not in classification["categories"]:
                classification["categories"][category] = {
                    "count": 0,
                    "keywords_found": [],
                    "review_ids": [],
                }
            
            classification["categories"][category]["count"] += 1
            classification["categories"][category]["keywords_found"].extend(matches)
            
            review_id = review.get("id", f"review_{classification['analyzed_reviews']}")
            classification["categories"][category]["review_ids"].append(review_id)
            
            # Record evidence
            classification["evidence"].append({
                "review_id": review_id,
                "category": category,
                "matched_keywords": matches,
                "text_snippet": text[:100] + "..." if len(text) > 100 else text,
            })
            
            # Categorize as negative signal
            classification["negative_signals"].append({
                "category": category,
                "review_id": review_id,
            })
    
    # Deduplicate keywords
    for category in classification["categories"]:
        classification["categories"][category]["keywords_found"] = list(
            dict.fromkeys(classification["categories"][category]["keywords_found"])
        )
    
    return classification


def calculate_risk_score(
    classification: Dict[str, Dict[str, Any]],
    weights: Dict[str, float] = None,
    traveler_profile: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Calculate overall risk score from classification.
    
    Args:
        classification: Output from classify_reviews
        weights: Category weights (defaults to DEFAULT_HOTEL_WEIGHTS)
        traveler_profile: User traveler profile
        
    Returns:
        Dictionary with scores and analysis
    """
    if weights is None:
        weights = DEFAULT_HOTEL_WEIGHTS.copy()
    
    if traveler_profile is None:
        traveler_profile = DEFAULT_TRAVELER_PROFILE.copy()
    
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
        for value in weights.values()
    ):
        raise ValueError("weights must contain finite non-negative numbers")

    # Apply traveler priorities to weights. Priority names use the same category
    # identifiers as the classifier so every documented profile has an effect.
    priorities = traveler_profile.get("priorities", {})
    adjusted_weights = {}
    for category, base_weight in weights.items():
        priority = priorities.get(category, 1.0)
        if isinstance(priority, bool) or not isinstance(priority, (int, float)) or not math.isfinite(priority) or priority < 0:
            raise ValueError(f"invalid traveler priority for {category}")
        adjusted_weights[category] = base_weight * priority
    
    # Normalize weights
    total_weight = sum(adjusted_weights.values())
    if total_weight > 0:
        adjusted_weights = {k: v / total_weight for k, v in adjusted_weights.items()}
    else:
        raise ValueError("at least one adjusted category weight must be positive")
    
    # Calculate category scores from prevalence (0-10, higher = more risk).
    # A category mentioned by 2 of 10 analyzed reviews receives raw score 2.0.
    category_scores = {}
    total_issues = 0
    analyzed_reviews = classification.get("analyzed_reviews", 0)
    
    for category, data in classification.get("categories", {}).items():
        count = data.get("count", 0)
        total_issues += count
        
        review_rate = min(1.0, count / analyzed_reviews) if analyzed_reviews else 0.0
        score = review_rate * 10.0

        category_scores[category] = {
            "issue_count": count,
            "review_rate": round(review_rate, 4),
            "raw_score": round(score, 2),
            "weight": round(adjusted_weights.get(category, 0), 4),
        }
    
    # Calculate overall risk score (0-100, higher = more risk)
    if analyzed_reviews == 0:
        overall_score = None
    else:
        weighted_sum = sum(
            category_scores[cat]["raw_score"] * category_scores[cat]["weight"]
            for cat in category_scores
        )
        overall_score = min(100.0, weighted_sum * 10)
    
    # Determine recommendation
    if overall_score is None:
        risk_level = "insufficient_data"
        confidence = "low"
    elif overall_score < 20:
        risk_level = "low"
        confidence = "high" if analyzed_reviews >= 20 else "medium" if analyzed_reviews >= 5 else "low"
    elif overall_score < 40:
        risk_level = "moderate"
        confidence = "high" if analyzed_reviews >= 20 else "medium" if analyzed_reviews >= 5 else "low"
    elif overall_score < 70:
        risk_level = "high"
        confidence = "high" if analyzed_reviews >= 20 else "medium" if analyzed_reviews >= 5 else "low"
    else:
        risk_level = "very_high"
        confidence = "high" if analyzed_reviews >= 20 else "medium" if analyzed_reviews >= 5 else "low"
    
    # Generate pre-booking checklist
    checklist = []
    for category, data in category_scores.items():
        if data["raw_score"] > 3.0:
            desc = RISK_CATEGORIES.get(category, {}).get("description", category)
            checklist.append(f"Verify: {desc}")
    
    return {
        "overall_risk_score": round(overall_score, 1) if overall_score is not None else None,
        "risk_level": risk_level,
        "confidence": confidence,
        "total_issues": total_issues,
        "category_scores": category_scores,
        "pre_booking_checklist": checklist,
        "rule_trace": {
            "formula": "category review rate * normalized category weight",
            "weights_used": adjusted_weights,
            "traveler_priorities": priorities,
        },
    }
