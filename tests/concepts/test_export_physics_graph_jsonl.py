import unittest

from jee_knowledge_graph import ConceptCatalog, MicroConceptRecord, PrerequisiteEdge
from scripts.export_physics_graph_jsonl import export_graph


def concept(concept_id: str, topic: str) -> MicroConceptRecord:
    return MicroConceptRecord(
        id=concept_id,
        subject="Physics",
        chapter="Electrostatics",
        topic=topic,
        micro_concept=topic,
        definition=f"Understand {topic}.",
        testable_skill=f"Apply {topic}.",
        common_confusions=[
            {
                "confusion": f"Confuses {topic} with another concept.",
                "diagnostic_signal": f"Uses another concept while solving {topic}.",
                "root_gap": topic,
            }
        ],
        difficulty="foundation",
    )


class ExportPhysicsGraphJsonlTest(unittest.TestCase):
    def test_exports_hierarchy_and_prerequisite_relationships(self):
        first = concept("physics.electrostatics.electric_field", "Electric Field")
        second = concept("physics.electrostatics.electric_potential", "Electric Potential")
        edge = PrerequisiteEdge(
            from_concept_id=second.id,
            to_prerequisite_id=first.id,
            dependency_type="conceptual",
            reason="Potential depends on field.",
            source="test",
        )

        nodes, relationships = export_graph(ConceptCatalog(records=[first, second]), [edge])

        node_labels = {node["label"] for node in nodes}
        relationship_types = {relationship["type"] for relationship in relationships}

        self.assertEqual(node_labels, {"Subject", "Chapter", "Topic", "MicroConcept"})
        self.assertIn("HAS_CHAPTER", relationship_types)
        self.assertIn("HAS_TOPIC", relationship_types)
        self.assertIn("HAS_MICRO_CONCEPT", relationship_types)
        self.assertIn("REQUIRES", relationship_types)
        first_node = next(node for node in nodes if node["id"] == first.id)
        self.assertEqual(
            f"Confuses {first.topic} with another concept.",
            first_node["common_confusions"][0]["confusion"],
        )

    def test_rejects_edges_to_unknown_concepts(self):
        first = concept("physics.electrostatics.electric_field", "Electric Field")
        edge = PrerequisiteEdge(
            from_concept_id=first.id,
            to_prerequisite_id="physics.missing",
            dependency_type="conceptual",
            reason="Missing concept.",
            source="test",
        )

        with self.assertRaisesRegex(ValueError, "unknown concept id"):
            export_graph(ConceptCatalog(records=[first]), [edge])


if __name__ == "__main__":
    unittest.main()
