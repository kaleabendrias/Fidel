"""
FidelRAG PDF Structural Extractor
Extracts curriculum units, sections, definitions, and mathematical formulas from secondary physics PDFs.
Preserves formula fidelity (Greek characters, exponents, subscripts) and 0-based PDF provenance.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field
from pypdf import PdfReader

from pipelines.ingestion.page_mapper import TextbookPageMap, build_page_map


# Regex patterns for section titles and structural blocks
SECTION_HEADING_REGEX = re.compile(r"^\s*(?:Section\s+)?(\d+\.\d+)\s+([^\n\r]+)", re.MULTILINE)
FORMULA_INDICATOR_REGEX = re.compile(
    r"(?:=|<=|>=|\^|\b[vV]0\b|\btheta\b|\bomega\b|\bsin\b|\bcos\b|\btan\b|\ba_c\b|\bv_x\b|\bv_y\b|\b\d+\s*m/s\b)",
    re.IGNORECASE,
)
DEFINITION_KEYWORDS_REGEX = re.compile(
    r"\b(?:is\s+defined\s+as|is\s+the\s+motion\s+of|describes\s+motion|states\s+that|is\s+called|refers\s+to)\b",
    re.IGNORECASE,
)
WORKED_EXAMPLE_REGEX = re.compile(r"\b(?:Example|Worked\s+Example|Activity)\b", re.IGNORECASE)
SUMMARY_REGEX = re.compile(r"\b(?:Summary|Review|Key\s+Concepts)\b", re.IGNORECASE)


class ExtractedBlock(BaseModel):
    block_id: str
    pdf_page_index: int = Field(..., description="0-based physical page index")
    printed_page_label: Optional[str] = Field(None, description="Printed corner page label")
    unit_number: int
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    content: str
    content_type: str = Field(
        default="narrative",
        description="One of: 'definition', 'formula', 'example', 'summary', 'narrative'",
    )
    has_formula: bool = False
    detected_formulas: List[str] = []
    char_count: int = 0
    token_estimate: int = 0


class UnitExtractionResult(BaseModel):
    textbook_id: str
    unit_number: int
    unit_title: str
    blocks: List[ExtractedBlock] = []
    page_indices: List[int] = []
    total_formulas_found: int = 0
    extracted_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


def extract_formulas_from_text(text: str) -> List[str]:
    """
    Extracts equation lines and mathematical expressions from text blocks.
    Preserves Greek symbols and kinematic relations.
    """
    formulas = []
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        # Check if line contains an explicit equation or mathematical expression
        if "=" in line_clean and FORMULA_INDICATOR_REGEX.search(line_clean):
            # Clean leading formula labels if present (e.g. 'Maximum Height: H = ...')
            cleaned = re.sub(r"^(?:Maximum Height|Horizontal Range|Time of Flight|Centripetal Acceleration Equation|Formula|Equation\s*\d*):?\s*", "", line_clean, flags=re.IGNORECASE)
            formulas.append(cleaned)
    return formulas


def classify_content_type(text: str, has_formula: bool) -> str:
    """
    Classifies a text block into a pedagogical curriculum category.
    """
    first_few_lines = "\n".join(text.splitlines()[:2])

    if SUMMARY_REGEX.search(first_few_lines):
        return "summary"
    if WORKED_EXAMPLE_REGEX.search(first_few_lines):
        return "example"
    if has_formula and ("=" in text and len(text.strip().splitlines()) <= 4):
        return "formula"
    if DEFINITION_KEYWORDS_REGEX.search(text):
        return "definition"
    if has_formula:
        return "formula"

    return "narrative"


def split_page_into_structural_blocks(
    page_text: str,
    pdf_page_index: int,
    printed_page_label: Optional[str],
    unit_number: int,
    current_section: Tuple[Optional[str], Optional[str]],
) -> Tuple[List[ExtractedBlock], Tuple[Optional[str], Optional[str]]]:
    """
    Splits text from a single page into structural curriculum blocks
    based on section headings and paragraph boundaries.
    """
    blocks: List[ExtractedBlock] = []
    active_sec_num, active_sec_title = current_section

    # Normalize paragraph breaks
    raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]

    block_counter = 1
    for para in raw_paragraphs:
        # Check if paragraph contains or starts with a section heading
        sec_match = SECTION_HEADING_REGEX.search(para)
        if sec_match:
            active_sec_num = sec_match.group(1).strip()
            active_sec_title = sec_match.group(2).strip()

        # Filter out standalone header/footer page label lines
        if para == printed_page_label or para.startswith("Unit 2:") and len(para.splitlines()) == 1:
            continue

        formulas = extract_formulas_from_text(para)
        has_formula = len(formulas) > 0
        content_type = classify_content_type(para, has_formula)

        token_est = int(len(para.split()) * 1.3)
        block_id = f"eth_g12_phy_u{unit_number:02d}_p{pdf_page_index:03d}_blk{block_counter:02d}"

        block = ExtractedBlock(
            block_id=block_id,
            pdf_page_index=pdf_page_index,
            printed_page_label=printed_page_label,
            unit_number=unit_number,
            section_number=active_sec_num,
            section_title=active_sec_title,
            content=para,
            content_type=content_type,
            has_formula=has_formula,
            detected_formulas=formulas,
            char_count=len(para),
            token_estimate=token_est,
        )
        blocks.append(block)
        block_counter += 1

    return blocks, (active_sec_num, active_sec_title)


def extract_unit_from_pdf(
    pdf_path: str | Path,
    target_unit: int = 2,
    textbook_id: str = "eth_sec_physics_g12_2023",
    page_map: Optional[TextbookPageMap] = None,
) -> UnitExtractionResult:
    """
    Extracts all sections and blocks for the target curriculum unit.
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_file}")

    if page_map is None:
        page_map = build_page_map(pdf_file, textbook_id=textbook_id)

    unit_pages = page_map.get_entries_for_unit(target_unit)
    if not unit_pages:
        # Fallback: scan all pages if unit numbers weren't pre-tagged
        unit_pages = page_map.entries

    reader = PdfReader(str(pdf_file))
    all_blocks: List[ExtractedBlock] = []
    matched_page_indices: List[int] = []
    unit_title = "Two-dimensional Motion" if target_unit == 2 else f"Unit {target_unit}"

    current_section: Tuple[Optional[str], Optional[str]] = (None, None)

    for entry in unit_pages:
        idx = entry.pdf_page_index
        if idx >= len(reader.pages):
            continue

        page_text = reader.pages[idx].extract_text() or ""
        # Check if page is relevant to target unit
        if entry.unit_number == target_unit or f"Unit {target_unit}" in page_text:
            matched_page_indices.append(idx)
            if entry.unit_title and entry.unit_title != "Front Matter":
                unit_title = entry.unit_title

            blocks, current_section = split_page_into_structural_blocks(
                page_text=page_text,
                pdf_page_index=idx,
                printed_page_label=entry.printed_page_label,
                unit_number=target_unit,
                current_section=current_section,
            )
            all_blocks.extend(blocks)

    total_formulas = sum(len(b.detected_formulas) for b in all_blocks)

    return UnitExtractionResult(
        textbook_id=textbook_id,
        unit_number=target_unit,
        unit_title=unit_title,
        blocks=all_blocks,
        page_indices=matched_page_indices,
        total_formulas_found=total_formulas,
    )


