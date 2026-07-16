"""Review classification and scoring engine."""

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
            set(classification["categories"][category]["keywords_found"])
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
    
    # Apply traveler priorities to weights
    priorities = traveler_profile.get("priorities", {})
    adjusted_weights = {}
    for category, base_weight in weights.items():
        priority = priorities.get(category, 1.0)
        adjusted_weights[category] = base_weight * priority
    
    # Normalize weights
    total_weight = sum(adjusted_weights.values())
    if total_weight > 0:
        adjusted_weights = {k: v / total_weight for k, v in adjusted_weights.items()}
    
    # Calculate category scores (0-10 scale, higher = more risk)
    category_scores = {}
    total_issues = 0
    
    for category, data in classification.get("categories", {}).items():
        count = data.get("count", 0)
        total_issues += count
        
        # Base score: logarithmic scale to avoid extreme values
        if count == 0:
            score = 0.0
        else:
            import math
            score = min(10.0, 2.0 + 1.5 * math.log10(count + 1))
        
        # Adjust for recent issues (simple heuristic: all issues treated equally in v1)
        category_scores[category] = {
            "issue_count": count,
            "raw_score": round(score, 2),
            "weight": round(adjusted_weights.get(category, 0), 4),
        }
    
    # Calculate overall risk score (0-100, higher = more risk)
    if classification.get("total_reviews", 0) == 0:
        overall_score = 50.0  # Neutral when no data
    else:
        weighted_sum = sum(
            category_scores[cat]["raw_score"] * category_scores[cat]["weight"]
            for cat in category_scores
        )
        overall_score = min(100.0, weighted_sum * 10)
    
    # Determine recommendation
    if overall_score < 30:
        recommendation = "recommended"
        confidence = "high" if classification["analyzed_reviews"] >= 5 else "medium"
    elif overall_score < 50:
        recommendation = "acceptable_with_caveats"
        confidence = "medium"
    elif overall_score < 70:
        recommendation = "proceed_with_caution"
        confidence = "medium"
    else:
        recommendation = "not_recommended"
        confidence = "high" if total_issues >= 3 else "medium"
    
    # Generate pre-booking checklist
    checklist = []
    for category, data in category_scores.items():
        if data["raw_score"] > 3.0:
            desc = RISK_CATEGORIES.get(category, {}).get("description", category)
            checklist.append(f"Verify: {desc}")
    
    return {
        "overall_risk_score": round(overall_score, 1),
        "recommendation": recommendation,
        "confidence": confidence,
        "total_issues": total_issues,
        "category_scores": category_scores,
        "pre_booking_checklist": checklist,
        "rule_trace": {
            "weights_used": adjusted_weights,
            "traveler_priorities": priorities,
        },
    }
