"""pykit_bench CLI — compare runs and view history."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pykit_bench.compare import RunComparator
from pykit_bench.storage import RunStorage


def cmd_compare(args: argparse.Namespace) -> None:
    """Compare two bench runs."""
    storage = RunStorage(Path(args.results_dir))
    try:
        run_a = storage.load(args.run_a)
        run_b = storage.load(args.run_b)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    result = RunComparator().compare(run_a, run_b)
    print(result.summary())


def cmd_history(args: argparse.Namespace) -> None:
    """List saved runs."""
    storage = RunStorage(Path(args.results_dir))
    runs = storage.list_runs(media_type=args.type)
    if not runs:
        print("No runs found.")
        return

    print(f"{'Run ID':<40s} {'Tag':<15s} {'F1':>6s} {'Acc':>6s} {'Samples':>8s}")
    print("─" * 80)
    for r in runs:
        print(f"{r.run_id:<40s} {r.tag:<15s} {r.f1:>6.3f} {r.accuracy:>6.3f} {r.sample_count:>8d}")


def cmd_latest(args: argparse.Namespace) -> None:
    """Show the latest run report."""
    from pykit_bench.report import MarkdownReporter

    storage = RunStorage(Path(args.results_dir))
    try:
        result = storage.latest()
    except FileNotFoundError:
        print("No runs found.")
        sys.exit(1)

    print(MarkdownReporter().generate(result))


def main() -> None:
    parser = argparse.ArgumentParser(prog="pykit.bench.cli", description="Bench run management")
    parser.add_argument("--results-dir", default="bench/results", help="Path to results directory")
    sub = parser.add_subparsers(dest="command")

    # compare
    p_cmp = sub.add_parser("compare", help="Compare two runs")
    p_cmp.add_argument("run_a", help="First run ID (baseline)")
    p_cmp.add_argument("run_b", help="Second run ID (new)")

    # history
    p_hist = sub.add_parser("history", help="List saved runs")
    p_hist.add_argument("--type", default=None, help="Filter by media type")

    # latest
    sub.add_parser("latest", help="Show latest run report")

    args = parser.parse_args()
    if args.command == "compare":
        cmd_compare(args)
    elif args.command == "history":
        cmd_history(args)
    elif args.command == "latest":
        cmd_latest(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