def main():
    parser = argparse.ArgumentParser(description="FidelRAG PDF Structural Extractor")
    parser.add_argument("--pdf", type=str, required=True, help="Path to textbook PDF")
    parser.add_argument("--unit", type=int, default=2, help="Curriculum unit number (default: 2)")
    parser.add_argument("--textbook-id", type=str, default="eth_sec_physics_g12_2023", help="Textbook ID")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--verify", action="store_true", help="Print verification summary")

    args = parser.parse_args()

    result = extract_unit_from_pdf(args.pdf, target_unit=args.unit, textbook_id=args.textbook_id)

    if args.verify:
        print("\n=== FidelRAG Unit Extraction Report ===")
        print(f"Textbook:         {result.textbook_id}")
        print(f"Unit:             {result.unit_number} - {result.unit_title}")
        print(f"Pages Extracted:  {result.page_indices}")
        print(f"Total Blocks:     {len(result.blocks)}")
        print(f"Total Formulas:   {result.total_formulas_found}")
        print("---------------------------------------")

        # Group by content type
        type_counts = {}
        for b in result.blocks:
            type_counts[b.content_type] = type_counts.get(b.content_type, 0) + 1
        for ctype, count in type_counts.items():
            print(f"  • {ctype.capitalize():<12}: {count} blocks")

        print("\nSample Extracted Formulas:")
        formula_sample = []
        for b in result.blocks:
            for f in b.detected_formulas:
                formula_sample.append((b.section_number, b.printed_page_label, f))
        for sec, page, form in formula_sample[:5]:
            print(f"  [{sec or 'Intro'} | Page {page}] {form}")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        print(f"\nSaved extraction result JSON to: {out_path}")


if __name__ == "__main__":
    main()
