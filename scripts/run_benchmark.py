#!/usr/bin/env python
"""
CLI wrapper for the RAGAS benchmark runner.

Usage:
    python scripts/run_benchmark.py                  # Run all three configs
    python scripts/run_benchmark.py --config graph_rag
    python scripts/run_benchmark.py --config all --report
    python scripts/run_benchmark.py --report         # Print latest results only
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RAGAS benchmarks for the Retail AI RAG pipeline.",
    )
    parser.add_argument(
        "--config",
        choices=["baseline", "vector_rag", "graph_rag", "all"],
        default="all",
        help="Which config(s) to evaluate (default: all).",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print Markdown comparison table after evaluation.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print the latest Markdown report without running any evaluation.",
    )
    args = parser.parse_args()

    if args.report_only:
        from backend.eval.results_reporter import print_report

        print_report()
        return

    configs = None if args.config == "all" else [args.config]

    from backend.eval.benchmark import main as run_benchmark

    asyncio.run(run_benchmark(configs))

    if args.report:
        print("\n" + "=" * 60 + "\n")
        from backend.eval.results_reporter import print_report

        print_report()


if __name__ == "__main__":
    main()
