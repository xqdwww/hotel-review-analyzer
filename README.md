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
# From an unpacked source checkout
python -m pip install .
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

Existing output files are not overwritten unless `--force` is supplied.

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
      "noise": 1.0
    }
  }
}
```

### Output Format

```json
{
  "hotel": {"name": "Example Hotel", "location": "City Center"},
  "risk_level": "moderate",
  "overall_risk_score": 35.0,
  "confidence": "medium",
  "risk_categories": {"noise": 1, "hygiene": 0},
  "pre_booking_checklist": ["Verify: Noise and soundproofing issues"],
  "explainability": {
    "rule_trace": {...}
  }
}
```

The example names and review text in this repository are synthetic. The
project contains no platform account, cookie, API client, crawler, or bundled
real-world hotel review dataset. Users supply review text in a local JSON file.

## Risk Categories

- **hygiene**: Cleanliness and hygiene issues
- **noise**: Noise and soundproofing issues  
- **air_conditioning**: Air conditioning problems
- **hot_water**: Hot water stability issues
- **room_mismatch**: Room type or facility mismatch
- **location**: Location or transit description mismatch
- **hidden_fees**: Unexpected fee, deposit, or refund issues
- **service**: Specific staff or response problems

## Traveler Profiles

- **general**: Balanced priorities
- **family**: Higher weight on hygiene, quiet sleep, temperature stability
- **business**: Higher weight on location accuracy

An input `traveler_profile.priorities` object can override individual category
weights. Supported keys are the risk-category identifiers listed above plus
`hidden_fees` and `service`. Profile multipliers must be finite non-negative
numbers.

## How Scoring Works

For each category, the analyzer computes the fraction of analyzed reviews that
contain one or more configured risk phrases. It multiplies that review rate by
the normalized category weight and sums the contributions into a 0-100 risk
score. The same input and profile always produce the same classification and
score; the report timestamp is informational.

Risk levels are `low`, `moderate`, `high`, and `very_high`. With no analyzable
reviews the result is `insufficient_data` and no numeric score is emitted.
These labels describe signals in the supplied sample, not the actual quality,
authenticity, or safety of a hotel.

## Non-Goals

This tool is NOT:
- A web crawler
- A booking platform integration
- A booking recommendation system
- A hotel authenticity or fraud detector
- An official partner of any hotel platform
- Guaranteed to predict actual hotel quality

This is an auxiliary decision-support tool. Keyword matches can miss context or
produce false positives, and a review sample may be incomplete or
unrepresentative. Inspect the evidence excerpts and source reviews before making
a booking decision.

## License

MIT
