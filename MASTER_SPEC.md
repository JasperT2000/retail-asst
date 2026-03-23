# MASTER_SPEC.md — Retail AI Store Assistant
> Claude Code: Read this file at the start of every session before writing any code.

---

## Project Overview

A web-based AI assistant for retail stores, accessible via QR code at store entrance. Customers can type or speak queries about products, pricing, availability, aisle locations, store policies, and more. The system uses a hybrid Graph + Vector RAG pipeline backed by Neo4j. When the model lacks confidence or a query involves payments or live demos, a human agent is notified via Slack.

The app is deployed publicly on the web for LinkedIn portfolio demonstration. It must look and feel production-grade.

---

## Goals

1. Demonstrate AI/LLM/RAG engineering skills for a LinkedIn portfolio
2. Show Graph RAG vs Vector RAG vs Baseline benchmarking with measurable improvement
3. Real-time streaming responses (text + voice)
4. CI/CD pipeline with monitoring via Langfuse
5. Stay within $15 total cloud spend

---

## Stores in Scope

All four stores are supported. At any time, the app serves ONE selected store. The store context filters all graph queries and retrieval.

| Store | Slug |
|---|---|
| JB Hi-Fi | `jbhifi` |
| Bunnings Warehouse | `bunnings` |
| Baby Bunting | `babybunting` |
| Supercheap Auto | `supercheapauto` |

---

## Tech Stack — Non-Negotiable

| Layer | Technology | Notes |
|---|---|---|
| Graph + Vector DB | Neo4j AuraDB Free | Single DB for both graph traversal and vector search |
| LLM (primary) | Groq — `llama-3.3-70b-versatile` | Streaming via SSE |
| LLM (fallback) | Google Gemini 2.0 Flash | Used when Groq rate limits hit |
| Embeddings | OpenAI `text-embedding-3-small` | One-time ingestion cost only |
| RAG Framework | LlamaIndex | Neo4j + Graph RAG integrations |
| Backend | FastAPI (Python) | Async, SSE streaming endpoint |
| Frontend | Next.js 14 (App Router) | TypeScript, Tailwind CSS |
| Voice STT | Web Speech API (browser-native) | No API cost |
| Voice TTS | Browser SpeechSynthesis API | No API cost |
| Human-in-Loop | Slack Incoming Webhook | Fires on low confidence or escalation triggers |
| Monitoring | Langfuse (cloud free tier) | Traces every LLM call |
| Benchmarking | RAGAS | Evaluates faithfulness, relevancy, precision, recall |
| Package Manager | pip + requirements.txt | |
| CI/CD | GitHub Actions | Lint → eval → deploy |
| Frontend Deploy | Vercel | Free tier |
| Backend Deploy | Render | Free tier (web service) |

---

## Repository Structure

