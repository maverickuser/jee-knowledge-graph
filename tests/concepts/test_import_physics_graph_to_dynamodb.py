import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jee_knowledge_graph.dynamodb_import import (
    build_active_control_item,
    build_dynamodb_items,
    build_import_plan,
    stale_item_filter,
)
from jee_knowledge_graph.dynamodb_import.cli import main


CREATED_AT = "2026-05-30T12:00:00+00:00"
GRAPH_VERSION = "physics-2026-05-30T120000Z"


def concept(concept_id: str, name: str, aliases: list[str] | None = None) -> dict:
    return {
        "id": concept_id,
        "label": "MicroConcept",
        "name": name,
        "subject": "Physics",
        "chapter": "Electrostatics",
        "topic": "Potential",
        "definition": f"Understand {name}.",
        "testable_skill": f"Apply {name}.",
        "formulas": [],
        "aliases": aliases or [],
        "source_refs": ["fixture"],
        "common_confusions": [],
        "difficulty": "foundation",
        "status": "draft",
    }


def edge(source: str, prerequisite: str, quality: str = "curated") -> dict:
    return {
        "from_concept_id": source,
        "to_prerequisite_id": prerequisite,
        "relation": "REQUIRES",
        "dependency_type": "conceptual",
        "required": True,
        "reason": f"{source} requires {prerequisite}.",
        "status": "draft",
        "source": "fixture",
        "quality": quality,
    }


