"""
Phase 2 smoke test — run from the backend/ directory.

Usage:
    cd backend
    python smoke_test.py

Requires a valid .env file with NEO4J_*, GROQ_API_KEY (or GEMINI_API_KEY),
and OPENAI_API_KEY populated and data already ingested into Neo4j.
"""

import asyncio
import sys
from pathlib import Path

# Allow running from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from backend.rag.pipeline import RAGPipeline


async def test() -> None:
    """Run the smoke test query and print the streaming response."""
    pipeline = RAGPipeline(store_slug="jbhifi")
    print("Query: Where can I find Sony headphones?\n")
    print("Response: ", end="", flush=True)

    async for token in pipeline.run(
        query="Where can I find Sony headphones?",
        conversation_history=[],
        session_id="test-123",
    ):
        print(token, end="", flush=True)

    print("\n")
    output = pipeline.get_last_output()
    print(f"Intent:     {output.intent}")
    print(f"Confidence: {output.confidence_score:.3f}")
    print(f"Sources:    {output.source_nodes[:3]}")
    print(f"Human notified: {output.human_notified}")


if __name__ == "__main__":
    asyncio.run(test())
