import argparse
import json
from pathlib import Path

import pdfplumber

from jee_knowledge_graph.source_extract import (
    SourceDocument,
    classify_physics_source,
    extract_heading_candidates,
    extract_page_texts,
    title_hint_from_filename,
)


DEFAULT_SOURCE_DIR = Path(r"C:\Users\Saurabh\Downloads\physics")
DEFAULT_OUTPUT_DIR = Path("data/concepts/physics_sources")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract reviewable heading candidates from local Physics PDFs."
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional cap for debugging extraction without reading whole PDFs.",
    )
    parser.add_argument(
        "--include-kind",
        action="append",
        default=[],
        help=(
            "Only extract source kinds matching this value. Can be passed multiple times. "
            "Examples: reference_book, ncert_physics_english, jee_syllabus."
        ),
    )
    parser.add_argument(
        "--include-name",
        action="append",
        default=[],
        help=(
            "Only extract PDFs whose filename contains this case-insensitive text. "
            "Can be passed multiple times."
        ),
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    documents: list[SourceDocument] = []
    all_headings = []

    pdf_paths = []
    for pdf_path in sorted(args.source_dir.glob("*.pdf")):
        source_kind = classify_physics_source(pdf_path)
        if args.include_kind and source_kind not in args.include_kind:
            continue
        if args.include_name and not any(
            name.lower() in pdf_path.name.lower() for name in args.include_name
        ):
            continue
        pdf_paths.append(pdf_path)
    for pdf_path in pdf_paths:
        source_kind = classify_physics_source(pdf_path)
        notes: list[str] = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_texts = extract_page_texts(pdf, args.max_pages)
                headings = extract_heading_candidates(
                    document=pdf_path.name,
                    source_kind=source_kind,
                    pages=page_texts,
                )
                if not page_texts:
                    notes.append("No embedded text extracted; OCR or text source required.")
                if not headings:
                    notes.append("No heading candidates extracted.")
                documents.append(
                    SourceDocument(
                        path=str(pdf_path),
                        filename=pdf_path.name,
                        source_kind=source_kind,
                        title_hint=title_hint_from_filename(pdf_path),
                        page_count=len(pdf.pages),
                        extracted_page_count=len(page_texts),
                        heading_count=len(headings),
                        extraction_notes=notes,
                    )
                )
                all_headings.extend(headings)
        except Exception as exc:
            documents.append(
                SourceDocument(
                    path=str(pdf_path),
                    filename=pdf_path.name,
                    source_kind=source_kind,
                    title_hint=title_hint_from_filename(pdf_path),
                    page_count=0,
                    extracted_page_count=0,
                    heading_count=0,
                    extraction_notes=[f"Extraction failed: {exc.__class__.__name__}: {exc}"],
                )
            )

    _write_json(args.output_dir / "inventory.json", [doc.model_dump() for doc in documents])
    _write_jsonl(args.output_dir / "heading_candidates.jsonl", all_headings)

    print(
        "Extracted "
        f"{len(all_headings)} heading candidates from {len(documents)} PDF source documents."
    )
    print(f"Wrote {args.output_dir / 'inventory.json'}")
    print(f"Wrote {args.output_dir / 'heading_candidates.jsonl'}")
    return 0


def _write_json(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
