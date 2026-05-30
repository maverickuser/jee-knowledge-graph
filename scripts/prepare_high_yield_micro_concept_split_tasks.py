import argparse
import json
from pathlib import Path

from jee_knowledge_graph import load_expert_concepts_jsonl


DEFAULT_CONCEPTS = Path("data/concepts/physics_concepts.enriched.jsonl")
DEFAULT_OUTPUT = Path("data/concepts/physics_sources/high_yield_micro_concept_split_tasks.jsonl")
DEFAULT_HIGH_YIELD_CHAPTERS = {
    "Electric Charges And Fields",
    "Electrostatic Potential And Capacitance",
    "Current Electricity",
    "Moving Charges And Magnetism",
    "Laws Of Motion",
    "Work, Energy And Power",
    "System Of Particles And Rotational Motion",
    "Gravitation",
}


INSTRUCTIONS = """Split this broad Physics topic into atomic JEE micro-concepts.

Rules:
- Each micro-concept must be testable by one question step.
- Keep the parent subject, chapter, and topic.
- Include direct prerequisites only, with dependency type and reason.
- Mark every generated record as status="draft".
- Reject broad labels that merely repeat the parent topic.
- Return JSONL records matching MicroConceptRecord.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare high-yield Physics topic split tasks for atomic micro-concepts."
    )
    parser.add_argument("--concepts", type=Path, default=DEFAULT_CONCEPTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--chapter",
        action="append",
        default=[],
        help="Chapter to include. Defaults to built-in high-yield JEE Physics chapters.",
    )
    args = parser.parse_args()

    selected_chapters = set(args.chapter) if args.chapter else DEFAULT_HIGH_YIELD_CHAPTERS
    tasks = build_split_tasks(args.concepts, selected_chapters)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        for task in tasks:
            output_file.write(json.dumps(task, ensure_ascii=False) + "\n")
    print(f"Wrote {len(tasks)} high-yield split tasks to {args.output}")
    return 0


def build_split_tasks(concepts_path: Path, selected_chapters: set[str]) -> list[dict]:
    catalog = load_expert_concepts_jsonl(concepts_path)
    tasks: list[dict] = []
    for record in catalog.records:
        if record.chapter not in selected_chapters:
            continue
        tasks.append(
            {
                "task_id": f"split.{record.id}",
                "instructions": INSTRUCTIONS,
                "parent_concept": record.model_dump(),
                "expected_quality_gate": {
                    "atomicity": "Each generated micro-concept is testable by one question step.",
                    "dependency_policy": "Use direct prerequisites only.",
                    "status": "draft",
                },
            }
        )
    return tasks


if __name__ == "__main__":
    raise SystemExit(main())
