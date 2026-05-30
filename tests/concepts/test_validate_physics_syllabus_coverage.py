import unittest

from scripts.validate_physics_syllabus_coverage import validate_coverage


class ValidatePhysicsSyllabusCoverageTest(unittest.TestCase):
    def test_validate_coverage_passes_when_all_mapped_chapters_exist(self):
        coverage = {
            "exam": "JEE Advanced",
            "year": 2026,
            "subject": "Physics",
            "official_source_url": "https://example.test/syllabus.pdf",
            "coverage_groups": [
                {
                    "official_area": "Electricity and Magnetism",
                    "graph_chapters": ["Electric Charges And Fields"],
                }
            ],
        }

        report = validate_coverage(coverage, {"Electric Charges And Fields"})

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["covered_chapter_count"], 1)

    def test_validate_coverage_reports_missing_chapters(self):
        coverage = {
            "exam": "JEE Advanced",
            "year": 2026,
            "subject": "Physics",
            "official_source_url": "https://example.test/syllabus.pdf",
            "coverage_groups": [
                {
                    "official_area": "Optics",
                    "graph_chapters": ["Wave Optics"],
                }
            ],
        }

        report = validate_coverage(coverage, set())

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["missing_chapters"][0]["chapter"], "Wave Optics")


if __name__ == "__main__":
    unittest.main()
