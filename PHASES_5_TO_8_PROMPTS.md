# PHASE 5 PROMPT — Benchmarking (RAGAS)
> Copy this entire prompt into Claude Code. Requires Phases 1–2 to be complete.

---

## Instructions for Claude Code

Read `MASTER_SPEC.md` and `DATA_SCHEMA.md`. Review `backend/rag/pipeline.py`.

You are building Phase 5: the RAGAS benchmarking suite that compares three configurations.

---

## Deliverables

### 1. `backend/eval/eval_dataset.json`

Create a realistic evaluation dataset of exactly 50 questions across all 4 stores.

Distribution:
- 15 easy (direct product/location lookup)
- 20 medium (policy, availability, category)
- 15 hard (recommendations, multi-hop, comparisons)
- ~12–13 questions per store

Each entry format (from DATA_SCHEMA.md). Ensure questions are natural, conversational Australian English:
- *"Mate, where do I find the drills?"* (Bunnings, easy)
- *"What's the return policy if I change my mind about a pram?"* (Baby Bunting, medium)
- *"I've got a 2018 Holden Commodore, what battery do you recommend and where is it?"* (Supercheap, hard)

### 2. `backend/eval/benchmark.py`

Three pipeline configurations:

```python
class BenchmarkConfig(Enum):
    BASELINE = "baseline"      # Raw LLM, no RAG
    VECTOR_RAG = "vector_rag"  # Vector search only
    GRAPH_RAG = "graph_rag"    # Full hybrid (production)
```

For each configuration:
- Run all 50 eval questions
- Collect: generated answer, retrieved contexts, ground truth
- Feed into RAGAS `evaluate()` with metrics: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`
- Save results to `eval/results/{config}_{timestamp}.json`

`BaselinePipeline`:
- Just calls Groq with the raw question, no retrieval
- System prompt: "You are a retail store assistant. Answer based on your knowledge."

`VectorRAGPipeline`:
- Only uses `VectorRetriever`, no graph traversal
- All other pipeline logic identical to production

`GraphRAGPipeline`:
- Full production `RAGPipeline`

### 3. `backend/eval/results_reporter.py`

- `generate_report(results_dir)` — reads all result JSONs, produces comparison table
- Prints a markdown table comparing all three configs across all 4 RAGAS metrics
- Highlights which config wins each metric
- Calculates % improvement of Graph RAG over Baseline

### 4. `scripts/run_benchmark.py`

CLI script:
```bash
python scripts/run_benchmark.py --config all      # run all three
python scripts/run_benchmark.py --config graph_rag # run one
python scripts/run_benchmark.py --report           # print comparison table
```

---

## Expected Output Example

```
┌─────────────────────┬─────────────┬────────────┬───────────┬────────────────┐
│ Configuration       │ Faithfulness│ Relevancy  │ Precision │ Recall         │
├─────────────────────┼─────────────┼────────────┼───────────┼────────────────┤
│ Baseline            │ 0.41        │ 0.53       │ 0.38      │ 0.44           │
│ Vector RAG          │ 0.71        │ 0.74       │ 0.69      │ 0.72           │
│ Graph RAG (ours) ✓  │ 0.89        │ 0.87       │ 0.84      │ 0.86           │
├─────────────────────┼─────────────┼────────────┼───────────┼────────────────┤
│ Improvement (B→G)   │ +117%       │ +64%       │ +121%     │ +95%           │
└─────────────────────┴─────────────┴────────────┴───────────┴────────────────┘
```

---

---

# PHASE 6 PROMPT — Langfuse Monitoring
> Copy this entire prompt into Claude Code. Requires Phase 2 to be complete.

---

## Instructions for Claude Code

Read `MASTER_SPEC.md`. Review `backend/monitoring/langfuse_client.py` stub from Phase 2.

You are completing the Langfuse monitoring integration.

---

## Deliverables

### 1. Complete `backend/monitoring/langfuse_client.py`

Full implementation using the `langfuse` Python SDK:

```python
class LangfuseTracer:
    def start_trace(self, session_id, store_slug, query) -> str
    def log_intent_classification(self, trace_id, intent, method)
    def log_retrieval(self, trace_id, intent, confidence, graph_nodes, vector_nodes, latency_ms)
    def log_llm_call(self, trace_id, model, messages, response, prompt_tokens, completion_tokens, latency_ms)
    def log_escalation(self, trace_id, reason, confidence)
    def end_trace(self, trace_id, full_response, total_latency_ms)
    def flush(self)
