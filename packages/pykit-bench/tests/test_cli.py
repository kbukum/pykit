"""Tests for cli.py — CLI entry points."""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from pykit_bench.cli import cmd_compare, cmd_history, cmd_latest, main

# ---------------------------------------------------------------------------
# cmd_compare
# ---------------------------------------------------------------------------


class TestCmdCompare:
    def test_compare_success(self):
        run_a = MagicMock()
        run_b = MagicMock()
        comparison = MagicMock()
        comparison.summary.return_value = "All good"

        mock_storage = MagicMock()
        mock_storage.load.side_effect = lambda rid: run_a if rid == "run-a" else run_b

        mock_comparator = MagicMock()
        mock_comparator.return_value.compare.return_value = comparison

        args = argparse.Namespace(results_dir="some/path", run_a="run-a", run_b="run-b")

        with (
            patch("pykit_bench.cli.RunStorage", return_value=mock_storage),
            patch("pykit_bench.cli.RunComparator", mock_comparator),
            patch("builtins.print") as mock_print,
        ):
            cmd_compare(args)
            mock_print.assert_called_once_with("All good")

    def test_compare_file_not_found(self):
        mock_storage = MagicMock()
        mock_storage.load.side_effect = FileNotFoundError("not found")

        args = argparse.Namespace(results_dir="some/path", run_a="run-a", run_b="run-b")

        with (
            patch("pykit_bench.cli.RunStorage", return_value=mock_storage),
            patch("builtins.print"),
            pytest.raises(SystemExit) as exc_info,
        ):
            cmd_compare(args)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# cmd_history
# ---------------------------------------------------------------------------


class TestCmdHistory:
    def test_history_no_runs(self):
        mock_storage = MagicMock()
        mock_storage.list_runs.return_value = []

        args = argparse.Namespace(results_dir="some/path", type=None)

        with (
            patch("pykit_bench.cli.RunStorage", return_value=mock_storage),
            patch("builtins.print") as mock_print,
        ):
            cmd_history(args)
            mock_print.assert_called_once_with("No runs found.")

    def test_history_with_runs(self):
        run_summary = MagicMock()
        run_summary.run_id = "run-1"
        run_summary.tag = "test"
        run_summary.f1 = 0.95
        run_summary.accuracy = 0.92
        run_summary.sample_count = 100

        mock_storage = MagicMock()
        mock_storage.list_runs.return_value = [run_summary]

        args = argparse.Namespace(results_dir="some/path", type=None)

        with (
            patch("pykit_bench.cli.RunStorage", return_value=mock_storage),
            patch("builtins.print") as mock_print,
        ):
            cmd_history(args)
            # Header + separator + 1 run line = 3 calls
            assert mock_print.call_count == 3

    def test_history_with_type_filter(self):
        mock_storage = MagicMock()
        mock_storage.list_runs.return_value = []

        args = argparse.Namespace(results_dir="some/path", type="audio")

        with (
            patch("pykit_bench.cli.RunStorage", return_value=mock_storage),
            patch("builtins.print"),
        ):
            cmd_history(args)
            mock_storage.list_runs.assert_called_once_with(media_type="audio")


# ---------------------------------------------------------------------------
# cmd_latest
# ---------------------------------------------------------------------------


class TestCmdLatest:
    def test_latest_success(self):
        mock_run = MagicMock()
        mock_storage = MagicMock()
        mock_storage.latest.return_value = mock_run

        mock_reporter = MagicMock()
        mock_reporter.return_value.generate.return_value = "Report text"

        args = argparse.Namespace(results_dir="some/path")

        with (
            patch("pykit_bench.cli.RunStorage", return_value=mock_storage),
            patch("pykit_bench.report.MarkdownReporter", mock_reporter),
            patch("builtins.print") as mock_print,
        ):
            cmd_latest(args)
            mock_print.assert_called_once_with("Report text")

    def test_latest_no_runs(self):
        mock_storage = MagicMock()
        mock_storage.latest.side_effect = FileNotFoundError("No runs")

        args = argparse.Namespace(results_dir="some/path")

        with (
            patch("pykit_bench.cli.RunStorage", return_value=mock_storage),
            patch("builtins.print"),
            pytest.raises(SystemExit) as exc_info,
        ):
            cmd_latest(args)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


class TestMain:
    def test_no_command_prints_help(self):
        with (
            patch("sys.argv", ["pykit.bench.cli"]),
            patch("argparse.ArgumentParser.print_help") as mock_help,
        ):
            main()
            mock_help.assert_called_once()

    def test_compare_command_dispatched(self):
        with (
            patch("sys.argv", ["pykit.bench.cli", "compare", "run-a", "run-b"]),
            patch("pykit_bench.cli.cmd_compare") as mock_cmd,
        ):
            main()
            mock_cmd.assert_called_once()

    def test_history_command_dispatched(self):
        with (
            patch("sys.argv", ["pykit.bench.cli", "history"]),
            patch("pykit_bench.cli.cmd_history") as mock_cmd,
        ):
            main()
            mock_cmd.assert_called_once()

    def test_latest_command_dispatched(self):
        with (
            patch("sys.argv", ["pykit.bench.cli", "latest"]),
            patch("pykit_bench.cli.cmd_latest") as mock_cmd,
        ):
            main()
            mock_cmd.assert_called_once()

    def test_custom_results_dir(self):
        with (
            patch("sys.argv", ["pykit.bench.cli", "--results-dir", "custom/dir", "history"]),
            patch("pykit_bench.cli.cmd_history") as mock_cmd,
        ):
            main()
            args = mock_cmd.call_args[0][0]
            assert args.results_dir == "custom/dir"
