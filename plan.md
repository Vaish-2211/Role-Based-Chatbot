# FinSolve RAG-RBAC Chatbot — Implementation Plan

> **Purpose:** Reference document to build a production-grade RAG chatbot with Role-Based Access Control.  
> Keep this open while coding. Check off tasks as you complete them. Do not deviate from the phases.

---

## 1. Problem Summary

FinSolve Technologies needs a chatbot where employees from different departments can query
company data in natural language — but each role must only see data they are authorized to access.

| Role | What they can query |
|---|---|
| `c_level` | Everything — all departments |
| `finance` | Financial reports, quarterly summaries + general policies |
| `marketing` | Campaign data, marketing reports + general policies |
| `hr` | Employee records (CSV), handbook + general policies |
| `engineering` | Technical architecture, engineering docs + general policies |
| `employee` | General policies, handbook FAQs only |

---

## 2. Architectural Improvements (over naive RAG)

These are deliberate decisions that make this production-grade. Understand each one.

| # | What | Why It Matters |
|---|---|---|
| 1 | **RBAC filter at vector DB layer** (Qdrant `must` filter) | Security-first: a Finance user physically cannot retrieve HR chunks — not just hidden in UI |
| 2 | **Hybrid retrieval** (Dense + BM25 + CrossEncoder rerank) | Dense alone misses exact keyword matches (e.g., "$2.4M Q3 revenue"). BM25 catches them. Reranker re-scores for final precision |
| 3 | **Streaming responses** (FastAPI SSE + Streamlit `st.write_stream`) | 70B model is slow. Users see tokens as they generate — critical for UX |
| 4 | **Multi-turn conversation history** (`RunnableWithMessageHistory`) | Enables follow-up queries: "What about Q3?" without repeating context |
| 5 | **Async-first** (`await chain.ainvoke()` throughout) | FastAPI is async. Sync calls block the event loop under concurrent users |
| 6 | **RAGAS TestsetGenerator** | Auto-generates evaluation Q&A from your actual documents — far better than manual golden sets |
| 7 | **PII Middleware** on HR outputs | Extra safety net: redacts names/emails/salaries even if something bypasses RBAC |
| 8 | **HR CSV dual-path** (semantic chunks + Pandas agent) | Semantic search answers "who works in engineering"; Pandas agent answers "average salary in HR dept" |

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        STREAMLIT FRONTEND                            │
│   Login Page ──► JWT in session_state ──► Chat UI (streaming)       │
│   Role Badge │ Message History │ Source Citations (st.expander)     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTP + JWT Bearer Token
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND  /api/v1/                       │
│                                                                      │
│  Middleware Stack (in order):                                        │
│  1. Rate Limiter (slowapi)                                           │
│  2. Request Logger (loguru + request_id)                             │
│  3. CORS Handler                                                     │
│  4. JWT Auth Dependency                                              │
│  5. Input Guardrail (prompt injection, length check)                 │
│                                                                      │
│  Routes:                                                             │
│  POST /auth/login    POST /auth/refresh                              │
│  POST /chat          GET  /chat/history                              │
│  GET  /health        GET  /ready                                     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ user_role + query
                               ▼
                    ┌──────────────────────┐
                    │    Query Router       │
                    │  (LLM classifier:    │
                    │   semantic vs        │
                    │   analytics)         │
                    └────────┬─────┬───────┘
                             │     │
               Semantic path │     │ Analytics path (HR + C-Level only)
                             │     │
              ┌──────────────▼─┐  ┌▼─────────────────┐
              │   RAG Chain     │  │  Pandas Agent     │
              │   (LCEL)        │  │  (hr_data.csv)    │
              └──────────┬──────┘  └──────────┬────────┘
                         │                    │
              ┌──────────▼──────────┐         │
              │  Hybrid Retriever   │         │
              │  ┌───────────────┐  │         │
              │  │ Qdrant Dense  │  │         │
              │  │ (RBAC filter) │  │         │
              │  └───────┬───────┘  │         │
              │  ┌───────▼───────┐  │         │
              │  │  BM25 Sparse  │  │         │
              │  └───────┬───────┘  │         │
              │  ┌───────▼───────┐  │         │
              │  │  Ensemble     │  │         │
              │  │  (0.6 + 0.4)  │  │         │
              │  └───────┬───────┘  │         │
              │  ┌───────▼───────┐  │         │
              │  │ CrossEncoder  │  │         │
              │  │  Reranker     │  │         │
              │  │  (top-5)      │  │         │
              │  └───────────────┘  │         │
              └──────────┬──────────┘         │
                         │                    │
              ┌──────────▼────────────────────▼──────┐
              │        Groq LLM (Llama 3.3-70B)       │
              │   + Conversation History               │
              │   + Citation prompt template           │
              └──────────────────┬────────────────────┘
                                 │
              ┌──────────────────▼────────────────────┐
              │  Output Guardrail (PII Middleware)     │
              │  LangSmith Trace                       │
              └────────────────────────────────────────┘
