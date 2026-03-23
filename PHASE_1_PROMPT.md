# PHASE 1 PROMPT — Repo Setup, Neo4j Schema & Data Ingestion Pipeline
> Copy this entire prompt into Claude Code to begin Phase 1.

---

## Instructions for Claude Code

First, read `MASTER_SPEC.md` and `DATA_SCHEMA.md` in full before writing any code.

You are building Phase 1 of the Retail AI Store Assistant project. Your job in this phase is:

1. Set up the complete repository folder structure as defined in MASTER_SPEC.md
2. Set up the Neo4j graph schema (constraints + vector indexes)
3. Build the data ingestion pipeline that reads processed JSON files and populates Neo4j
4. Build a data validation script
5. Create a sample dataset for ONE store (JB Hi-Fi, 5 products only) so the pipeline can be tested immediately

---

## Deliverables

### 1. Repository Structure
Create all folders and placeholder files as per MASTER_SPEC.md. Every Python file should have a docstring. Every folder should have a `__init__.py` where appropriate.

### 2. `backend/requirements.txt`
Include exact pinned versions for:
- `fastapi`
- `uvicorn[standard]`
- `neo4j` (official Python driver)
- `llama-index`
- `llama-index-graph-stores-neo4j`
- `llama-index-vector-stores-neo4j`
- `openai`
- `groq`
- `google-generativeai`
- `langfuse`
- `ragas`
- `python-dotenv`
- `pydantic`
- `httpx`
- `tenacity` (for retry logic)
- `structlog`

### 3. `backend/.env.example`
All env vars from MASTER_SPEC.md with placeholder values and a comment explaining where to get each key.

### 4. `backend/graph/neo4j_client.py`
- `Neo4jClient` class with async connection management
- `connect()`, `close()`, `execute_query(query, params)` methods
- Connection must use the `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` env vars
- Include retry logic with `tenacity` (3 retries, exponential backoff)
- Proper logging with `structlog`

### 5. `backend/graph/schema.py`
- `setup_schema(client: Neo4jClient)` async function
- Runs ALL the `CREATE CONSTRAINT` and `CREATE VECTOR INDEX` Cypher statements from DATA_SCHEMA.md
- Idempotent — safe to run multiple times (use `IF NOT EXISTS`)
- Logs each step

### 6. `backend/graph/ingest.py`
- `StoreIngester` class
- `load_store_json(filepath: str) -> dict` — loads and validates a processed JSON file
- `ingest_store(data: dict)` — main ingestion method, calls sub-methods below
- `_ingest_store_node(store: dict)`
- `_ingest_categories(categories: list, store_slug: str)`
- `_ingest_products(products: list, store_slug: str)` — creates Product nodes + AisleLocation nodes
- `_ingest_policies(policies: list, store_slug: str)`
- `_ingest_faqs(product: dict, store_slug: str)`
- `_ingest_relationships(products: list)` — creates COMPATIBLE_WITH, ALTERNATIVE_TO, BOUGHT_WITH relationships
- `_compute_and_attach_embeddings(items: list, node_type: str)` — calls OpenAI text-embedding-3-small, attaches to nodes
- All Cypher queries must use MERGE (not CREATE) so re-ingestion is safe
- Batch embedding calls (max 100 items per API call)
- Progress logging at each step

### 7. `scripts/ingest_all.py`
- Iterates over all 4 store JSON files in `data/processed/`
- Calls `StoreIngester` for each
- Reports total nodes created, relationships created, embeddings computed
- Accepts `--store` flag to ingest a single store: `python ingest_all.py --store jbhifi`

### 8. `scripts/validate_data.py`
- Validates every JSON in `data/processed/` against the schema in DATA_SCHEMA.md
- Checks: required fields present, price is positive float, stock_status is valid enum, all `compatible_with` and `alternatives` slugs exist in the same dataset
- Prints a clear pass/fail report per store

### 9. `data/processed/jbhifi.json` — Sample Data (5 products only for testing)
Create a realistic sample with exactly these products:
- Apple MacBook Air M3 13-inch
- Sony WH-1000XM5 Headphones
- Samsung 65" QLED TV QN65Q80C
- PlayStation 5 Console (Disc Edition)
- Apple iPhone 15 Pro 256GB

Each must have:
- Correct schema structure from DATA_SCHEMA.md
- 3 FAQs per product
- Realistic aisle locations (Aisle 1–5, Bay 1–15)
- At least 1 compatible_with and 1 alternative relationship per product
- Realistic Australian pricing (check approximate real prices)

Also include:
- 3 policies: returns, price_match, warranty
- All 6 categories (even if some have 0 products for now)
- Store node with Melbourne Central store details

### 10. `docker-compose.yml`
Local Neo4j instance for development:
```yaml
# Neo4j Community Edition for local dev
# Production uses Neo4j AuraDB Free
```
Port 7474 (browser), 7687 (bolt). Include neo4j browser accessible at localhost:7474.

### 11. `README.md`
Full setup instructions from MASTER_SPEC.md, formatted clearly with code blocks for every command.

---

## Constraints

- No hardcoded credentials
- All Neo4j Cypher queries must be parameterised
- The ingestion pipeline must be idempotent (safe to run twice without duplicates)
- Type hints on every function
- Every class and function must have a docstring
- Use `structlog` for all logging, not `print()`

---

## Test Command

After building, the following must work without errors:

```bash
cd backend
cp .env.example .env  # (user fills in their keys)
pip install -r requirements.txt
python scripts/validate_data.py
python scripts/ingest_all.py --store jbhifi
```

Expected output of ingest:
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
