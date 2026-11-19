# Content Licensing & Educational Copyright Gate

> **Document ID**: `LIC-GATE-001`  
> **Status**: Active / Enforced  
> **Applicable Corpus**: Ethiopian Secondary School Textbooks (Grade 12 Physics, 2023 New Curriculum)

---

## 1. Legal Context & Policy Statement

Educational textbooks published by the Ministry of Education of the Federal Democratic Republic of Ethiopia (and regional education bureaus such as ANRSEB) are protected under national copyright statutes and international intellectual property conventions. The copyright notice explicitly restricts unauthorized copying, reproduction, or redistribution into automated retrieval systems without proper authorization.

**FidelRAG strictly enforces an architectural and legal separation:**
1. **Open-Source Software Engine**: The core retrieval architecture, FastAPI services, React web UI, FTS5 sync triggers, SQLite schema scripts, and evaluation harness are released under the permissive **MIT License** and hosted in the public repository.
2. **Proprietary Curriculum Content**: Raw textbook PDFs, extracted page text, high-resolution diagram figures, and production SQLite database binaries (`*.sqlite`) are **strictly prohibited from being checked into the public Git repository**.
3. **Decoupled Packaging**: Content packages are generated on-demand by end-users or participating school administrators who supply their own legally obtained textbook files to the local ingestion pipeline.

---

## 2. Ingestion & Storage Boundaries

| Asset Type | Storage Location | Version Controlled? | Permitted Distribution |
| :--- | :--- | :---: | :--- |
| **Raw Textbook PDFs** | `data/raw/*.pdf` | ❌ **No (Git-ignored)** | Local edge server only; user-provided. |
| **Extracted Text Chunks** | `data/extracted/*.json` | ❌ **No (Git-ignored)** | Local edge server only; user-generated. |
| **Production SQLite Packages**| `data/packages/*.sqlite` | ❌ **No (Git-ignored)** | Distributed offline via physical USB to authorized schools. |
| **Synthetic Test Fixtures** | `tests/fixtures/*.json` | ✅ **Yes** | Permissively licensed, synthetic/original mini-curriculum. |
| **Code, Schemas & Harness** | `apps/`, `pipelines/`, `plans/` | ✅ **Yes** | Fully open source under MIT. |

---

## 3. Curriculum Edition Tracking

Every curriculum package built for deployment must record:
- **Title**: *Grade 12 Physics Student's Textbook*
- **Curriculum Edition**: *2023 New Curriculum (FDRE Ministry of Education)*
- **Target Unit**: *Unit 2: Two-dimensional Motion*
- **Source Verification URL**: Official repository or accredited regional bureau (e.g., `https://anrseb.gov.et/downloads/new-textbooks/`).
- **File Integrity**: SHA-256 checksum of the original unedited source PDF.

---

## 4. Fair Use for Academic Benchmark Questions

Benchmark questions developed for academic evaluation (`evaluation/datasets/`):
- Consist of original student queries and conceptual prompts formulated by researchers/educators.
- Expected ground truth contains minimal, transformative factual citations and reference page numbers necessary to verify mathematical correctness and citation validity under fair dealing / fair use educational research exceptions.
- Full textbook pages or extensive verbatim passages are not published in public benchmark datasets.
