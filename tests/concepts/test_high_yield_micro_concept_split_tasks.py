import tempfile
import unittest
from pathlib import Path

from scripts.prepare_high_yield_micro_concept_split_tasks import build_split_tasks


class HighYieldMicroConceptSplitTasksTest(unittest.TestCase):
    def test_builds_tasks_for_selected_chapter_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "concepts.jsonl"
            path.write_text(
                (
                    '{"id":"physics.electrostatics.field","subject":"Physics",'
                    '"chapter":"Electric Charges And Fields","topic":"Electric Field",'
                    '"micro_concept":"Electric Field","definition":"Definition.",'
                    '"testable_skill":"Skill.","difficulty":"foundation","status":"draft"}\n'
                    '{"id":"physics.optics.ray","subject":"Physics",'
                    '"chapter":"Ray Optics And Optical Instruments","topic":"Reflection",'
                    '"micro_concept":"Reflection","definition":"Definition.",'
                    '"testable_skill":"Skill.","difficulty":"foundation","status":"draft"}\n'
                ),
                encoding="utf-8",
            )

            tasks = build_split_tasks(path, {"Electric Charges And Fields"})

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["parent_concept"]["chapter"], "Electric Charges And Fields")


if __name__ == "__main__":
    unittest.main()