```

---

## 4. Data Flow — Document Ingestion (One-Time)

```
resources/data/
  ├── finance/*.md     ──► TextLoader ──► MarkdownHeaderSplitter ──► chunks
  ├── marketing/*.md   ──► TextLoader ──► MarkdownHeaderSplitter ──► chunks
  ├── engineering/*.md ──► TextLoader ──► MarkdownHeaderSplitter ──► chunks
  ├── general/*.md     ──► TextLoader ──► MarkdownHeaderSplitter ──► chunks
  └── hr/hr_data.csv   ──► pandas ──► row-to-text converter ──► chunks

Each chunk gets metadata:
  {
    "source_file": "quarterly_financial_report.md",
    "department":  "finance",
    "allowed_roles": ["finance", "c_level"],   ← RBAC tag
    "section":     "Q3 Performance",
    "chunk_id":    "<uuid>",
    "doc_type":    "markdown"  or  "csv"
  }

  ──► HuggingFace Embedder (BAAI/bge-large-en-v1.5)
  ──► Qdrant Collection ("finsolve_docs")
       └── Payload index on `allowed_roles` for fast filtering
```

---

## 5. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| LLM | Groq API — `llama-3.3-70b-versatile` | Free tier, fast |
| LLM (router) | Groq API — `llama-3.1-8b-instant` | Cheap + fast for classification |
| Embeddings | `BAAI/bge-large-en-v1.5` via HuggingFace | Local, free, 1024-dim |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local cross-encoder |
| Vector DB | Qdrant (Docker locally, Qdrant Cloud in prod) | Supports payload metadata filtering |
| Framework | LangChain (LCEL) | Chains, agents, history, RAGAS compat |
| Backend | FastAPI + Pydantic v2 | Async-native |
| Auth | `python-jose` (JWT) + `passlib[bcrypt]` | Hardcoded users, bcrypt-hashed passwords |
| Rate limiting | `slowapi` | Per-IP |
| Logging | `loguru` | Structured, request_id correlation |
| Frontend | Streamlit | `st.chat_message` + `st.write_stream` |
| Evaluation | RAGAS | `TestsetGenerator` + `evaluate()` |
| Monitoring | LangSmith | `LANGCHAIN_TRACING_V2=true` |
| Config | `pydantic-settings` | `.env` file |
| Containerization | Docker Compose | Qdrant + backend + frontend |
| Cloud | GCP Cloud Run | Deployment guide only |
| CI | GitHub Actions | ruff lint + pytest |

---

## 6. Project Structure

```
finsolve-rag/
│
├── app/                          # FastAPI application
│   ├── __init__.py
│   ├── main.py                   # App factory, middleware, router registration
│   │
│   ├── api/                      # Route handlers
│   │   ├── __init__.py
│   │   ├── auth.py               # POST /auth/login, POST /auth/refresh
│   │   ├── chat.py               # POST /chat (streaming), GET /chat/history
│   │   └── health.py             # GET /health, GET /ready
│   │
│   ├── auth/                     # Authentication logic
│   │   ├── __init__.py
│   │   ├── jwt_handler.py        # create_token(), decode_token()
│   │   ├── users.json            # Hardcoded users (bcrypt-hashed passwords)
│   │   └── dependencies.py      # FastAPI get_current_user dependency
│   │
│   ├── core/                     # Shared config and constants
│   │   ├── __init__.py
│   │   ├── settings.py           # pydantic-settings: all env vars
│   │   ├── rbac.py               # Role enum, ROLE_ACCESS dict, access check fn
│   │   └── constants.py          # Collection name, model names, chunk sizes
│   │
│   ├── ingestion/                # Document processing pipeline
│   │   ├── __init__.py
│   │   ├── loader.py             # Load .md files + hr_data.csv
│   │   ├── chunker.py            # Split + attach metadata
│   │   ├── embedder.py           # HuggingFace embeddings singleton
│   │   └── indexer.py            # Create Qdrant collection + upload
│   │
│   ├── retrieval/                # RAG retrieval components
│   │   ├── __init__.py
│   │   ├── qdrant_retriever.py   # Dense retriever with RBAC filter
│   │   ├── bm25_retriever.py     # Sparse keyword retriever
│   │   ├── ensemble.py           # EnsembleRetriever (dense + sparse)
│   │   ├── reranker.py           # CrossEncoderReranker, top-5
│   │   └── router.py             # LLM query classifier: semantic vs analytics
│   │
│   ├── chains/                   # LangChain LCEL chains
│   │   ├── __init__.py
│   │   ├── prompts.py            # System prompt + citation template
│   │   ├── rag_chain.py          # Main RAG chain with history support
│   │   └── pandas_agent.py       # Pandas agent for HR CSV analytics
│   │
│   ├── guardrails/               # Input/output safety
│   │   ├── __init__.py
│   │   ├── input_guard.py        # Prompt injection detection, length limit
│   │   └── output_guard.py       # PII middleware wrapper
│   │
│   └── models/                   # Pydantic schemas
│       ├── __init__.py
│       └── schemas.py            # LoginRequest, ChatRequest, ChatResponse, Source
│
├── frontend/
│   └── streamlit_app.py          # Login + Chat UI
│
├── evaluation/
│   ├── generate_testset.py       # RAGAS TestsetGenerator from documents
│   ├── run_eval.py               # RAGAS evaluate() runner
│   └── testsets/                 # Auto-generated Q&A per role (gitignored initially)
│       ├── finance_testset.json
│       ├── marketing_testset.json
│       ├── hr_testset.json
│       ├── engineering_testset.json
│       └── employee_testset.json
│
├── tests/
│   ├── unit/
│   │   ├── test_auth.py          # JWT encode/decode, bcrypt verify
│   │   ├── test_rbac.py          # access_check() for all role combinations
│   │   ├── test_chunker.py       # Chunk count, metadata presence
│   │   └── test_input_guard.py   # Injection pattern detection
│   └── integration/
│       └── test_chat_api.py      # Full login → chat flow per role
│
├── scripts/
│   └── ingest.py                 # One-shot: load → chunk → embed → index
│
├── resources/                    # Source documents (existing)
│   └── data/
│       ├── finance/
│       ├── marketing/
│       ├── engineering/
│       ├── general/
│       └── hr/
│
├── docker-compose.yml
├── Dockerfile.app
├── Dockerfile.frontend
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 7. RBAC Access Matrix (Exact Mapping)

```python
ROLE_ACCESS = {
    "c_level":     ["finance", "marketing", "hr", "engineering", "general"],
    "finance":     ["finance", "general"],
    "marketing":   ["marketing", "general"],
    "hr":          ["hr", "general"],
    "engineering": ["engineering", "general"],
    "employee":    ["general"],
}
```

Each document chunk is tagged with `allowed_roles` — the list of roles permitted to retrieve it.
Qdrant filter: `must: {key: "allowed_roles", match: {any: [user_role]}}`

---

## 8. Hardcoded Test Users

Stored in `app/auth/users.json`. Passwords are **bcrypt-hashed** (never plaintext).

| username | role | password (plain — for testing only) |
|---|---|---|
| `tony_sharma` | `c_level` | `tony@123` |
| `alice_finance` | `finance` | `alice@123` |
| `bob_marketing` | `marketing` | `bob@123` |
| `carol_hr` | `hr` | `carol@123` |
| `dave_eng` | `engineering` | `dave@123` |
| `eve_employee` | `employee` | `eve@123` |

---

## 9. Key Implementation Details

### 9.1 Chunking Strategy

**Markdown files:**
```
MarkdownHeaderTextSplitter(headers_to_split_on=[("#","H1"),("##","H2"),("###","H3")])
  → RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
```
Preserves section context in each chunk so the LLM knows what section a fact came from.

**CSV rows (hr_data.csv):**
Each row becomes a sentence:
```
"Employee {full_name} (ID: {employee_id}) is a {role} in the {department} department,
 located in {location}, earning ${salary:,}/year. Attendance: {attendance_pct}%.
 Performance rating: {performance_rating}/5. Leave balance: {leave_balance} days."
```
This is what gets embedded for semantic search.

### 9.2 RAG Chain (LCEL)

```python
# Simplified structure — actual code in app/chains/rag_chain.py
chain = (
    RunnableParallel({
        "context": retriever | format_docs_with_sources,
        "question": RunnablePassthrough(),
        "history":  RunnablePassthrough(),
    })
    | prompt          # SystemMessage with role + context + citation instructions
    | llm             # ChatGroq(model="llama-3.3-70b-versatile", streaming=True)
    | StrOutputParser()
)

# Wrapped with history support:
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,   # returns InMemoryChatMessageHistory by session_id
    input_messages_key="question",
    history_messages_key="history",
)
```

### 9.3 System Prompt Template

```
You are FinSolve's internal AI assistant.
The user is authenticated as role: {role}.
Answer ONLY using the context provided below. Do not use prior knowledge.
For every fact you state, cite the source inline as: [Source: <filename>, Section: <section>]
If the answer is not in the context, respond: "I don't have access to that information."
Do not reveal data from departments outside the user's access level.

Context:
{context}

Conversation history:
{history}

Question: {question}
```

### 9.4 Streaming (FastAPI → Streamlit)

**FastAPI** returns `StreamingResponse` using generator:
```python
async def stream_tokens(chain, input, config):
    async for chunk in chain.astream(input, config=config):
        yield f"data: {chunk}\n\n"   # SSE format

return StreamingResponse(stream_tokens(...), media_type="text/event-stream")
```

**Streamlit** consumes it:
```python
with st.chat_message("assistant"):
    response = st.write_stream(fetch_stream(query, jwt_token))
```

### 9.5 Query Router

Uses a fast small model (`llama-3.1-8b-instant`) to classify:
```
Is the following query asking for aggregated analytics (average, total, count, top-N, list all)?
Or is it a semantic/conceptual question?
Reply with only: ANALYTICS or SEMANTIC

Query: {query}
```
- `ANALYTICS` + role in `[hr, c_level]` → Pandas Agent  
- Everything else → RAG Chain

### 9.6 Guardrails

**Input Guard** (before chain):
- Reject queries > 1000 characters
- Block prompt injection patterns: `ignore previous instructions`, `system:`, `<|im_start|>`, etc.
- Strip leading/trailing control characters

**Output Guard** (after chain — PII Middleware):
- Redact email patterns: `[REDACTED_EMAIL]`
- Redact phone patterns: `[REDACTED_PHONE]`
- Applied to all non-HR, non-C-Level roles as extra safety net

---

## 10. Implementation Phases & Checklist

### Phase 1 — Foundation
> **Learn:** Python project structure, pydantic-settings, JWT auth, bcrypt

- [ ] Create `finsolve-rag/` folder structure (all directories)
- [ ] `requirements.txt` — pin all dependencies
- [ ] `.env.example` — template with all required env vars
- [ ] `app/core/settings.py` — `Settings` class with pydantic-settings
- [ ] `app/core/rbac.py` — `Role` enum, `ROLE_ACCESS` dict, `has_access(role, department)` fn
- [ ] `app/core/constants.py` — model names, collection name, chunk sizes
- [ ] `app/auth/users.json` — 6 users, bcrypt-hashed passwords
- [ ] `app/auth/jwt_handler.py` — `create_access_token()`, `decode_token()`
- [ ] `app/auth/dependencies.py` — `get_current_user` FastAPI dependency
- [ ] `app/models/schemas.py` — all Pydantic v2 request/response models
- [ ] `docker-compose.yml` — Qdrant service (port 6333) + placeholder backend + frontend
- [ ] **Verify:** `pytest tests/unit/test_auth.py` passes

---

### Phase 2 — Ingestion Pipeline
> **Learn:** LangChain document loaders, text splitters, HuggingFace embeddings, Qdrant collections, metadata filtering

- [ ] `app/ingestion/loader.py` — load all .md files + hr_data.csv with proper metadata tagging
- [ ] `app/ingestion/chunker.py` — `MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter`; CSV row-to-text converter
- [ ] `app/ingestion/embedder.py` — singleton `HuggingFaceEmbeddings("BAAI/bge-large-en-v1.5")`
- [ ] `app/ingestion/indexer.py` — create Qdrant collection with `allowed_roles` payload index; batch upsert
- [ ] `scripts/ingest.py` — orchestrates loader → chunker → embedder → indexer
- [ ] **Verify:** `python scripts/ingest.py` completes; open `localhost:6333/dashboard` → confirm chunk count and metadata

---

### Phase 3 — Retrieval + RAG Chain
> **Learn:** Qdrant filtering, BM25, EnsembleRetriever, CrossEncoder, LCEL composition, RunnableWithMessageHistory

- [ ] `app/retrieval/qdrant_retriever.py` — `QdrantVectorStore` + `must` filter on `allowed_roles`
- [ ] `app/retrieval/bm25_retriever.py` — `BM25Retriever` initialized per role (filtered corpus)
- [ ] `app/retrieval/ensemble.py` — `EnsembleRetriever(retrievers=[dense, sparse], weights=[0.6, 0.4])`
- [ ] `app/retrieval/reranker.py` — `CrossEncoderReranker("cross-encoder/ms-marco-MiniLM-L-6-v2", top_n=5)`
- [ ] `app/retrieval/router.py` — LLM-based classifier (llama-3.1-8b-instant): SEMANTIC vs ANALYTICS
- [ ] `app/chains/prompts.py` — system prompt template with role, context, history, citation instructions
- [ ] `app/chains/rag_chain.py` — LCEL chain + `RunnableWithMessageHistory`; returns `{answer, sources[]}`
- [ ] `app/chains/pandas_agent.py` — `create_pandas_dataframe_agent` on hr_data.csv with role guard
- [ ] **Verify:** Manual Python test — instantiate chain for each role, run 2-3 queries, confirm RBAC filter blocks cross-role data

---

### Phase 4 — Guardrails + FastAPI Backend
> **Learn:** FastAPI middleware, dependency injection, rate limiting, SSE streaming, structured logging

- [ ] `app/guardrails/input_guard.py` — injection pattern list, length check, sanitization function
- [ ] `app/guardrails/output_guard.py` — PII regex redaction for non-HR roles
- [ ] `app/api/auth.py` — `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`
- [ ] `app/api/chat.py` — `POST /api/v1/chat` (streaming SSE), `GET /api/v1/chat/history`
- [ ] `app/api/health.py` — `GET /health` (liveness), `GET /ready` (Qdrant ping)
- [ ] `app/main.py` — app factory, CORS, slowapi rate limiter, loguru request logger, router registration
- [ ] **Verify:** `uvicorn app.main:app --reload` → test all endpoints with curl/Swagger UI (`/docs`)

---

### Phase 5 — Streamlit Frontend
> **Learn:** Streamlit session state, st.chat_message, st.write_stream, HTTP streaming consumption

- [ ] `frontend/streamlit_app.py`:
  - [ ] Login page — username/password form → `POST /auth/login` → store JWT + role in `st.session_state`
  - [ ] Role badge in sidebar (color-coded by role)
  - [ ] `st.chat_input` + `st.chat_message` loop with streaming via `st.write_stream`
  - [ ] Source citations rendered in `st.expander("Sources")` after each response
  - [ ] "Clear conversation" button in sidebar
  - [ ] Logout button (clears session state)
- [ ] **Verify:** Login as all 6 roles, run cross-role queries, confirm access control in UI

---

### Phase 6 — Evaluation + Monitoring
> **Learn:** RAGAS metrics (faithfulness, context_precision, context_recall, answer_relevancy), LangSmith tracing

- [ ] Add `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_PROJECT=finsolve-rag` to `.env`; confirm LangSmith traces appear
- [ ] `evaluation/generate_testset.py` — use `ragas.testset.TestsetGenerator` on each department's docs; save to `testsets/`
- [ ] `evaluation/run_eval.py` — load testset, run RAG chain per question, call `ragas.evaluate()`; print scores
- [ ] **Target scores:** Faithfulness > 0.85 | Answer Relevancy > 0.80 | Context Precision > 0.75
- [ ] If scores are low: adjust chunk size, top-k, or prompt template; re-run

---

### Phase 7 — Docker + Cloud Deployment
> **Learn:** Docker multi-stage builds, Docker Compose networking, GCP Cloud Run

- [ ] `Dockerfile.app` — multi-stage build for FastAPI backend
- [ ] `Dockerfile.frontend` — Streamlit frontend image
- [ ] Full `docker-compose.yml` — Qdrant (with volume) + backend + frontend with env injection
- [ ] **Verify:** `docker compose up --build` → all 3 services healthy; full chat flow works in browser
- [ ] `docs/cloud-deployment.md` — GCP Cloud Run step-by-step:
  - Qdrant Cloud free tier setup
  - Build + push images to Google Artifact Registry
  - Deploy backend + frontend to Cloud Run
  - Set environment variables via Cloud Run secrets
- [ ] `.github/workflows/ci.yml` — on push: `ruff check .` + `pytest tests/unit/`

---

## 11. Environment Variables Reference

```bash
# .env.example

# LLM
GROQ_API_KEY=your_groq_api_key_here

# Vector DB
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=finsolve_docs

# Auth
JWT_SECRET_KEY=your-very-long-random-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# LangSmith Monitoring
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=finsolve-rag

# App
BACKEND_URL=http://localhost:8000
LOG_LEVEL=INFO
```

---

## 12. Verification Checklist (Before Calling It Done)

- [ ] `pytest tests/` — all unit + integration tests pass
- [ ] `python scripts/ingest.py` — completes without error; Qdrant dashboard shows correct chunk counts
- [ ] Manual RBAC test: login as `eve_employee`, ask "What is Alice's salary?" → response: "I don't have access to that information"
- [ ] Manual RBAC test: login as `carol_hr`, ask same question → gets correct answer with citation
- [ ] Streaming works: responses appear token-by-token in Streamlit
- [ ] Multi-turn works: ask follow-up "What about Q3?" after a Q2 query — context is retained
- [ ] RAGAS scores meet targets (faithfulness > 0.85)
- [ ] LangSmith dashboard shows traces for every chat call
- [ ] `docker compose up --build` — all 3 services start; full flow works on ports 8000 + 8501

---

## 13. Key Concepts to Learn Per Phase

| Phase | Core concepts |
|---|---|
| 1 | pydantic-settings, JWT (HS256), bcrypt hashing, Python enums |
| 2 | LangChain document loaders, text splitters, Qdrant collections, vector embeddings |
| 3 | Dense vs sparse retrieval, BM25, EnsembleRetriever, CrossEncoder reranking, LCEL (`|` pipe), RunnableWithMessageHistory |
| 4 | FastAPI dependency injection, middleware, SSE streaming, slowapi, loguru |
| 5 | Streamlit session_state, st.chat_message, consuming SSE streams |
| 6 | RAGAS metrics (what faithfulness means), LangSmith trace structure |
| 7 | Docker multi-stage builds, Docker Compose networking, GCP Cloud Run |

---

*Last updated: May 24, 2026*
