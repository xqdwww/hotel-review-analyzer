"""Command-line interface for Hotel Review Analyzer."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from . import __version__
from .schema import validate_input_schema, DEFAULT_TRAVELER_PROFILE
from .classify import classify_reviews, calculate_risk_score
from .deep_screen import analyze_deep_screen
from .destination import rank_destination_candidates
from .profiles import get_preference_profile
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

  # Rerank a Ctrip destination candidate pool
  hotel-review-analyzer rank-destination --input candidates.json --output shortlist.json

  # Deep-screen one selected hotel
  hotel-review-analyzer deep-screen --input deep-screen.json --output report.json

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
        choices=["general", "family", "business", "hotel_family_comfort_v1"],
        default=None,
        help="Built-in traveler profile (default: general; input traveler_profile priorities are merged on top)",
    )
    analyze_parser.add_argument(
        "--force", "-F",
        action="store_true",
        help="Overwrite the output file if it exists",
    )

    destination_parser = subparsers.add_parser(
        "rank-destination",
        help="Rerank a local Ctrip destination candidate pool",
    )
    destination_parser.add_argument(
        "--input",
        "-i",
        required=True,
        type=Path,
        help="Input JSON with 20-30 Ctrip hotel candidates",
    )
    destination_parser.add_argument(
        "--output",
        "-o",
        required=True,
        type=Path,
        help="Output Top 10 shortlist JSON",
    )
    destination_parser.add_argument(
        "--force",
        "-F",
        action="store_true",
        help="Overwrite the output file if it exists",
    )

    deep_screen_parser = subparsers.add_parser(
        "deep-screen",
        help="Analyze one hotel using latest and separately collected negative reviews",
    )
    deep_screen_parser.add_argument(
        "--input",
        "-i",
        required=True,
        type=Path,
        help="Deep-screen input JSON",
    )
    deep_screen_parser.add_argument(
        "--output",
        "-o",
        required=True,
        type=Path,
        help="Deep-screen report JSON",
    )
    deep_screen_parser.add_argument(
        "--force",
        "-F",
        action="store_true",
        help="Overwrite the output file if it exists",
    )
    
    return parser


def get_traveler_profile(profile_name: str) -> dict:
    """Get traveler profile by name."""
    family_comfort = get_preference_profile("hotel_family_comfort_v1")
    profiles = {
        "general": DEFAULT_TRAVELER_PROFILE,
        "family": {
            "trip_type": "family",
            "priorities": {
                "hygiene": 1.2,
                "noise": 1.3,
                "air_conditioning": 1.2,
                "hot_water": 1.2,
                "facility": 1.2,
                "room_mismatch": 1.1,
                "location": 0.9,
                "hidden_fees": 1.0,
                "service": 0.8,
            },
        },
        "business": {
            "trip_type": "business",
            "priorities": {
                "hygiene": 1.0,
                "noise": 1.1,
                "air_conditioning": 1.0,
                "hot_water": 1.0,
                "facility": 1.0,
                "room_mismatch": 1.0,
                "location": 1.3,
                "hidden_fees": 0.8,
                "service": 0.8,
            },
        },
        "hotel_family_comfort_v1": {
            "trip_type": "family",
            "profile_id": "hotel_family_comfort_v1",
            "priorities": family_comfort["priorities"],
            "tolerances": family_comfort["tolerances"],
        },
    }
    return profiles.get(profile_name, DEFAULT_TRAVELER_PROFILE).copy()


def merge_traveler_profile(base: dict, custom: dict) -> dict:
    """Merge a validated custom profile over a built-in profile."""
    merged = {**base, **custom}
    merged["priorities"] = {
        **base.get("priorities", {}),
        **custom.get("priorities", {}),
    }
    return merged


def atomic_write_text(path: Path, content: str, *, force: bool) -> None:
    """Write a private report atomically with owner-only permissions."""
    if path.is_symlink():
        raise OSError(f"Refusing to overwrite symbolic link: {path}")
    path = path.absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if force:
            os.replace(temporary_path, path)
        else:
            try:
                os.link(temporary_path, path)
            except FileExistsError as exc:
                raise OSError("Output appeared during write; use --force to overwrite") from exc
            temporary_path.unlink()
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def load_json_input(path: Path) -> Optional[dict]:
    """Load a JSON object and report user-facing errors."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON in input file: {exc}", file=sys.stderr)
        return None
    except OSError as exc:
        print(f"Error reading input file: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print("Error: Input root must be an object", file=sys.stderr)
        return None
    return data


def write_json_output(path: Path, report: dict, force: bool) -> int:
    """Write a JSON report with the CLI's existing safe-output behavior."""
    if path.exists() and not force:
        print(f"Error: Output file exists: {path}", file=sys.stderr)
        print("Use --force to overwrite.", file=sys.stderr)
        return 1
    try:
        atomic_write_text(path, json.dumps(report, indent=2, ensure_ascii=False), force=force)
    except OSError as exc:
        print(f"Error writing output: {exc}", file=sys.stderr)
        return 1
    print(f"Report written to: {path}")
    return 0


def cmd_rank_destination(args: argparse.Namespace) -> int:
    """Execute Ctrip destination candidate ranking."""
    data = load_json_input(args.input)
    if data is None:
        return 1
    try:
        report = rank_destination_candidates(data)
    except ValueError as exc:
        print(f"Destination scan failed: {exc}", file=sys.stderr)
        return 1
    result = write_json_output(args.output, report, args.force)
    if result == 0:
        print(f"Candidates ranked: {len(report['final_top10'])}")
    return result


def cmd_deep_screen(args: argparse.Namespace) -> int:
    """Execute evidence-gated single-hotel deep screening."""
    data = load_json_input(args.input)
    if data is None:
        return 1
    try:
        report = analyze_deep_screen(data)
    except ValueError as exc:
        print(f"Deep screen failed: {exc}", file=sys.stderr)
        return 1
    result = write_json_output(args.output, report, args.force)
    if result == 0:
        print(f"Risk Level: {report['risk_level']}")
        print(f"Risk Score: {report['overall_risk_score']}/100")
    return result


def cmd_analyze(args: argparse.Namespace) -> int:
    """Execute analyze command."""
    # Load input
    try:
        with args.input.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        return 1
    
    # Validate input
    is_valid, issues = validate_input_schema(data)
    if not is_valid:
        print("Input validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    
    # Get traveler profile
    traveler_profile = get_traveler_profile(args.profile or "general")
    if "traveler_profile" in data:
        traveler_profile = merge_traveler_profile(traveler_profile, data["traveler_profile"])
    
    # Extract data
    hotel_info = data.get("hotel", {})
    reviews = data.get("reviews", [])
    
    # Classify reviews
    classification = classify_reviews(reviews)
    
    # Calculate risk score
    try:
        scoring = calculate_risk_score(
            classification,
            traveler_profile=traveler_profile,
        )
    except ValueError as e:
        print(f"Scoring failed: {e}", file=sys.stderr)
        return 1
    
    # Generate report
    json_report = generate_json_report(
        hotel_info,
        classification,
        scoring,
        traveler_profile,
    )
    
    # Write output
    if args.output.exists() and not args.force:
        print(f"Error: Output file exists: {args.output}", file=sys.stderr)
        print("Use --force to overwrite.", file=sys.stderr)
        return 1

    try:
        if args.format == "markdown":
            content = generate_markdown_report(json_report)
        else:
            content = json.dumps(json_report, indent=2, ensure_ascii=False)
        atomic_write_text(args.output, content, force=args.force)
        
        print(f"Report written to: {args.output}")
        print(f"Risk Level: {scoring['risk_level']}")
        score = scoring["overall_risk_score"] if scoring["overall_risk_score"] is not None else "N/A"
        print(f"Risk Score: {score}/100")
        return 0
        
    except OSError as e:
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
    if args.command == "rank-destination":
        return cmd_rank_destination(args)
    if args.command == "deep-screen":
        return cmd_deep_screen(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
