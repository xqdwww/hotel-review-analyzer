# Hotel Review Analyzer

An explainable, configurable hotel review risk analyzer for traveler-specific decision support.

## v0.2.0 Highlights

- Preference-based Ctrip hotel screening with destination ranking through
  `rank-destination`.
- Ctrip overall rating is an entry signal, not the final judgment.
- A 20-30 hotel entry pool is reranked into a Top 10 candidate list using
  `hotel_family_comfort_v1`.
- Results preserve both `entry_rank` and `preference_rank`, and mark 2-3
  candidates for further review.
- The `deep-screen` command evaluates selected hotels using latest reviews and
  a separately collected negative/low-score review sample.
- Destination scan results are candidates only, not final PASS/REJECT
  decisions, and therefore contain no final risk score or confidence.

## Features

- **Offline Analysis**: No network dependencies
- **Explainable Results**: Clear evidence and rule traces
- **Configurable Profiles**: Family, business, general traveler modes
- **Ctrip Candidate Ranking**: Use ratings as an entry pool, then rerank by traveler fit
- **Evidence-Gated Deep Screen**: Require latest and separately collected low-score reviews
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

# Build a preference-reranked Ctrip destination Top 10
hotel-review-analyzer rank-destination --input candidates.json --output shortlist.json

# Deep-screen one selected hotel
hotel-review-analyzer deep-screen --input deep-screen.json --output report.json
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

An abridged JSON report looks like this:

```json
{
  "hotel": {"name": "Example Hotel", "location": "Downtown Area"},
  "risk_level": "low",
  "overall_risk_score": 16.6,
  "confidence": "low",
  "traveler_profile": {
    "trip_type": "general",
    "priorities": {"hygiene": 1.0, "noise": 1.0}
  },
  "risk_categories": {"noise": 1, "hygiene": 1, "hot_water": 1},
  "evidence_counts": {
    "total_reviews": 3,
    "analyzed_reviews": 3,
    "total_issues": 3
  },
  "evidence": [
    {"review_id": "r2", "category": "noise", "matched_keywords": ["traffic noise"]}
  ],
  "pre_booking_checklist": ["Verify: Noise and soundproofing issues"],
  "explainability": {
    "rule_trace": {"formula": "category review rate * normalized category weight"}
  },
  "limitations": ["Analysis based on text keyword matching only"]
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
- **facility**: Elevator, door-lock, network, or other facility stability issues
- **room_mismatch**: Room type or facility mismatch
- **location**: Location or transit description mismatch
- **hidden_fees**: Unexpected fee, deposit, or refund issues
- **service**: Specific staff or response problems

## Traveler Profiles

- **general**: Balanced priorities
- **family**: Higher weight on hygiene, quiet sleep, temperature stability
- **business**: Higher weight on location accuracy
- **hotel_family_comfort_v1**: Family comfort profile for Ctrip screening

An input `traveler_profile.priorities` object can override individual category
weights. Supported keys are the risk-category identifiers listed above plus
`hidden_fees` and `service`. Profile multipliers must be finite non-negative
numbers.

### `hotel_family_comfort_v1`

This profile uses three preference tiers:

- High: hygiene, quiet sleep, air conditioning, hot water, facility stability,
  and transport/location
- Medium: room size/comfort, decor age, and location truthfulness
- Low: ordinary breakfast, ordinary service, parking-process hassle, and price alone

Price becomes material only when it is tied to a room/facility mismatch, hidden
fee, arrival surcharge, or broken booking promise. Recent, specific issues
repeated by multiple guests carry more weight than old or vague comments.

## Ctrip Destination Scan

`rank-destination` accepts a local JSON candidate pool captured from a Ctrip
destination, city, commercial area, or attraction hotel list.

1. Sort the visible list by overall rating, positive-review-first, or rating
   descending.
2. Capture 20-30 high-rating hotels as the entry pool (default 25).
3. Include each hotel's name, URL, Ctrip rating, review count, price/range,
   location, class, family tags, recent-review summary, visible negative summary,
   and structured preference signals.
4. Rerank with `hotel_family_comfort_v1` and emit Top 10.

The Ctrip rating component is capped and is only an entry signal. The output
keeps both `entry_rank` and `preference_rank`, explains keep/downrank reasons,
and marks 2-3 hotels for deep screening. Candidate-stage output intentionally
contains no final hotel verdict, risk score, or confidence.

## Single-Hotel Deep Screen

`deep-screen` requires all of the following:

- `review_collection.sort_order` is `latest` (map UI labels such as latest
  reviews or recent stays to this value)
- a non-empty latest/recent sample
- a separately collected non-empty low-score/negative sample
- provenance on every review: `sample_bucket`, `is_recent`, and `specific`

Recent and specific evidence receives multipliers. A concrete issue reported by
multiple recent guests receives an additional repeat multiplier. Missing latest
sorting or a separate negative sample is a validation error, not low-risk evidence.

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
