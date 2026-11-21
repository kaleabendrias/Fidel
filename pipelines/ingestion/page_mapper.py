"""
FidelRAG Page Mapper & Provenance Registry
Maps physical 0-based PDF page indices to printed textbook corner labels (including Roman numerals),
detects unit transitions, tracks mapping status, and populates the SQLite pages table idempotently.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field
from pypdf import PdfReader

from apps.api.core.database import get_connection


ROMAN_NUMERAL_REGEX = re.compile(r"^(?=[mdclxvi])m*(c[md]|d?c*)(x[cl]|l?x*)(i[xv]|v?i*)$", re.IGNORECASE)
ARABIC_PAGE_REGEX = re.compile(r"^\s*(?:Page\s*)?(\d{1,4})\s*$", re.IGNORECASE)
UNIT_HEADER_REGEX = re.compile(r"(?:Unit|UNIT)\s+(\d+)[\s:\-–—]+([^\n\r]+)")


class PageMappingEntry(BaseModel):
    id: str
    pdf_page_index: int = Field(..., description="0-based index matching pypdf")
    printed_page_label: Optional[str] = Field(None, description="Textual label: '34' or Roman 'iv'")
    unit_number: int = Field(default=0, description="Active curriculum unit number")
    unit_title: str = Field(default="", description="Active curriculum unit title")
    mapping_status: str = Field(
        default="inferred",
        description="One of: 'verified', 'inferred', 'missing', 'not_applicable'",
    )
    extraction_status: str = Field(
        default="ok",
        description="One of: 'ok', 'needs_review', 'failed'",
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_evidence: Optional[str] = None


class TextbookPageMap(BaseModel):
    textbook_id: str
    pdf_path: str
    total_pages: int
    detected_offset: Optional[int] = None
    entries: List[PageMappingEntry] = []

    def get_entry_by_index(self, pdf_index: int) -> Optional[PageMappingEntry]:
        for entry in self.entries:
            if entry.pdf_page_index == pdf_index:
                return entry
        return None

    def get_entries_for_unit(self, unit_number: int) -> List[PageMappingEntry]:
        return [e for e in self.entries if e.unit_number == unit_number]


def detect_page_label_from_text(text: str) -> Optional[Tuple[str, str]]:
    """
    Inspects header (first 3 lines) and footer (last 3 lines) for solitary page numbers.
    Returns (label_str, 'arabic' | 'roman') or None.
    """
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return None

    candidates = []
    # Check bottom lines first (standard textbook layout)
    footer_lines = lines[-3:] if len(lines) >= 3 else lines
    for line in reversed(footer_lines):
        candidates.append(line)

    # Check top lines
    header_lines = lines[:2] if len(lines) >= 2 else []
    for line in header_lines:
        candidates.append(line)

    for line in candidates:
        # Check Arabic number
        m_arabic = ARABIC_PAGE_REGEX.match(line)
        if m_arabic:
            val = m_arabic.group(1)
            # Filter out numbers that are too large to be textbook page numbers
            if int(val) <= 1500:
                return (val, "arabic")

        # Check Roman numeral
        m_roman = ROMAN_NUMERAL_REGEX.match(line.lower())
        if m_roman and line.lower() not in {"c", "d", "m", "i"}:
            return (line.lower(), "roman")

    return None


def detect_unit_header(text: str) -> Optional[Tuple[int, str]]:
    """
    Extracts Unit number and title if present on the page.
    e.g. 'Unit 2: Two-dimensional Motion' -> (2, 'Two-dimensional Motion')
    """
    for line in text.splitlines():
        line_clean = line.strip()
        match = UNIT_HEADER_REGEX.search(line_clean)
        if match:
            unit_num = int(match.group(1))
            unit_title = match.group(2).strip()
            # Clean trailing dots from table of contents lines
            unit_title = re.sub(r"\.{2,}.*$", "", unit_title).strip()
            return (unit_num, unit_title)
    return None


def build_page_map(
    pdf_path: str | Path,
    textbook_id: str = "eth_sec_physics_g12_2023",
    manual_offset: Optional[int] = None,
) -> TextbookPageMap:
    """
    Walks all pages in the PDF, detects page numbers and unit headers,
    computes offset, and creates a verified TextbookPageMap.
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_file}")

    reader = PdfReader(str(pdf_file))
    total_pages = len(reader.pages)

    entries: List[PageMappingEntry] = []
    current_unit_number = 0
    current_unit_title = "Front Matter"
    detected_offsets: List[int] = []

    # First pass: collect raw extractions
    raw_pages = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        unit_info = detect_unit_header(text)
        page_label_info = detect_page_label_from_text(text)
        raw_pages.append({
            "index": idx,
            "text": text,
            "unit_info": unit_info,
            "page_label_info": page_label_info,
        })

    # Second pass: construct mapping with unit propagation and offset estimation
    for p in raw_pages:
        idx = p["index"]
        if p["unit_info"]:
            current_unit_number, current_unit_title = p["unit_info"]

        label_info = p["page_label_info"]
        page_id = f"{textbook_id}_p{idx:03d}"

        if label_info:
            label, num_type = label_info
            if num_type == "arabic":
                arabic_val = int(label)
                offset = idx - arabic_val
                detected_offsets.append(offset)
                mapping_status = "verified"
            else:
                mapping_status = "verified"

            entry = PageMappingEntry(
                id=page_id,
                pdf_page_index=idx,
                printed_page_label=label,
                unit_number=current_unit_number,
                unit_title=current_unit_title,
                mapping_status=mapping_status,
                extraction_status="ok",
                confidence=1.0,
                source_evidence=f"detected_{num_type}:{label}",
            )
        else:
            # No label detected
            if idx == 0:
                # Cover page
                mapping_status = "not_applicable"
                label = None
            else:
                mapping_status = "missing"
                label = None

            entry = PageMappingEntry(
                id=page_id,
                pdf_page_index=idx,
                printed_page_label=label,
                unit_number=current_unit_number,
                unit_title=current_unit_title,
                mapping_status=mapping_status,
                extraction_status="ok" if idx == 0 else "needs_review",
                confidence=0.5 if idx > 0 else 1.0,
                source_evidence="no_label_detected",
            )
        entries.append(entry)

    # Estimate dominant offset
    chosen_offset = manual_offset
    if chosen_offset is None and detected_offsets:
        from collections import Counter
        chosen_offset = Counter(detected_offsets).most_common(1)[0][0]

    # Third pass: interpolate missing labels using chosen offset
    if chosen_offset is not None:
        for entry in entries:
            if entry.mapping_status == "missing":
                inferred_num = entry.pdf_page_index - chosen_offset
                if inferred_num > 0:
                    entry.printed_page_label = str(inferred_num)
                    entry.mapping_status = "inferred"
                    entry.confidence = 0.85
                    entry.source_evidence = f"inferred_from_offset_{chosen_offset}"

    return TextbookPageMap(
        textbook_id=textbook_id,
        pdf_path=str(pdf_file),
        total_pages=total_pages,
        detected_offset=chosen_offset,
        entries=entries,
    )


