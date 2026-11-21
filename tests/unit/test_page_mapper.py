"""
Unit tests for pipelines/ingestion/page_mapper.py
Verifies PDF page index to printed label mapping, Roman numeral detection,
unit transition tracking, and SQLite pages table population.
"""

from pathlib import Path
import pytest

from apps.api.core.database import init_content_database
from pipelines.ingestion.page_mapper import (
    build_page_map,
    detect_page_label_from_text,
    detect_unit_header,
    save_page_map_to_sqlite,
)


SAMPLE_PDF_PATH = Path("tests/fixtures/sample_unit2_physics.pdf")


def test_detect_page_label_arabic():
    text = "Some physics text here...\n\n35\n"
    res = detect_page_label_from_text(text)
    assert res is not None
    assert res[0] == "35"
    assert res[1] == "arabic"


def test_detect_page_label_roman():
    text = "Preface content...\n\niv\n"
    res = detect_page_label_from_text(text)
    assert res is not None
    assert res[0] == "iv"
    assert res[1] == "roman"


def test_detect_unit_header():
    text = "UNIT 2: Two-dimensional Motion\nIntroduction"
    res = detect_unit_header(text)
    assert res is not None
    assert res[0] == 2
    assert "Two-dimensional Motion" in res[1]


def test_build_page_map_from_sample_pdf():
    assert SAMPLE_PDF_PATH.exists(), "Sample test PDF fixture must exist"

    page_map = build_page_map(SAMPLE_PDF_PATH, textbook_id="eth_sec_physics_g12_2023")
    assert page_map.total_pages == 6

    # Page 0: Cover
    p0 = page_map.get_entry_by_index(0)
    assert p0 is not None
    assert p0.printed_page_label is None
    assert p0.mapping_status == "not_applicable"

    # Page 1: Preface
    p1 = page_map.get_entry_by_index(1)
    assert p1 is not None
    assert p1.printed_page_label == "iii"
    assert p1.mapping_status == "verified"

    # Page 2: Table of Contents
    p2 = page_map.get_entry_by_index(2)
    assert p2 is not None
    assert p2.printed_page_label == "iv"
    assert p2.mapping_status == "verified"

    # Pages 3, 4, 5: Unit 2
    p3 = page_map.get_entry_by_index(3)
    assert p3.printed_page_label == "34"
    assert p3.unit_number == 2

    p4 = page_map.get_entry_by_index(4)
    assert p4.printed_page_label == "35"
    assert p4.unit_number == 2

    p5 = page_map.get_entry_by_index(5)
    assert p5.printed_page_label == "36"
    assert p5.unit_number == 2


def test_save_page_map_to_sqlite():
    page_map = build_page_map(SAMPLE_PDF_PATH, textbook_id="eth_sec_physics_g12_2023")
    conn = init_content_database(":memory:")

    # Insert parent textbook first to satisfy foreign key constraint
    conn.execute(
        """
        INSERT INTO textbooks (id, title, grade, subject, curriculum_edition, source_url, pdf_checksum)
        VALUES ('eth_sec_physics_g12_2023', 'Physics Grade 12', 12, 'Physics', '2023', 'http://example.com', 'chk123');
        """
    )
    conn.commit()

    # Save to SQLite
    rows = save_page_map_to_sqlite(page_map, conn)
    assert rows == 6

    # Query back
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pages WHERE unit_number = 2;")
    assert cursor.fetchone()[0] == 3
