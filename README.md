# Hotel Review Analyzer

An explainable, configurable hotel review risk analyzer for traveler-specific decision support.

## Features

- **Offline Analysis**: No network dependencies
- **Explainable Results**: Clear evidence and rule traces
- **Configurable Profiles**: Family, business, general traveler modes
- **Multi-format Output**: JSON and Markdown reports
- **No External APIs**: Pure Python standard library

## Installation

```bash
pip install hotel-review-analyzer
```

## Usage

### CLI

```bash
# Basic analysis
hotel-review-analyzer analyze --input reviews.json --output report.json

# Markdown output
hotel-review-analyzer analyze --input reviews.json --format markdown --output report.md

# With traveler profile
hotel-review-analyzer analyze --input reviews.json --profile family --output report.json
```

### Input Format

```json
{
  "hotel": {
    "name": "Example Hotel",
    "location": "City Center"
  },
  "reviews": [
    {
      "id": "r1",
      "rating": 3,
      "text": "The room was clean but traffic noise was noticeable at night."
    }
  ],
  "traveler_profile": {
    "trip_type": "family",
    "priorities": {
      "hygiene": 1.0,
      "quiet_sleep": 1.0
    }
  }
}
```

### Output Format

```json
{
  "hotel": {"name": "Example Hotel", "location": "City Center"},
  "recommendation": "acceptable_with_caveats",
  "recommendation_score": 65,
  "confidence": "medium",
  "risk_categories": {"noise": 1, "hygiene": 0},
  "pre_booking_checklist": ["Verify: Noise and soundproofing issues"],
  "explainability": {
    "rule_trace": {...}
  }
}
```

## Risk Categories

- **hygiene**: Cleanliness and hygiene issues
- **noise**: Noise and soundproofing issues  
- **air_conditioning**: Air conditioning problems
- **hot_water**: Hot water stability issues
- **room_mismatch**: Room type or facility mismatch
- **location**: Location or transit description mismatch

## Traveler Profiles

- **general**: Balanced priorities
- **family**: Higher weight on hygiene, quiet sleep, temperature stability
- **business**: Higher weight on location accuracy

## Non-Goals

This tool is NOT:
- A web crawler
- A booking platform integration
- An official partner of any hotel platform
- Guaranteed to predict actual hotel quality

## License

MIT
