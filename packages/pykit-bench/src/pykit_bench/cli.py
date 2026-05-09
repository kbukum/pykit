"""pykit_bench CLI — compare runs and view history."""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from pykit_bench.comparator import BenchRunComparator
from pykit_bench.report_gen.markdown import MarkdownReporter
from pykit_bench.storage import FileRunStorage, ListOptions


def cmd_compare(args: argparse.Namespace) -> None:
    """Compare two bench runs."""
    storage = FileRunStorage(Path(args.results_dir))
    try:
        run_a = storage.load(args.run_a)
        run_b = storage.load(args.run_b)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    result = BenchRunComparator().compare(run_a, run_b)
    print(result.summary())


def cmd_history(args: argparse.Namespace) -> None:
    """List saved runs."""
    storage = FileRunStorage(Path(args.results_dir))
    runs = storage.list_runs(ListOptions())
    if args.type:
        runs = [run for run in runs if args.type in run.dataset or args.type in run.id]
    if not runs:
        print("No runs found.")
        return

    print(f"{'Run ID':<40s} {'Tag':<15s} {'F1':>6s} {'Dataset':<20s}")
    print("─" * 90)
    for run in runs:
        print(f"{run.id:<40s} {run.tag:<15s} {run.f1:>6.3f} {run.dataset:<20.20s}")


def cmd_latest(args: argparse.Namespace) -> None:
    """Show the latest run report."""
    storage = FileRunStorage(Path(args.results_dir))
    try:
        result = storage.latest()
    except FileNotFoundError:
        print("No runs found.")
        sys.exit(1)

    writer = io.StringIO()
    MarkdownReporter().generate(writer, result)
    print(writer.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser(prog="pykit.bench.cli", description="Bench run management")
    parser.add_argument("--results-dir", default="bench/results", help="Path to results directory")
    sub = parser.add_subparsers(dest="command")

    p_cmp = sub.add_parser("compare", help="Compare two runs")
    p_cmp.add_argument("run_a", help="First run ID (baseline)")
    p_cmp.add_argument("run_b", help="Second run ID (new)")

    p_hist = sub.add_parser("history", help="List saved runs")
    p_hist.add_argument("--type", default=None, help="Filter by dataset or run ID substring")

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