def save_page_map_to_sqlite(
    page_map: TextbookPageMap,
    db: str | Path | sqlite3.Connection,
) -> int:
    """
    Idempotently persists the page map into the SQLite 'pages' table.
    Accepts a database path or an existing sqlite3.Connection.
    Returns the number of rows inserted/updated.
    """
    if isinstance(db, sqlite3.Connection):
        conn = db
    else:
        conn = get_connection(db, read_only=False)

    cursor = conn.cursor()

    count = 0
    with conn:
        for entry in page_map.entries:
            cursor.execute(
                """
                INSERT INTO pages (
                    id, textbook_id, pdf_page_index, printed_page_label,
                    unit_number, unit_title, mapping_status, extraction_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    printed_page_label = excluded.printed_page_label,
                    unit_number = excluded.unit_number,
                    unit_title = excluded.unit_title,
                    mapping_status = excluded.mapping_status,
                    extraction_status = excluded.extraction_status;
                """,
                (
                    entry.id,
                    page_map.textbook_id,
                    entry.pdf_page_index,
                    entry.printed_page_label,
                    entry.unit_number,
                    entry.unit_title,
                    entry.mapping_status,
                    entry.extraction_status,
                ),
            )
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="FidelRAG PDF Page Mapping & Provenance Tool")
    parser.add_argument("--pdf", type=str, required=True, help="Path to textbook PDF")
    parser.add_argument("--textbook-id", type=str, default="eth_sec_physics_g12_2023", help="Textbook identifier")
    parser.add_argument("--offset", type=int, default=None, help="Manual offset override (pdf_index - printed_page)")
    parser.add_argument("--sample-pages", type=str, default=None, help="Comma-separated page indices to inspect")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path for page map")
    parser.add_argument("--db", type=str, default=None, help="SQLite content database path to populate")
    parser.add_argument("--verify", action="store_true", help="Print summary verification report")

    args = parser.parse_args()

    page_map = build_page_map(args.pdf, args.textbook_id, args.offset)

    if args.verify or args.sample_pages:
        print("\n=== FidelRAG Page Provenance Report ===")
        print(f"Textbook ID:     {page_map.textbook_id}")
        print(f"Total PDF Pages: {page_map.total_pages}")
        print(f"Detected Offset: {page_map.detected_offset}")
        print("---------------------------------------")

        sample_indices = (
            [int(x.strip()) for x in args.sample_pages.split(",")]
            if args.sample_pages
            else [0, 1, 2, 3, 4, 5]
        )
        for idx in sample_indices:
            entry = page_map.get_entry_by_index(idx)
            if entry:
                print(
                    f"PDF Index {entry.pdf_page_index:03d} -> Printed: {str(entry.printed_page_label):>4} | "
                    f"Unit {entry.unit_number} ({entry.unit_title[:20]}) | "
                    f"Status: {entry.mapping_status} ({entry.source_evidence})"
                )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page_map.model_dump_json(indent=2))
        print(f"\nSaved page map JSON to: {out_path}")

    if args.db:
        rows = save_page_map_to_sqlite(page_map, args.db)
        print(f"Populated {rows} pages in SQLite: {args.db}")


if __name__ == "__main__":
    main()
