import argparse
import json
from pathlib import Path

from jee_knowledge_graph import ConceptCatalog, MicroConceptRecord, Prerequisite, PrerequisiteEdge


DEFAULT_CONCEPT_INPUT = Path("data/concepts/physics_concepts.draft.jsonl")
DEFAULT_CONCEPT_OVERLAY_INPUT = Path("data/concepts/physics_atomic_concepts_overlay.jsonl")
DEFAULT_OVERLAY_INPUT = Path("data/concepts/physics_prerequisite_overlay.jsonl")
DEFAULT_CONCEPT_OUTPUT = Path("data/concepts/physics_concepts.enriched.jsonl")
DEFAULT_EDGE_OUTPUT = Path("data/concepts/physics_prerequisite_edges.enriched.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply curated prerequisite overlay edges to draft Physics concept records."
    )
    parser.add_argument("--concept-input", type=Path, default=DEFAULT_CONCEPT_INPUT)
    parser.add_argument("--concept-overlay-input", type=Path, default=DEFAULT_CONCEPT_OVERLAY_INPUT)
    parser.add_argument("--overlay-input", type=Path, default=DEFAULT_OVERLAY_INPUT)
    parser.add_argument("--concept-output", type=Path, default=DEFAULT_CONCEPT_OUTPUT)
    parser.add_argument("--edge-output", type=Path, default=DEFAULT_EDGE_OUTPUT)
    args = parser.parse_args()

    catalog = _load_concepts(args.concept_input, args.concept_overlay_input)
    overlay_edges = _load_edges(args.overlay_input)
    enriched = apply_overlay(catalog, overlay_edges)
    edge_records = collect_edges(enriched)

    args.concept_output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.concept_output, [record.model_dump() for record in enriched.records])
    _write_jsonl(args.edge_output, [edge.model_dump() for edge in edge_records])

    print(f"Applied {len(overlay_edges)} overlay edges.")
    print(f"Wrote {len(enriched.records)} enriched concept records to {args.concept_output}")
    print(f"Wrote {len(edge_records)} enriched prerequisite edges to {args.edge_output}")
    return 0


def apply_overlay(catalog: ConceptCatalog, overlay_edges: list[PrerequisiteEdge]) -> ConceptCatalog:
    by_id = catalog.by_id()
    _validate_edge_references(by_id, overlay_edges)

    updated_records: list[MicroConceptRecord] = []
    overlay_by_from: dict[str, list[PrerequisiteEdge]] = {}
    for edge in overlay_edges:
        overlay_by_from.setdefault(edge.from_concept_id, []).append(edge)

    for record in catalog.records:
        prerequisites = list(record.prerequisites)
        prerequisite_indexes = {
            prerequisite.concept_id: index
            for index, prerequisite in enumerate(prerequisites)
            if prerequisite.concept_id
        }
        for edge in overlay_by_from.get(record.id, []):
            if edge.to_prerequisite_id in prerequisite_indexes:
                index = prerequisite_indexes[edge.to_prerequisite_id]
                prerequisite_record = by_id[edge.to_prerequisite_id]
                prerequisites[index] = Prerequisite(
                    concept=prerequisite_record.micro_concept,
                    concept_id=edge.to_prerequisite_id,
                    type=edge.dependency_type,
                    reason=edge.reason,
                    required=edge.required,
                    quality=edge.quality,
                )
                continue
            prerequisite_record = by_id[edge.to_prerequisite_id]
            prerequisites.append(
                Prerequisite(
                    concept=prerequisite_record.micro_concept,
                    concept_id=edge.to_prerequisite_id,
                    type=edge.dependency_type,
                    reason=edge.reason,
                    required=edge.required,
                    quality=edge.quality,
                )
            )
            prerequisite_indexes[edge.to_prerequisite_id] = len(prerequisites) - 1
        updated_records.append(record.model_copy(update={"prerequisites": prerequisites}))

    return ConceptCatalog(records=updated_records)


def collect_edges(catalog: ConceptCatalog) -> list[PrerequisiteEdge]:
    edges: list[PrerequisiteEdge] = []
    for record in catalog.records:
        for prerequisite in record.prerequisites:
            if not prerequisite.concept_id:
                continue
            edges.append(
                PrerequisiteEdge(
                    from_concept_id=record.id,
                    to_prerequisite_id=prerequisite.concept_id,
                    dependency_type=prerequisite.type,
                    required=prerequisite.required,
                    reason=prerequisite.reason,
                    status=record.status,
                    source="record_prerequisites",
                    quality=prerequisite.quality,
                )
            )
    return edges


def _load_concepts(path: Path, overlay_path: Path | None = None) -> ConceptCatalog:
    records = _load_concept_records(path)
    if overlay_path and overlay_path.exists():
        records.extend(_load_concept_records(overlay_path))
    return ConceptCatalog(records=records)


def _load_concept_records(path: Path) -> list[MicroConceptRecord]:
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
    return records


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


def _validate_edge_references(
    records_by_id: dict[str, MicroConceptRecord],
    edges: list[PrerequisiteEdge],
) -> None:
    missing: list[str] = []
    for edge in edges:
        if edge.from_concept_id not in records_by_id:
            missing.append(edge.from_concept_id)
        if edge.to_prerequisite_id not in records_by_id:
            missing.append(edge.to_prerequisite_id)
    if missing:
        unique_missing = ", ".join(sorted(set(missing)))
        raise ValueError(f"overlay references unknown concept ids: {unique_missing}")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