```

Each log call creates a span under the parent trace.
Tag every trace with: `store_slug`, `intent`, `confidence_bucket` (high/medium/low).

### 2. `backend/monitoring/metrics.py`

Simple in-memory metrics collector (for the demo dashboard):
```python
class MetricsCollector:
    # Thread-safe counters
    total_queries: int
    queries_by_store: dict[str, int]
    queries_by_intent: dict[str, int]
    escalations: int
    avg_confidence: float
    avg_latency_ms: float

    def record_query(self, store_slug, intent, confidence, latency_ms, escalated)
    def get_summary() -> dict
```

### 3. `GET /monitoring/summary` endpoint

Returns live metrics summary (uses MetricsCollector):
```json
{
  "total_queries": 142,
  "queries_by_store": {"jbhifi": 58, "bunnings": 34, ...},
  "queries_by_intent": {"product_info": 61, "location": 29, ...},
  "escalation_rate": 0.08,
  "avg_confidence": 0.82,
  "avg_latency_ms": 1240
}
```

### 4. Live Monitoring Panel in Frontend

Add a small monitoring panel accessible at `/monitoring` (password-protected with a simple hardcoded PIN — good enough for demo).

Show:
- Total queries counter (auto-refreshes every 10s)
- Bar chart of queries by store
- Intent distribution pie chart
- Average confidence gauge
- Recent escalations list

Use Recharts for the charts (already in Next.js ecosystem).

---

---

# PHASE 7 PROMPT — CI/CD Pipeline
> Copy this entire prompt into Claude Code. Requires all previous phases to be complete.

---

## Instructions for Claude Code

Read `MASTER_SPEC.md`. You are setting up the complete CI/CD pipeline.

---

## Deliverables

### 1. `.github/workflows/ci.yml`

Triggers: on every PR to `main`

Jobs:
1. **lint** — `ruff check backend/` and `mypy backend/` (type checking)
2. **test** — runs `scripts/run_benchmark.py --config graph_rag` on a small 5-question subset; fails if faithfulness < 0.75
3. **frontend-build** — `cd frontend && npm install && npm run build`

All jobs run in parallel where possible.

### 2. `.github/workflows/deploy.yml`

Triggers: on merge to `main`

Jobs:
1. **deploy-backend** — trigger Render deploy hook (use `RENDER_DEPLOY_HOOK_URL` secret)
2. **deploy-frontend** — Vercel auto-deploys from GitHub (just add a status check step)

### 3. `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4. `backend/render.yaml`

Render deployment config:
```yaml
services:
  - type: web
    name: retail-ai-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: APP_ENV
        value: production
      # All other env vars added via Render dashboard
```

### 5. `frontend/vercel.json`

```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next"
}
```

### 6. `README.md` — Deployment Section

Add a deployment section:

**Backend (Render):**
1. Create account at render.com
2. New Web Service → connect GitHub repo
3. Set root directory to `backend/`
4. Add all env vars in Render dashboard
5. First deploy runs automatically

**Frontend (Vercel):**
1. Create account at vercel.com
2. Import GitHub repo
3. Set root directory to `frontend/`
4. Add `NEXT_PUBLIC_BACKEND_URL` env var pointing to Render URL
5. Deploy

---

---

# PHASE 8 PROMPT — Full Dataset (All 4 Stores, 100 Products Each)
> Copy this entire prompt into Claude Code. This phase is data-only — no new code needed.

---

## Instructions for Claude Code

Read `MASTER_SPEC.md` and `DATA_SCHEMA.md`.

You are completing the dataset. Phase 1 created 5 sample products for JB Hi-Fi. Now create the full dataset for all 4 stores, 100 products each.

---

## Deliverables

Generate the following files, each following the exact JSON schema from DATA_SCHEMA.md:

### `data/processed/jbhifi.json` (expand from 5 to 100 products)
Categories and counts per MASTER_SPEC.md.

### `data/processed/bunnings.json` (100 products)
Categories and counts per MASTER_SPEC.md.

### `data/processed/babybunting.json` (100 products)
Categories and counts per MASTER_SPEC.md.

### `data/processed/supercheapauto.json` (100 products)
Categories and counts per MASTER_SPEC.md.

---

## Data Quality Requirements

For every product:
- Use real brand names and realistic model numbers
- Prices must be realistic Australian retail prices (AUD)
- Aisle locations must be internally consistent (same aisle-section mapping per store)
- 3 FAQs minimum per product — make them genuinely useful (installation, compatibility, warranty)
- Every product must have at least 1 `compatible_with` reference and 1 `alternative` reference
- `stock_status` should be varied: ~70% in_stock, ~20% low_stock, ~10% out_of_stock
- Specifications must be realistic for the product type

For every store:
- 8 policies: returns, warranty, price_match, loyalty, layby, delivery, privacy, trade_in
- Opening hours consistent with real Australian retail hours
- Store address: use a real suburb but a fictional street address

---

## After Generating

Run:
```bash
python scripts/validate_data.py
python scripts/ingest_all.py
```

Both must complete with zero errors before this phase is considered done.
