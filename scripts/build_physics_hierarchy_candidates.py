import argparse
import json
from pathlib import Path

from jee_knowledge_graph.source_extract import HeadingCandidate, build_hierarchy_candidates


DEFAULT_INPUT = Path("data/concepts/physics_sources/heading_candidates.jsonl")
DEFAULT_OUTPUT = Path("data/concepts/physics_sources/hierarchy_candidates.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Group extracted Physics source headings into chapter/topic hierarchy candidates."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    headings = _load_headings(args.input)
    candidates = build_hierarchy_candidates(headings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        for candidate in candidates:
            output_file.write(json.dumps(candidate.model_dump(), ensure_ascii=False) + "\n")

    print(f"Wrote {len(candidates)} hierarchy candidates to {args.output}")
    return 0


def _load_headings(path: Path) -> list[HeadingCandidate]:
    headings: list[HeadingCandidate] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                headings.append(HeadingCandidate.model_validate(json.loads(stripped)))
            except Exception as exc:
                raise ValueError(f"{path}:{line_number} contains an invalid heading") from exc
    return headings


if __name__ == "__main__":
    raise SystemExit(main())
