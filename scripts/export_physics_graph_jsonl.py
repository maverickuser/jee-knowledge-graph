import argparse
import json
import re
from pathlib import Path

from jee_knowledge_graph import ConceptCatalog, MicroConceptRecord, PrerequisiteEdge


DEFAULT_CONCEPT_INPUT = Path("data/concepts/physics_concepts.enriched.jsonl")
DEFAULT_EDGE_INPUT = Path("data/concepts/physics_prerequisite_edges.enriched.jsonl")
DEFAULT_NODE_OUTPUT = Path("data/concepts/graph/physics_nodes.jsonl")
DEFAULT_REL_OUTPUT = Path("data/concepts/graph/physics_relationships.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export enriched Physics concepts as graph node and relationship JSONL."
    )
    parser.add_argument("--concept-input", type=Path, default=DEFAULT_CONCEPT_INPUT)
    parser.add_argument("--edge-input", type=Path, default=DEFAULT_EDGE_INPUT)
    parser.add_argument("--node-output", type=Path, default=DEFAULT_NODE_OUTPUT)
    parser.add_argument("--relationship-output", type=Path, default=DEFAULT_REL_OUTPUT)
    args = parser.parse_args()

    catalog = _load_concepts(args.concept_input)
    prerequisite_edges = _load_edges(args.edge_input)
    nodes, relationships = export_graph(catalog, prerequisite_edges)

    args.node_output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.node_output, nodes)
    _write_jsonl(args.relationship_output, relationships)

    print(f"Wrote {len(nodes)} graph nodes to {args.node_output}")
    print(f"Wrote {len(relationships)} graph relationships to {args.relationship_output}")
    return 0


def export_graph(
    catalog: ConceptCatalog,
    prerequisite_edges: list[PrerequisiteEdge],
) -> tuple[list[dict], list[dict]]:
    nodes_by_id: dict[str, dict] = {}
    relationships_by_key: dict[tuple[str, str, str], dict] = {}

    for record in catalog.records:
        subject_id = _node_id("subject", record.subject)
        chapter_id = _node_id("chapter", record.subject, record.chapter)
        topic_id = _node_id("topic", record.subject, record.chapter, record.topic)

        nodes_by_id.setdefault(
            subject_id,
            {"id": subject_id, "label": "Subject", "name": record.subject},
        )
        nodes_by_id.setdefault(
            chapter_id,
            {
                "id": chapter_id,
                "label": "Chapter",
                "name": record.chapter,
                "subject": record.subject,
            },
        )
        nodes_by_id.setdefault(
            topic_id,
            {
                "id": topic_id,
                "label": "Topic",
                "name": record.topic,
                "subject": record.subject,
                "chapter": record.chapter,
            },
        )
        nodes_by_id[record.id] = _micro_concept_node(record)

        _add_relationship(
            relationships_by_key,
            subject_id,
            chapter_id,
            "HAS_CHAPTER",
            {"source": "concept_record"},
        )
        _add_relationship(
            relationships_by_key,
            chapter_id,
            topic_id,
            "HAS_TOPIC",
            {"source": "concept_record"},
        )
        _add_relationship(
            relationships_by_key,
            topic_id,
            record.id,
            "HAS_MICRO_CONCEPT",
            {"source": "concept_record"},
        )

    concept_ids = {record.id for record in catalog.records}
    for edge in prerequisite_edges:
        if edge.from_concept_id not in concept_ids or edge.to_prerequisite_id not in concept_ids:
            raise ValueError(
                "prerequisite edge references unknown concept id: "
                f"{edge.from_concept_id} -> {edge.to_prerequisite_id}"
            )
        _add_relationship(
            relationships_by_key,
            edge.from_concept_id,
            edge.to_prerequisite_id,
            edge.relation,
            {
                "dependency_type": edge.dependency_type,
                "required": edge.required,
                "reason": edge.reason,
                "status": edge.status,
                "source": edge.source,
                "quality": edge.quality,
            },
        )

    return list(nodes_by_id.values()), list(relationships_by_key.values())


def _micro_concept_node(record: MicroConceptRecord) -> dict:
    return {
        "id": record.id,
        "label": "MicroConcept",
        "name": record.micro_concept,
        "subject": record.subject,
        "chapter": record.chapter,
        "topic": record.topic,
        "definition": record.definition,
        "testable_skill": record.testable_skill,
        "formulas": record.formulas,
        "aliases": record.aliases,
        "source_refs": record.source_refs,
        "common_confusions": [
            confusion.model_dump() for confusion in record.common_confusions
        ],
        "difficulty": record.difficulty,
        "status": record.status,
    }


def _add_relationship(
    relationships_by_key: dict[tuple[str, str, str], dict],
    start_id: str,
    end_id: str,
    relationship_type: str,
    properties: dict,
) -> None:
    key = (start_id, end_id, relationship_type)
    relationships_by_key.setdefault(
        key,
        {
            "start_id": start_id,
            "end_id": end_id,
            "type": relationship_type,
            **properties,
        },
    )


def _load_concepts(path: Path) -> ConceptCatalog:
    records: list[MicroConceptRecord] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(MicroConceptRecord.model_validate(json.loads(stripped)))
            except Exception as exc:
                raise ValueError(f"{path}:{line_number} contains an invalid concept") from exc
    return ConceptCatalog(records=records)


def _load_edges(path: Path) -> list[PrerequisiteEdge]:
    edges: list[PrerequisiteEdge] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                edges.append(PrerequisiteEdge.model_validate(json.loads(stripped)))
            except Exception as exc:
                raise ValueError(f"{path}:{line_number} contains an invalid edge") from exc
    return edges


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _node_id(label: str, *parts: str) -> str:
    return f"{label}:{'.'.join(_slug(part) for part in parts)}"


def _slug(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


if __name__ == "__main__":
    raise SystemExit(main())
