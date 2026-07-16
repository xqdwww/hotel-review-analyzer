"""Command-line interface for Hotel Review Analyzer."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .schema import validate_input_schema, DEFAULT_TRAVELER_PROFILE
from .classify import classify_reviews, calculate_risk_score
from .reporting import generate_json_report, generate_markdown_report


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="hotel-review-analyzer",
        description="Analyze hotel reviews and generate risk assessment reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis
  hotel-review-analyzer analyze --input reviews.json --output report.json
  
  # Generate Markdown report
  hotel-review-analyzer analyze --input reviews.json --format markdown --output report.md
  
  # With custom traveler profile
  hotel-review-analyzer analyze --input reviews.json --profile family

Input format (JSON):
{
  "hotel": {"name": "Example Hotel", "location": "City"},
  "reviews": [
    {"id": "r1", "text": "The room was clean but noisy at night.", "rating": 3}
  ],
  "traveler_profile": {
    "trip_type": "family",
    "priorities": {"hygiene": 1.0, "quiet_sleep": 1.0}
  }
}
""",
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze hotel reviews",
    )
    analyze_parser.add_argument(
        "--input", "-i",
        required=True,
        type=Path,
        help="Input JSON file with hotel and reviews",
    )
    analyze_parser.add_argument(
        "--output", "-o",
        required=True,
        type=Path,
        help="Output file path",
    )
    analyze_parser.add_argument(
        "--format", "-f",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    analyze_parser.add_argument(
        "--profile", "-p",
        choices=["general", "family", "business"],
        default="general",
        help="Traveler profile (default: general)",
    )
    
    return parser


def get_traveler_profile(profile_name: str) -> dict:
    """Get traveler profile by name."""
    profiles = {
        "general": DEFAULT_TRAVELER_PROFILE,
        "family": {
            "trip_type": "family",
            "priorities": {
                "hygiene": 1.2,
                "quiet_sleep": 1.3,
                "temperature_stability": 1.2,
                "location_accuracy": 0.9,
                "value_for_money": 0.8,
            },
        },
        "business": {
            "trip_type": "business",
            "priorities": {
                "hygiene": 1.0,
                "quiet_sleep": 1.1,
                "location_accuracy": 1.3,
                "value_for_money": 0.6,
            },
        },
    }
    return profiles.get(profile_name, DEFAULT_TRAVELER_PROFILE).copy()


def cmd_analyze(args: argparse.Namespace) -> int:
    """Execute analyze command."""
    # Load input
    try:
        with args.input.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        return 1
    
    # Validate input
    is_valid, issues = validate_input_schema(data)
    if not is_valid:
        print("Input validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    
    # Get traveler profile
    traveler_profile = get_traveler_profile(args.profile)
    
    # Extract data
    hotel_info = data.get("hotel", {})
    reviews = data.get("reviews", [])
    
    # Classify reviews
    classification = classify_reviews(reviews)
    
    # Calculate risk score
    scoring = calculate_risk_score(
        classification,
        traveler_profile=traveler_profile,
    )
    
    # Generate report
    json_report = generate_json_report(
        hotel_info,
        classification,
        scoring,
        traveler_profile,
    )
    
    # Write output
    try:
        if args.format == "markdown":
            content = generate_markdown_report(json_report)
            args.output.write_text(content, encoding="utf-8")
        else:
            content = json.dumps(json_report, indent=2, ensure_ascii=False)
            args.output.write_text(content, encoding="utf-8")
        
        print(f"Report written to: {args.output}")
        print(f"Recommendation: {scoring['recommendation']}")
        print(f"Risk Score: {scoring['overall_risk_score']}/100")
        return 0
        
    except IOError as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        return 1


def main(argv: Optional[list] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 0
    
    if args.command == "analyze":
        return cmd_analyze(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
