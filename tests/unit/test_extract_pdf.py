"""
Unit tests for pipelines/ingestion/extract_pdf.py
Verifies structural PDF extraction, section detection, formula parsing,
content categorization, and page-level provenance.
"""

from pathlib import Path
import pytest

from pipelines.ingestion.extract_pdf import (
    classify_content_type,
    extract_formulas_from_text,
    extract_unit_from_pdf,
)


SAMPLE_PDF_PATH = Path("tests/fixtures/sample_unit2_physics.pdf")


def test_classify_content_type():
    formula_text = "H = (v0^2 * sin^2(theta)) / (2 * g)"
    assert classify_content_type(formula_text, has_formula=True) == "formula"

    definition_text = "Projectile motion is the motion of an object launched into the air."
    assert classify_content_type(definition_text, has_formula=False) == "definition"

    summary_text = "Unit 2 Review and Key Concepts summary"
    assert classify_content_type(summary_text, has_formula=False) == "summary"

    example_text = "Worked Example 2.1: A football is kicked at 45 degrees."
    assert classify_content_type(example_text, has_formula=False) == "example"


def test_extract_formulas_from_text():
    text = (
        "Key formulas:\n"
        "Maximum Height: H = (v0^2 * sin^2(theta)) / (2 * g)\n"
        "Horizontal Range: R = (v0^2 * sin(2 * theta)) / g\n"
        "Just a regular sentence with no equals sign."
    )
    formulas = extract_formulas_from_text(text)
    assert len(formulas) == 2
    assert "H = (v0^2 * sin^2(theta)) / (2 * g)" in formulas
    assert "R = (v0^2 * sin(2 * theta)) / g" in formulas


def test_extract_unit_from_pdf():
    assert SAMPLE_PDF_PATH.exists(), "Sample test PDF fixture must exist"

    result = extract_unit_from_pdf(SAMPLE_PDF_PATH, target_unit=2)
    assert result.unit_number == 2
    assert "Two-dimensional Motion" in result.unit_title
    assert len(result.blocks) >= 2
    assert result.total_formulas_found >= 3

    # Check block structure
    found_projectile_section = False
    for b in result.blocks:
        assert b.unit_number == 2
        assert b.pdf_page_index in [3, 4, 5]
        assert b.printed_page_label in ["34", "35", "36"]
        if b.section_number == "2.1":
            found_projectile_section = True
            assert "Projectile Motion" in (b.section_title or "")

    assert found_projectile_section, "Must extract Section 2.1 Projectile Motion"
