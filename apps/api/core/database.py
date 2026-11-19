"""
FidelRAG Dual-Database Schema & Connection Manager
Separates immutable curriculum content (content.sqlite) from local edge runtime data (runtime.sqlite).
Enforces PRAGMA foreign_keys = ON and deterministic FTS5 trigger synchronization.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional


CONTENT_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- 1. Textbook Metadata
CREATE TABLE IF NOT EXISTS textbooks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    grade INTEGER NOT NULL,
    subject TEXT NOT NULL,
    curriculum_edition TEXT NOT NULL,
    source_url TEXT,
    pdf_checksum TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Physical & Printed Page Registry
CREATE TABLE IF NOT EXISTS pages (
    id TEXT PRIMARY KEY,
    textbook_id TEXT NOT NULL,
    pdf_page_index INTEGER NOT NULL,
    printed_page_label TEXT,
    unit_number INTEGER NOT NULL,
    unit_title TEXT NOT NULL,
    mapping_status TEXT NOT NULL CHECK (mapping_status IN ('verified', 'inferred', 'missing', 'not_applicable')),
    extraction_status TEXT NOT NULL CHECK (extraction_status IN ('ok', 'needs_review', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(textbook_id) REFERENCES textbooks(id) ON DELETE CASCADE
);

-- 3. Curriculum Passages (Semantic Chunks)
CREATE TABLE IF NOT EXISTS passages (
    rowid_key INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT UNIQUE NOT NULL,
    textbook_id TEXT NOT NULL,
    unit_number INTEGER NOT NULL,
    section_number TEXT,
    section_title TEXT,
    content TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK (content_type IN ('narrative', 'definition', 'formula', 'example', 'summary')),
    token_estimate INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(textbook_id) REFERENCES textbooks(id) ON DELETE CASCADE
);

-- 4. Cross-Page Passage Junction Table
CREATE TABLE IF NOT EXISTS passage_pages (
    passage_id TEXT NOT NULL,
    page_id TEXT NOT NULL,
    page_order INTEGER NOT NULL,
    PRIMARY KEY (passage_id, page_id),
    FOREIGN KEY (passage_id) REFERENCES passages(id) ON DELETE CASCADE,
    FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
);

-- 5. SQLite FTS5 External Content Virtual Table
CREATE VIRTUAL TABLE IF NOT EXISTS fts_passages USING fts5(
    section_title,
    content,
    content='passages',
    content_rowid='rowid_key',
    tokenize = 'porter unicode61 remove_diacritics 2'
);

-- 6. FTS5 Synchronization Triggers (Prevent Index Drift)
CREATE TRIGGER IF NOT EXISTS passages_ai AFTER INSERT ON passages BEGIN
    INSERT INTO fts_passages(rowid, section_title, content)
    VALUES (new.rowid_key, new.section_title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS passages_ad AFTER DELETE ON passages BEGIN
    INSERT INTO fts_passages(fts_passages, rowid, section_title, content)
    VALUES ('delete', old.rowid_key, old.section_title, old.content);
END;

CREATE TRIGGER IF NOT EXISTS passages_au AFTER UPDATE ON passages BEGIN
    INSERT INTO fts_passages(fts_passages, rowid, section_title, content)
    VALUES ('delete', old.rowid_key, old.section_title, old.content);
    INSERT INTO fts_passages(rowid, section_title, content)
    VALUES (new.rowid_key, new.section_title, new.content);
END;

-- 7. Curriculum Concepts
CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    grade INTEGER NOT NULL,
    unit_number INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Multilingual Concept Aliases & Spelling Variants
CREATE TABLE IF NOT EXISTS concept_aliases (
    concept_id TEXT NOT NULL,
    language_code TEXT NOT NULL,
    alias TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'proposed' CHECK (review_status IN ('proposed', 'verified', 'rejected')),
    PRIMARY KEY (concept_id, language_code, alias),
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE
);

-- 9. Concept Discussion Passages
CREATE TABLE IF NOT EXISTS concept_passages (
    concept_id TEXT NOT NULL,
    passage_id TEXT NOT NULL,
    significance TEXT DEFAULT 'primary' CHECK (significance IN ('primary', 'mention')),
    PRIMARY KEY (concept_id, passage_id),
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    FOREIGN KEY (passage_id) REFERENCES passages(id) ON DELETE CASCADE
);

-- 10. Explicit Pedagogical Relationships
CREATE TABLE IF NOT EXISTS concept_relationships (
    id TEXT PRIMARY KEY,
    source_concept_id TEXT NOT NULL,
    target_concept_id TEXT NOT NULL,
    relation_type TEXT NOT NULL CHECK (relation_type IN ('PREREQUISITE_OF', 'USES_FORMULA', 'SPECIAL_CASE_OF')),
    relationship_origin TEXT NOT NULL CHECK (relationship_origin IN ('textbook_explicit', 'teacher_curated', 'model_proposed')),
    review_status TEXT NOT NULL DEFAULT 'proposed' CHECK (review_status IN ('proposed', 'verified', 'rejected')),
    reviewer_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    FOREIGN KEY (target_concept_id) REFERENCES concepts(id) ON DELETE CASCADE
);

-- 11. Relationship Supporting Evidence
CREATE TABLE IF NOT EXISTS relationship_evidence (
    relationship_id TEXT NOT NULL,
    passage_id TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'proposed' CHECK (review_status IN ('proposed', 'verified', 'rejected')),
    reviewer_notes TEXT,
    PRIMARY KEY (relationship_id, passage_id),
    FOREIGN KEY (relationship_id) REFERENCES concept_relationships(id) ON DELETE CASCADE,
    FOREIGN KEY (passage_id) REFERENCES passages(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pages_textbook ON pages(textbook_id);
CREATE INDEX IF NOT EXISTS idx_passages_textbook ON passages(textbook_id);
CREATE INDEX IF NOT EXISTS idx_rel_source ON concept_relationships(source_concept_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON concept_relationships(target_concept_id);
CREATE INDEX IF NOT EXISTS idx_cp_concept ON concept_passages(concept_id);
CREATE INDEX IF NOT EXISTS idx_re_rel ON relationship_evidence(relationship_id);
"""


