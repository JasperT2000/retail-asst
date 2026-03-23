"""
RAGAS benchmark runner (ragas 0.4.x API).

Evaluates the RAG pipeline across three configurations:
  - baseline: Raw LLM, no retrieval
  - vector_rag: Vector search only (no graph)
  - graph_rag: Full hybrid Graph + Vector (production)

Results are saved to eval/results/{config}_{timestamp}.json.
Intermediate samples (Q/A/context) are saved to eval/results/{config}_{timestamp}_samples.json
so individual metrics can be re-scored without regenerating answers.

Usage:
  # Full run (generate answers + score all metrics):
  OPENAI_ONLY=1 python -m backend.eval.benchmark

  # Score only specific metrics against saved samples:
  OPENAI_ONLY=1 python -m backend.eval.benchmark \\
      --samples-file eval/results/graph_rag_20260323_samples.json \\
      --metrics context_precision context_recall
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / "backend" / ".env")

log = structlog.get_logger(__name__)

EVAL_DATASET_PATH = Path(__file__).parent / "eval_dataset.json"
RESULTS_DIR = Path(__file__).parent / "results"

ALL_METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


async def run_baseline(question: str, store_slug: str) -> tuple[str, list[str]]:
    """Raw LLM with no retrieval."""
    from backend.llm.router import LLMRouter

    router = LLMRouter()
    answer = await router.complete(
        system=f"You are a helpful store assistant for {store_slug}. Answer questions about the store.",
        user=question,
    )
    return answer, ["No retrieval — baseline LLM only."]


async def run_vector_rag(question: str, store_slug: str) -> tuple[str, list[str]]:
    """Vector-only RAG config."""
    from backend.rag.vector_retriever import VectorRetriever
    from backend.rag.prompt_builder import PromptBuilder
    from backend.rag.models import RetrievalResult
    from backend.rag.hybrid_retriever import _format_merged_context
    from backend.llm.router import LLMRouter

    retriever = VectorRetriever()
    embedding = await retriever.get_query_embedding(question)
    products = await retriever.search_products(store_slug, embedding)
    policies = await retriever.search_policies(store_slug, embedding)
    faqs = await retriever.search_faqs(store_slug, embedding)

    all_nodes = products + policies + faqs
    context_text = _format_merged_context(all_nodes) if all_nodes else "No relevant context found."

    retrieval_result = RetrievalResult(
        graph_context=[],
        vector_context=all_nodes,
        merged_context=context_text,
        confidence_score=0.65 if all_nodes else 0.2,
        source_nodes=[p["slug"] for p in products if p.get("slug")],
    )

    messages = PromptBuilder().build_user_prompt(
        query=question,
        retrieval_result=retrieval_result,
        conversation_history=[],
        store_slug=store_slug,
    )
    router = LLMRouter()
    tokens = []
    async for token in router.stream(messages):
        tokens.append(token)
    return "".join(tokens), [context_text]


async def run_graph_rag(question: str, store_slug: str) -> tuple[str, list[str]]:
    """Full hybrid Graph + Vector RAG config (production)."""
    from backend.rag.pipeline import classify_intent
    from backend.rag.hybrid_retriever import HybridRetriever
    from backend.rag.graph_retriever import GraphRetriever
    from backend.rag.vector_retriever import VectorRetriever
    from backend.rag.prompt_builder import PromptBuilder
    from backend.llm.router import LLMRouter

    intent = classify_intent(question)
    graph = GraphRetriever()
    vector = VectorRetriever()
    hybrid = HybridRetriever(graph, vector)

    retrieval = await hybrid.retrieve(
        store_slug=store_slug,
        query=question,
        intent=intent,
    )
    context_text = retrieval.merged_context or "No relevant context found."

    store_info = await graph.get_store_info(store_slug)
    messages = PromptBuilder().build_user_prompt(
        query=question,
        retrieval_result=retrieval,
        conversation_history=[],
        store_slug=store_slug,
        store_info=store_info,
        intent=intent,
    )
    router = LLMRouter()
    tokens = []
    async for token in router.stream(messages):
        tokens.append(token)
    return "".join(tokens), [context_text]


async def generate_samples(
    config: str,
    dataset: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Generate answers and retrieve contexts for each question.

    Saves raw samples to disk so metrics can be re-scored without
    regenerating answers.

    Returns:
        List of dicts with keys: user_input, response, reference, retrieved_contexts.
    """
    run_fn = {
        "baseline": run_baseline,
        "vector_rag": run_vector_rag,
        "graph_rag": run_graph_rag,
    }[config]

    samples = []
    for item in dataset:
        log.info("benchmark.generating", config=config, id=item["id"])
        try:
            answer, contexts = await run_fn(item["question"], item["store_slug"])
        except Exception as exc:
            log.error("benchmark.run_failed", config=config, id=item["id"], error=str(exc))
            answer = ""
            contexts = [""]

        samples.append({
            "user_input": item["question"],
            "response": answer,
            "reference": item["ground_truth"],
            "retrieved_contexts": contexts,
        })
        await asyncio.sleep(1.5)

    return samples


