import unittest

from jee_knowledge_graph import ConceptCatalog, MicroConceptRecord, PrerequisiteEdge
from scripts.apply_physics_prerequisite_overlay import apply_overlay, collect_edges, _load_concepts


def record(concept_id: str, name: str) -> MicroConceptRecord:
    return MicroConceptRecord(
        id=concept_id,
        subject="Physics",
        chapter="Sample",
        topic=name,
        micro_concept=name,
        definition=f"Understand {name}.",
        testable_skill=f"Apply {name}.",
        difficulty="foundation",
    )


class ApplyPhysicsPrerequisiteOverlayTest(unittest.TestCase):
    def test_applies_overlay_edge_to_concept_record(self):
        base = record("physics.sample.base", "Base")
        target = record("physics.sample.target", "Target")
        catalog = ConceptCatalog(records=[base, target])

        enriched = apply_overlay(
            catalog,
            [
                PrerequisiteEdge(
                    from_concept_id=target.id,
                    to_prerequisite_id=base.id,
                    dependency_type="conceptual",
                    reason="Target requires Base.",
                    source="test",
                )
            ],
        )

        target_record = enriched.by_id()[target.id]
        self.assertEqual(target_record.prerequisites[0].concept_id, base.id)
        self.assertEqual(target_record.prerequisites[0].concept, "Base")

    def test_collect_edges_from_enriched_records(self):
        base = record("physics.sample.base", "Base")
        target = record("physics.sample.target", "Target")
        enriched = apply_overlay(
            ConceptCatalog(records=[base, target]),
            [
                PrerequisiteEdge(
                    from_concept_id=target.id,
                    to_prerequisite_id=base.id,
                    dependency_type="conceptual",
                    reason="Target requires Base.",
                    source="test",
                )
            ],
        )

        edges = collect_edges(enriched)

        self.assertEqual(edges[0].from_concept_id, target.id)
        self.assertEqual(edges[0].to_prerequisite_id, base.id)

    def test_overlay_upgrades_existing_prerequisite_quality(self):
        base = record("physics.sample.base", "Base")
        target = MicroConceptRecord(
            id="physics.sample.target",
            subject="Physics",
            chapter="Sample",
            topic="Target",
            micro_concept="Target",
            definition="Understand Target.",
            testable_skill="Apply Target.",
            prerequisites=[
                {
                    "concept": "Base",
                    "concept_id": base.id,
                    "type": "conceptual",
                    "reason": "Source-order reason.",
                    "quality": "source_order",
                }
            ],
        )

        enriched = apply_overlay(
            ConceptCatalog(records=[base, target]),
            [
                PrerequisiteEdge(
                    from_concept_id=target.id,
                    to_prerequisite_id=base.id,
                    dependency_type="procedural",
                    reason="Curated reason.",
                    source="test",
                    quality="curated",
                )
            ],
        )

        prerequisite = enriched.by_id()[target.id].prerequisites[0]
        self.assertEqual(prerequisite.quality, "curated")
        self.assertEqual(prerequisite.reason, "Curated reason.")
        self.assertEqual(prerequisite.type, "procedural")

    def test_rejects_unknown_overlay_references(self):
        catalog = ConceptCatalog(records=[record("physics.sample.base", "Base")])

        with self.assertRaisesRegex(ValueError, "unknown concept ids"):
            apply_overlay(
                catalog,
                [
                    PrerequisiteEdge(
                        from_concept_id="physics.sample.missing",
                        to_prerequisite_id="physics.sample.base",
                        dependency_type="conceptual",
                        reason="Missing source.",
                        source="test",
                    )
                ],
            )

    def test_load_concepts_accepts_overlay_referencing_base_records(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        import json

        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "base.jsonl"
            overlay_path = Path(tmpdir) / "overlay.jsonl"
            base = record("physics.sample.base", "Base")
            overlay = MicroConceptRecord(
                id="physics.sample.overlay",
                subject="Physics",
                chapter="Sample",
                topic="Overlay",
                micro_concept="Overlay",
                definition="Understand Overlay.",
                testable_skill="Apply Overlay.",
                prerequisites=[
                    {
                        "concept": "Base",
                        "concept_id": base.id,
                        "type": "conceptual",
                        "reason": "Overlay uses Base.",
                        "quality": "curated",
                    }
                ],
            )
            base_path.write_text(json.dumps(base.model_dump()) + "\n", encoding="utf-8")
            overlay_path.write_text(json.dumps(overlay.model_dump()) + "\n", encoding="utf-8")

            catalog = _load_concepts(base_path, overlay_path)

        self.assertIn("physics.sample.overlay", catalog.by_id())


if __name__ == "__main__":
    unittest.main()
