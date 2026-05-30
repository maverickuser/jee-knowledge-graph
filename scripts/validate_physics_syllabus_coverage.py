import argparse
import json
from pathlib import Path


DEFAULT_COVERAGE = Path("data/concepts/jee_advanced_physics_syllabus_2026_coverage.json")
DEFAULT_NODES = Path("data/concepts/graph/physics_nodes.jsonl")
DEFAULT_OUTPUT = Path("data/concepts/graph/physics_syllabus_coverage_report.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate generated Physics graph chapters against syllabus coverage groups."
    )
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    coverage = json.loads(args.coverage.read_text(encoding="utf-8"))
    chapter_names = _load_chapter_names(args.nodes)
    report = validate_coverage(coverage, chapter_names)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if report["missing_chapters"]:
        print(f"Missing {len(report['missing_chapters'])} mapped graph chapters.")
        return 1

    print(
        "Validated syllabus coverage: "
        f"{report['covered_chapter_count']} mapped chapters across "
        f"{report['coverage_group_count']} official areas."
    )
    print(f"Wrote {args.output}")
    return 0


def validate_coverage(coverage: dict, chapter_names: set[str]) -> dict:
    missing: list[dict] = []
    covered: set[str] = set()
    for group in coverage["coverage_groups"]:
        for chapter in group["graph_chapters"]:
            if chapter not in chapter_names:
                missing.append(
                    {
                        "official_area": group["official_area"],
                        "chapter": chapter,
                    }
                )
            else:
                covered.add(chapter)

    return {
        "exam": coverage["exam"],
        "year": coverage["year"],
        "subject": coverage["subject"],
        "official_source_url": coverage["official_source_url"],
        "coverage_group_count": len(coverage["coverage_groups"]),
        "covered_chapter_count": len(covered),
        "missing_chapters": missing,
        "status": "pass" if not missing else "fail",
    }


def _load_chapter_names(path: Path) -> set[str]:
    chapter_names: set[str] = set()
    with path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                node = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} contains invalid JSON") from exc
            if node.get("label") == "Chapter":
                chapter_names.add(node["name"])
    return chapter_names


if __name__ == "__main__":
    raise SystemExit(main())
