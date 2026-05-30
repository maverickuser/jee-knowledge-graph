import unittest

from scripts.filter_diagnostic_prerequisite_edges import filter_edges


class FilterDiagnosticPrerequisiteEdgesTest(unittest.TestCase):
    def test_keeps_only_allowed_quality_edges(self):
        edges = [
            {"quality": "source_order", "id": "a"},
            {"quality": "curated", "id": "b"},
            {"quality": "expert_reviewed", "id": "c"},
        ]

        filtered = filter_edges(edges, {"curated", "expert_reviewed"})

        self.assertEqual([edge["id"] for edge in filtered], ["b", "c"])


if __name__ == "__main__":
    unittest.main()
