"""
Unit tests for FidelRAG dual-database schemas and foreign key integrity.
"""

import json
import sqlite3
from pathlib import Path
import pytest

from apps.api.core.database import (
    init_content_database,
    init_runtime_database,
    get_connection,
)


def test_init_content_database_creates_all_tables():
    conn = init_content_database(":memory:")
    cursor = conn.cursor()

    # Query master table list
    cursor.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view');")
    tables = {row["name"] for row in cursor.fetchall()}

    required_tables = {
        "textbooks",
        "pages",
        "passages",
        "passage_pages",
        "fts_passages",
        "concepts",
        "concept_aliases",
        "concept_passages",
        "concept_relationships",
        "relationship_evidence",
    }
    assert required_tables.issubset(tables), f"Missing tables: {required_tables - tables}"


def test_init_runtime_database_creates_all_tables():
    conn = init_runtime_database(":memory:")
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view');")
    tables = {row["name"] for row in cursor.fetchall()}

    required_tables = {
        "student_sessions",
        "reviewed_cache",
        "query_audit_logs",
    }
    assert required_tables.issubset(tables), f"Missing tables: {required_tables - tables}"


def test_content_foreign_key_enforcement():
    conn = init_content_database(":memory:")
    cursor = conn.cursor()

    # Verify foreign_keys pragma is enabled
    cursor.execute("PRAGMA foreign_keys;")
    assert cursor.fetchone()[0] == 1

    # Attempt to insert a page with a non-existent textbook_id
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO pages (id, textbook_id, pdf_page_index, printed_page_label, unit_number, unit_title, mapping_status, extraction_status)
            VALUES ('p1', 'non_existent_book', 10, '5', 2, 'Two-dimensional Motion', 'verified', 'ok');
            """
        )


def test_cross_page_passage_junction():
    conn = init_content_database(":memory:")
    cursor = conn.cursor()

    # Load synthetic fixture
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_physics_unit.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Insert textbook
    tb = data["textbook"]
    cursor.execute(
        """
        INSERT INTO textbooks (id, title, grade, subject, curriculum_edition, source_url, pdf_checksum)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (tb["id"], tb["title"], tb["grade"], tb["subject"], tb["curriculum_edition"], tb["source_url"], tb["pdf_checksum"]),
    )

    # Insert pages
    for p in data["pages"]:
        cursor.execute(
            """
            INSERT INTO pages (id, textbook_id, pdf_page_index, printed_page_label, unit_number, unit_title, mapping_status, extraction_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (p["id"], p["textbook_id"], p["pdf_page_index"], p["printed_page_label"], p["unit_number"], p["unit_title"], p["mapping_status"], p["extraction_status"]),
        )

    # Insert cross-page passage (chunk02 spans p034 and p035)
    chunk2 = data["passages"][1]
    cursor.execute(
        """
        INSERT INTO passages (id, textbook_id, unit_number, section_number, section_title, content, content_type, token_estimate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (chunk2["id"], chunk2["textbook_id"], chunk2["unit_number"], chunk2["section_number"], chunk2["section_title"], chunk2["content"], chunk2["content_type"], chunk2["token_estimate"]),
    )

    # Link across pages
    for page_link in chunk2["pages"]:
        cursor.execute(
            """
            INSERT INTO passage_pages (passage_id, page_id, page_order)
            VALUES (?, ?, ?);
            """,
            (chunk2["id"], page_link["page_id"], page_link["page_order"]),
        )
    conn.commit()

    # Query junction table: assert passage is linked to exactly 2 distinct pages
    cursor.execute(
        """
        SELECT pg.printed_page_label, pp.page_order
        FROM passage_pages pp
        JOIN pages pg ON pg.id = pp.page_id
        WHERE pp.passage_id = ?
        ORDER BY pp.page_order ASC;
        """,
        (chunk2["id"],),
    )
    rows = cursor.fetchall()
    assert len(rows) == 2
    assert rows[0]["printed_page_label"] == "34"
    assert rows[1]["printed_page_label"] == "35"
