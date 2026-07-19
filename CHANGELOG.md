# Changelog

## [0.2.0] - 2026-07-19

### Added

- Preference-based Ctrip hotel screening through the `rank-destination` CLI.
- The `hotel_family_comfort_v1` profile for reranking a 20-30 hotel entry pool
  into a Top 10 candidate list.
- Separate `entry_rank` and `preference_rank` fields, with 2-3 candidates
  marked for deep screening.
- The `deep-screen` CLI workflow for latest reviews and a separately collected
  negative/low-score review sample.

### Clarified

- Ctrip overall rating is an entry signal, not the final judgment.
- Destination scan output contains candidates only, not final PASS/REJECT
  decisions, risk scores, or confidence.

## [0.1.0] - 2026-07-16

### Added

- Initial offline hotel-review risk analyzer.
- Explainable category evidence and configurable traveler profiles.
- JSON and Markdown reports with explicit limitations.
