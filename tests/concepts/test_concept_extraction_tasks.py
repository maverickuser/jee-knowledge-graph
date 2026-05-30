import unittest

from scripts.prepare_physics_concept_extraction_tasks import _build_task
from jee_knowledge_graph.source_extract import HierarchyCandidate, TopicCandidate


class ConceptExtractionTaskTest(unittest.TestCase):
    def test_build_task_contains_schema_and_source_context(self):
        candidate = HierarchyCandidate(
            document="leph1ps.pdf",
            chapter_label="TWO",
            chapter="Electrostatic Potential And Capacitance",
            topics=[
                TopicCandidate(
                    number="2.2",
                    title="Electrostatic Potential",
                    source_page=13,
                )
            ],
        )

        task = _build_task(candidate)

        self.assertEqual(task["task_id"], "physics.electrostatic_potential_and_capacitance")
        self.assertEqual(task["source_context"]["chapter"], candidate.chapter)
        self.assertEqual(task["expected_output_schema"]["status"], "draft")
        self.assertIn("prerequisites", task["expected_output_schema"])


if __name__ == "__main__":
    unittest.main()
