# PHASE 3 PROMPT — FastAPI Backend with SSE Streaming
> Copy this entire prompt into Claude Code. Requires Phases 1 and 2 to be complete.

---

## Instructions for Claude Code

Read `MASTER_SPEC.md` in full. Review `backend/rag/pipeline.py` and `backend/rag/models.py` from Phase 2.

You are building Phase 3: the FastAPI backend that exposes the RAG pipeline as a streaming HTTP API.

---

## Deliverables

### 1. `backend/main.py`

FastAPI app entry point:
- Create `FastAPI` app with title, description, version
- Include all routers (chat, stores, health)
- Configure CORS to allow requests from `localhost:3000` and the Vercel frontend domain (use env var `ALLOWED_ORIGINS`)
- Lifespan handler: connect to Neo4j on startup, close on shutdown
- Global exception handler: return `{"error": "Internal server error"}` with 500 (never expose stack traces in production)
- Startup log: print ASCII banner with app name and env

### 2. `backend/api/health.py`

`GET /health`
```json
{"status": "ok", "neo4j": "connected", "env": "production"}
```
Checks Neo4j connectivity. Returns 503 if Neo4j is down.

### 3. `backend/api/stores.py`

`GET /stores`
Returns all 4 stores with slug, name, primary_color, logo_url, category count, product count.

`GET /stores/{store_slug}`
Returns full store info including opening hours, address, phone.

`GET /stores/{store_slug}/categories`
Returns categories for a store, each with product count.

`GET /stores/{store_slug}/products`
Query params: `category_slug` (optional), `page` (default 1), `page_size` (default 20)
Returns paginated product list with name, slug, price, image_url, stock_status, short_description.

`GET /stores/{store_slug}/products/{product_slug}`
Returns full product detail including specs, FAQs, aisle location, compatible_with list, alternatives list.

### 4. `backend/api/chat.py`

`POST /chat/stream`

SSE streaming endpoint. This is the most important endpoint.

Request body (Pydantic):
```python
class ChatRequest(BaseModel):
    store_slug: str
    message: str
    session_id: str
    conversation_history: list[ChatMessage] = []
```

Response: `text/event-stream`

SSE event format:
```
event: token
data: {"token": "..."}

event: metadata
data: {"confidence": 0.87, "sources": [...], "human_notified": false, "intent": "location"}

event: error
data: {"message": "..."}

event: done
data: {}
```

Implementation:
- Use `fastapi.responses.StreamingResponse` with `media_type="text/event-stream"`
- Call `RAGPipeline(store_slug).run(...)` and yield tokens
- After streaming completes, send the `metadata` event
- Always send `done` event at the end, even on error
- Set headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`
- Validate `store_slug` — return 422 if store not found

Input validation:
- `message` max length: 500 characters
- `conversation_history` max: 10 turns (trim older turns if more)
- `store_slug` must be one of the 4 valid slugs

### 5. `backend/api/middleware.py`

- Request ID middleware: attach `X-Request-ID` header to every response (UUID)
- Request logging middleware: log method, path, status code, duration in ms
- Rate limiting: max 30 requests/minute per IP (use simple in-memory counter, good enough for demo)

---

## Error Handling Rules

| Scenario | HTTP Code | Response |
|---|---|---|
| Store not found | 404 | `{"error": "Store not found"}` |
| Message too long | 422 | `{"error": "Message exceeds 500 characters"}` |
| Neo4j down | 503 | `{"error": "Service temporarily unavailable"}` |
| LLM error | 500 | SSE error event then done event |
| Rate limited | 429 | `{"error": "Too many requests"}` |

---

## Constraints

- CORS must be properly configured (frontend will call from different origin)
- SSE endpoint must set correct headers to prevent buffering
- Never expose internal error details in responses (log them server-side)
- All endpoints must have Pydantic response models
- Include OpenAPI docstring on every endpoint
- The SSE endpoint must handle client disconnection gracefully (catch `asyncio.CancelledError`)

---

## Test

```bash
uvicorn main:app --reload --port 8000
```

Then test with curl:
```bash
# Health check
curl http://localhost:8000/health

# Get stores
curl http://localhost:8000/stores

# Stream chat
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"store_slug":"jbhifi","message":"Where are the Sony headphones?","session_id":"test-1","conversation_history":[]}'
```

Expected: tokens stream in real time, metadata event fires after, done event closes stream.
