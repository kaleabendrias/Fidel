"""
Unit tests for SQLite FTS5 external content synchronization triggers.
Verifies that INSERT, UPDATE, and DELETE on passages stay synchronized without index drift.
"""

import sqlite3
import pytest
from apps.api.core.database import init_content_database


@pytest.fixture
def populated_content_db():
    conn = init_content_database(":memory:")
    cursor = conn.cursor()

    # Seed textbook
    cursor.execute(
        """
        INSERT INTO textbooks (id, title, grade, subject, curriculum_edition, source_url, pdf_checksum)
        VALUES ('eth_g12_phy', 'Grade 12 Physics', 12, 'Physics', '2023 New Curriculum', 'https://example.com', 'checksum123');
        """
    )
    # Seed page
    cursor.execute(
        """
        INSERT INTO pages (id, textbook_id, pdf_page_index, printed_page_label, unit_number, unit_title, mapping_status, extraction_status)
        VALUES ('page_01', 'eth_g12_phy', 38, '34', 2, 'Two-dimensional Motion', 'verified', 'ok');
        """
    )
    conn.commit()
    return conn


def test_fts_insert_trigger_indexes_passage(populated_content_db):
    cursor = populated_content_db.cursor()

    # Insert a passage
    cursor.execute(
        """
        INSERT INTO passages (id, textbook_id, unit_number, section_number, section_title, content, content_type, token_estimate)
        VALUES ('chunk_01', 'eth_g12_phy', 2, '2.1', 'Projectile Motion', 'Centripetal acceleration occurs when moving in a curved path.', 'definition', 30);
        """
    )
    populated_content_db.commit()

    # Query FTS5 table
    cursor.execute("SELECT * FROM fts_passages WHERE fts_passages MATCH 'centripetal';")
    results = cursor.fetchall()
    assert len(results) == 1
    assert "Centripetal acceleration" in results[0]["content"]


def test_fts_update_trigger_synchronizes_content(populated_content_db):
    cursor = populated_content_db.cursor()

    # Insert initial passage
    cursor.execute(
        """
        INSERT INTO passages (id, textbook_id, unit_number, section_number, section_title, content, content_type, token_estimate)
        VALUES ('chunk_02', 'eth_g12_phy', 2, '2.2', 'Circular Kinematics', 'Initial text mentioning tangential velocity.', 'definition', 25);
        """
    )
    populated_content_db.commit()

    # Confirm initial match
    cursor.execute("SELECT * FROM fts_passages WHERE fts_passages MATCH 'tangential';")
    assert len(cursor.fetchall()) == 1

    # Update content in base table
    cursor.execute(
        """
        UPDATE passages
        SET content = 'Updated text mentioning angular displacement rather than linear motion.'
        WHERE id = 'chunk_02';
        """
    )
    populated_content_db.commit()

    # Old term should no longer match
    cursor.execute("SELECT * FROM fts_passages WHERE fts_passages MATCH 'tangential';")
    assert len(cursor.fetchall()) == 0

    # New term should match exactly once (no duplicate rows)
    cursor.execute("SELECT * FROM fts_passages WHERE fts_passages MATCH 'displacement';")
    updated_results = cursor.fetchall()
    assert len(updated_results) == 1
    assert "angular displacement" in updated_results[0]["content"]


def test_fts_delete_trigger_removes_from_index(populated_content_db):
    cursor = populated_content_db.cursor()

    # Insert passage
    cursor.execute(
        """
        INSERT INTO passages (id, textbook_id, unit_number, section_number, section_title, content, content_type, token_estimate)
        VALUES ('chunk_03', 'eth_g12_phy', 2, '2.3', 'Relative Velocity', 'Relative velocity is vector difference between two frames.', 'definition', 25);
        """
    )
    populated_content_db.commit()

    # Confirm index contains it
    cursor.execute("SELECT * FROM fts_passages WHERE fts_passages MATCH 'relative';")
    assert len(cursor.fetchall()) == 1

    # Delete passage
    cursor.execute("DELETE FROM passages WHERE id = 'chunk_03';")
    populated_content_db.commit()

    # Index must now be empty for that term
    cursor.execute("SELECT * FROM fts_passages WHERE fts_passages MATCH 'relative';")
    assert len(cursor.fetchall()) == 0
