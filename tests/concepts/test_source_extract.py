import unittest
from pathlib import Path

from jee_knowledge_graph.source_extract import (
    HeadingCandidate,
    PageText,
    build_hierarchy_candidates,
    classify_physics_source,
    extract_heading_candidates,
    title_hint_from_filename,
)


class SourceExtractTest(unittest.TestCase):
    def test_classifies_known_physics_sources(self):
        self.assertEqual(
            classify_physics_source(Path("concepts_of_physics_by_h.c._verma_volume_1.pdf")),
            "reference_book",
        )
        self.assertEqual(classify_physics_source(Path("leph101.pdf")), "ncert_physics_english")
        self.assertEqual(classify_physics_source(Path("keph101.pdf")), "ncert_physics_english")
        self.assertEqual(classify_physics_source(Path("syllabus (1).pdf")), "jee_syllabus")

    def test_title_hint_normalizes_filename(self):
        self.assertEqual(
            title_hint_from_filename(Path("concepts_of_physics_by_h.c._verma_volume_1.pdf")),
            "concepts of physics by h c verma volume 1",
        )

    def test_extracts_ncert_numbered_headings(self):
        headings = extract_heading_candidates(
            document="leph101.pdf",
            source_kind="ncert_physics_english",
            pages=[
                PageText(
                    page_number=1,
                    text=(
                        "CHAPTER ONE\n"
                        "ELECTRIC CHARGES AND FIELDS\n"
                        "1.1 Introduction 1\n"
                        "1.4.1 Additivity of charges 4\n"
                    ),
                )
            ],
        )

        self.assertEqual(
            [heading.text for heading in headings],
            [
                "Chapter ONE: Electric Charges And Fields",
                "1.1 Introduction",
                "1.4.1 Additivity of charges",
            ],
        )
        self.assertEqual(headings[-1].level, "subsection")

    def test_extracts_hcv_table_of_contents_headings(self):
        headings = extract_heading_candidates(
            document="concepts_of_physics_by_h.c._verma_volume_1.pdf",
            source_kind="reference_book",
            pages=[
                PageText(
                    page_number=7,
                    text=(
                        "Chapter 5\n"
                        "Newton's Laws of Motion 64\n"
                        "5.1 First Law of Motion 64\n"
                        "5.2 Second Law of Motion 65\n"
                    ),
                )
            ],
        )

        self.assertEqual(
            [heading.text for heading in headings],
            [
                "5.1 First Law of Motion",
                "5.2 Second Law of Motion",
            ],
        )

    def test_drops_hcv_mixed_column_lines(self):
        headings = extract_heading_candidates(
            document="concepts_of_physics_by_h.c._verma_volume_1.pdf",
            source_kind="reference_book",
            pages=[
                PageText(
                    page_number=7,
                    text="1.2 Physics and Mathematics 1 The Forces 56\n1.3 Units 2\n",
                )
            ],
        )

        self.assertEqual([heading.text for heading in headings], ["1.3 Units"])

    def test_builds_hierarchy_candidates_from_ncert_headings(self):
        hierarchy = build_hierarchy_candidates(
            [
                HeadingCandidate(
                    document="keph1ps.pdf",
                    source_kind="ncert_physics_english",
                    page=13,
                    level="chapter",
                    text="Chapter 1: Units And Measurements",
                ),
                HeadingCandidate(
                    document="keph1ps.pdf",
                    source_kind="ncert_physics_english",
                    page=13,
                    level="section",
                    text="1.2 The international system of units",
                ),
            ]
        )

        self.assertEqual(len(hierarchy), 1)
        self.assertEqual(hierarchy[0].chapter, "Units And Measurements")
        self.assertEqual(hierarchy[0].topics[0].number, "1.2")


if __name__ == "__main__":
    unittest.main()
