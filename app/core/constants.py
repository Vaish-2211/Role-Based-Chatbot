# ── LLM Models ────────────────────────────────────────────────────────────────
# Main model: used for the final RAG answer generation.
# Llama 3.3-70B gives high-quality, nuanced responses.
LLM_MODEL = "llama-3.3-70b-versatile"

# Router model: used only to classify "SEMANTIC vs ANALYTICS".
# A fast, cheap 8B model is more than enough for this binary classification.
LLM_ROUTER_MODEL = "llama-3.1-8b-instant"

# ── Embedding Model ───────────────────────────────────────────────────────────
# BAAI/bge-large-en-v1.5 produces 1024-dimensional vectors.
# It consistently ranks top-5 on the MTEB leaderboard for retrieval tasks.
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
EMBEDDING_DIMENSION = 1024

# ── Reranker Model ────────────────────────────────────────────────────────────
# A cross-encoder: takes (query, candidate_chunk) pairs and scores relevance.
# Much more accurate than dot-product similarity — but slower, so we only use
# it to re-score the top-20 candidates down to top-5.
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_TOP_N = 5

# ── Vector Database ───────────────────────────────────────────────────────────
QDRANT_COLLECTION_NAME = "finsolve_docs"

# The payload field that stores which roles can see a given chunk.
# Used in the Qdrant `must` filter:
#   Filter(must=[FieldCondition(key=RBAC_PAYLOAD_KEY, match=MatchAny(any=[role]))])
RBAC_PAYLOAD_KEY = "allowed_roles"

# ── Chunking ──────────────────────────────────────────────────────────────────
# chunk_size: max characters per chunk.
# chunk_overlap: characters shared between adjacent chunks to preserve context
#   that sits at a boundary (e.g., a sentence split across two chunks).
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# ── Retrieval ─────────────────────────────────────────────────────────────────
# How many candidates to fetch before reranking.
# Dense + BM25 each return RETRIEVAL_TOP_K; ensemble deduplicates; reranker
# picks the best RERANKER_TOP_N from the merged list.
RETRIEVAL_TOP_K = 10

# Weights for the EnsembleRetriever: dense (semantic) + sparse (BM25).
# 0.6 / 0.4 gives a slight preference to semantic similarity while still
# benefiting from exact keyword matches.
ENSEMBLE_WEIGHTS = [0.6, 0.4]

# ── Input Guardrail ───────────────────────────────────────────────────────────
MAX_QUERY_LENGTH = 1000
