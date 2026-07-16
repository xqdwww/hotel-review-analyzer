# Contributing

Use synthetic or fully sanitized review examples. Never submit platform
credentials, cookies, account identifiers, or real review text without the
reviewer's explicit permission.

Install development dependencies and run the release gates:

```bash
python -m pip install -e ".[dev]"
ruff check src tests
python -m compileall -q src tests
python -m pytest
```

Changes to scoring weights, phrases, or thresholds must include focused tests
that explain the intended risk interpretation. Do not turn risk signals into
hotel-quality claims or booking guarantees.
