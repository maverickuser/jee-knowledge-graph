import argparse
import json
import re
from pathlib import Path

from jee_knowledge_graph.models import ConceptCatalog, MicroConceptRecord, Prerequisite
from jee_knowledge_graph.source_extract import HierarchyCandidate


DEFAULT_INPUT = Path("data/concepts/physics_sources/hierarchy_candidates.jsonl")
DEFAULT_CONCEPT_OUTPUT = Path("data/concepts/physics_concepts.draft.jsonl")
DEFAULT_EDGE_OUTPUT = Path("data/concepts/physics_prerequisite_edges.draft.jsonl")

CHAPTER_TITLE_FIXES = {
    "Urrent Lectricity": "Current Electricity",
    "M C M": "Moving Charges And Magnetism",
    "Agnetismand Atter": "Magnetism And Matter",
}

TEXT_FIXES = {
    "â€™": "’",
    "â€œ": "“",
    "â€": "”",
    "â€“": "-",
    "â€”": "-",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate draft Physics concept graph input from hierarchy candidates."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--concept-output", type=Path, default=DEFAULT_CONCEPT_OUTPUT)
    parser.add_argument("--edge-output", type=Path, default=DEFAULT_EDGE_OUTPUT)
    args = parser.parse_args()

    hierarchy = _load_hierarchy(args.input)
    records = generate_records(hierarchy)
    catalog = ConceptCatalog(records=records)
    edges = generate_edges(catalog)

    args.concept_output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.concept_output, [record.model_dump() for record in catalog.records])
    _write_jsonl(args.edge_output, edges)

    print(f"Wrote {len(catalog.records)} draft concept records to {args.concept_output}")
    print(f"Wrote {len(edges)} draft prerequisite edges to {args.edge_output}")
    return 0


def generate_records(hierarchy: list[HierarchyCandidate]) -> list[MicroConceptRecord]:
    records: list[MicroConceptRecord] = []
    for candidate in hierarchy:
        chapter = _clean_title(CHAPTER_TITLE_FIXES.get(candidate.chapter, candidate.chapter))
        previous_id: str | None = None
        previous_name: str | None = None
        for topic in candidate.topics:
            topic_title = _clean_title(topic.title)
            concept_id = _concept_id(chapter, topic.number, topic_title)
            prerequisites: list[Prerequisite] = []
            if previous_id and previous_name:
                prerequisites.append(
                    Prerequisite(
                        concept=previous_name,
                        concept_id=previous_id,
                        type="conceptual",
                        reason=(
                            "This source-derived draft dependency follows the chapter's "
                            "teaching sequence and should be expert-reviewed."
                        ),
                        quality="source_order",
                    )
                )
            records.append(
                MicroConceptRecord(
                    id=concept_id,
                    subject="Physics",
                    chapter=chapter,
                    topic=topic_title,
                    micro_concept=topic_title,
                    definition=f"Understand and apply the Physics concept: {topic_title}.",
                    testable_skill=(
                        f"Solve or classify a single JEE-level step involving {topic_title}."
                    ),
                    aliases=[],
                    source_refs=[
                        f"{candidate.document}:chapter:{candidate.chapter_label}:topic:{topic.number}"
                    ],
                    prerequisites=prerequisites,
                    common_confusions=[],
                    difficulty="foundation" if not prerequisites else "medium",
                    status="draft",
                )
            )
            previous_id = concept_id
            previous_name = topic_title
    return records


def generate_edges(catalog: ConceptCatalog) -> list[dict]:
    edges: list[dict] = []
    for record in catalog.records:
        for prerequisite in record.prerequisites:
            if not prerequisite.concept_id:
                continue
            edges.append(
                {
                    "from_concept_id": record.id,
                    "to_prerequisite_id": prerequisite.concept_id,
                    "relation": "REQUIRES",
                    "dependency_type": prerequisite.type,
                    "required": prerequisite.required,
                    "reason": prerequisite.reason,
                    "status": record.status,
                    "quality": prerequisite.quality,
                }
            )
    return edges


def _load_hierarchy(path: Path) -> list[HierarchyCandidate]:
    candidates: list[HierarchyCandidate] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                candidates.append(HierarchyCandidate.model_validate(json.loads(stripped)))
            except Exception as exc:
                raise ValueError(f"{path}:{line_number} contains an invalid hierarchy") from exc
    return candidates


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _clean_title(value: str) -> str:
    cleaned = value
    for broken, fixed in TEXT_FIXES.items():
        cleaned = cleaned.replace(broken, fixed)
    return re.sub(r"\s+", " ", cleaned).strip()


def _concept_id(chapter: str, number: str, topic_title: str) -> str:
    chapter_slug = _slug(chapter)
    topic_slug = _slug(topic_title)
    number_slug = number.replace(".", "_")
    return f"physics.{chapter_slug}.{number_slug}_{topic_slug}"


def _slug(value: str) -> str:
    value = _clean_title(value).lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


if __name__ == "__main__":
    raise SystemExit(main())
