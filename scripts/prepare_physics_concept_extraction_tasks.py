import argparse
import json
from pathlib import Path

from jee_knowledge_graph.source_extract import HierarchyCandidate


DEFAULT_INPUT = Path("data/concepts/physics_sources/hierarchy_candidates.jsonl")
DEFAULT_OUTPUT = Path("data/concepts/physics_sources/concept_extraction_tasks.jsonl")


TASK_INSTRUCTIONS = """Create draft Expert Concept Breakdown records for this Physics chapter.

Rules:
- Use the provided NCERT chapter/topic hierarchy as the canonical source context.
- Break each topic into micro-concepts small enough to test with one question step.
- For every non-foundational micro-concept, include direct prerequisites only.
- Each prerequisite must include concept, type, and reason.
- Include common confusions only when they are predictable for JEE diagnosis.
- Mark every record as status="draft".
- Return JSONL records matching the MicroConceptRecord schema used by this repo.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare chapter-level LLM tasks for Physics micro-concept extraction."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    hierarchy = _load_hierarchy(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        for candidate in hierarchy:
            task = _build_task(candidate)
            output_file.write(json.dumps(task, ensure_ascii=False) + "\n")

    print(f"Wrote {len(hierarchy)} concept extraction tasks to {args.output}")
    return 0


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


def _build_task(candidate: HierarchyCandidate) -> dict:
    return {
        "task_id": _task_id(candidate),
        "instructions": TASK_INSTRUCTIONS,
        "source_context": candidate.model_dump(),
        "expected_output_schema": {
            "id": "stable dotted concept id",
            "subject": "Physics",
            "chapter": candidate.chapter,
            "topic": "topic name from source_context.topics or a refined subtopic",
            "micro_concept": "smallest directly testable concept",
            "definition": "short concept definition",
            "testable_skill": "what one question step can test",
            "formulas": ["optional formula strings"],
            "aliases": ["optional alternate names"],
            "source_refs": [f"{candidate.document}:chapter:{candidate.chapter_label}"],
            "prerequisites": [
                {
                    "concept": "direct prerequisite concept name",
                    "type": "conceptual | procedural | mathematical | formula | representation",
                    "reason": "why this prerequisite is needed",
                    "required": True,
                }
            ],
            "common_confusions": [
                {
                    "confusion": "predictable mistake",
                    "diagnostic_signal": "what a wrong answer or rough work would show",
                    "root_gap": "underlying missing concept",
                }
            ],
            "difficulty": "foundation | easy | medium | hard | advanced",
            "status": "draft",
        },
    }


def _task_id(candidate: HierarchyCandidate) -> str:
    chapter = (
        candidate.chapter.lower()
        .replace("&", "and")
        .replace(",", "")
        .replace("-", " ")
        .replace(" ", "_")
    )
    return f"physics.{chapter}"


if __name__ == "__main__":
    raise SystemExit(main())