```
retail-ai-assistant/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── requirements.txt
│   ├── .env.example
│   ├── api/
│   │   ├── chat.py              # SSE streaming chat endpoint
│   │   ├── stores.py            # Store metadata endpoint
│   │   └── health.py
│   ├── rag/
│   │   ├── pipeline.py          # Main RAG orchestrator
│   │   ├── graph_retriever.py   # Neo4j graph traversal queries
│   │   ├── vector_retriever.py  # Vector similarity search
│   │   ├── hybrid_retriever.py  # Merges graph + vector results
│   │   └── prompt_builder.py    # Builds final LLM prompt
│   ├── llm/
│   │   ├── groq_client.py       # Groq streaming client
│   │   ├── gemini_client.py     # Gemini fallback client
│   │   └── router.py            # Routes between LLMs, handles fallback
│   ├── graph/
│   │   ├── neo4j_client.py      # Neo4j connection + query helpers
│   │   ├── schema.py            # Node/relationship definitions
│   │   └── ingest.py            # Data ingestion pipeline
│   ├── monitoring/
│   │   └── langfuse_client.py   # Langfuse trace wrapper
│   ├── human_loop/
│   │   └── slack_notifier.py    # Slack webhook notifications
│   └── eval/
│       ├── benchmark.py         # RAGAS eval runner
│       ├── eval_dataset.json    # 50 Q&A eval pairs
│       └── results/             # Benchmark output JSONs
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # Store selector landing page
│   │   └── [store]/
│   │       ├── page.tsx         # Main chat interface per store
│   │       ├── products/
│   │       │   ├── page.tsx     # Category browser
│   │       │   └── [slug]/
│   │       │       └── page.tsx # Individual product page
│   │       └── policies/
│   │           └── page.tsx     # Store policies page
│   ├── components/
│   │   ├── ChatInterface.tsx    # Main chat component with SSE
│   │   ├── VoiceInput.tsx       # Web Speech API STT
│   │   ├── VoiceOutput.tsx      # Browser TTS
│   │   ├── StoreSelector.tsx    # Landing store picker
│   │   ├── ProductCard.tsx      # Product display card
│   │   ├── CategoryGrid.tsx     # Category navigation
│   │   ├── MessageBubble.tsx    # Individual chat message
│   │   └── HumanHandoff.tsx     # UI indicator when human is notified
│   └── lib/
│       ├── api.ts               # Backend API client
│       ├── sse.ts               # SSE stream handler
│       └── types.ts             # Shared TypeScript types
├── data/
│   ├── raw/                     # Scraped/collected raw data
│   │   ├── jbhifi/
│   │   ├── bunnings/
│   │   ├── babybunting/
│   │   └── supercheapauto/
│   ├── processed/               # Cleaned, structured JSON
│   │   ├── jbhifi.json
│   │   ├── bunnings.json
│   │   ├── babybunting.json
│   │   └── supercheapauto.json
│   └── schema/
│       └── product_schema.json  # JSON schema for validation
├── scripts/
│   ├── ingest_all.py            # Runs full ingestion for all stores
│   ├── validate_data.py         # Validates processed JSONs against schema
│   └── generate_embeddings.py   # Pre-computes embeddings before ingestion
├── .github/
│   └── workflows/
│       ├── ci.yml               # Lint + type check + eval on PR
│       └── deploy.yml           # Deploy on merge to main
├── docker-compose.yml           # Local dev (Neo4j local instance)
├── MASTER_SPEC.md               # This file
├── DATA_SCHEMA.md               # Graph + data schema reference
└── README.md
```

---

## Environment Variables

### Backend `.env`

```
# Neo4j AuraDB
NEO4J_URI=neo4j+s://<your-aura-instance>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-password>

# LLMs
GROQ_API_KEY=<your-groq-key>
GEMINI_API_KEY=<your-gemini-key>

# Embeddings
OPENAI_API_KEY=<your-openai-key>

# Monitoring
LANGFUSE_PUBLIC_KEY=<your-langfuse-public-key>
LANGFUSE_SECRET_KEY=<your-langfuse-secret-key>
LANGFUSE_HOST=https://cloud.langfuse.com

# Human-in-loop
SLACK_WEBHOOK_URL=<your-slack-webhook-url>

# App
CONFIDENCE_THRESHOLD=0.65
APP_ENV=production
```

### Frontend `.env.local`

```
NEXT_PUBLIC_BACKEND_URL=https://<your-render-app>.onrender.com
```

---

## API Contracts

### `POST /chat/stream`
SSE endpoint. Returns a stream of tokens.

**Request body:**
```json
{
  "store_slug": "jbhifi",
  "message": "Where can I find the Sony headphones?",
  "session_id": "uuid-string",
  "conversation_history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

**SSE Events:**
```
event: token
data: {"token": "The "}

event: token
data: {"token": "Sony "}

event: metadata
data: {"confidence": 0.87, "sources": ["product:sony-wh1000xm5"], "human_notified": false}

event: done
data: {}
```

### `GET /stores`
Returns list of available stores with metadata.

### `GET /stores/{store_slug}/categories`
Returns categories and product counts for a store.

### `GET /stores/{store_slug}/products/{product_slug}`
Returns full product detail for a single product.

---

## RAG Pipeline Logic

```
User Query
    │
    ▼
Intent Classifier (LLM call, cheap model)
    │
    ├── "product_info"     → Vector search + graph product traversal
    ├── "availability"     → Graph query on stock node
    ├── "location"         → Graph query on AisleLocation node
    ├── "policy"           → Graph query on PolicyDoc node
    ├── "recommendation"   → Vector search + ALTERNATIVE_TO graph traversal
    ├── "payment"          → Immediate human escalation
    ├── "live_demo"        → Immediate human escalation
    └── "general"          → Vector search only

    │
    ▼
