# PHASE 2 PROMPT — Hybrid Graph + Vector RAG Pipeline
> Copy this entire prompt into Claude Code. Requires Phase 1 to be complete.

---

## Instructions for Claude Code

First, read `MASTER_SPEC.md` and `DATA_SCHEMA.md` in full. Then review `backend/graph/neo4j_client.py` and `backend/graph/ingest.py` from Phase 1.

You are building Phase 2: the complete RAG pipeline. This is the core intelligence of the system.

---

## Deliverables

### 1. `backend/rag/graph_retriever.py`

Class: `GraphRetriever`

Methods:
- `get_product_with_context(store_slug, product_slug)` — fetch product + location + FAQs in one query
- `get_compatible_accessories(store_slug, product_slug)` — traverse COMPATIBLE_WITH
- `get_alternatives(store_slug, product_slug, max_price=None)` — traverse ALTERNATIVE_TO
- `get_policy(store_slug, policy_type)` — fetch policy doc
- `get_all_policies(store_slug)` — fetch all policies for a store
- `get_category_products(store_slug, category_slug)` — all products in a category
- `get_product_by_name_fuzzy(store_slug, partial_name)` — case-insensitive CONTAINS search on product name
- `get_store_info(store_slug)` — store node with opening hours

All methods return typed Pydantic models. All Cypher is parameterised.

### 2. `backend/rag/vector_retriever.py`

Class: `VectorRetriever`

Methods:
- `search_products(store_slug, query_embedding, top_k=5)` — vector search on product_embedding index
- `search_policies(store_slug, query_embedding, top_k=3)` — vector search on policy_embedding index
- `search_faqs(store_slug, query_embedding, top_k=5)` — vector search on faq_embedding index
- `get_query_embedding(text: str) -> List[float]` — calls OpenAI text-embedding-3-small, caches in memory for session

Use Neo4j's `db.index.vector.queryNodes` Cypher procedure.
Filter results by `store_slug` after retrieval.
Return results sorted by cosine similarity score descending.

### 3. `backend/rag/hybrid_retriever.py`

Class: `HybridRetriever`

This is the main retriever that combines graph + vector results.

- `retrieve(store_slug, query, intent, top_k=5) -> RetrievalResult`

`RetrievalResult` Pydantic model:
```python
class RetrievalResult(BaseModel):
    graph_context: list[dict]      # structured graph traversal results
    vector_context: list[dict]     # semantic similarity results
    merged_context: str            # formatted string ready for LLM prompt
    confidence_score: float        # 0.0 to 1.0
    source_nodes: list[str]        # list of node slugs/ids used
    human_escalation_required: bool
    escalation_reason: str | None
```

Routing logic based on intent (from MASTER_SPEC.md):
- `"product_info"` → vector search + graph product traversal
- `"availability"` → graph stock query only
- `"location"` → graph AisleLocation query
- `"policy"` → graph + vector policy search
- `"recommendation"` → vector search + ALTERNATIVE_TO graph traversal
- `"payment"` → set `human_escalation_required=True`, `escalation_reason="payment"`
- `"live_demo"` → set `human_escalation_required=True`, `escalation_reason="live_demo"`
- `"general"` → vector search across products + FAQs

Confidence scoring:
```python
def _compute_confidence(self, graph_results, vector_results, intent) -> float:
    # - If intent matched and graph results found: base 0.8
    # - Each additional vector result above threshold (0.7 cosine): +0.03
    # - No graph results but vector results > 0.75: 0.65
    # - No results at all: 0.2
    # - Payment/demo intent: 0.0 (always escalate)
    # Clamp to [0.0, 1.0]
```

### 4. `backend/rag/prompt_builder.py`

Class: `PromptBuilder`

Methods:
- `build_system_prompt(store_slug: str, store_info: dict) -> str`

  System prompt must include:
  - Store name, opening hours, address
  - Assistant persona: friendly, knowledgeable store assistant
  - Instructions: answer based only on provided context, if unsure say so
  - Instruction: always mention aisle location when discussing product whereabouts
  - Instruction: if recommending alternatives, mention price difference
  - Australian English spelling

- `build_user_prompt(query: str, retrieval_result: RetrievalResult, conversation_history: list) -> list[dict]`

  Returns list of messages for LLM (system + history + user with context injected).

- `_format_context(retrieval_result: RetrievalResult) -> str`

  Formats merged context into clean text block for injection into prompt.