def score_samples(
    samples: list[dict[str, Any]],
    metric_names: list[str],
) -> dict[str, Any]:
    """
    Run RAGAS scoring on pre-generated samples.

    Args:
        samples: List of dicts from generate_samples().
        metric_names: Which metrics to compute.

    Returns:
        Dict of metric name → mean score.
    """
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from openai import OpenAI
    from langchain_openai import OpenAIEmbeddings
    from ragas import evaluate, EvaluationDataset
    from ragas.dataset_schema import SingleTurnSample
    from ragas.llms import llm_factory
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )

    metric_map = {
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "context_recall": context_recall,
    }
    metrics = [metric_map[m] for m in metric_names if m in metric_map]

    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    llm = llm_factory("gpt-4o-mini", client=openai_client)
    emb = OpenAIEmbeddings(model="text-embedding-3-small", api_key=os.environ["OPENAI_API_KEY"])

    eval_dataset = EvaluationDataset(samples=[
        SingleTurnSample(
            user_input=s["user_input"],
            response=s["response"],
            reference=s["reference"],
            retrieved_contexts=s["retrieved_contexts"],
        )
        for s in samples
    ])

    result = evaluate(
        eval_dataset,
        metrics=metrics,
        llm=llm,
        embeddings=emb,
        raise_exceptions=False,
    )
    df = result.to_pandas()
    return {col: float(df[col].mean()) for col in df.columns if df[col].dtype in ("float64", "float32")}


async def evaluate_config(
    config: str,
    dataset: list[dict[str, Any]],
    metric_names: list[str],
    timestamp: str,
) -> dict[str, Any]:
    """Generate answers and score them, saving samples to disk."""
    samples_path = RESULTS_DIR / f"{config}_{timestamp}_samples.json"

    # Generate answers (or load if already done)
    if samples_path.exists():
        log.info("benchmark.loading_cached_samples", path=str(samples_path))
        with open(samples_path) as fh:
            samples = json.load(fh)
    else:
        samples = await generate_samples(config, dataset)
        with open(samples_path, "w") as fh:
            json.dump(samples, fh, indent=2)
        log.info("benchmark.samples_saved", path=str(samples_path))

    return score_samples(samples, metric_names)


async def main(
    configs: list[str] | None = None,
    metric_names: list[str] | None = None,
    samples_file: str | None = None,
) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    all_configs = configs or ["baseline", "vector_rag", "graph_rag"]
    metrics_to_run = metric_names or ALL_METRICS
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # --samples-file: score a single saved samples file against specific metrics
    if samples_file:
        with open(samples_file) as fh:
            samples = json.load(fh)
        log.info("benchmark.scoring_from_file", file=samples_file, metrics=metrics_to_run)
        scores = score_samples(samples, metrics_to_run)
        print(f"\nScores for {samples_file}:")
        for k, v in scores.items():
            print(f"  {k}: {v:.3f}")
        return

    with open(EVAL_DATASET_PATH) as fh:
        dataset = json.load(fh)

    # Sample every other question: 25 from 50
    dataset = dataset[::2]

    log.info("benchmark.start", configs=all_configs, questions=len(dataset), metrics=metrics_to_run)

    for config in all_configs:
        log.info("benchmark.config_start", config=config)
        scores = await evaluate_config(config, dataset, metrics_to_run, timestamp)
        result = {
            "config": config,
            "timestamp": timestamp,
            "num_questions": len(dataset),
            "metrics": scores,
        }
        out_path = RESULTS_DIR / f"{config}_{timestamp}.json"
        with open(out_path, "w") as fh:
            json.dump(result, fh, indent=2)
        log.info("benchmark.config_done", config=config, metrics=scores, output=str(out_path))
        print(f"\n[{config}] Results:")
        for k, v in scores.items():
            print(f"  {k}: {v:.3f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=["baseline", "vector_rag", "graph_rag"])
    parser.add_argument("--metrics", nargs="+", choices=ALL_METRICS)
    parser.add_argument("--samples-file", help="Path to a saved _samples.json to score without regenerating answers")
    args = parser.parse_args()

    asyncio.run(main(
        configs=[args.config] if args.config else None,
        metric_names=args.metrics,
        samples_file=args.samples_file,
    ))
