import unittest

from jee_knowledge_graph.models import ConceptCatalog
from jee_knowledge_graph.source_extract import HierarchyCandidate, TopicCandidate
from scripts.generate_physics_concept_graph_input import generate_edges, generate_records


class GeneratePhysicsConceptGraphInputTest(unittest.TestCase):
    def test_generates_records_with_stable_ids_and_prerequisite_edges(self):
        hierarchy = [
            HierarchyCandidate(
                document="leph1ps.pdf",
                chapter_label="TWO",
                chapter="Electrostatic Potential And Capacitance",
                topics=[
                    TopicCandidate(
                        number="2.2",
                        title="Electrostatic Potential",
                        source_page=13,
                    ),
                    TopicCandidate(
                        number="2.3",
                        title="Potential due to a Point Charge",
                        source_page=13,
                    ),
                ],
            )
        ]

        records = generate_records(hierarchy)
        catalog = ConceptCatalog(records=records)
        edges = generate_edges(catalog)

        self.assertEqual(
            records[0].id,
            "physics.electrostatic_potential_and_capacitance.2_2_electrostatic_potential",
        )
        self.assertEqual(records[1].prerequisites[0].concept_id, records[0].id)
        self.assertEqual(edges[0]["relation"], "REQUIRES")

    def test_repairs_known_pdf_chapter_text_artifacts(self):
        hierarchy = [
            HierarchyCandidate(
                document="leph1ps.pdf",
                chapter_label="THREE",
                chapter="Urrent Lectricity",
                topics=[
                    TopicCandidate(
                        number="3.2",
                        title="Electric Current",
                        source_page=14,
                    )
                ],
            )
        ]

        records = generate_records(hierarchy)

        self.assertEqual(records[0].chapter, "Current Electricity")


if __name__ == "__main__":
    unittest.main()
