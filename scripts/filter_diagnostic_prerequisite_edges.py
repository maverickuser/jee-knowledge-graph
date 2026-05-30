import argparse
import json
from pathlib import Path


DEFAULT_INPUT = Path("data/concepts/physics_prerequisite_edges.enriched.jsonl")
DEFAULT_OUTPUT = Path("data/concepts/physics_prerequisite_edges.diagnostic.jsonl")
DEFAULT_ALLOWED_QUALITIES = {"curated", "expert_reviewed", "validated_by_questions"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter prerequisite edges to diagnostic-safe quality levels."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--quality",
        action="append",
        default=[],
        help="Allowed quality. Defaults to curated, expert_reviewed, validated_by_questions.",
    )
    args = parser.parse_args()

    allowed = set(args.quality) if args.quality else DEFAULT_ALLOWED_QUALITIES
    edges = _load_jsonl(args.input)
    filtered = filter_edges(edges, allowed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output, filtered)

    print(f"Kept {len(filtered)} of {len(edges)} prerequisite edges.")
    print(f"Wrote {args.output}")
    return 0


def filter_edges(edges: list[dict], allowed_qualities: set[str]) -> list[dict]:
    return [edge for edge in edges if edge.get("quality") in allowed_qualities]


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} contains invalid JSON") from exc
    return records


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