RUNTIME_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- 1. Anonymous Student Sessions
CREATE TABLE IF NOT EXISTS student_sessions (
    session_id TEXT PRIMARY KEY,
    language_preference TEXT DEFAULT 'en',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Reviewed / Approved Question Cache with Content Checksum Invalidation
CREATE TABLE IF NOT EXISTS reviewed_cache (
    query_hash TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    language_code TEXT NOT NULL,
    answer TEXT NOT NULL,
    supporting_passage_ids_json TEXT NOT NULL,
    content_package_checksum TEXT NOT NULL,
    reviewer_verified BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Anonymous Query Audit Logs
CREATE TABLE IF NOT EXISTS query_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    language_code TEXT NOT NULL,
    query_text TEXT NOT NULL,
    retrieval_mode TEXT NOT NULL,
    abstained BOOLEAN NOT NULL,
    latency_ms REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection(db_path: str | Path, read_only: bool = False) -> sqlite3.Connection:
    """
    Creates a SQLite connection with PRAGMA foreign_keys = ON enforced.
    Supports file paths, in-memory databases (':memory:'), and read-only URI mode.
    """
    db_str = str(db_path)
    if db_str == ":memory:":
        conn = sqlite3.connect(":memory:")
    elif read_only:
        uri_path = f"file:{os.path.abspath(db_str)}?mode=ro"
        conn = sqlite3.connect(uri_path, uri=True)
    else:
        # Ensure parent directory exists for file databases
        Path(db_str).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_str)

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_content_database(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """
    Initializes and applies schema migrations to content.sqlite.
    """
    conn = get_connection(db_path, read_only=False)
    conn.executescript(CONTENT_SCHEMA_SQL)
    conn.commit()
    return conn


def init_runtime_database(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """
    Initializes and applies schema migrations to runtime.sqlite.
    """
    conn = get_connection(db_path, read_only=False)
    conn.executescript(RUNTIME_SCHEMA_SQL)
    conn.commit()
    return conn
