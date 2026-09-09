#!/bin/bash
# IncidentRAG — Project scaffolding + reference repo cloning
# Run from the parent directory where you want the project created.

set -e

PROJECT_NAME="incidentrag"

# ═══════════════════════════════════════════════════════════════════
# Create project root
# ═══════════════════════════════════════════════════════════════════
mkdir -p "$PROJECT_NAME"
cd "$PROJECT_NAME"

# ═══════════════════════════════════════════════════════════════════
# Top-level directories
# ═══════════════════════════════════════════════════════════════════
mkdir -p configs
mkdir -p data/runbooks
mkdir -p data/historical_incidents
mkdir -p data/synthetic_alerts
mkdir -p data/ground_truth
mkdir -p docs/layer_guides
mkdir -p deploy/helm/incidentrag
mkdir -p deploy/k8s
mkdir -p deploy/terraform

# ═══════════════════════════════════════════════════════════════════
# Source tree
# ═══════════════════════════════════════════════════════════════════
mkdir -p src/incidentrag/core

mkdir -p src/incidentrag/ingestion/loaders
mkdir -p src/incidentrag/ingestion/chunking
mkdir -p src/incidentrag/ingestion/metadata

mkdir -p src/incidentrag/query

mkdir -p src/incidentrag/retrieval

mkdir -p src/incidentrag/graph

mkdir -p src/incidentrag/generation

mkdir -p src/incidentrag/evaluation/custom_metrics

mkdir -p src/incidentrag/observability

mkdir -p src/incidentrag/approval/ui

mkdir -p src/incidentrag/execution/guardrails

mkdir -p src/incidentrag/feedback

mkdir -p src/incidentrag/alerts

mkdir -p src/incidentrag/api/routes
mkdir -p src/incidentrag/api/middleware

mkdir -p src/incidentrag/cli/commands

# ═══════════════════════════════════════════════════════════════════
# Tests tree
# ═══════════════════════════════════════════════════════════════════
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/e2e/test_public_postmortems

# ═══════════════════════════════════════════════════════════════════
# References directory (read-only reference repos)
# ═══════════════════════════════════════════════════════════════════
mkdir -p references
cd references

echo "→ Cloning reference repositories (read-only, do not modify)..."

git clone --depth 1 https://github.com/tim-ponomarev/hybrid-rag.git
git clone --depth 1 https://github.com/Shreyash-Gaur/agentic-graph-rag.git
git clone --depth 1 https://github.com/puspanjalis/production-rag-assistant.git
git clone --depth 1 https://github.com/swapnildahiphale/OpenSRE.git
git clone --depth 1 https://github.com/Sahith59/Kairos.git kairos
git clone --depth 1 https://github.com/redevops-io/redevops-rag.git
git clone --depth 1 https://github.com/athina-ai/rag-cookbooks.git
git clone --depth 1 https://github.com/explodinggradients/ragas.git
git clone --depth 1 https://github.com/Arvo-AI/aurora.git

cd ..

# ═══════════════════════════════════════════════════════════════════
# .cursorignore — critical for token efficiency
# ═══════════════════════════════════════════════════════════════════
cat > .cursorignore << 'EOF'
references/
.venv/
__pycache__/
*.pyc
.pytest_cache/
node_modules/
.mypy_cache/
.ruff_cache/
data/runbooks/
data/historical_incidents/
EOF

# ═══════════════════════════════════════════════════════════════════
# .gitignore
# ═══════════════════════════════════════════════════════════════════
cat > .gitignore << 'EOF'
references/
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
runs/
.cache/
EOF

echo ""
echo "✅ Project scaffolding complete."
echo "📁 Project root: $(pwd)"
echo ""
echo "Next steps:"
echo "  1. cd $PROJECT_NAME"
echo "  2. Place SPEC.md in the project root"
echo "  3. Open in Cursor and follow Phase 1 in SPEC.md §18"