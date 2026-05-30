from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PdfPage(Protocol):
    def extract_text(self) -> str | None: ...


class SourceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    filename: str
    source_kind: str
    title_hint: str
    page_count: int
    extracted_page_count: int
    heading_count: int
    extraction_notes: list[str] = Field(default_factory=list)


class HeadingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: str
    source_kind: str
    page: int
    level: str
    text: str

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("heading text cannot be blank")
        return stripped


class TopicCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str
    title: str
    source_page: int


class HierarchyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = "Physics"
    document: str
    chapter_label: str
    chapter: str
    topics: list[TopicCandidate] = Field(default_factory=list)
    status: str = "source_extracted"


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


NCERT_SECTION_PATTERN = re.compile(r"^(?P<number>\d{1,2}(?:\.\d+){1,3})\s+(?P<title>.+)$")
NCERT_CHAPTER_MARKER_PATTERN = re.compile(
    r"^(?:C\s+H\s+A\s+P\s+T\s+E\s+R|CHAPTER)\s+(?P<label>[A-Za-z0-9]+)$",
    re.IGNORECASE,
)
HCV_SECTION_PATTERN = re.compile(r"^(?P<number>\d{1,2}(?:\.\d+)?)\s+(?P<title>[A-Z][A-Za-z0-9 ,()'’/&-]+)\s+\d+$")
HCV_MIXED_COLUMN_PATTERN = re.compile(r"\b\d+\s+[A-Z]")
CHAPTER_HEADING_PATTERN = re.compile(r"^Chapter\s+(?P<label>[^:]+):\s+(?P<title>.+)$")
SECTION_HEADING_PATTERN = re.compile(r"^(?P<number>\d{1,2}(?:\.\d+){1,3})\s+(?P<title>.+)$")
MULTISPACE_PATTERN = re.compile(r"\s+")


def classify_physics_source(path: Path) -> str:
    name = path.name.lower()
    if "syllabus" in name:
        return "jee_syllabus"
    if "h.c._verma" in name or "hcverma" in name or "concepts_of_physics" in name:
        return "reference_book"
    if name.startswith("leph"):
        return "ncert_physics_english"
    if name.startswith("keph"):
        return "ncert_physics_english"
    return "unknown"


def title_hint_from_filename(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace(".", " ")
    return MULTISPACE_PATTERN.sub(" ", stem).strip()


def extract_page_texts(pdf, max_pages: int | None = None) -> list[PageText]:
    pages = pdf.pages[:max_pages] if max_pages else pdf.pages
    page_texts: list[PageText] = []
    for index, page in enumerate(pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            page_texts.append(PageText(page_number=index, text=text))
    return page_texts


def extract_heading_candidates(
    *,
    document: str,
    source_kind: str,
    pages: list[PageText],
) -> list[HeadingCandidate]:
    if source_kind == "reference_book":
        return _extract_hcv_headings(document, source_kind, pages)
    if source_kind.startswith("ncert_physics"):
        return _extract_ncert_headings(document, source_kind, pages)
    return []


def build_hierarchy_candidates(headings: list[HeadingCandidate]) -> list[HierarchyCandidate]:
    candidates: list[HierarchyCandidate] = []
    active_by_document: dict[str, HierarchyCandidate] = {}

    for heading in headings:
        if heading.source_kind != "ncert_physics_english":
            continue
        chapter_match = CHAPTER_HEADING_PATTERN.match(heading.text)
        if heading.level == "chapter" and chapter_match:
            candidate = HierarchyCandidate(
                document=heading.document,
                chapter_label=chapter_match.group("label"),
                chapter=chapter_match.group("title"),
            )
            candidates.append(candidate)
            active_by_document[heading.document] = candidate
            continue

        section_match = SECTION_HEADING_PATTERN.match(heading.text)
        active = active_by_document.get(heading.document)
        if heading.level in {"section", "subsection"} and section_match and active:
            active.topics.append(
                TopicCandidate(
                    number=section_match.group("number"),
                    title=section_match.group("title"),
                    source_page=heading.page,
                )
            )

    return [candidate for candidate in candidates if candidate.topics]


def _extract_ncert_headings(
    document: str,
    source_kind: str,
    pages: list[PageText],
) -> list[HeadingCandidate]:
    headings: list[HeadingCandidate] = []
    pending_chapter_label: str | None = None
    for page in pages:
        for raw_line in page.text.splitlines():
            line = _clean_line(raw_line)
            if not line:
                continue
            chapter_marker = NCERT_CHAPTER_MARKER_PATTERN.match(line)
            if chapter_marker:
                pending_chapter_label = chapter_marker.group("label")
                continue
            if pending_chapter_label and _looks_like_ncert_contents_chapter_title(line):
                headings.append(
                    HeadingCandidate(
                        document=document,
                        source_kind=source_kind,
                        page=page.page_number,
                        level="chapter",
                        text=f"Chapter {pending_chapter_label}: {_strip_trailing_page_number(line).title()}",
                    )
                )
                pending_chapter_label = None
                continue
            section_match = NCERT_SECTION_PATTERN.match(line)
            if section_match:
                text = f"{section_match.group('number')} {section_match.group('title')}"
                headings.append(
                    HeadingCandidate(
                        document=document,
                        source_kind=source_kind,
                        page=page.page_number,
                        level=_level_for_number(section_match.group("number")),
                        text=_strip_trailing_page_number(text),
                    )
                )
                continue
    return _dedupe_headings(headings)


def _extract_hcv_headings(
    document: str,
    source_kind: str,
    pages: list[PageText],
) -> list[HeadingCandidate]:
    headings: list[HeadingCandidate] = []
    for page in pages:
        lines = [_clean_line(line) for line in page.text.splitlines()]
        for line in lines:
            if not line:
                continue
            section_match = HCV_SECTION_PATTERN.match(line)
            if section_match and not _looks_like_mixed_hcv_columns(section_match.group("title")):
                headings.append(
                    HeadingCandidate(
                        document=document,
                        source_kind=source_kind,
                        page=page.page_number,
                        level=_level_for_number(section_match.group("number")),
                        text=f"{section_match.group('number')} {section_match.group('title')}",
                    )
                )
    return _dedupe_headings(headings)


def _clean_line(line: str) -> str:
    line = line.replace("\u2013", "-").replace("\u2014", "-")
    return MULTISPACE_PATTERN.sub(" ", line).strip()


def _level_for_number(number: str) -> str:
    depth = number.count(".")
    if depth == 0:
        return "chapter"
    if depth == 1:
        return "section"
    return "subsection"


def _looks_like_ncert_contents_chapter_title(line: str) -> bool:
    if len(line) < 4 or len(line) > 80:
        return False
    words = line.split()
    if len(words) > 8:
        return False
    without_page = _strip_trailing_page_number(line)
    if not without_page or without_page.lower() in {"answers", "appendices", "bibliography", "index"}:
        return False
    return bool(re.search(r"[A-Za-z]", without_page))


def _looks_like_mixed_hcv_columns(title: str) -> bool:
    return bool(HCV_MIXED_COLUMN_PATTERN.search(title))


def _strip_trailing_page_number(line: str) -> str:
    return re.sub(r"\s+\d+\s*$", "", line).strip()


def _dedupe_headings(headings: list[HeadingCandidate]) -> list[HeadingCandidate]:
    deduped: list[HeadingCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for heading in headings:
        key = (heading.document, heading.level, heading.text.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(heading)
    return deduped
