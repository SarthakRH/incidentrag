"""
Application settings for IncidentRAG.
All configuration is read from environment variables (or a .env file).
Uses pydantic-settings for type-safe, validated access.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings object.  Import and call `get_settings()` everywhere —
    never instantiate Settings() directly in production code so the cached
    singleton is always returned.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM API Keys ──────────────────────────────────────────────────────
    anthropic_api_key: str = Field(..., description="Anthropic API key (required)")
    openai_api_key: str = Field(..., description="OpenAI API key (required)")

    # ── Model Names ────────────────────────────────────────────────────────
    anthropic_reasoning_model: str = Field(
        default="claude-opus-4-5",
        description="Primary Anthropic model for reasoning and generation",
    )
    openai_reasoning_model: str = Field(
        default="gpt-4o",
        description="OpenAI model used as fallback / secondary reasoner",
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model for dense retrieval",
    )
    reranker_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        description="sentence-transformers cross-encoder model for reranking",
    )

    # ── Neo4j ──────────────────────────────────────────────────────────────
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j Bolt URI",
    )
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(
        default="incidentrag", description="Neo4j password"
    )

    # ── Qdrant ─────────────────────────────────────────────────────────────
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant HTTP endpoint",
    )
    qdrant_api_key: str = Field(
        default="",
        description="Qdrant API key (leave empty for local unauthenticated instances)",
    )
    qdrant_collection_name: str = Field(
        default="incidentrag_chunks",
        description="Qdrant collection that stores chunk embeddings",
    )
    qdrant_embedding_dim: int = Field(
        default=1536,
        description="Embedding dimensionality — must match the index manifest",
    )

    # ── Redis ──────────────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL (used for caching and feedback queue)",
    )

    # ── OpenTelemetry ──────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP gRPC collector endpoint",
    )

    # ── Application Behaviour ──────────────────────────────────────────────
    app_environment: str = Field(
        default="development",
        description="Runtime environment tag (development | staging | production)",
    )
    max_context_tokens: int = Field(
        default=180_000,
        description="Hard token ceiling per inference call",
    )
    retrieval_top_k: int = Field(
        default=10,
        description="Number of chunks returned after reranking",
    )
    bm25_candidate_k: int = Field(
        default=50,
        description="BM25 candidate pool size before reranking",
    )
    dense_candidate_k: int = Field(
        default=50,
        description="Dense retrieval candidate pool size before reranking",
    )

    # ── Evaluation ─────────────────────────────────────────────────────────
    eval_dataset_path: str = Field(
        default="data/ground_truth/eval_set.jsonl",
        description="Path to the JSONL ground-truth evaluation dataset",
    )
    eval_min_faithfulness: float = Field(
        default=0.85,
        description="Minimum RAGAS faithfulness score required to pass the CI gate",
    )

    # ── Caching ────────────────────────────────────────────────────────────
    diskcache_dir: str = Field(
        default=".cache/embeddings",
        description="Directory for the embedding diskcache",
    )

    # ── Validators ─────────────────────────────────────────────────────────
    @field_validator("app_environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"app_environment must be one of {allowed}, got '{v}'")
        return v

    @field_validator("eval_min_faithfulness")
    @classmethod
    def validate_faithfulness_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("eval_min_faithfulness must be between 0.0 and 1.0")
        return v

    @field_validator("retrieval_top_k", "bm25_candidate_k", "dense_candidate_k")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Retrieval k values must be positive integers")
        return v


_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Return the cached Settings singleton.
    Reads from .env on first call; subsequent calls return the cached instance.
    Use this function everywhere instead of instantiating Settings() directly.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
