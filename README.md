# Retail AI Store Assistant

A web-based AI assistant for retail stores, accessible via QR code at the store entrance. Customers can type or speak queries about products, pricing, availability, aisle locations, and store policies. Powered by a hybrid **Graph + Vector RAG** pipeline backed by Neo4j AuraDB.

Built as a LinkedIn portfolio project demonstrating AI/LLM/RAG engineering with measurable benchmarks.

---

## Features

- **Hybrid RAG** — Neo4j graph traversal + vector similarity search for richer context
- **Streaming responses** — SSE token-by-token streaming via Groq (llama-3.3-70b) with Gemini fallback
- **Voice I/O** — Web Speech API (STT) + SpeechSynthesis (TTS), no API cost
- **Human-in-the-loop** — Slack alerts on low confidence, payment intent, or escalation triggers
- **Multi-store** — JB Hi-Fi, Bunnings, Baby Bunting, Supercheap Auto, each with store-specific theming
- **RAGAS benchmarking** — baseline vs. vector RAG vs. graph RAG comparison
- **CI/CD** — GitHub Actions lint → eval → deploy pipeline

---

## Stores Supported

| Store | Slug |
|---|---|
| JB Hi-Fi | `jbhifi` |
| Bunnings Warehouse | `bunnings` |
| Baby Bunting | `babybunting` |
| Supercheap Auto | `supercheapauto` |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Graph + Vector DB | Neo4j AuraDB Free |
| LLM (primary) | Groq — `llama-3.3-70b-versatile` |
| LLM (fallback) | Google Gemini 2.0 Flash |
| Embeddings | OpenAI `text-embedding-3-small` |
| RAG Framework | LlamaIndex |
| Backend | FastAPI (Python, async) |
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind) |
| Voice STT/TTS | Web Speech API + SpeechSynthesis (browser-native) |
| Human-in-Loop | Slack Incoming Webhook |
| Monitoring | Langfuse |
| Benchmarking | RAGAS |
| Backend Deploy | Render (free tier) |
| Frontend Deploy | Vercel (free tier) |

---

## Setup

### Prerequisites

1. **Neo4j AuraDB** — Create a free instance at https://neo4j.com/cloud/aura/
2. **Groq API key** — https://console.groq.com (free tier available)
3. **Google Gemini API key** — https://aistudio.google.com (free tier available)
4. **OpenAI API key** — https://platform.openai.com (embeddings only, ~$0.01 total)
5. **Langfuse account** — https://cloud.langfuse.com (free cloud tier)
6. **Slack Incoming Webhook** — https://api.slack.com/apps → Create App → Incoming Webhooks

---

### Backend Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-username/retail-ai-assistant.git
cd retail-ai-assistant

# 2. Set up Python environment (Python 3.12 recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install backend dependencies
pip install -r backend/requirements.txt

# 4. Configure environment variables
cp backend/.env.example backend/.env
# Edit backend/.env and fill in all values

# 5. Validate the sample data
python scripts/validate_data.py

# 6. Ingest JB Hi-Fi sample data (5 products)
python scripts/ingest_all.py --store jbhifi

# 7. Start the backend
cd backend
uvicorn main:app --reload --port 8000
```

Expected ingest output:
```
✓ Connected to Neo4j
✓ Schema setup complete
  ✓ Ingested store: JB Hi-Fi
    ✓ Ingested 6 categories
    ✓ Ingested 5 products
    ✓ Ingested 3 policies
    ✓ Ingested 15 FAQs
    ✓ Created 8 relationships
    ✓ Computed and attached 26 embeddings
✓ Done. Total time: Xs
```

---

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Set NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Run development server
npm run dev
```

Open http://localhost:3000 in your browser.

---

### Local Neo4j (optional, for development without AuraDB)

```bash
# Start local Neo4j via Docker
docker compose up -d

# Neo4j Browser: http://localhost:7474
# Bolt URL for .env: bolt://localhost:7687
# Default credentials: neo4j / devpassword
```

---

## Ingesting All Stores

```bash
# Ingest all 4 stores (requires all 4 processed JSON files in data/processed/)
python scripts/ingest_all.py

# Ingest a specific store
python scripts/ingest_all.py --store bunnings
```

---

## Running Benchmarks