Hybrid Retriever
    ├── Graph traversal (Neo4j Cypher) → structured relationship context
    └── Vector search (Neo4j vector index) → semantic similarity context
    │
    ▼
Context Merger + Re-ranker
    │
    ▼
Prompt Builder (system prompt + store context + retrieved context + history)
    │
    ▼
Confidence Scorer (checks if context is sufficient)
    ├── Score >= threshold → Stream to user
    └── Score < threshold → Stream to user + notify Slack
```

---

## Confidence Scoring

Confidence is estimated by:
1. Number of relevant nodes retrieved (more = higher)
2. Top vector similarity score (cosine distance of best match)
3. Whether the intent was matched to a specific node type

If `confidence < CONFIDENCE_THRESHOLD (0.65)`, fire Slack notification alongside streaming the response (do not block the response).

---

## Human-in-Loop Triggers

| Trigger | Action |
|---|---|
| Confidence < 0.65 | Slack alert: low confidence query |
| Intent = "payment" | Slack alert: customer wants to pay |
| Intent = "live_demo" | Slack alert: customer wants live demo |
| Any explicit "speak to human" | Slack alert: explicit escalation |

Slack message format:
```
🔔 *[STORE NAME] — Customer Query Escalation*
Type: <trigger type>
Query: "<user message>"
Session: <session_id>
Time: <timestamp AEST>
```

---

## Benchmarking

Three configurations evaluated on the same `eval/eval_dataset.json` (50 questions):

| Config | Description |
|---|---|
| `baseline` | Raw Groq LLM, no retrieval |
| `vector_rag` | LlamaIndex vector search only, no graph |
| `graph_rag` | Full hybrid Neo4j graph + vector (production config) |

Metrics (RAGAS):
- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall

Results saved to `eval/results/{config}_{timestamp}.json`. CI runs `graph_rag` eval on every PR and fails if faithfulness drops below 0.75.

---

## Frontend UX Requirements

- **Landing page:** Store selector with logo/colour per store, clean card layout
- **Chat page:** Split layout — chat on left, product knowledge panel on right
- **Voice:** Mic button toggles listening, waveform animation while active
- **Streaming:** Tokens appear word by word, not all at once
- **Human handoff indicator:** Subtle banner appears when human has been notified
- **Product pages:** Clean product detail page — image, specs, aisle badge, stock badge, FAQ accordion
- **Category pages:** Grid of product cards filterable by subcategory
- **Mobile responsive:** Must work on phone (QR scan scenario)
- **Store theming:** Each store has its own primary colour applied to UI

### Store Theme Colours
```
jbhifi:          #FFD700 (yellow) on #1a1a1a (dark)
bunnings:        #E8352A (red) on #FFFFFF
babybunting:     #F472B6 (pink) on #FFFFFF
supercheapauto:  #E8352A (red) on #1a1a1a (dark)
```

---

## Code Quality Rules (Claude Code must follow these)

- All Python files must have type hints
- All async functions must use `async/await` properly
- No hardcoded credentials anywhere — always use env vars
- All Neo4j queries must be parameterised (no string interpolation)
- Frontend components must be typed with TypeScript interfaces
- Every API endpoint must have error handling and return meaningful HTTP codes
- Logging must use Python's `logging` module, not `print()`
- Each module must have a docstring explaining its purpose

---

## Setup Instructions to Include in README

1. Clone repo
2. Create Neo4j AuraDB free instance at https://neo4j.com/cloud/aura/
3. Create Groq account + API key at https://console.groq.com
4. Create Gemini API key at https://aistudio.google.com
5. Create OpenAI account + API key at https://platform.openai.com (embedding only, ~$0.01)
6. Create Langfuse account at https://cloud.langfuse.com
7. Create Slack app + Incoming Webhook at https://api.slack.com/apps
8. Copy `.env.example` to `.env`, fill in all values
9. `pip install -r requirements.txt`
10. `python scripts/ingest_all.py`
11. `uvicorn main:app --reload`
12. Frontend: `npm install && npm run dev`
