"""
RAGAS benchmark results reporter.

Reads all result JSON files from backend/eval/results/ and prints a
Markdown comparison table across baseline, vector_rag, and graph_rag configs.
"""

from __future__ import annotations

import json
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
CONFIGS = ["baseline", "vector_rag", "graph_rag"]
METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def _load_latest(config: str) -> dict | None:
    """Load the most recent result file for a given config."""
    files = sorted(RESULTS_DIR.glob(f"{config}_*.json"))
    if not files:
        return None
    with open(files[-1]) as fh:
        return json.load(fh)


def generate_report(results_dir: Path | None = None) -> str:
    """
    Generate a Markdown comparison table from the latest results for each config.

    Args:
        results_dir: Override path to results directory (defaults to eval/results/).

    Returns:
        Markdown string with header, table, and improvement notes.
    """
    search_dir = results_dir or RESULTS_DIR
    lines: list[str] = []

    # Collect data
    data: dict[str, dict | None] = {}
    for config in CONFIGS:
        files = sorted(search_dir.glob(f"{config}_*.json"))
        if not files:
            data[config] = None
            continue
        with open(files[-1]) as fh:
            data[config] = json.load(fh)

    lines.append("# RAGAS Benchmark Report\n")

    # Timestamps
    for config in CONFIGS:
        if data[config]:
            ts = data[config].get("timestamp", "unknown")
            n = data[config].get("num_questions", "?")
            lines.append(f"- **{config}**: {n} questions evaluated at `{ts}`")
    lines.append("")

    # Table header
    col_headers = ["Metric"] + [c.replace("_", " ").title() for c in CONFIGS]
    lines.append("| " + " | ".join(col_headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(col_headers)) + " |")

    # One row per metric
    for metric in METRICS:
        row = [metric.replace("_", " ").title()]
        for config in CONFIGS:
            if data[config] and data[config].get("metrics", {}).get(metric) is not None:
                val = data[config]["metrics"][metric]
                row.append(f"{val:.3f}")
            else:
                row.append("—")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    # Graph RAG vs Baseline delta
    baseline = data.get("baseline")
    graph_rag = data.get("graph_rag")
    if baseline and graph_rag:
        lines.append("## Graph RAG vs Baseline Improvement\n")
        for metric in METRICS:
            b_val = baseline.get("metrics", {}).get(metric)
            g_val = graph_rag.get("metrics", {}).get(metric)
            if b_val is not None and g_val is not None:
                delta = g_val - b_val
                sign = "+" if delta >= 0 else ""
                lines.append(
                    f"- **{metric.replace('_', ' ').title()}**: {sign}{delta:.3f} "
                    f"({b_val:.3f} → {g_val:.3f})"
                )

    return "\n".join(lines)


def print_report() -> None:
    """Print the Markdown report to stdout."""
    report = generate_report()
    print(report)


if __name__ == "__main__":
    print_report()