```bash
# Run full benchmark (all 3 configs) and print comparison table
python scripts/run_benchmark.py --report

# Run a single config
python scripts/run_benchmark.py --config graph_rag

# Print the latest results without re-running
python scripts/run_benchmark.py --report-only
```

Results are saved to `backend/eval/results/`. The comparison table shows
faithfulness, answer relevancy, context precision, and context recall for
baseline vs. vector RAG vs. graph RAG, plus the improvement delta.

---

## API Reference

### `POST /chat/stream`

SSE streaming chat endpoint.

**Request body:**
```json
{
  "store_slug": "jbhifi",
  "message": "Where can I find Sony headphones?",
  "session_id": "uuid-string",
  "conversation_history": []
}
```

**SSE Events:**
```
event: token
data: {"token": "Sony "}

event: metadata
data: {"confidence": 0.87, "sources": ["jbhifi-sony-wh1000xm5"], "human_notified": false, "intent": "location"}

event: done
data: {}
```

### `GET /stores`
Returns available stores.

### `GET /stores/{store_slug}/categories`
Returns categories with product counts.

### `GET /stores/{store_slug}/products/{product_slug}`
Returns full product detail including FAQs, location, and related products.

### `GET /health`
Returns `{"status": "ok"}`.

---

## Project Structure

```
retail-ai-assistant/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── requirements.txt
│   ├── .env.example
│   ├── api/                     # Route handlers
│   ├── rag/                     # RAG pipeline components
│   ├── llm/                     # LLM clients (Groq + Gemini)
│   ├── graph/                   # Neo4j client, schema, ingestion
│   ├── monitoring/              # Langfuse tracing
│   ├── human_loop/              # Slack notifications
│   └── eval/                    # RAGAS benchmark runner + dataset
├── frontend/                    # Next.js 14 app
├── data/
│   ├── processed/               # Processed store JSON files
│   └── schema/                  # JSON schema for validation
├── scripts/                     # CLI tools: ingest, validate, embeddings
├── docker-compose.yml           # Local Neo4j
└── .github/workflows/           # CI/CD pipelines
```

---

## Environment Variables

See `backend/.env.example` for the full list with descriptions.

---

## Deployment

### Backend → Render (Free Tier)

1. Push the repo to GitHub.
2. Go to [render.com](https://render.com) → **New** → **Blueprint** → connect your repo.
   Render will detect `render.yaml` automatically and create the service.
3. In the Render dashboard, set all secret environment variables under **Environment**:
   - `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
   - `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`
   - `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
   - `SLACK_WEBHOOK_URL` (optional)
   - `ALLOWED_ORIGINS` — set to your Vercel frontend URL (e.g. `https://retail-ai.vercel.app`)
   - `MONITOR_PIN` — optional PIN for the `/monitoring` dashboard
4. Render will build from `backend/Dockerfile` and deploy on every push to `main`.
5. The service URL will be something like `https://retail-ai-backend.onrender.com`.
   - Free tier spins down after 15 minutes of inactivity (cold start ~30s).

### Frontend → Vercel (Free Tier)

1. Go to [vercel.com](https://vercel.com) → **New Project** → import your GitHub repo.
2. Set **Root Directory** to `frontend/`.
3. Add environment variable:
   - `NEXT_PUBLIC_BACKEND_URL` = `https://retail-ai-backend.onrender.com`
4. Vercel reads `frontend/vercel.json` for headers and API rewrites automatically.
5. Deploy — the live URL will be your portfolio link.

### GitHub Actions CI/CD

The `.github/workflows/ci.yml` pipeline runs on every PR:
- Lint (ruff) + type check (mypy)
- Data validation
- RAGAS eval on `graph_rag` config with faithfulness ≥ 0.75 gate

The `.github/workflows/deploy.yml` pipeline runs on push to `main`:
- Triggers the Render deploy hook (set `RENDER_DEPLOY_HOOK_URL` in GitHub Secrets)
- Deploys frontend to Vercel (set `VERCEL_TOKEN` and `NEXT_PUBLIC_BACKEND_URL` in GitHub Secrets)

Required GitHub Secrets:
```
NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY
LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
RENDER_DEPLOY_HOOK_URL
VERCEL_TOKEN
NEXT_PUBLIC_BACKEND_URL
```

---

## Contributing

This is a portfolio project. Feel free to fork and adapt for your own use.