class ImportPhysicsGraphToDynamoDbTest(unittest.TestCase):
    def test_builds_versioned_concept_and_index_items(self):
        first = concept("physics.a", "Electric Field", aliases=["field strength"])

        items = build_dynamodb_items(
            nodes=[first],
            relationships=[],
            diagnostic_edges=[],
            graph_version=GRAPH_VERSION,
            created_at=CREATED_AT,
        )

        concept_item = next(item for item in items if item["entity_type"] == "Concept")
        self.assertEqual(
            concept_item["PK"],
            f"GRAPH#physics#VERSION#{GRAPH_VERSION}#CONCEPT#physics.a",
        )
        self.assertEqual(concept_item["SK"], "META")
        self.assertEqual(concept_item["graph_version"], GRAPH_VERSION)
        token_keys = {item["PK"] for item in items if item["entity_type"] == "SearchTermConcept"}
        self.assertIn(f"GRAPH#physics#VERSION#{GRAPH_VERSION}#TERM#field", token_keys)
        self.assertIn(f"GRAPH#physics#VERSION#{GRAPH_VERSION}#TERM#strength", token_keys)

    def test_diagnostic_edges_create_direct_prerequisite_and_reverse_items(self):
        first = concept("physics.a", "Electric Field")
        second = concept("physics.b", "Electric Potential")

        items = build_dynamodb_items(
            nodes=[first, second],
            relationships=[],
            diagnostic_edges=[edge("physics.b", "physics.a")],
            graph_version=GRAPH_VERSION,
            created_at=CREATED_AT,
        )

        prerequisite = next(
            item
            for item in items
            if item["entity_type"] == "Prerequisite" and item["depth"] == 1
        )
        reverse = next(item for item in items if item["entity_type"] == "RequiredBy")

        self.assertEqual(prerequisite["SK"], "PREREQ#D1#curated#physics.a")
        self.assertEqual(prerequisite["concept_id"], "physics.b")
        self.assertEqual(reverse["PK"], f"GRAPH#physics#VERSION#{GRAPH_VERSION}#CONCEPT#physics.a")
        self.assertEqual(reverse["dependent_concept_id"], "physics.b")

    def test_excludes_source_order_edges_from_diagnostic_items(self):
        first = concept("physics.a", "Electric Field")
        second = concept("physics.b", "Electric Potential")

        items = build_dynamodb_items(
            nodes=[first, second],
            relationships=[],
            diagnostic_edges=[edge("physics.b", "physics.a", quality="source_order")],
            graph_version=GRAPH_VERSION,
            created_at=CREATED_AT,
        )

        self.assertFalse(any(item["entity_type"] == "Prerequisite" for item in items))

    def test_precomputes_depth_two_prerequisite_chain(self):
        first = concept("physics.a", "Electric Field")
        second = concept("physics.b", "Electric Potential")
        third = concept("physics.c", "Capacitance")

        items = build_dynamodb_items(
            nodes=[first, second, third],
            relationships=[],
            diagnostic_edges=[
                edge("physics.c", "physics.b"),
                edge("physics.b", "physics.a"),
            ],
            graph_version=GRAPH_VERSION,
            created_at=CREATED_AT,
        )

        depth_two = next(
            item
            for item in items
            if item["entity_type"] == "Prerequisite" and item["depth"] == 2
        )

        self.assertEqual(depth_two["concept_id"], "physics.c")
        self.assertEqual(depth_two["prerequisite_id"], "physics.a")
        self.assertEqual(depth_two["path"], ["physics.c", "physics.b", "physics.a"])

    def test_builds_active_control_item_from_validated_report(self):
        active = build_active_control_item(
            {
                "graph_version": GRAPH_VERSION,
                "created_at": CREATED_AT,
                "counts": {"Concept": 1, "total_items": 3},
                "source_artifacts": [{"path": "nodes.jsonl", "sha256": "abc"}],
                "status": "validated",
            }
        )

        self.assertEqual(active["PK"], "GRAPH#physics")
        self.assertEqual(active["SK"], "ACTIVE")
        self.assertEqual(active["active_graph_version"], GRAPH_VERSION)

    def test_build_import_plan_reads_files_and_computes_artifact_hashes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nodes = root / "nodes.jsonl"
            relationships = root / "relationships.jsonl"
            diagnostic = root / "diagnostic.jsonl"
            _write_jsonl(nodes, [concept("physics.a", "Electric Field"), concept("physics.b", "Potential")])
            _write_jsonl(relationships, [{"start_id": "x", "end_id": "y", "type": "HAS_TOPIC"}])
            _write_jsonl(diagnostic, [edge("physics.b", "physics.a")])

            plan = build_import_plan(
                nodes_path=nodes,
                relationships_path=relationships,
                diagnostic_edges_path=diagnostic,
                graph_version=GRAPH_VERSION,
                created_at=CREATED_AT,
            )

        self.assertEqual(plan["report"]["status"], "validated")
        self.assertEqual(plan["active_control_item"]["active_graph_version"], GRAPH_VERSION)
        self.assertEqual(len(plan["report"]["source_artifacts"]), 3)

    def test_dry_run_cli_writes_preview_and_report_without_aws(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nodes = root / "nodes.jsonl"
            relationships = root / "relationships.jsonl"
            diagnostic = root / "diagnostic.jsonl"
            preview = root / "preview.jsonl"
            report = root / "report.json"
            _write_jsonl(nodes, [concept("physics.a", "Electric Field"), concept("physics.b", "Potential")])
            _write_jsonl(relationships, [{"start_id": "x", "end_id": "y", "type": "HAS_TOPIC"}])
            _write_jsonl(diagnostic, [edge("physics.b", "physics.a")])

            with patch(
                "sys.argv",
                [
                    "import_physics_graph_to_dynamodb.py",
                    "--table-name",
                    "test-table",
                    "--artifact-bucket",
                    "test-bucket",
                    "--graph-version",
                    GRAPH_VERSION,
                    "--nodes",
                    str(nodes),
                    "--relationships",
                    str(relationships),
                    "--diagnostic-edges",
                    str(diagnostic),
                    "--output",
                    str(preview),
                    "--report-output",
                    str(report),
                    "--dry-run",
                ],
            ):
                exit_code = main()

            self.assertEqual(exit_code, 0)
            self.assertTrue(preview.exists())
            self.assertTrue(report.exists())
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "validated")

    def test_stale_item_filter_never_deletes_active_version(self):
        old_item = {
            "graph_version": "physics-old",
            "created_at": "2026-04-01T00:00:00+00:00",
        }
        active_item = {
            "graph_version": GRAPH_VERSION,
            "created_at": "2026-04-01T00:00:00+00:00",
        }

        self.assertTrue(stale_item_filter(old_item, GRAPH_VERSION, "2026-05-01T00:00:00+00:00"))
        self.assertFalse(stale_item_filter(active_item, GRAPH_VERSION, "2026-05-01T00:00:00+00:00"))


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    unittest.main()
