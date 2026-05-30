import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from jee_knowledge_graph import (
    CommonConfusion,
    ConceptCatalog,
    MicroConceptRecord,
    Prerequisite,
    load_expert_concepts_jsonl,
)


def foundation_record(concept_id: str, name: str) -> MicroConceptRecord:
    return MicroConceptRecord(
        id=concept_id,
        subject="Physics",
        chapter="Electrostatics",
        topic="Electric Potential & Energy",
        micro_concept=name,
        definition=f"Definition for {name}.",
        testable_skill=f"Test {name}.",
        difficulty="foundation",
        status="approved",
    )


class ExpertConceptTest(unittest.TestCase):
    def test_validates_micro_concept_record(self):
        record = MicroConceptRecord(
            id="physics.electrostatics.electric_potential.uniform_solid_sphere_potential",
            subject="Physics",
            chapter="Electrostatics",
            topic="Electric Potential & Energy",
            micro_concept="Potential due to uniformly charged non-conducting solid sphere",
            definition=(
                "Find and reason about electric potential inside, on, and outside a uniformly "
                "charged insulating sphere."
            ),
            testable_skill=(
                "Given radius, charge, and point distance, determine potential using the "
                "correct inside or outside expression."
            ),
            formulas=[
                "$V(r)=\\frac{kQ}{r}$ for $r \\ge R$",
                "$V(r)=\\frac{kQ}{2R}\\left(3-\\frac{r^2}{R^2}\\right)$ for $r < R$",
            ],
            prerequisites=[
                Prerequisite(
                    concept="Gauss law for spherical symmetry",
                    type="procedural",
                    reason="Needed to derive the electric field inside and outside the sphere.",
                )
            ],
            common_confusions=[
                CommonConfusion(
                    confusion="Treating non-conducting sphere like conducting sphere",
                    diagnostic_signal="Student assumes potential is constant everywhere inside.",
                    root_gap="Difference between conductor and non-conductor charge distribution.",
                )
            ],
        )

        self.assertEqual(record.subject, "Physics")
        self.assertEqual(record.prerequisites[0].type, "procedural")

    def test_rejects_blank_required_text(self):
        with self.assertRaises(ValidationError):
            MicroConceptRecord(
                id=" ",
                subject="Physics",
                chapter="Electrostatics",
                topic="Electric Potential & Energy",
                micro_concept="Potential",
                definition="Definition.",
                testable_skill="Skill.",
            )

    def test_approved_non_foundation_record_requires_prerequisite(self):
        with self.assertRaisesRegex(ValidationError, "require at least one prerequisite"):
            MicroConceptRecord(
                id="physics.electrostatics.electric_potential.uniform_solid_sphere_potential",
                subject="Physics",
                chapter="Electrostatics",
                topic="Electric Potential & Energy",
                micro_concept="Potential due to uniformly charged non-conducting solid sphere",
                definition="Definition.",
                testable_skill="Skill.",
                status="approved",
            )

    def test_catalog_rejects_duplicate_ids(self):
        record = foundation_record("physics.electrostatics.potential", "Potential")

        with self.assertRaisesRegex(ValidationError, "duplicate concept ids"):
            ConceptCatalog(records=[record, record])

    def test_catalog_rejects_unknown_prerequisite_reference(self):
        record = MicroConceptRecord(
            id="physics.electrostatics.electric_potential.uniform_solid_sphere_potential",
            subject="Physics",
            chapter="Electrostatics",
            topic="Electric Potential & Energy",
            micro_concept="Potential due to uniformly charged non-conducting solid sphere",
            definition="Definition.",
            testable_skill="Skill.",
            prerequisites=[
                Prerequisite(
                    concept="Gauss law for spherical symmetry",
                    concept_id="physics.electrostatics.gauss_law.spherical_symmetry",
                    type="procedural",
                    reason="Needed to derive the field expression.",
                )
            ],
        )

        with self.assertRaisesRegex(ValidationError, "unknown prerequisite concept ids"):
            ConceptCatalog(records=[record])

    def test_catalog_rejects_required_dependency_cycles(self):
        first = foundation_record("concept.a", "Concept A")
        first.prerequisites.append(
            Prerequisite(
                concept="Concept B",
                concept_id="concept.b",
                type="conceptual",
                reason="A requires B.",
            )
        )
        second = foundation_record("concept.b", "Concept B")
        second.prerequisites.append(
            Prerequisite(
                concept="Concept A",
                concept_id="concept.a",
                type="conceptual",
                reason="B requires A.",
            )
        )

        with self.assertRaisesRegex(ValidationError, "required prerequisite cycle"):
            ConceptCatalog(records=[first, second])

    def test_loads_jsonl_catalog(self):
        sample = (
            '{"id":"concept.a","subject":"Physics","chapter":"Electrostatics",'
            '"topic":"Electric Potential & Energy","micro_concept":"Concept A",'
            '"definition":"Definition.","testable_skill":"Skill.",'
            '"difficulty":"foundation","status":"approved"}\n'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "concepts.jsonl"
            path.write_text(sample, encoding="utf-8")

            catalog = load_expert_concepts_jsonl(path)

        self.assertEqual(list(catalog.by_id()), ["concept.a"])

    def test_sample_expert_concepts_file_is_valid(self):
        sample_path = Path(__file__).parents[2] / "data" / "concepts" / "expert_concepts.sample.jsonl"

        catalog = load_expert_concepts_jsonl(sample_path)

        self.assertEqual(len(catalog.records), 1)


if __name__ == "__main__":
    unittest.main()
