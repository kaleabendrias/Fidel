# FidelRAG / EdTigray 🎓

> **An Offline, Evidence-Grounded, Curriculum-Aware Retrieval System for Multilingual Secondary Education**  
> *Target Content*: Ethiopian Grade 12 Physics (2023 New Curriculum) — Unit 2: Two-dimensional Motion  
> *Release Milestone*: **FidelRAG v0.1 — Offline Research Prototype**

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20%2B%20FTS5%20%2B%20sqlite--vec-003B57.svg)](https://sqlite.org/)
[![Inference](https://img.shields.io/badge/Inference-llama--server%20GGUF-orange.svg)](https://github.com/ggml-org/llama.cpp)
[![Frontend](https://img.shields.io/badge/UI-React%20%2B%20Vite%20%2B%20Tailwind-61DAFB.svg)](https://vitejs.dev/)
[![Offline First](https://img.shields.io/badge/Deployment-Local%20Wi--Fi%20LAN-success.svg)](#offline-classroom-deployment)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📖 Executive Summary

In rural Ethiopia and Tigray, secondary schools operate under severe resource constraints: no internet connectivity, intermittent electrical power, and an acute shortage of physical textbooks. While students and teachers frequently have access to basic smartphones or a school computer, cloud-hosted AI tutoring platforms cannot be accessed.

**FidelRAG** is an open-source, evidence-grounded educational retrieval system designed specifically for offline edge hardware (e.g., a school laptop, refurbished mini-PC, or Raspberry Pi 5 acting as a local Wi-Fi hotspot). Rather than functioning as a generic chatbot over PDFs, FidelRAG integrates:

1. **2023 Ethiopian National Curriculum Grounding**: Laser-focused on **Grade 12 Physics (Unit 2: Two-dimensional Motion)**, covering vectors, projectile trajectories, and circular kinematics.
2. **Dual-Database Architecture**:
   - `content.sqlite` (Read-Only): Versioned curriculum package with multi-page passages (`passage_pages`), synchronized FTS5 virtual tables, `sqlite-vec` embeddings, and a curriculum knowledge graph.
   - `runtime.sqlite` (Read-Write): Manages local student sessions, anonymous progress, and content-invalidated answer caches.
3. **Structured Citation Verification & Calibrated Abstention**: The model outputs structured `supporting_passage_ids`, and the API verifies these against retrieved chunks and resolves canonical printed page labels. Out-of-syllabus queries trigger calibrated refusal.
4. **Decoupled Edge Inference (`llama-server`)**: Runs the official `llama.cpp` HTTP server as an external daemon with single-worker FIFO queuing, avoiding thread contention in FastAPI.
5. **Rigorous Graph-RAG Ablation**: Compares **Mode D (Graph-Hybrid)** directly against **Mode C (Hybrid without Graph)** under an identical top-$K$ evidence budget.
6. **Content Licensing Gate**: Open-source application code is distributed independently from licensed curriculum packages, respecting textbook copyright.

---

## 🏗️ System Architecture

```
                       FIDELRAG ARCHITECTURE (v2.0)

  =================== WORKSTATION: Content Preparation ===================
  [2023 Grade 12 Physics PDF] (Unit 2: Two-dimensional Motion)
            │
            ▼
  [Docling & pypdf Ingestion] ──────► [Cross-Page Chunking & Provenance]
            │                                         │
            ▼                                         ▼
  [Multilingual E5 Small]                [Curriculum Graph Builder]
  (384-dim Dense Embeddings)             (concept_passages, relationship_evidence)
            │                                         │
            └────────────────────┬────────────────────┘
                                 ▼
              [content.sqlite (Read-Only Content Package)]
              (passages, passage_pages, fts_passages, vec_passages, graph)
                                 │
             Offline USB Transfer (with SHA-256 Manifest)
                                 │
  ==================== EDGE SERVER: Classroom Offline ====================
                                 ▼
                     [FastAPI Modular Monolith]
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
   [Hybrid & Graph RAG]  [Citation Validator]  [runtime.sqlite]
   - FTS5 Keyword Search - Resolves Passage IDs- Student Progress
   - sqlite-vec Cosine   - Calibrated Refusal  - Cache Metadata
   - 1-2 Hop Graph Query - Strips Invalid Refs
            ▲                    ▲
            └─────────┬──────────┘
                      │ Local HTTP/SSE API
                      ▼
             [llama-server (llama.cpp)]
             - Quantized GGUF SLM (Qwen2.5-1.5B/3B, Qwen3.5-2B, Gemma-3-1B)
             - Independent daemon with single-worker FIFO queue
                      │
                      ▼ Local Wi-Fi Hotspot (LAN without WAN)
             [React + Vite Static UI]
             - Curriculum Explorer (Offline-first)
             - Ask the Tutor (Interactive Passage Resolution Drawers)
             - Practice & Revision (Step-by-step Hints)
                      ▲
             ┌────────┴────────┐
             ▼                 ▼
     [Student Phone A] [Student Phone B]
```

---

## 🌐 3-Level Multilingual Strategy

| Level | Capability | Status in v0.1 Prototype | Evaluation Method |
| :---: | :--- | :--- | :--- |
| **Level 1** | English $\to$ English QA | **Mandatory Baseline** | Evaluated on 50Q Held-Out Benchmark |
| **Level 2** | Tigrinya/Amharic $\to$ English Retrieval | **Experimental Milestone** | 20 test queries evaluated for Hit@5 & Recall@5 |
| **Level 3** | Tigrinya/Amharic Generated Answers | **Research Feature** | Qualitative native-speaker review |

*Note*: The UI provides an explicit language selector (English / ትግርኛ / አማርኛ). The Unicode block `[\u1200-\u137F]` is utilized as an input assistant rather than an automatic language classifier.

---

## 📁 Repository Structure

```
fidelrag/
├── .agents/
│   └── skills/                   # Project-specific Antigravity skills
│       ├── fidelrag-ingestion/   # Docling extraction, page mapping, FTS5 sync
│       ├── fidelrag-graph-builder/# SQLite concept graph & directional traversal
│       ├── fidelrag-evaluation/  # Controlled 4-way ablation & metrics harness
│       └── fidelrag-offline-packaging/ # Modular packaging & LAN hotspot setup
├── apps/
│   ├── api/                      # FastAPI modular monolith application
│   │   ├── core/                 # Database managers (content & runtime), config
│   │   ├── routers/              # API endpoints (curriculum, tutor, inspect)
│   │   └── services/             # Retrieval (lexical, dense, graph), queue, validator
│   └── web/                      # React 19 + TypeScript + Tailwind student interface
│       ├── src/                  # Explorer, Tutor, Inspection UI, Drawers
│       └── package.json
├── pipelines/
│   ├── ingestion/                # Docling parser, cross-page chunker, FTS5 triggers
│   ├── graph_builder/            # Concept extraction, edge provenance audit
│   └── packaging/                # Modular packaging CLI (app, content, models)
├── evaluation/
│   ├── datasets/                 # Split benchmark (50 dev, 50 held-out)
│   ├── runners/                  # Ablation test runners (Modes A, B, C, D)
│   └── reports/                  # Generated research reports & metrics
├── data/
│   ├── raw/                      # Raw PDFs (Git-ignored)
│   └── packages/                 # Versioned SQLite packages (Git-ignored)
├── docs/
│   ├── adr/                      # Architectural Decision Records
│   ├── research/                 # Technical report & research findings
│   └── content_licensing.md      # Copyright boundaries & permitted use registry
├── plans/                        # Revised 5-phase engineering plans
├── tests/
│   ├── unit/                     # Unit tests (schemas, traversal, validation)
│   └── integration/              # Integration tests (idempotency, FTS5 sync)
├── pyproject.toml                # Unified Python dependency management
└── README.md
```

---

## ⚡ Engineering Phase Roadmap (v2.0 Revised)

FidelRAG is organized into 5 disciplined engineering phases:

- **[Phase 1: Foundation, Schemas & Ingestion](plans/phase_1_foundation_ingestion.md)**: Target 2023 Grade 12 Physics Unit 2; Content Licensing Gate; dual-database schema (`content.sqlite` & `runtime.sqlite`); `passage_pages` junction table; FTS5 synchronization triggers; and idempotent extraction.
- **[Phase 2: Hybrid Retrieval, Benchmark & Early Smoke Tests](plans/phase_2_hybrid_retrieval_benchmark.md)**: FTS5 BM25 search; `sqlite-vec` dense search with E5 Small; RRF reranker; Hit@K, Recall@K, Complete Evidence@K, and MRR metrics; split benchmark (50 dev, 50 held-out); early Tigrinya/Amharic retrieval smoke test; and React vertical slice.
- **[Phase 3: Curriculum Knowledge Graph & Bounded Traversal](plans/phase_3_curriculum_knowledge_graph.md)**: Normalized relational graph schema (`concept_passages`, `relationship_evidence`); directional traversal (backward for prerequisites, forward for formulas); controlled 4-way ablation comparing Mode D directly against Mode C under identical budgets.
- **[Phase 4: Local SLM Server, Structured Citations & Abstention](plans/phase_4_slm_inference_citations_multilingual.md)**: Decoupled `llama-server` inference daemon; FIFO queue manager; structured JSON response contract returning `supporting_passage_ids`; calibrated abstention; and gated multilingual support.
- **[Phase 5: Student UI, Modular Packaging & Research Report](plans/phase_5_ui_edge_packaging_research.md)**: Polished mobile React UI; modular distribution packaging (runtime, content, models); local Wi-Fi LAN deployment (`home.arpa`); answer cache invalidation; and academic technical research report.

---

## 🔬 Research Hypotheses & Ablation Design

FidelRAG evaluates the contribution of hybrid and graph-based retrieval on resource-constrained devices:

| Mode | Name | Description | Evidence Budget |
| :---: | :--- | :--- | :--- |
| **A** | Lexical | SQLite FTS5 (BM25) | Top 5 passages |
| **B** | Dense | `sqlite-vec` (`multilingual-e5-small`) | Top 5 passages |
| **C** | Hybrid | FTS5 + Dense with Reciprocal Rank Fusion | Top 5 passages |
| **D** | Graph-Hybrid | Hybrid + Bounded 1-hop Graph Traversal | **Top 5 passages (Identical Budget)** |

### Core Research Questions
1. **Does Graph-RAG outperform Hybrid RAG?**
   $$\text{Complete Evidence@5}_{\text{Mode D}} > \text{Complete Evidence@5}_{\text{Mode C}}$$
   Evaluated specifically on multi-hop questions requiring vector resolution and kinematics formulas.
2. **Does structured passage ID generation eliminate citation hallucination?**
   Verifying that models citing internal IDs rather than raw page numbers achieve 100% citation-reference validity.
3. **What is the incremental latency of graph traversal on edge hardware?**
   Measuring $\Delta T = T_{\text{Mode D}} - T_{\text{Mode C}}$ on CPU architectures.

---

## 🔒 Content Licensing, Copyright & Ethics

- **Textbook Content**: Educational textbooks produced by the Ministry of Education of Ethiopia are used under educational authorization. The software engine is decoupled from curriculum data; raw PDFs and proprietary SQLite content packages are not checked into Git.
- **Student Privacy**: Designed for offline local Wi-Fi operation with no WAN connection. Zero student telemetry, no external font/script CDNs, and no cloud dependencies.
- **Scientific Responsibility**: AI-generated native language text is treated as experimental and clearly flagged with source verification links to the underlying curriculum text.

---

## 📜 Citation

```bibtex
@misc{fidelrag2026,
  author = {FidelRAG Contributors},
  title = {FidelRAG: An Offline, Evidence-Grounded, Curriculum-Aware Retrieval System for Multilingual Secondary Education},
  year = {2026},
  publisher = {GitHub},
  howpublished = {\url{https://github.com/your-username/fidelrag}}
}
```