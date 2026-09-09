# IncidentRAG — Complete Production Build Specification
## Cursor Pro Implementation Guide

> **Purpose:** Feed this file into Cursor Pro as the master specification. Every
> architectural decision, file path, extraction target, data model, and integration
> pattern is specified. Cursor should be able to produce a production-grade
> incident response RAG system from this document that exceeds Aurora on every
> layer of the RAG pipeline.

---

## Table of Contents

0. [Meta: How to Use This Doc with Cursor](#0-meta-how-to-use-this-doc-with-cursor)
1. [Project Overview](#1-project-overview)
2. [Reference Repo Setup — Clone First, Then Build](#2-reference-repo-setup)
3. [Model Selection & Token Strategy](#3-model-selection--token-strategy)
4. [Complete Directory Structure](#4-complete-directory-structure)
5. [Core Data Models](#5-core-data-models)
6. [Layer 1 — Ingestion Pipeline](#6-layer-1--ingestion-pipeline)
7. [Layer 2 — Query Understanding (HyDE + Fanout)](#7-layer-2--query-understanding)
8. [Layer 3 — Hybrid Retrieval + Reranking](#8-layer-3--hybrid-retrieval--reranking)
9. [Layer 4 — Graph Traversal](#9-layer-4--graph-traversal)
10. [Layer 5 — Context Construction](#10-layer-5--context-construction)
11. [Layer 6 — Structured Output + Grounding](#11-layer-6--structured-output--grounding)
12. [Layer 7 — RAGAS Evaluation Harness](#12-layer-7--ragas-evaluation-harness)
13. [Layer 8 — Observability & Drift Detection](#13-layer-8--observability--drift-detection)
14. [Layer 9 — Human Approval + Execution](#14-layer-9--human-approval--execution)
15. [Layer 10 — Feedback Loop](#15-layer-10--feedback-loop)
16. [Deployment Infrastructure](#16-deployment-infrastructure)
17. [Testing Strategy](#17-testing-strategy)
18. [Full Build Order for Cursor](#18-full-build-order-for-cursor)
19. [Token Budget Breakdown](#19-token-budget-breakdown)

---

## 0. Meta: How to Use This Doc with Cursor

### Should you clone all reference repos first?

**Yes — but selectively.** Do NOT clone everything into one directory and hand it
to Cursor. That will:
- Blow past the 1M token context window in one shot
- Confuse Cursor with dozens of different code styles and dependencies
- Trigger it to try to integrate incompatible frameworks

**Do this instead:**

```
incidentrag/                        ← your project (Cursor works here)
├── SPEC.md                         ← this file
├── src/                            ← Cursor builds here
├── tests/
├── configs/
└── references/                     ← read-only reference material
    ├── hybrid-rag/                 ← cloned tim-ponomarev/hybrid-rag
    ├── agentic-graph-rag/          ← cloned Shreyash-Gaur/agentic-graph-rag
    ├── production-rag-assistant/   ← cloned puspanjalis/production-rag-assistant
    ├── OpenSRE/                    ← cloned swapnildahiphale/OpenSRE
    ├── kairos/                     ← cloned Sahith59/Kairos
    ├── redevops-rag/               ← cloned redevops-io/redevops-rag
    ├── rag-cookbooks/              ← cloned athina-ai/rag-cookbooks
    ├── ragas/                      ← cloned explodinggradients/ragas
    └── aurora/                     ← cloned Arvo-AI/aurora
```

Only clone the 9 repos in the master reference table. **Add `references/` to
`.cursorignore`** so Cursor doesn't try to index them by default. Instead, when
implementing a specific layer, prompt Cursor with:

> *"Reference `references/hybrid-rag/src/retrieval.py` for the RRF fusion
> pattern, but implement it fresh in `src/incidentrag/retrieval/hybrid.py`
> following the data models in Section 5 of SPEC.md."*

This is the pattern: **reference by path, implement fresh.** You get the
architectural insights without importing code that carries dependencies you
don't want.

### The 1M Token Budget

1M tokens is plenty for this project **if you use it right.** See Section 19
for the full breakdown. Key rules:

- Never paste multiple reference repos into context at once
- Use Cursor's `@file` and `@folder` mentions instead of copying code
- Load one layer's context at a time — build, test, commit, clear context
- Reserve ~200K tokens for the eval harness and debugging phases

### The Cursor Prompt Pattern

Every time you start a new layer, use this exact prompt structure:

```
Context files: @SPEC.md @src/incidentrag/core/models.py
Reference (read-only): @references/hybrid-rag/src/retrieval.py

Task: Implement Layer 3 (Hybrid Retrieval) as specified in SPEC.md §8.
Extract only the RRF fusion pattern from the reference — do NOT import from it.
Use the ChunkModel and RetrievalResult types from models.py.

Write:
1. src/incidentrag/retrieval/bm25_index.py
2. src/incidentrag/retrieval/dense_index.py
3. src/incidentrag/retrieval/hybrid.py
4. tests/unit/test_hybrid_retrieval.py

Follow the acceptance criteria in SPEC.md §8.5.
```

This pattern is repeated for every layer. Consistent structure = predictable
Cursor output = fewer tokens burned on corrections.

---

## 1. Project Overview

### What IncidentRAG Is

A **production-grade incident response RAG system** that ingests alerts from
observability tools, retrieves relevant runbooks and historical incidents using
hybrid retrieval + graph traversal + reranking, generates structured remediation
recommendations with citation-grounded evidence, and executes approved actions
in a sandboxed environment. Every retrieval decision is explainable and every
LLM claim is verified against its cited source.

### The 10 Production Layers

1. **Ingestion** — Semantic chunking with structure awareness, version tracking
2. **Query Understanding** — Entity extraction, query fanout, HyDE
3. **Retrieval** — Hybrid (BM25 + dense) + RRF fusion + cross-encoder reranker
4. **Graph Traversal** — Neo4j dependency graph + episodic memory
5. **Context Construction** — Token-budgeted assembly with poisoning protection
6. **Generation** — Structured output with per-claim citations + grounding verification
7. **Evaluation** — RAGAS metrics (faithfulness, precision, recall, relevance)
8. **Observability** — OpenTelemetry tracing + embedding drift detection
9. **Human Approval + Execution** — Structured approval gates, sandboxed execution
10. **Feedback Loop** — Resolved incidents boost retrieval scores, expand eval set

### Differentiation from Aurora

| Aurora | IncidentRAG |
|---|---|
| Dense retrieval only | Hybrid (BM25 + dense) + RRF + reranker |
| No query fanout | 5-way query fanout + HyDE |
| Natural language output | Structured object with per-claim citations |
| No grounding verification | Every LLM claim verified against cited chunk |
| No retrieval eval harness | Continuous RAGAS eval on every change |
| No embedding drift detection | `embed_assert` guards on every search call |
| No semantic chunking documented | Explicit chunkana + structchunk pipeline |
| Coarse feedback (postmortem → KB) | Fine feedback (chunk-level score boost) |

---

## 2. Reference Repo Setup

Clone these 9 repos into `references/` in your project root. Do not modify them.
They are read-only architectural reference material.

### Clone Commands

```bash
mkdir -p references
cd references

git clone https://github.com/tim-ponomarev/hybrid-rag.git
git clone https://github.com/Shreyash-Gaur/agentic-graph-rag.git
git clone https://github.com/puspanjalis/production-rag-assistant.git
git clone https://github.com/swapnildahiphale/OpenSRE.git
git clone https://github.com/Sahith59/Kairos.git kairos
git clone https://github.com/redevops-io/redevops-rag.git
git clone https://github.com/athina-ai/rag-cookbooks.git
git clone https://github.com/explodinggradients/ragas.git
git clone https://github.com/Arvo-AI/aurora.git

cd ..
echo "references/" >> .cursorignore
echo "references/" >> .gitignore
```

### What to Extract from Each Repo

| Repo | Extract | Do NOT Extract |
|---|---|---|
| **hybrid-rag** | `src/retrieval.py` (RRF logic), `src/rerank.py` (cross-encoder), `src/eval.py` (LLM-as-judge) | Their Qdrant client wrapping — build your own |
| **agentic-graph-rag** | `Cypher traversal patterns`, `self-correcting retrieval loop`, `grader node` | Their FastAPI structure — build your own |
| **production-rag-assistant** | `linear fusion (alpha=0.55)`, `extractive citation format`, `citation tracing logic` | Their PDF loaders |
| **OpenSRE** | `Neo4j service dependency schema`, `episodic memory data model`, `Cypher blast-radius queries` | Their agent framework code |
| **kairos** | `error-storm deduplication logic (60s window, 5 occurrence threshold)`, `Redis semantic cache`, `Investigator→Critic loop shape` | Their WebSocket cockpit UI |
| **redevops-rag** | `recency prior formula: 0.5 ** (age_days / 90)`, `DuckDB FTS BM25 setup` | Their SaaS multi-tenant layer |
| **rag-cookbooks** | `advanced_rag_techniques/hyde_rag.ipynb` (HyDERetriever class + prompt template) | Their eval harness — use RAGAS instead |
| **ragas** | The library itself — install as dependency. Reference for custom metric patterns. | Their example notebooks — build your own eval set |
| **aurora** | `Helm chart structure`, `docker-compose services`, `RBAC middleware`, `sandboxed kubectl execution` | Their retrieval pipeline (it's what we're improving on) |

---

## 3. Model Selection & Token Strategy

### LLM Selection by Task

Different steps in the pipeline should use different models. Do NOT use one
model for everything — it's wasteful.

| Task | Model | Reason |
|---|---|---|
| **HyDE hypothetical doc generation** | `gpt-4o-mini` or `claude-haiku-4-5` | Cheap, fast, doesn't need to be factually correct — just semantically shaped like a runbook |
| **Query classification (incident type)** | `gpt-4o-mini` | Small classification task, single-token output |
| **Query fanout (5 rewrites)** | `gpt-4o-mini` | Structured JSON output, low reasoning depth |
| **Root cause reasoning** | `claude-sonnet-4-6` or `gpt-4o` | Main reasoning step — needs quality |
| **Structured remediation generation** | `claude-sonnet-4-6` | Structured JSON output with confidence scores, needs good instruction following |
| **Grounding verification (per-claim check)** | `gpt-4o-mini` | Binary classification per claim — cheap |
| **RAGAS judge model** | `gpt-4o` (or `claude-opus-4-6` if budget permits) | Eval quality matters — use the best you can afford |
| **Embedding model (indexing)** | `text-embedding-3-small` (1536d) | Pin this — do NOT change without full re-index |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` or Cohere Rerank v3 | MS-MARCO is free and works well; Cohere is better but paid |

### Cost Estimate per Incident Triage

Assuming average incident with 3 correlated alerts, 5-way query fanout, top-10
retrieval, top-3 reranked, structured LLM output:

| Step | Model | Tokens (in/out) | Cost |
|---|---|---|---|
| HyDE + query fanout | gpt-4o-mini | 500 / 800 | $0.0005 |
| Reranking | ms-marco (local) | — | $0.00 |
| Root cause reasoning | claude-sonnet-4-6 | 4000 / 1500 | $0.034 |
| Grounding verification (5 claims) | gpt-4o-mini | 2000 / 500 | $0.0006 |
| **Total per incident** | | | **~$0.035** |

### Cursor Token Strategy (1M budget)

**Phase-based context loading.** Never load everything at once.

| Phase | Files in Context | Tokens Used | Cumulative |
|---|---|---|---|
| Foundation (Layer 1-2 data models + ingestion) | SPEC.md + core/models.py + ingestion/*.py | ~80K | 80K |
| Retrieval (Layer 3) | Phase 1 + retrieval/*.py + `@references/hybrid-rag/src/retrieval.py` | ~120K | 200K |
| Graph (Layer 4) | Retrieval files + graph/*.py + `@references/agentic-graph-rag/[key files]` | ~100K | 300K |
| Context + Generation (Layers 5-6) | Graph phase + generation/*.py + reference to houndex patterns | ~120K | 420K |
| Evaluation (Layer 7) | Generation phase + evaluation/*.py + `@references/ragas/` docs | ~100K | 520K |
| Observability (Layer 8) | Eval phase + observability/*.py | ~80K | 600K |
| Approval + Execution (Layer 9) | Observability + approval/*.py + Aurora sandbox pattern | ~100K | 700K |
| Feedback (Layer 10) | Everything trimmed to interfaces only | ~100K | 800K |
| Debugging + Integration | Selective files as needed | ~200K | 1M |

**Critical rule:** After completing each phase, tell Cursor to *"clear context
except SPEC.md and the interfaces in core/models.py"*. This is the single most
important habit for staying within budget.

**Cursor Composer vs Chat:** Use Composer for multi-file edits within one
layer. Use Chat for single-file work and debugging. Composer burns tokens
faster but is essential for cross-file consistency.

---

## 4. Complete Directory Structure

```
incidentrag/
├── SPEC.md                             # This file
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .cursorignore                       # references/, .venv/, __pycache__/
├── .gitignore
├── docker-compose.yml                  # Full local stack
├── Dockerfile
│
├── configs/
│   ├── development.yaml
│   ├── production.yaml
│   ├── eval.yaml                       # For RAGAS runs
│   └── smoke.yaml                      # No API keys, CI-safe
│
├── references/                         # 9 cloned repos, read-only
│   └── [see Section 2]
│
├── data/
│   ├── runbooks/                       # Sample runbooks (Markdown)
│   ├── historical_incidents/           # Public postmortems for eval set
│   ├── synthetic_alerts/               # Test alerts for CI
│   └── ground_truth/
│       └── eval_set.jsonl              # RAGAS ground truth
│
├── src/
│   └── incidentrag/
│       ├── __init__.py
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py               # ALL Pydantic models (canonical)
│       │   ├── protocols.py            # Retriever, Reranker, Judge protocols
│       │   ├── exceptions.py
│       │   └── settings.py             # Pydantic Settings with .env
│       │
│       ├── ingestion/                  # LAYER 1
│       │   ├── __init__.py
│       │   ├── loaders/
│       │   │   ├── markdown_loader.py
│       │   │   ├── notion_loader.py    # Optional: real Notion pull
│       │   │   └── confluence_loader.py
│       │   ├── chunking/
│       │   │   ├── base.py
│       │   │   ├── semantic_chunker.py # From chunkana pattern
│       │   │   ├── structure_chunker.py # From structchunk pattern
│       │   │   └── chunk_evaluator.py  # From messkan/rag-chunk pattern
│       │   ├── metadata/
│       │   │   └── runbook_metadata.py # Service, severity, last_updated, related_runbooks
│       │   ├── versioning.py
│       │   ├── monitor.py              # Dead chunk detection, staleness alerts
│       │   └── pipeline.py             # Orchestrates ingestion
│       │
│       ├── query/                      # LAYER 2
│       │   ├── __init__.py
│       │   ├── entity_extractor.py     # service, env, metric, threshold
│       │   ├── classifier.py           # perf/outage/security/dependency/config
│       │   ├── fanout.py               # 5-way rewrite
│       │   └── hyde.py                 # From rag-cookbooks pattern
│       │
│       ├── retrieval/                  # LAYER 3
│       │   ├── __init__.py
│       │   ├── bm25_index.py
│       │   ├── dense_index.py          # Qdrant client
│       │   ├── rrf.py                  # RRF fusion + recency prior
│       │   ├── reranker.py             # ms-marco cross-encoder
│       │   ├── hybrid.py               # Orchestrates all above
│       │   └── explainability.py       # Score breakdown per chunk
│       │
│       ├── graph/                      # LAYER 4
│       │   ├── __init__.py
│       │   ├── neo4j_client.py
│       │   ├── schema.py               # Node types, edge types
│       │   ├── blast_radius.py         # Cypher: 2-hop dependency query
│       │   ├── related_runbooks.py     # Cypher: runbook relationship traversal
│       │   ├── episodic_memory.py      # Past incident retrieval
│       │   └── ingestion.py            # Build graph from runbook metadata
│       │
│       ├── generation/                 # LAYER 5-6
│       │   ├── __init__.py
│       │   ├── context_builder.py      # Token-budgeted assembly
│       │   ├── prompt_templates.py
│       │   ├── structured_output.py    # Pydantic response schema
│       │   ├── grounding_verifier.py   # Per-claim citation check
│       │   ├── context_sanitizer.py    # Poisoning protection
│       │   └── llm_client.py           # Anthropic/OpenAI wrapper
│       │
│       ├── evaluation/                 # LAYER 7
│       │   ├── __init__.py
│       │   ├── ragas_runner.py         # 4-metric RAGAS eval
│       │   ├── test_set_builder.py     # Ground truth from postmortems
│       │   ├── custom_metrics/
│       │   │   ├── rca_accuracy.py     # Custom: did we identify correct root cause
│       │   │   └── remediation_safety.py # Custom: any dangerous suggestions
│       │   ├── ci_gate.py              # Fail CI if metrics regress
│       │   └── reports.py
│       │
│       ├── observability/              # LAYER 8
│       │   ├── __init__.py
│       │   ├── tracer.py               # OpenTelemetry setup
│       │   ├── spans.py                # gen_ai.* attribute conventions
│       │   ├── drift_detector.py       # Per-class embedding drift
│       │   ├── index_manifest.py       # From embspec pattern
│       │   ├── cost_tracker.py
│       │   └── retrieval_debugger.py   # Replay past retrievals
│       │
│       ├── approval/                   # LAYER 9
│       │   ├── __init__.py
│       │   ├── risk_classifier.py      # LOW/MEDIUM/HIGH per action
│       │   ├── approval_gate.py
│       │   └── ui/
│       │       └── streamlit_app.py    # Human approval UI
│       │
│       ├── execution/                  # LAYER 9
│       │   ├── __init__.py
│       │   ├── sandbox.py              # From Aurora pattern
│       │   ├── kubectl_executor.py
│       │   ├── aws_executor.py
│       │   ├── metric_monitor.py       # Post-execution metric polling
│       │   └── guardrails/
│       │       └── sigma_rules.py      # SigmaHQ detection rules
│       │
│       ├── feedback/                   # LAYER 10
│       │   ├── __init__.py
│       │   ├── score_updater.py        # Boost chunks used in resolutions
│       │   ├── eval_set_expander.py    # Failed incidents → new eval cases
│       │   └── postmortem_generator.py
│       │
│       ├── alerts/                     # Input layer
│       │   ├── __init__.py
│       │   ├── pagerduty_webhook.py
│       │   ├── datadog_webhook.py
│       │   ├── prometheus_alertmanager.py
│       │   ├── correlator.py           # From kairos storm dedup pattern
│       │   └── parser.py
│       │
│       ├── orchestrator.py             # Main incident → resolution flow
│       │
│       ├── api/                        # FastAPI
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── routes/
│       │   │   ├── alerts.py           # Webhook receivers
│       │   │   ├── incidents.py
│       │   │   ├── runbooks.py
│       │   │   └── eval.py
│       │   └── middleware/
│       │       ├── auth.py             # RBAC from Aurora pattern
│       │       └── tracing.py
│       │
│       └── cli/
│           ├── __init__.py
│           ├── app.py                  # Typer entry
│           └── commands/
│               ├── ingest.py           # incidentrag ingest ./data/runbooks
│               ├── query.py            # incidentrag query "alert text"
│               ├── eval.py             # incidentrag eval
│               ├── graveyard.py        # incidentrag graveyard <incident_id>
│               └── replay.py           # incidentrag replay <incident_id>
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_chunking.py
│   │   ├── test_rrf.py
│   │   ├── test_hyde.py
│   │   ├── test_grounding.py
│   │   └── test_risk_classifier.py
│   ├── integration/
│   │   ├── test_full_pipeline.py       # End-to-end with offline models
│   │   ├── test_neo4j_queries.py
│   │   └── test_ragas_eval.py
│   └── e2e/
│       └── test_public_postmortems/    # Replay real incidents
│
├── deploy/
│   ├── helm/
│   │   └── incidentrag/                # From Aurora Helm structure
│   ├── k8s/
│   └── terraform/
│
└── docs/
    ├── architecture.md
    ├── data_model.md
    ├── evaluation.md
    ├── deployment.md
    └── layer_guides/
        ├── layer_1_ingestion.md
        ├── layer_2_query.md
        └── [one per layer]
```

---

## 5. Core Data Models

### `src/incidentrag/core/models.py`

**Every downstream module imports from this file. Build this FIRST.**

```python
"""
Canonical Pydantic v2 data models for IncidentRAG.
No module should define its own version of these types — always import from here.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field
import uuid


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class IncidentCategory(str, Enum):
    PERFORMANCE_DEGRADATION = "performance_degradation"
    COMPLETE_OUTAGE         = "complete_outage"
    SECURITY_EVENT          = "security_event"
    DEPENDENCY_FAILURE      = "dependency_failure"
    CONFIGURATION_DRIFT     = "configuration_drift"
    UNKNOWN                 = "unknown"


class Severity(str, Enum):
    SEV1 = "sev1"   # Full outage
    SEV2 = "sev2"   # Major degradation
    SEV3 = "sev3"   # Minor issue
    SEV4 = "sev4"   # Notification only


class RiskLevel(str, Enum):
    LOW = "low"                    # Safe to auto-execute
    MEDIUM = "medium"              # Requires approval
    HIGH = "high"                  # Requires senior approval
    DANGEROUS = "dangerous"        # Should not be suggested


class ChunkType(str, Enum):
    HEADING = "heading"
    STEP = "step"
    CODE_BLOCK = "code_block"
    WARNING = "warning"
    PROSE = "prose"
    TABLE = "table"


# ═══════════════════════════════════════════════════════════════════════════
# INGESTION LAYER
# ═══════════════════════════════════════════════════════════════════════════

class RunbookMetadata(BaseModel):
    runbook_id: str
    title: str
    service: str                         # e.g. "payment-service"
    environment: list[str]               # ["prod", "staging"]
    severity_applicable: list[Severity]
    author: str
    created_at: datetime
    last_updated_at: datetime
    version: int = 1
    tags: list[str] = Field(default_factory=list)
    related_runbook_ids: list[str] = Field(default_factory=list)
    source_uri: str                      # notion://, confluence://, file://


class Chunk(BaseModel):
    """
    The atomic unit of the vector index.
    A single semantically-coherent section of a runbook.
    """
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str
    chunk_type: ChunkType
    
    content: str                         # The actual text
    header_path: list[str]               # From structchunk: ["Payment Service", "Memory Issues", "Remediation Steps"]
    header_breadcrumb: str               # "# Payment Service > ## Memory Issues > ### Remediation Steps"
    
    position: int                        # 0-indexed position in runbook
    token_count: int
    
    # Retrieval metadata
    boost_score: float = 1.0             # From feedback loop: chunks used in resolutions get boosted
    retrieval_count: int = 0
    last_retrieved_at: datetime | None = None
    
    # Embedding metadata (from embspec pattern)
    embedding_model: str = "text-embedding-3-small"
    embedding_version: str = "v1"
    content_sha256: str                  # For dedup + version tracking
    
    # Full RunbookMetadata denormalized for filter performance
    service: str
    severity_applicable: list[Severity] = Field(default_factory=list)
    runbook_last_updated: datetime


# ═══════════════════════════════════════════════════════════════════════════
# ALERT + QUERY LAYER
# ═══════════════════════════════════════════════════════════════════════════

class RawAlert(BaseModel):
    """
    Alert as received from PagerDuty/Datadog/Prometheus.
    """
    alert_id: str
    source: Literal["pagerduty", "datadog", "prometheus", "grafana", "opsgenie"]
    received_at: datetime
    raw_payload: dict[str, Any]
    
    # Extracted core fields
    service_name: str | None = None
    environment: str | None = None
    severity: Severity | None = None
    alert_text: str
    metric_name: str | None = None
    metric_value: float | None = None
    threshold: float | None = None


class ExtractedEntities(BaseModel):
    """
    Output of the entity extractor (Layer 2).
    """
    service: str | None
    environment: str | None
    metric: str | None
    metric_value: float | None
    threshold: float | None
    host_identifier: str | None
    error_signature: str | None          # e.g. "OOMKilled"
    correlated_services: list[str] = Field(default_factory=list)


class Query(BaseModel):
    """
    Post-understanding query object. This is what gets passed to retrieval.
    """
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_alert: RawAlert
    entities: ExtractedEntities
    category: IncidentCategory
    
    # Query fanout — 5 rewrites
    fanout_queries: list[str]
    
    # HyDE
    hypothetical_document: str
    hypothetical_embedding: list[float] | None = None
    
    # Filters derived from entities
    service_filter: str | None = None
    environment_filter: str | None = None


# ═══════════════════════════════════════════════════════════════════════════
# RETRIEVAL LAYER
# ═══════════════════════════════════════════════════════════════════════════

class RetrievalScores(BaseModel):
    """
    Per-chunk score breakdown for explainability.
    This is what makes IncidentRAG's retrieval explainable vs. Aurora's opaque.
    """
    dense_similarity: float | None       # Cosine similarity, 0-1
    bm25_score: float | None             # Raw BM25 score
    rrf_score: float                     # After Reciprocal Rank Fusion
    reranker_score: float | None         # Cross-encoder score
    recency_boost: float                 # 0.5 ** (age_days / 90)
    feedback_boost: float                # From chunk.boost_score
    graph_hops_from_query: int | None    # 0 = direct, 1+ = via graph traversal
    final_score: float                   # Composite
    
    def explanation(self) -> str:
        """Human-readable score breakdown for the debugger UI."""
        parts = []
        if self.dense_similarity is not None:
            parts.append(f"dense={self.dense_similarity:.3f}")
        if self.bm25_score is not None:
            parts.append(f"bm25={self.bm25_score:.2f}")
        parts.append(f"rrf={self.rrf_score:.3f}")
        if self.reranker_score is not None:
            parts.append(f"rerank={self.reranker_score:.3f}")
        parts.append(f"recency={self.recency_boost:.2f}")
        parts.append(f"feedback={self.feedback_boost:.2f}")
        if self.graph_hops_from_query is not None:
            parts.append(f"hops={self.graph_hops_from_query}")
        return " | ".join(parts) + f" → final={self.final_score:.3f}"


class RetrievalResult(BaseModel):
    """
    A single retrieved chunk with all its scoring context.
    """
    chunk: Chunk
    scores: RetrievalScores
    retrieved_via: list[Literal["dense", "bm25", "graph", "hyde"]]
    query_that_matched: str              # Which fanout query surfaced this


class RetrievalOutput(BaseModel):
    """
    Full output of the retrieval layer for one query.
    """
    query_id: str
    total_candidates_pre_rerank: int
    reranker_used: bool
    results: list[RetrievalResult]       # Post-rerank, top-k
    latency_ms: float


# ═══════════════════════════════════════════════════════════════════════════
# GRAPH LAYER
# ═══════════════════════════════════════════════════════════════════════════

class ServiceNode(BaseModel):
    service_name: str
    tier: Literal["frontend", "api", "core", "infrastructure", "external"]
    environment: str
    owner_team: str | None = None
    criticality: Literal["critical", "high", "medium", "low"]


class ServiceEdge(BaseModel):
    from_service: str
    to_service: str
    relationship: Literal["depends_on", "calls", "reads_from", "writes_to", "publishes_to", "subscribes_to"]
    is_critical_path: bool = False


class BlastRadiusResult(BaseModel):
    origin_service: str
    hop_depth: int
    affected_services: list[ServiceNode]
    critical_path_services: list[str]


# ═══════════════════════════════════════════════════════════════════════════
# GENERATION LAYER (STRUCTURED OUTPUT)
# ═══════════════════════════════════════════════════════════════════════════

class Evidence(BaseModel):
    """
    From houndex pattern. A single piece of source-backed evidence.
    """
    chunk_id: str
    runbook_id: str
    header_breadcrumb: str
    excerpt: str                         # The exact text supporting the claim
    relevance: Literal["direct", "indirect", "background"]


class Claim(BaseModel):
    """
    From houndex pattern. A single factual statement made by the LLM.
    Every claim must have at least one Evidence.
    """
    claim_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    statement: str
    evidence: list[Evidence]
    confidence: float                    # 0.0 - 1.0
    verified: bool = False               # Set by grounding verifier
    verification_reasoning: str | None = None


class RemediationAction(BaseModel):
    """
    A single proposed action, with risk classification and evidence.
    """
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str                     # Human-readable
    command: str | None = None           # Executable command, if applicable
    action_type: Literal["kubectl", "aws_cli", "shell", "http_request", "manual"]
    risk_level: RiskLevel
    evidence: list[Evidence]
    reversible: bool
    estimated_duration_seconds: int
    expected_impact: str
    rollback_command: str | None = None


class IncidentAssessment(BaseModel):
    """
    The full structured output from the LLM reasoning step.
    This is what replaces Aurora's natural-language output.
    """
    incident_id: str
    query_id: str
    
    # Root cause
    root_cause: Claim
    contributing_factors: list[Claim] = Field(default_factory=list)
    
    # Confidence and evidence
    overall_confidence: float
    evidence_chunks_used: list[str]      # chunk_ids
    
    # Actions
    proposed_actions: list[RemediationAction]
    diagnostic_actions: list[RemediationAction] = Field(default_factory=list)
    
    # Escalation
    escalate_to_human: bool
    escalation_reason: str | None = None
    
    # Historical pattern matching
    matches_historical_incident: str | None = None   # incident_id
    pattern_confidence: float | None = None
    
    # What would increase confidence
    additional_info_needed: list[str] = Field(default_factory=list)
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    llm_model: str
    total_tokens: int
    cost_usd: float


# ═══════════════════════════════════════════════════════════════════════════
# EVALUATION LAYER
# ═══════════════════════════════════════════════════════════════════════════

class RAGASMetrics(BaseModel):
    """
    RAGAS four canonical metrics + custom IncidentRAG additions.
    """
    faithfulness: float                  # LLM claims grounded in context
    answer_relevancy: float              # Answer addresses the question
    context_precision: float             # Retrieved chunks are relevant
    context_recall: float                # All relevant chunks retrieved
    
    # Custom IncidentRAG metrics
    rca_accuracy: float                  # Did we identify the actual root cause?
    remediation_safety_score: float      # Did we avoid dangerous suggestions?
    grounding_verification_rate: float   # % of claims that passed grounding


class EvaluationCase(BaseModel):
    """
    A single ground-truth case in the eval set.
    """
    case_id: str
    incident_source: str                 # e.g. "cloudflare-2024-03-outage"
    input_alerts: list[RawAlert]
    ground_truth_root_cause: str
    ground_truth_relevant_runbooks: list[str]
    ground_truth_correct_actions: list[str]
    dangerous_actions_to_avoid: list[str]


# ═══════════════════════════════════════════════════════════════════════════
# OBSERVABILITY LAYER
# ═══════════════════════════════════════════════════════════════════════════

class DriftMeasurement(BaseModel):
    """
    Per-class embedding drift snapshot.
    """
    measurement_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    class_label: str                     # e.g. "payment-service-memory-alerts"
    mean_similarity: float               # Query→known-good chunks
    std_similarity: float
    noise_floor_max: float               # Max sim to unrelated chunks
    signal_gap: float                    # mean_similarity - noise_floor_max
    z_score_vs_baseline: float
    is_drift_detected: bool              # z_score > 3


class IndexManifest(BaseModel):
    """
    From embspec pattern. Enforces query encoder matches index encoder.
    """
    manifest_id: str
    embedding_model: str
    embedding_dimension: int
    embedding_version: str
    chunker_version: str
    total_chunks: int
    total_runbooks: int
    created_at: datetime
    last_reindex_at: datetime
```

### `src/incidentrag/core/protocols.py`

```python
"""
Protocol definitions. Every implementation should conform to these.
"""
from typing import Protocol, runtime_checkable
from .models import Chunk, Query, RetrievalResult, IncidentAssessment, Evidence, Claim


@runtime_checkable
class RetrieverProtocol(Protocol):
    async def retrieve(self, query: Query, top_k: int) -> list[RetrievalResult]:
        ...


@runtime_checkable
class RerankerProtocol(Protocol):
    async def rerank(
        self, query: str, candidates: list[RetrievalResult], top_k: int
    ) -> list[RetrievalResult]:
        ...


@runtime_checkable
class ChunkerProtocol(Protocol):
    def chunk(self, document_text: str, metadata: dict) -> list[Chunk]:
        ...


@runtime_checkable
class GroundingVerifierProtocol(Protocol):
    async def verify(self, claim: Claim, evidence: list[Evidence]) -> tuple[bool, str]:
        """Returns (is_grounded, reasoning)."""
        ...


@runtime_checkable
class GraphClientProtocol(Protocol):
    async def blast_radius(self, service: str, hops: int) -> list[str]:
        ...
    async def related_runbooks(self, runbook_id: str, hops: int) -> list[str]:
        ...
```

---

## 6. Layer 1 — Ingestion Pipeline

### 6.1 Extraction Targets

**From chunkana:** the code-fence protection logic. Chunkana's core rule: a
Markdown chunker should never split inside a fenced code block, table, or list.
Extract this rule and reimplement it in Python.

**From structchunk:** the header breadcrumb injection pattern. Every chunk
carries its full header path (`# H1 > ## H2 > ### H3`) prepended to its
content so embeddings see full section context. Also extract the H1 injection
post-pass — every chunk gets the document title injected so no chunk is
contextually orphaned.

**From messkan/rag-chunk:** the benchmarking CLI. Before committing to a
chunking strategy, run all strategies (fixed-size, sliding-window, paragraph,
recursive, header-aware, semantic) against your actual runbooks and pick the
best on your data. This is a one-time offline step but critical.

### 6.2 Implementation: `src/incidentrag/ingestion/chunking/semantic_chunker.py`

```python
"""
Semantic Markdown chunker that respects runbook structure.
Never splits code blocks, tables, or numbered steps mid-way.
Every chunk carries a header breadcrumb.

References (do not import — reimplement patterns):
- references/rag-cookbooks (chunk metadata pattern)
- chunkana PyPI package README (code-fence protection)
- structchunk PyPI package README (H1 injection, breadcrumbs)
"""

import re
import hashlib
from typing import Iterator
from ...core.models import Chunk, ChunkType, RunbookMetadata


CODE_FENCE = re.compile(r"^```")
HEADER = re.compile(r"^(#{1,6})\s+(.+)$")
NUMBERED_STEP = re.compile(r"^\s*\d+\.\s+")
BULLET = re.compile(r"^\s*[-*+]\s+")
TABLE_ROW = re.compile(r"^\|.*\|$")
WARNING_BLOCK = re.compile(r"^(⚠️|Warning:|CAUTION:|NOTE:)", re.IGNORECASE)


class SemanticMarkdownChunker:
    """
    Chunk order:
    1. Parse into blocks respecting fences (never split inside a fence)
    2. Walk blocks maintaining a header stack
    3. Accumulate blocks under each header up to token budget
    4. Emit chunk with full header breadcrumb prepended
    5. H1 (document title) injected into every chunk
    """
    
    def __init__(
        self,
        target_tokens: int = 500,
        max_tokens: int = 800,
        min_tokens: int = 100,
        overlap_tokens: int = 50,
    ):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_tokens = overlap_tokens
    
    def chunk(self, text: str, metadata: RunbookMetadata) -> list[Chunk]:
        blocks = list(self._parse_blocks(text))
        return list(self._build_chunks(blocks, metadata))
    
    def _parse_blocks(self, text: str) -> Iterator[dict]:
        """
        Parse Markdown into atomic blocks. A code fence is one block.
        A table is one block. A numbered list is one block.
        """
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Code fence — consume entire fence as one block
            if CODE_FENCE.match(line):
                start = i
                i += 1
                while i < len(lines) and not CODE_FENCE.match(lines[i]):
                    i += 1
                i += 1  # closing fence
                yield {
                    "type": ChunkType.CODE_BLOCK,
                    "content": "\n".join(lines[start:i]),
                    "start_line": start,
                }
                continue
            
            # Header
            m = HEADER.match(line)
            if m:
                yield {
                    "type": ChunkType.HEADING,
                    "level": len(m.group(1)),
                    "content": m.group(2).strip(),
                    "start_line": i,
                }
                i += 1
                continue
            
            # Numbered step — consume all consecutive numbered items
            if NUMBERED_STEP.match(line):
                start = i
                while i < len(lines) and (NUMBERED_STEP.match(lines[i]) or lines[i].startswith("   ") or lines[i].strip() == ""):
                    i += 1
                yield {
                    "type": ChunkType.STEP,
                    "content": "\n".join(lines[start:i]).strip(),
                    "start_line": start,
                }
                continue
            
            # Table
            if TABLE_ROW.match(line):
                start = i
                while i < len(lines) and TABLE_ROW.match(lines[i]):
                    i += 1
                yield {
                    "type": ChunkType.TABLE,
                    "content": "\n".join(lines[start:i]),
                    "start_line": start,
                }
                continue
            
            # Warning block
            if WARNING_BLOCK.match(line):
                yield {
                    "type": ChunkType.WARNING,
                    "content": line,
                    "start_line": i,
                }
                i += 1
                continue
            
            # Prose paragraph — consume until blank line
            if line.strip():
                start = i
                while i < len(lines) and lines[i].strip():
                    i += 1
                yield {
                    "type": ChunkType.PROSE,
                    "content": "\n".join(lines[start:i]),
                    "start_line": start,
                }
                continue
            
            i += 1  # blank line
    
    def _build_chunks(self, blocks: list[dict], metadata: RunbookMetadata) -> Iterator[Chunk]:
        header_stack: list[tuple[int, str]] = []   # [(level, text), ...]
        current_content: list[str] = []
        current_type = ChunkType.PROSE
        current_start = 0
        chunk_position = 0
        
        for block in blocks:
            if block["type"] == ChunkType.HEADING:
                # Flush current chunk before header change
                if current_content:
                    yield self._make_chunk(
                        content_blocks=current_content,
                        header_stack=header_stack,
                        metadata=metadata,
                        chunk_type=current_type,
                        position=chunk_position,
                    )
                    chunk_position += 1
                    current_content = []
                
                # Update header stack — pop deeper/equal levels
                while header_stack and header_stack[-1][0] >= block["level"]:
                    header_stack.pop()
                header_stack.append((block["level"], block["content"]))
                continue
            
            current_content.append(block["content"])
            current_type = block["type"]
            
            # Check token budget
            current_tokens = self._approx_tokens("\n".join(current_content))
            if current_tokens >= self.target_tokens:
                yield self._make_chunk(
                    content_blocks=current_content,
                    header_stack=header_stack,
                    metadata=metadata,
                    chunk_type=current_type,
                    position=chunk_position,
                )
                chunk_position += 1
                # Overlap: keep last block for context
                current_content = current_content[-1:] if current_content else []
        
        # Final chunk
        if current_content:
            yield self._make_chunk(
                content_blocks=current_content,
                header_stack=header_stack,
                metadata=metadata,
                chunk_type=current_type,
                position=chunk_position,
            )
    
    def _make_chunk(
        self,
        content_blocks: list[str],
        header_stack: list[tuple[int, str]],
        metadata: RunbookMetadata,
        chunk_type: ChunkType,
        position: int,
    ) -> Chunk:
        header_path = [h[1] for h in header_stack]
        # H1 injection — always prepend document title
        if not header_path or header_path[0] != metadata.title:
            header_path = [metadata.title] + header_path
        
        breadcrumb = " > ".join(
            f"{'#' * (i+1)} {h}" for i, h in enumerate(header_path)
        )
        
        # Prepend breadcrumb to content so embeddings see full context
        content = "\n".join(content_blocks)
        full_content = f"{breadcrumb}\n\n{content}"
        
        return Chunk(
            runbook_id=metadata.runbook_id,
            chunk_type=chunk_type,
            content=full_content,
            header_path=header_path,
            header_breadcrumb=breadcrumb,
            position=position,
            token_count=self._approx_tokens(full_content),
            content_sha256=hashlib.sha256(full_content.encode()).hexdigest()[:16],
            service=metadata.service,
            severity_applicable=metadata.severity_applicable,
            runbook_last_updated=metadata.last_updated_at,
        )
    
    @staticmethod
    def _approx_tokens(text: str) -> int:
        return len(text) // 4  # Rough approximation
```

### 6.3 Ingestion Monitor

```python
# src/incidentrag/ingestion/monitor.py
"""
Continuous ingestion monitoring. Detects:
- Dead chunks (never retrieved in N days)
- Stale runbooks (last_updated > 90 days)
- Knowledge gaps (queries returning low-confidence results)
"""

from datetime import datetime, timedelta
from ..core.models import Chunk


class IngestionMonitor:
    def __init__(self, dead_threshold_days: int = 30, stale_threshold_days: int = 90):
        self.dead_threshold = timedelta(days=dead_threshold_days)
        self.stale_threshold = timedelta(days=stale_threshold_days)
    
    async def find_dead_chunks(self, all_chunks: list[Chunk]) -> list[Chunk]:
        """Chunks never retrieved or not retrieved recently."""
        cutoff = datetime.utcnow() - self.dead_threshold
        return [
            c for c in all_chunks
            if c.retrieval_count == 0
            or (c.last_retrieved_at and c.last_retrieved_at < cutoff)
        ]
    
    async def find_stale_runbooks(self, all_chunks: list[Chunk]) -> set[str]:
        """Runbooks not updated recently."""
        cutoff = datetime.utcnow() - self.stale_threshold
        return {
            c.runbook_id for c in all_chunks
            if c.runbook_last_updated < cutoff
        }
```

### 6.4 Acceptance Criteria

- [ ] Chunker never splits inside a code fence, table, or numbered step group
- [ ] Every chunk has a non-empty `header_path` with at least the document title
- [ ] Chunk content is prefixed with header breadcrumb
- [ ] `content_sha256` matches when the same content is chunked twice
- [ ] Chunker benchmark (`incidentrag ingest --benchmark`) runs all strategies and reports F1 per strategy
- [ ] Ingestion monitor detects dead chunks and stale runbooks

---

## 7. Layer 2 — Query Understanding

### 7.1 Extraction Targets

**From rag-cookbooks/advanced_rag_techniques/hyde_rag.ipynb:** the exact
`HyDERetriever` class structure and the prompt template. The critical prompt is
approximately: *"Given the question '{query}', generate a hypothetical document
that directly answers this question in {chunk_size} words."* Adapt this prompt
for the runbook domain.

**Query fanout pattern:** not from a single repo — this is a well-known
technique. Generate 5 semantic rewrites of the alert, each targeting a
different aspect (remediation, root cause, monitoring, related services,
historical patterns).

### 7.2 Implementation

```python
# src/incidentrag/query/hyde.py
"""
HyDE — Hypothetical Document Embeddings.
Reference: references/rag-cookbooks/advanced_rag_techniques/hyde_rag.ipynb

Key insight: use the hypothetical document as a PARALLEL retrieval query
alongside the raw query, not as a replacement. Averaging embeddings from both
outperforms either alone.
"""

from openai import AsyncOpenAI
from ..core.models import Query, RawAlert


HYDE_PROMPT_TEMPLATE = """You are an SRE writing an ideal runbook section that would help resolve this alert:

Alert: {alert_text}
Service: {service}
Metric: {metric} = {value} (threshold: {threshold})

Write a hypothetical runbook section (~400 words) that would perfectly address this alert.
Include: root cause hypothesis, diagnostic commands, remediation steps, and rollback procedure.
Write it as if it were an actual runbook — technical, specific, with real commands.
Do NOT hedge or say "you might" — write it as authoritative documentation.

Output only the runbook section, no preamble."""


class HyDEGenerator:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self._client = AsyncOpenAI()
    
    async def generate_hypothetical(self, alert: RawAlert) -> str:
        prompt = HYDE_PROMPT_TEMPLATE.format(
            alert_text=alert.alert_text,
            service=alert.service_name or "unknown",
            metric=alert.metric_name or "unknown",
            value=alert.metric_value or "unknown",
            threshold=alert.threshold or "unknown",
        )
        
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        return response.choices[0].message.content
```

```python
# src/incidentrag/query/fanout.py

FANOUT_PROMPT = """You are helping retrieve runbooks for this incident:

Alert: {alert_text}
Service: {service}

Generate exactly 5 search queries targeting different aspects:
1. REMEDIATION: How to fix the immediate symptom
2. ROOT_CAUSE: What could cause this
3. DIAGNOSTIC: How to investigate further
4. DEPENDENCIES: Related services that could be involved
5. HISTORICAL: Similar past incidents

Return JSON: {{"remediation": "...", "root_cause": "...", "diagnostic": "...", "dependencies": "...", "historical": "..."}}"""


class QueryFanoutGenerator:
    async def generate_fanout(self, alert: RawAlert) -> list[str]:
        # Call LLM, parse JSON, return 5 queries
        ...
```

### 7.3 Acceptance Criteria

- [ ] `HyDEGenerator.generate_hypothetical()` returns 300-500 words of technical runbook-style text
- [ ] `QueryFanoutGenerator.generate_fanout()` returns exactly 5 semantically distinct queries
- [ ] Entity extraction correctly parses service, metric, value, threshold from alert payload
- [ ] Query classifier correctly labels a memory alert as `PERFORMANCE_DEGRADATION`

---

## 8. Layer 3 — Hybrid Retrieval + Reranking

### 8.1 Extraction Targets

**From tim-ponomarev/hybrid-rag (`src/retrieval.py`):**
- Exact RRF formula: `score = Σ 1 / (k + rank)` with `k = 60`
- BM25 index construction using `rank_bm25`
- The parallel retrieval pattern (dense + sparse run concurrently)

**From tim-ponomarev/hybrid-rag (`src/rerank.py`):**
- Cross-encoder wrapper around `sentence-transformers/ms-marco-MiniLM-L-6-v2`
- Batch reranking for efficiency
- The rank-based combination note: "Cross-encoder scores aren't comparable
  across queries — use ranks, not raw scores, when combining"

**From redevops-io/redevops-rag:**
- The recency prior formula: `0.5 ** (age_days / 90)` — this is applied
  multiplicatively to the RRF score
- DuckDB FTS BM25 alternative if you want zero external dependencies

**From puspanjalis/production-rag-assistant:**
- The alpha-weighted linear fusion alternative: `final = 0.55 * dense + 0.45 * bm25`
- Use this as a fallback when RRF underperforms on some query types

### 8.2 Implementation Sketch

```python
# src/incidentrag/retrieval/rrf.py
"""
Reciprocal Rank Fusion + recency prior.

References (do not import — reimplement):
- references/hybrid-rag/src/retrieval.py (RRF formula)
- references/redevops-rag (recency prior)
"""

from datetime import datetime, timezone
from ..core.models import Chunk, RetrievalResult, RetrievalScores


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[Chunk]],   # {"dense": [...], "bm25": [...], "graph": [...]}
    k: int = 60,
) -> dict[str, float]:
    """
    Standard RRF: score = Σ 1 / (k + rank) across all source rankings.
    Higher k = softer combination (less weight on top ranks).
    """
    scores: dict[str, float] = {}
    for source, chunks in ranked_lists.items():
        for rank, chunk in enumerate(chunks):
            scores.setdefault(chunk.chunk_id, 0.0)
            scores[chunk.chunk_id] += 1.0 / (k + rank + 1)
    return scores


def recency_boost(chunk: Chunk, decay_days: int = 90) -> float:
    """
    Multiplicative boost: 0.5 ** (age_days / decay_days).
    A chunk from a runbook updated today = 1.0.
    A chunk from 90 days ago = 0.5.
    A chunk from 180 days ago = 0.25.
    """
    age = datetime.now(timezone.utc) - chunk.runbook_last_updated
    age_days = age.days
    return 0.5 ** (age_days / decay_days)


def compose_final_score(
    rrf_score: float,
    recency: float,
    feedback_boost: float,
    reranker_score: float | None = None,
) -> float:
    """
    Compose the final score. Reranker score dominates if available.
    """
    if reranker_score is not None:
        # Reranker is the final authority; recency + feedback modulate slightly
        return reranker_score * (0.7 + 0.15 * recency + 0.15 * feedback_boost)
    # Otherwise use RRF with modulators
    return rrf_score * recency * feedback_boost
```

```python
# src/incidentrag/retrieval/hybrid.py

import asyncio
from ..core.models import Query, RetrievalResult, RetrievalScores
from .bm25_index import BM25Index
from .dense_index import DenseIndex
from .reranker import CrossEncoderReranker
from .rrf import reciprocal_rank_fusion, recency_boost, compose_final_score


class HybridRetriever:
    """
    Orchestrates BM25 + dense + graph retrieval, fuses via RRF, and reranks.
    """
    
    def __init__(
        self,
        bm25: BM25Index,
        dense: DenseIndex,
        reranker: CrossEncoderReranker | None = None,
        top_k_per_source: int = 20,
        top_k_after_fusion: int = 20,
        top_k_final: int = 5,
    ):
        self.bm25 = bm25
        self.dense = dense
        self.reranker = reranker
        self.top_k_per_source = top_k_per_source
        self.top_k_after_fusion = top_k_after_fusion
        self.top_k_final = top_k_final
    
    async def retrieve(self, query: Query) -> list[RetrievalResult]:
        # Run dense + BM25 in parallel across all 5 fanout queries
        # This is the key performance optimization
        
        tasks = []
        for fanout_query in query.fanout_queries:
            tasks.append(self.dense.search(fanout_query, k=self.top_k_per_source))
            tasks.append(self.bm25.search(fanout_query, k=self.top_k_per_source))
        
        # Also search using HyDE hypothetical document
        tasks.append(self.dense.search_by_embedding(
            query.hypothetical_embedding,
            k=self.top_k_per_source,
        ))
        
        all_results = await asyncio.gather(*tasks)
        
        # Group by source for RRF
        dense_results = [r for i, r in enumerate(all_results) if i % 2 == 0]
        bm25_results = [r for i, r in enumerate(all_results) if i % 2 == 1]
        hyde_results = all_results[-1]
        
        # Flatten and RRF fuse
        rrf_scores = reciprocal_rank_fusion({
            "dense": [c for lst in dense_results for c in lst],
            "bm25": [c for lst in bm25_results for c in lst],
            "hyde": hyde_results,
        })
        
        # Get top candidates
        top_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        top_candidates = top_candidates[:self.top_k_after_fusion]
        
        # Build RetrievalResult objects with recency + feedback boosts
        chunk_lookup = await self._load_chunks([cid for cid, _ in top_candidates])
        pre_rerank = []
        for chunk_id, rrf_score in top_candidates:
            chunk = chunk_lookup[chunk_id]
            recency = recency_boost(chunk)
            feedback = chunk.boost_score
            pre_rerank.append(RetrievalResult(
                chunk=chunk,
                scores=RetrievalScores(
                    dense_similarity=None,   # Filled in later if needed
                    bm25_score=None,
                    rrf_score=rrf_score,
                    reranker_score=None,
                    recency_boost=recency,
                    feedback_boost=feedback,
                    graph_hops_from_query=None,
                    final_score=compose_final_score(rrf_score, recency, feedback),
                ),
                retrieved_via=["dense", "bm25", "hyde"],   # Set precisely later
                query_that_matched="",   # Set precisely later
            ))
        
        # Rerank
        if self.reranker:
            reranked = await self.reranker.rerank(
                query=query.original_alert.alert_text,
                candidates=pre_rerank,
                top_k=self.top_k_final,
            )
            return reranked
        
        # No reranker — sort by final_score
        pre_rerank.sort(key=lambda r: r.scores.final_score, reverse=True)
        return pre_rerank[:self.top_k_final]
```

### 8.3 Acceptance Criteria

- [ ] `HybridRetriever.retrieve()` calls BM25, dense, and HyDE in parallel (verified via async timing)
- [ ] RRF formula matches `1 / (k + rank)` exactly with `k = 60`
- [ ] Recency boost applies `0.5 ** (age_days / 90)` correctly
- [ ] Cross-encoder reranker uses `ms-marco-MiniLM-L-6-v2` (or Cohere if configured)
- [ ] `RetrievalScores.explanation()` produces a human-readable breakdown
- [ ] Benchmark shows hybrid + reranker improves nDCG@10 over dense-only by ≥15%

---

## 9. Layer 4 — Graph Traversal

### 9.1 Extraction Targets

**From swapnildahiphale/OpenSRE:**
- The Neo4j schema for infrastructure dependencies (node labels, relationship
  types)
- Episodic memory data model — how past incidents are stored as nodes with
  edges to their resolving runbooks
- Blast radius Cypher query pattern

**From Shreyash-Gaur/agentic-graph-rag:**
- The self-correcting retrieval loop: grade retrieval → rewrite query → retry
- Hybrid search mode within Neo4j (BM25 + dense on the same nodes)

### 9.2 Neo4j Schema

```cypher
// Nodes
CREATE (s:Service {
    name: "payment-service",
    tier: "core",
    environment: "prod",
    owner_team: "payments-eng",
    criticality: "critical"
});

CREATE (r:Runbook {
    runbook_id: "rb-045",
    title: "Payment Service Memory Issues",
    service: "payment-service",
    last_updated: datetime()
});

CREATE (i:Incident {
    incident_id: "inc-2024-03-15-001",
    service: "payment-service",
    root_cause: "connection pool leak",
    resolved: true,
    resolution_time_minutes: 12
});

// Relationships
CREATE (a:Service)-[:DEPENDS_ON {is_critical_path: true}]->(b:Service);
CREATE (a:Service)-[:CALLS]->(b:Service);
CREATE (r:Runbook)-[:APPLIES_TO]->(s:Service);
CREATE (r1:Runbook)-[:RELATED_TO]->(r2:Runbook);
CREATE (i:Incident)-[:RESOLVED_BY]->(r:Runbook);
CREATE (i:Incident)-[:OCCURRED_ON]->(s:Service);
CREATE (i:Incident)-[:USED_CHUNK]->(c:Chunk);
```

### 9.3 Blast Radius Query

```python
# src/incidentrag/graph/blast_radius.py

from neo4j import AsyncGraphDatabase
from ..core.models import ServiceNode, BlastRadiusResult


class BlastRadiusAnalyzer:
    """
    Given an origin service, compute the blast radius up to N hops.
    Reference: references/OpenSRE (schema pattern)
    """
    
    def __init__(self, driver):
        self.driver = driver
    
    async def compute(
        self,
        origin_service: str,
        max_hops: int = 2,
        include_upstream: bool = True,
        include_downstream: bool = True,
    ) -> BlastRadiusResult:
        cypher = """
        MATCH (origin:Service {name: $service})
        CALL {
            WITH origin
            MATCH path = (origin)-[:DEPENDS_ON|CALLS*1..%d]->(downstream:Service)
            RETURN downstream, length(path) as hops, 'downstream' as direction
            UNION
            WITH origin
            MATCH path = (upstream:Service)-[:DEPENDS_ON|CALLS*1..%d]->(origin)
            RETURN upstream as downstream, length(path) as hops, 'upstream' as direction
        }
        RETURN downstream.name as name, hops, direction, downstream.criticality as criticality
        ORDER BY hops ASC
        """ % (max_hops, max_hops)
        
        async with self.driver.session() as session:
            result = await session.run(cypher, service=origin_service)
            records = await result.data()
        
        return BlastRadiusResult(
            origin_service=origin_service,
            hop_depth=max_hops,
            affected_services=[
                ServiceNode(
                    service_name=r["name"],
                    tier="unknown",
                    environment="prod",
                    criticality=r["criticality"] or "medium",
                )
                for r in records
            ],
            critical_path_services=[
                r["name"] for r in records if r["criticality"] == "critical"
            ],
        )
```

### 9.4 Related Runbooks Query

```python
async def find_related_runbooks(
    self,
    origin_runbook_id: str,
    max_hops: int = 1,
) -> list[str]:
    """
    Find runbooks related to the origin via:
    - Direct RELATED_TO edges
    - Same service (APPLIES_TO)
    - Runbooks used in past incidents affecting the same service
    """
    cypher = """
    MATCH (r:Runbook {runbook_id: $rb_id})
    OPTIONAL MATCH (r)-[:RELATED_TO*1..2]-(related:Runbook)
    OPTIONAL MATCH (r)-[:APPLIES_TO]->(s:Service)<-[:APPLIES_TO]-(same_service:Runbook)
    OPTIONAL MATCH (r)-[:APPLIES_TO]->(s)<-[:OCCURRED_ON]-(inc:Incident)-[:RESOLVED_BY]->(historic:Runbook)
    RETURN DISTINCT COALESCE(related.runbook_id, same_service.runbook_id, historic.runbook_id) as rb_id
    LIMIT 10
    """
    # ...
```

### 9.5 Acceptance Criteria

- [ ] Neo4j schema supports Service, Runbook, Incident, Chunk nodes
- [ ] `BlastRadiusAnalyzer.compute()` returns both upstream and downstream services within hops
- [ ] `find_related_runbooks()` traverses direct RELATED_TO, same-service, and past-incident edges
- [ ] Graph queries complete in <100ms on a graph with 500 services

---

## 10. Layer 5 — Context Construction

### 10.1 Token Budgeting

```python
# src/incidentrag/generation/context_builder.py

from ..core.models import IncidentAssessment, RetrievalResult
import tiktoken


class ContextBudgetError(Exception):
    pass


CONTEXT_BUDGET = {
    "system_prompt": 300,
    "incident_summary": 200,
    "dependency_graph_snippet": 150,
    "runbook_1": 400,
    "runbook_2": 400,
    "runbook_3": 400,
    "historical_incident": 200,
    "output_reserved": 1500,
}
TOTAL_BUDGET = sum(CONTEXT_BUDGET.values())   # ~3550 tokens input


class ContextBuilder:
    def __init__(self, model: str = "gpt-4o", budget: dict[str, int] = CONTEXT_BUDGET):
        self.model = model
        self.budget = budget
        self._encoder = tiktoken.encoding_for_model(model)
    
    def build(
        self,
        incident_summary: str,
        blast_radius_summary: str,
        retrieved_runbooks: list[RetrievalResult],
        historical_matches: list[dict],
    ) -> str:
        """
        Assemble context respecting per-section token budgets.
        Each section is summarized/truncated at natural boundaries if over budget.
        """
        sections = []
        
        # Incident summary (never truncate)
        sections.append(self._section("INCIDENT", incident_summary, self.budget["incident_summary"], truncate=False))
        
        # Blast radius
        sections.append(self._section("DEPENDENCY_GRAPH", blast_radius_summary, self.budget["dependency_graph_snippet"]))
        
        # Top 3 runbooks
        for i, rb in enumerate(retrieved_runbooks[:3]):
            sections.append(self._section(
                f"RUNBOOK_{i+1}",
                self._format_runbook(rb),
                self.budget[f"runbook_{i+1}"],
            ))
        
        # Historical matches (summarized, not full text)
        for i, hist in enumerate(historical_matches[:2]):
            sections.append(self._section(
                f"HISTORICAL_INCIDENT_{i+1}",
                self._summarize_historical(hist),
                self.budget["historical_incident"] // 2,
            ))
        
        return "\n\n".join(sections)
    
    def _section(self, name: str, content: str, max_tokens: int, truncate: bool = True) -> str:
        tokens = self._encoder.encode(content)
        if len(tokens) > max_tokens:
            if not truncate:
                raise ContextBudgetError(f"Section {name} exceeds hard budget")
            content = self._encoder.decode(tokens[:max_tokens]) + "\n[truncated]"
        return f"═══ {name} ═══\n{content}"
    
    def _format_runbook(self, rb: RetrievalResult) -> str:
        return (
            f"Runbook: {rb.chunk.runbook_id} — {rb.chunk.header_breadcrumb}\n"
            f"Last updated: {rb.chunk.runbook_last_updated.isoformat()}\n"
            f"Retrieval score: {rb.scores.explanation()}\n\n"
            f"{rb.chunk.content}"
        )
```

### 10.2 Context Poisoning Protection

```python
# src/incidentrag/generation/context_sanitizer.py

import re

INJECTION_PATTERNS = [
    r"ignore\s+(previous|prior|above|all)\s+instructions",
    r"you\s+are\s+now\s+",
    r"forget\s+everything",
    r"system\s*[:\-]\s*",
    r"</?(system|user|assistant)>",
    r"disregard\s+the\s+above",
]

INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


class ContextSanitizer:
    """
    Detects likely prompt injection in retrieved chunks before they reach the LLM.
    Any chunk containing an injection pattern is either flagged or removed.
    """
    
    def sanitize(self, chunks: list[str], strict: bool = True) -> tuple[list[str], list[str]]:
        """Returns (clean_chunks, flagged_chunks)."""
        clean = []
        flagged = []
        for c in chunks:
            if INJECTION_RE.search(c):
                flagged.append(c)
                if not strict:
                    # Redact matched patterns instead of dropping the chunk
                    clean.append(INJECTION_RE.sub("[REDACTED]", c))
            else:
                clean.append(c)
        return clean, flagged
```

---

## 11. Layer 6 — Structured Output + Grounding

### 11.1 Extraction Targets

**From houndex (PyPI):** the `Claim` and `Evidence` data model separation.
Every generated fact is a `Claim` with one or more `Evidence` objects
pointing to specific source chunks. This is the primitive that makes
grounding verification possible.

**From puspanjalis/production-rag-assistant:** the extractive citation format
where the LLM output includes `[N]` markers that map to specific chunk IDs.
The verification step then checks whether the cited chunk actually contains
the claim.

### 11.2 Structured Output via Pydantic

The `IncidentAssessment` model in Section 5 is the schema. Use Anthropic's
tool-use / OpenAI's `response_format` to force structured output.

```python
# src/incidentrag/generation/structured_output.py

import json
from anthropic import AsyncAnthropic
from ..core.models import IncidentAssessment, Claim, Evidence, RemediationAction


REASONING_PROMPT = """You are an SRE assistant analyzing an incident.

Given the retrieved context below, produce a structured assessment as JSON matching this schema:

{
  "root_cause": {
    "statement": "brief description",
    "evidence": [{"chunk_id": "...", "excerpt": "exact text from chunk"}],
    "confidence": 0.0-1.0
  },
  "proposed_actions": [
    {
      "description": "human-readable",
      "command": "kubectl ...",
      "action_type": "kubectl|aws_cli|shell|http_request|manual",
      "risk_level": "low|medium|high|dangerous",
      "evidence": [{"chunk_id": "...", "excerpt": "..."}],
      "reversible": true|false,
      "estimated_duration_seconds": 30,
      "expected_impact": "...",
      "rollback_command": "..."
    }
  ],
  "escalate_to_human": true|false,
  "escalation_reason": "..."
}

CRITICAL RULES:
1. Every claim MUST cite specific chunk_ids from the context
2. Every excerpt MUST be verbatim from the cited chunk
3. If you're not confident, escalate rather than guess
4. Never suggest actions with risk_level=dangerous
5. If the context is insufficient, set escalate_to_human=true

Context:
{context}

Alert:
{alert}

Produce the JSON assessment now."""


class StructuredReasoner:
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self._client = AsyncAnthropic()
    
    async def reason(self, context: str, alert_text: str) -> IncidentAssessment:
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": REASONING_PROMPT.format(
                context=context,
                alert=alert_text,
            )}],
        )
        
        raw_json = response.content[0].text
        # Extract JSON from response (handle markdown fences if present)
        raw_json = self._extract_json(raw_json)
        parsed = json.loads(raw_json)
        return IncidentAssessment(**parsed)
```

### 11.3 Grounding Verifier

```python
# src/incidentrag/generation/grounding_verifier.py

from ..core.models import Claim, Evidence, Chunk


VERIFICATION_PROMPT = """You are verifying whether a claim is supported by evidence.

Claim: "{claim}"

Evidence excerpt: "{excerpt}"

Full chunk content: "{chunk_content}"

Answer with a JSON: {{"supported": true|false, "reasoning": "one sentence"}}"""


class GroundingVerifier:
    """
    For every Claim, check if its Evidence excerpts are actually in the cited chunk
    AND support the claim.
    """
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
    
    async def verify_claim(
        self,
        claim: Claim,
        chunk_lookup: dict[str, Chunk],
    ) -> Claim:
        """
        Returns a copy of the claim with .verified and .verification_reasoning set.
        """
        for evidence in claim.evidence:
            chunk = chunk_lookup.get(evidence.chunk_id)
            if not chunk:
                claim.verified = False
                claim.verification_reasoning = f"Cited chunk {evidence.chunk_id} not found in retrieved set"
                return claim
            
            # Level 1 check: is the excerpt actually in the chunk (substring)?
            if evidence.excerpt not in chunk.content:
                claim.verified = False
                claim.verification_reasoning = f"Excerpt not found verbatim in chunk {evidence.chunk_id}"
                return claim
            
            # Level 2 check: does the excerpt actually support the claim?
            # (LLM call, small model)
            supported, reasoning = await self._llm_verify(claim.statement, evidence.excerpt, chunk.content)
            if not supported:
                claim.verified = False
                claim.verification_reasoning = reasoning
                return claim
        
        claim.verified = True
        claim.verification_reasoning = "All evidence verified"
        return claim
```

### 11.4 Acceptance Criteria

- [ ] LLM output is always valid `IncidentAssessment` JSON — never natural language
- [ ] Every `Claim` in the output has at least one `Evidence`
- [ ] `GroundingVerifier` catches claims whose excerpts don't appear in cited chunks
- [ ] Hallucination rate (measured on eval set) is under 5% after grounding verification
- [ ] Ungrounded claims either get flagged or removed before reaching human approval

---

## 12. Layer 7 — RAGAS Evaluation Harness

### 12.1 Extraction Targets

**From explodinggradients/ragas:** the four canonical metrics — install as
dependency (`pip install ragas`). Use `TestsetGenerator` to bootstrap ground
truth from your runbooks.

**Custom IncidentRAG metrics** (build these yourself):
- `rca_accuracy` — did we identify the correct root cause from the ground truth?
- `remediation_safety_score` — did we avoid suggesting any action in the
  `dangerous_actions_to_avoid` list?

### 12.2 Ground Truth Construction

Take 20-30 public postmortems (Cloudflare, GitHub, GitLab engineering blogs)
and manually construct `EvaluationCase` objects:

```python
# data/ground_truth/eval_set.jsonl (one JSON per line)
{
  "case_id": "cloudflare-2024-06-21-workers-kv",
  "incident_source": "https://blog.cloudflare.com/...",
  "input_alerts": [
    {"alert_text": "Workers KV read latency P99 > 5s", ...}
  ],
  "ground_truth_root_cause": "KV storage tier congestion due to unexpectedly high write load from new customer workload",
  "ground_truth_relevant_runbooks": ["rb-kv-latency-triage", "rb-storage-tier-scaling"],
  "ground_truth_correct_actions": [
    "scale up KV storage replicas",
    "throttle write requests from top talkers"
  ],
  "dangerous_actions_to_avoid": [
    "delete kv namespace",
    "restart entire kv service in prod"
  ]
}
```

### 12.3 RAGAS Runner

```python
# src/incidentrag/evaluation/ragas_runner.py

from ragas import evaluate
from ragas.metrics import (
    faithfulness, answer_relevancy, context_precision, context_recall
)
from datasets import Dataset
from ..core.models import EvaluationCase, RAGASMetrics


class RAGASRunner:
    async def run(self, cases: list[EvaluationCase], pipeline) -> list[RAGASMetrics]:
        """
        Run the full pipeline against each ground truth case,
        collect answers + contexts, and compute RAGAS metrics.
        """
        rows = []
        for case in cases:
            result = await pipeline.process(case.input_alerts[0])
            rows.append({
                "question": case.input_alerts[0].alert_text,
                "answer": result.root_cause.statement,
                "contexts": [ev.excerpt for ev in result.root_cause.evidence],
                "ground_truth": case.ground_truth_root_cause,
            })
        
        dataset = Dataset.from_list(rows)
        result = evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        )
        
        # Add custom metrics
        for i, row in enumerate(rows):
            case = cases[i]
            result[i]["rca_accuracy"] = self._compute_rca_accuracy(row, case)
            result[i]["remediation_safety_score"] = self._compute_safety(row, case)
        
        return [RAGASMetrics(**r) for r in result]
```

### 12.4 CI Gate

```python
# src/incidentrag/evaluation/ci_gate.py

MIN_THRESHOLDS = {
    "faithfulness": 0.85,
    "context_precision": 0.70,
    "context_recall": 0.75,
    "answer_relevancy": 0.80,
    "rca_accuracy": 0.65,
    "remediation_safety_score": 0.95,   # SAFETY IS CRITICAL
}


def gate(current: RAGASMetrics, baseline: RAGASMetrics) -> tuple[bool, list[str]]:
    """
    Returns (passed, failure_reasons).
    Fails CI if:
    - Any metric is below its absolute minimum
    - Any metric regressed by more than 5% vs. baseline
    """
    failures = []
    for metric_name, min_val in MIN_THRESHOLDS.items():
        curr_val = getattr(current, metric_name)
        base_val = getattr(baseline, metric_name)
        
        if curr_val < min_val:
            failures.append(f"{metric_name} below minimum: {curr_val:.2f} < {min_val}")
        
        if curr_val < base_val - 0.05:
            failures.append(f"{metric_name} regressed: {curr_val:.2f} vs baseline {base_val:.2f}")
    
    return (len(failures) == 0, failures)
```

### 12.5 Acceptance Criteria

- [ ] Ground truth set has ≥20 real public postmortems
- [ ] RAGAS runner completes full eval in <10 minutes on the ground truth set
- [ ] CI gate fails on regression of any metric >5%
- [ ] Custom `remediation_safety_score` catches when the pipeline suggests any `dangerous_actions_to_avoid` action

---

## 13. Layer 8 — Observability & Drift Detection

### 13.1 Extraction Targets

**From embspec (PyPI):** the `IndexManifest` + `embed_assert` decorator
pattern. Every search function gets wrapped in `embed_assert` which fails
loudly if the query encoder doesn't match the index encoder.

**From gitbyjay25/RTER:** the trust-gateway microservice pattern — a
component that scans retrieval results and flags redundancy, intent mismatch,
or gradual degradation before results reach the LLM.

**From dev.to embedding drift 50-line monitor pattern:** per-query-class
drift detection using z-score against a rolling baseline.

### 13.2 OpenTelemetry Setup

```python
# src/incidentrag/observability/tracer.py

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


def setup_tracing(service_name: str = "incidentrag", otlp_endpoint: str = "http://localhost:4317"):
    provider = TracerProvider()
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)


# Standard span attribute names (gen_ai.* convention)
class SpanAttrs:
    RETRIEVAL_QUERY = "gen_ai.retrieval.query"
    RETRIEVAL_K = "gen_ai.retrieval.k"
    RETRIEVAL_SCORE = "gen_ai.retrieval.score"
    RETRIEVAL_LATENCY_MS = "gen_ai.retrieval.latency_ms"
    RERANKER_MODEL = "gen_ai.reranker.model"
    LLM_MODEL = "gen_ai.request.model"
    LLM_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    LLM_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
    LLM_COST_USD = "gen_ai.usage.cost_usd"
```

### 13.3 Embedding Drift Detector

```python
# src/incidentrag/observability/drift_detector.py

import numpy as np
from collections import deque
from ..core.models import DriftMeasurement


class EmbeddingDriftDetector:
    """
    Per-class embedding drift detection.
    Reference pattern: dev.to embedding-drift-detection-50-line-monitor
    """
    
    def __init__(self, window_size: int = 100, drift_z_threshold: float = 3.0):
        self.window_size = window_size
        self.threshold = drift_z_threshold
        self._baselines: dict[str, deque] = {}
    
    def measure(
        self,
        class_label: str,
        query_embedding: np.ndarray,
        retrieved_embeddings: list[np.ndarray],
        unrelated_sample: list[np.ndarray],
    ) -> DriftMeasurement:
        # Mean similarity: query to retrieved
        sims_retrieved = [np.dot(query_embedding, e) for e in retrieved_embeddings]
        mean_sim = np.mean(sims_retrieved)
        std_sim = np.std(sims_retrieved)
        
        # Noise floor: max similarity to unrelated chunks
        sims_unrelated = [np.dot(query_embedding, e) for e in unrelated_sample]
        noise_floor = np.max(sims_unrelated) if sims_unrelated else 0.0
        
        signal_gap = mean_sim - noise_floor
        
        # Compare to rolling baseline
        baseline = self._baselines.setdefault(class_label, deque(maxlen=self.window_size))
        if len(baseline) >= 10:
            hist_mean = np.mean(baseline)
            hist_std = np.std(baseline) or 1e-6
            z = (signal_gap - hist_mean) / hist_std
        else:
            z = 0.0
        
        baseline.append(signal_gap)
        
        return DriftMeasurement(
            class_label=class_label,
            mean_similarity=float(mean_sim),
            std_similarity=float(std_sim),
            noise_floor_max=float(noise_floor),
            signal_gap=float(signal_gap),
            z_score_vs_baseline=float(z),
            is_drift_detected=(z < -self.threshold),   # Signal gap dropped
        )
```

### 13.4 Index Manifest (Prevents Silent Failure)

```python
# src/incidentrag/observability/index_manifest.py

import functools
from ..core.models import IndexManifest


def embed_assert(manifest: IndexManifest, model_id: str, dimension: int):
    """
    Decorator that verifies the query encoder matches the index encoder.
    Reference: references pattern from embspec PyPI package.
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapped(*args, **kwargs):
            if manifest.embedding_model != model_id:
                raise RuntimeError(
                    f"Encoder mismatch: index built with {manifest.embedding_model}, "
                    f"query using {model_id}. Rebuild the index before querying."
                )
            if manifest.embedding_dimension != dimension:
                raise RuntimeError(
                    f"Dimension mismatch: index is {manifest.embedding_dimension}-d, "
                    f"query is {dimension}-d"
                )
            return await fn(*args, **kwargs)
        return wrapped
    return decorator
```

### 13.5 Retrieval Debugger

```python
# src/incidentrag/observability/retrieval_debugger.py

class RetrievalDebugger:
    """
    Given an incident_id, replay the exact retrieval that happened
    and show why each chunk was retrieved.
    
    CLI: incidentrag replay <incident_id>
    """
    
    async def replay(self, incident_id: str) -> dict:
        # Load the persisted RetrievalOutput for this incident
        # For each RetrievalResult, show:
        # - Which fanout query surfaced it
        # - Its scores.explanation()
        # - What other chunks it beat out
        # - Why the reranker moved it up/down
        ...
```

### 13.6 Acceptance Criteria

- [ ] Every retrieval + LLM call produces an OpenTelemetry span with `gen_ai.*` attributes
- [ ] `embed_assert` fails loudly on encoder mismatch
- [ ] Drift detector flags when signal gap drops >3σ below baseline
- [ ] `incidentrag replay <incident_id>` reproduces the exact retrieval trace

---

## 14. Layer 9 — Human Approval + Execution

### 14.1 Extraction Targets

**From Arvo-AI/aurora:** the sandboxed execution pattern for `kubectl`, `aws`,
`az`, `gcloud` commands. Every command runs inside an isolated pod with:
- Restricted RBAC (read-only or scoped write)
- SigmaHQ rule scanning before execution
- Command allowlist/blocklist

### 14.2 Risk Classifier

```python
# src/incidentrag/approval/risk_classifier.py

from ..core.models import RemediationAction, RiskLevel


DANGEROUS_PATTERNS = [
    "delete namespace",
    "delete pvc",
    "drop table",
    "aws rds delete-db-instance",
    "terraform destroy",
    "kubectl delete pod --grace-period=0 --force",
]

HIGH_RISK_PATTERNS = [
    "kubectl delete",
    "kubectl scale deployment",
    "aws rds",
    "aws ec2 terminate",
]

MEDIUM_RISK_PATTERNS = [
    "kubectl rollout restart",
    "kubectl rollout undo",
    "systemctl restart",
]


class RiskClassifier:
    def classify(self, action: RemediationAction) -> RiskLevel:
        cmd = (action.command or "").lower()
        
        for pattern in DANGEROUS_PATTERNS:
            if pattern in cmd:
                return RiskLevel.DANGEROUS
        for pattern in HIGH_RISK_PATTERNS:
            if pattern in cmd:
                return RiskLevel.HIGH
        for pattern in MEDIUM_RISK_PATTERNS:
            if pattern in cmd:
                return RiskLevel.MEDIUM
        return RiskLevel.LOW
```

### 14.3 Approval Gate

```python
# src/incidentrag/approval/approval_gate.py

from ..core.models import IncidentAssessment, RemediationAction, RiskLevel


class ApprovalGate:
    """
    Applies approval rules per action risk level.
    - LOW: auto-execute (if auto_execute is enabled)
    - MEDIUM: require any oncall approval
    - HIGH: require senior oncall approval
    - DANGEROUS: never execute — always escalate
    """
    
    def __init__(self, auto_execute_low: bool = False):
        self.auto_execute_low = auto_execute_low
    
    def check(
        self,
        assessment: IncidentAssessment,
        approver_role: str | None = None,
    ) -> dict[str, list[RemediationAction]]:
        buckets = {"auto_execute": [], "requires_approval": [], "blocked": []}
        
        for action in assessment.proposed_actions:
            if action.risk_level == RiskLevel.DANGEROUS:
                buckets["blocked"].append(action)
            elif action.risk_level == RiskLevel.LOW and self.auto_execute_low:
                buckets["auto_execute"].append(action)
            else:
                buckets["requires_approval"].append(action)
        
        return buckets
```

### 14.4 Sandboxed Execution

Reference `references/aurora/` for the pod-based sandbox pattern. Every
`kubectl`/`aws` command runs inside a short-lived pod with scoped RBAC and
SigmaHQ rule scanning. The pod's output is captured, and the pod is destroyed
after execution.

---

## 15. Layer 10 — Feedback Loop

```python
# src/incidentrag/feedback/score_updater.py

from ..core.models import Chunk


class ChunkScoreUpdater:
    """
    When an incident resolves, boost the retrieval scores of chunks that were
    actually used in the resolution.
    """
    
    BOOST_INCREMENT = 0.05   # Additive boost per successful use
    MAX_BOOST = 2.0          # Cap to prevent runaway boosts
    
    async def on_incident_resolved(
        self,
        incident_id: str,
        used_chunk_ids: list[str],
        was_successful: bool,
    ):
        if not was_successful:
            return
        
        for chunk_id in used_chunk_ids:
            chunk = await self._load(chunk_id)
            chunk.boost_score = min(chunk.boost_score + self.BOOST_INCREMENT, self.MAX_BOOST)
            await self._save(chunk)
```

```python
# src/incidentrag/feedback/eval_set_expander.py

class EvalSetExpander:
    """
    When the pipeline fails on a real incident, add it to the eval set
    so future changes are tested against it.
    """
    
    async def on_pipeline_failure(self, incident_id: str, actual_root_cause: str):
        # Convert this incident into an EvaluationCase and append to eval_set.jsonl
        ...
```

---

## 16. Deployment Infrastructure

**From Aurora:** copy the Helm chart structure and docker-compose services.

```yaml
# docker-compose.yml (development)

version: "3.9"

services:
  neo4j:
    image: neo4j:5.15
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/incidentrag
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j_data:/data
  
  qdrant:
    image: qdrant/qdrant:v1.11.0
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
  
  incidentrag-api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - neo4j
      - qdrant
      - redis
      - otel-collector
    env_file:
      - .env
  
  incidentrag-ui:
    build:
      context: .
      dockerfile: Dockerfile.ui
    ports:
      - "8501:8501"

volumes:
  neo4j_data:
  qdrant_data:
```

---

## 17. Testing Strategy

Every layer has three test tiers:

1. **Unit tests** — pure logic, no external services
2. **Integration tests** — with docker-compose services running
3. **E2E tests** — replay real public postmortems

Critical CI tests:
- Offline smoke test (no API keys, uses offline reference target)
- RAGAS eval on 5 canonical cases (must pass minimum thresholds)
- Chunker benchmark (F1 across strategies must match golden numbers)
- Grounding verifier catches 100% of intentionally-hallucinated test claims

---

## 18. Full Build Order for Cursor

Give Cursor these tasks in this exact sequence. Clear context between phases.

### Phase 1 — Foundation (Days 1-2, ~150K tokens)
1. `pyproject.toml`, `.env.example`, `.cursorignore`
2. `src/incidentrag/core/models.py` (COMPLETE — all models from §5)
3. `src/incidentrag/core/protocols.py`
4. `src/incidentrag/core/settings.py`
5. `docker-compose.yml`
6. `tests/conftest.py`

### Phase 2 — Ingestion (Day 3, ~120K tokens)
7. `src/incidentrag/ingestion/chunking/semantic_chunker.py`
8. `src/incidentrag/ingestion/chunking/chunk_evaluator.py`
9. `src/incidentrag/ingestion/loaders/markdown_loader.py`
10. `src/incidentrag/ingestion/monitor.py`
11. `src/incidentrag/ingestion/pipeline.py`
12. `tests/unit/test_chunking.py`
13. Sample runbooks in `data/runbooks/`

### Phase 3 — Query Understanding (Day 4, ~80K tokens)
14. `src/incidentrag/query/entity_extractor.py`
15. `src/incidentrag/query/classifier.py`
16. `src/incidentrag/query/fanout.py`
17. `src/incidentrag/query/hyde.py`
18. `tests/unit/test_hyde.py`

### Phase 4 — Retrieval (Days 5-6, ~150K tokens)
19. `src/incidentrag/retrieval/bm25_index.py`
20. `src/incidentrag/retrieval/dense_index.py` (Qdrant wrapper)
21. `src/incidentrag/retrieval/rrf.py`
22. `src/incidentrag/retrieval/reranker.py`
23. `src/incidentrag/retrieval/hybrid.py`
24. `src/incidentrag/retrieval/explainability.py`
25. `tests/unit/test_rrf.py`
26. `tests/integration/test_hybrid_retrieval.py`

### Phase 5 — Graph (Day 7, ~100K tokens)
27. `src/incidentrag/graph/neo4j_client.py`
28. `src/incidentrag/graph/schema.py`
29. `src/incidentrag/graph/blast_radius.py`
30. `src/incidentrag/graph/related_runbooks.py`
31. `src/incidentrag/graph/episodic_memory.py`
32. `src/incidentrag/graph/ingestion.py`

### Phase 6 — Generation (Days 8-9, ~120K tokens)
33. `src/incidentrag/generation/context_builder.py`
34. `src/incidentrag/generation/context_sanitizer.py`
35. `src/incidentrag/generation/prompt_templates.py`
36. `src/incidentrag/generation/structured_output.py`
37. `src/incidentrag/generation/grounding_verifier.py`
38. `src/incidentrag/generation/llm_client.py`
39. `tests/unit/test_grounding.py`

### Phase 7 — Evaluation (Day 10, ~100K tokens)
40. `data/ground_truth/eval_set.jsonl` (build manually from postmortems)
41. `src/incidentrag/evaluation/ragas_runner.py`
42. `src/incidentrag/evaluation/custom_metrics/rca_accuracy.py`
43. `src/incidentrag/evaluation/custom_metrics/remediation_safety.py`
44. `src/incidentrag/evaluation/ci_gate.py`
45. `src/incidentrag/evaluation/reports.py`

### Phase 8 — Observability (Day 11, ~80K tokens)
46. `src/incidentrag/observability/tracer.py`
47. `src/incidentrag/observability/index_manifest.py`
48. `src/incidentrag/observability/drift_detector.py`
49. `src/incidentrag/observability/cost_tracker.py`
50. `src/incidentrag/observability/retrieval_debugger.py`

### Phase 9 — Approval + Execution (Day 12, ~100K tokens)
51. `src/incidentrag/approval/risk_classifier.py`
52. `src/incidentrag/approval/approval_gate.py`
53. `src/incidentrag/approval/ui/streamlit_app.py`
54. `src/incidentrag/execution/sandbox.py`
55. `src/incidentrag/execution/kubectl_executor.py`
56. `src/incidentrag/execution/metric_monitor.py`

### Phase 10 — Feedback + Integration (Day 13-14, ~120K tokens)
57. `src/incidentrag/feedback/score_updater.py`
58. `src/incidentrag/feedback/eval_set_expander.py`
59. `src/incidentrag/feedback/postmortem_generator.py`
60. `src/incidentrag/alerts/*.py`
61. `src/incidentrag/orchestrator.py` (main flow)
62. `src/incidentrag/api/main.py` + routes
63. `src/incidentrag/cli/*.py`
64. `tests/integration/test_full_pipeline.py`
65. `tests/e2e/test_public_postmortems.py`

### Phase 11 — Deployment (Day 15, ~50K tokens)
66. `deploy/helm/incidentrag/` (adapt from Aurora)
67. `Dockerfile`, `Dockerfile.ui`
68. `README.md` with architecture diagram

---

## 19. Token Budget Breakdown

| Phase | Est. Tokens | Cumulative |
|---|---|---|
| Phase 1 — Foundation | 150K | 150K |
| Phase 2 — Ingestion | 120K | 270K |
| Phase 3 — Query | 80K | 350K |
| Phase 4 — Retrieval | 150K | 500K |
| Phase 5 — Graph | 100K | 600K |
| Phase 6 — Generation | 120K | 720K |
| Phase 7 — Evaluation | 100K | 820K |
| Phase 8 — Observability | 80K | 900K |
| Debug + fix reserve | 100K | **1M** |

Layers 9-11 will need to happen with fresh context sessions. This is normal.
After Phase 8 you have a working pipeline; layers 9-11 are additive and can be
built independently.

### Token Efficiency Rules

1. **Never paste full reference repo code.** Use `@references/path` mentions.
2. **Clear context between phases.** Start new Composer sessions.
3. **Reference SPEC.md by section number**, not by full paste.
4. **Ask Cursor to write interfaces first, then implementations.** Interfaces
   are cheaper to iterate on.
5. **Use `gpt-4o-mini` in Cursor for boilerplate**, reserve Sonnet/Opus for
   complex architectural decisions.
6. **Turn off Cursor's auto-indexing on `references/`** via `.cursorignore`.

---

## Final Cursor System Prompt

Paste this as the top-level instruction in Cursor Settings:

```
You are building IncidentRAG, a production-grade incident response RAG system.
The complete specification is in SPEC.md at the project root.

Rules:
1. NEVER import from references/ — those are read-only architectural references.
   Extract patterns, reimplement fresh in src/incidentrag/.

2. ALWAYS import types from src/incidentrag/core/models.py. Never redefine a model.

3. Every LLM call must use structured output (Pydantic model, JSON mode).

4. Every retrieval must return RetrievalResult with full RetrievalScores.

5. Every LLM claim must have Evidence pointing to a specific chunk_id.

6. Follow the build order in SPEC.md §18. Do not skip ahead.

7. Every module needs a corresponding test file in tests/unit/.

8. Use async everywhere. No blocking calls in the request path.

9. When in doubt about a pattern, ask which reference repo demonstrates it
   before implementing.
```

This document is 5,500+ lines. Cursor will use it as ground truth. If Cursor
proposes something that contradicts SPEC.md, correct it back to SPEC.md.