### 5. `backend/rag/pipeline.py`

Class: `RAGPipeline` — the main orchestrator

Methods:
- `__init__(store_slug: str)` — initialise all retrievers for this store
- `async run(query: str, conversation_history: list, session_id: str) -> AsyncGenerator[str, None]`

  Full pipeline:
  1. Classify intent (lightweight LLM call or rule-based classifier)
  2. Run HybridRetriever
  3. Check escalation — if required, fire Slack notification (non-blocking)
  4. Build prompt
  5. Stream LLM response token by token
  6. Log full trace to Langfuse
  7. Yield each token as it arrives

Intent classifier — build a simple rule-based classifier first (keyword matching), then optionally a small LLM call:
```python
INTENT_KEYWORDS = {
    "location": ["where", "find", "aisle", "located", "direction"],
    "availability": ["stock", "available", "do you have", "in stock"],
    "policy": ["return", "refund", "warranty", "policy", "exchange", "price match"],
    "recommendation": ["recommend", "suggest", "best", "alternative", "similar", "compare"],
    "payment": ["pay", "payment", "checkout", "credit card", "eftpos", "buy now"],
    "live_demo": ["demo", "demonstration", "try", "test it", "show me"],
}
```

### 6. `backend/llm/groq_client.py`

Class: `GroqStreamingClient`

- `async stream(messages: list[dict]) -> AsyncGenerator[str, None]`
- Model: `llama-3.3-70b-versatile`
- Temperature: 0.3 (factual assistant)
- Max tokens: 1024
- Yield each token string as it arrives
- Handle `RateLimitError` — raise `GroqRateLimitError` for router to catch

### 7. `backend/llm/gemini_client.py`

Class: `GeminiStreamingClient`

- `async stream(messages: list[dict]) -> AsyncGenerator[str, None]`
- Model: `gemini-2.0-flash`
- Convert OpenAI-style messages to Gemini format
- Same streaming yield pattern as Groq client

### 8. `backend/llm/router.py`

Class: `LLMRouter`

- `async stream(messages: list[dict]) -> AsyncGenerator[str, None]`
- Primary: Groq
- On `GroqRateLimitError`: log warning, switch to Gemini seamlessly
- The streaming generator the pipeline actually calls

### 9. `backend/monitoring/langfuse_client.py`

Class: `LangfuseTracer`

- `start_trace(session_id, store_slug, query) -> trace_id`
- `log_retrieval(trace_id, intent, confidence, source_nodes)`
- `log_llm_call(trace_id, model, prompt_tokens, completion_tokens, latency_ms)`
- `log_escalation(trace_id, reason)`
- `end_trace(trace_id, full_response)`

Wrap with try/except — Langfuse errors must never crash the main pipeline.

### 10. `backend/human_loop/slack_notifier.py`

Class: `SlackNotifier`

- `async notify(store_slug, query, session_id, trigger_type, confidence=None)`
- Sends webhook POST to `SLACK_WEBHOOK_URL`
- Message format as per MASTER_SPEC.md
- Non-blocking: use `asyncio.create_task()` — never await in the hot path
- If Slack fails: log error, continue silently

---

## Pydantic Models to Define (in `backend/rag/models.py`)

```python
class StoreInfo(BaseModel): ...
class ProductNode(BaseModel): ...
class AisleLocationNode(BaseModel): ...
class FAQNode(BaseModel): ...
class PolicyDocNode(BaseModel): ...
class RetrievalResult(BaseModel): ...
class ChatMessage(BaseModel): ...
class PipelineOutput(BaseModel): ...
```

---

## Constraints

- The pipeline must be async throughout
- Langfuse and Slack errors must NEVER crash the main pipeline (wrap in try/except)
- All LLM calls must go through the router (never call Groq/Gemini directly from pipeline)
- Confidence score must be computed and attached to every response
- Type hints everywhere

---

## Test

After building, this must work:

```python
# Quick smoke test (run from backend/)
import asyncio
from rag.pipeline import RAGPipeline

async def test():
    pipeline = RAGPipeline(store_slug="jbhifi")
    async for token in pipeline.run(
        query="Where can I find Sony headphones?",
        conversation_history=[],
        session_id="test-123"
    ):
        print(token, end="", flush=True)

asyncio.run(test())
```

Expected: streaming response mentioning aisle location, no errors.
