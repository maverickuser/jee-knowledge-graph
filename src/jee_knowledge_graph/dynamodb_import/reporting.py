from collections import defaultdict

from jee_knowledge_graph.dynamodb_import.constants import SUBJECT


def build_import_report(
    *,
    items: list[dict],
    nodes: list[dict],
    relationships: list[dict],
    diagnostic_edges: list[dict],
    graph_version: str,
    created_at: str,
    source_artifacts: list[dict],
) -> dict:
    counts = count_item_types(items)
    report = {
        "subject": SUBJECT,
        "graph_version": graph_version,
        "created_at": created_at,
        "source_artifacts": source_artifacts,
        "source_counts": {
            "nodes": len(nodes),
            "relationships": len(relationships),
            "diagnostic_edges": len(diagnostic_edges),
        },
        "counts": counts,
        "status": "validated",
    }
    validate_report(report)
    return report


def count_item_types(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item["entity_type"]] += 1
    counts["total_items"] = len(items)
    counts["concepts"] = counts["Concept"]
    return dict(counts)


def validate_report(report: dict) -> None:
    counts = report["counts"]
    if counts.get("Concept", 0) == 0:
        raise ValueError("import plan contains no concept metadata items")
    if counts.get("Prerequisite", 0) == 0:
        raise ValueError("import plan contains no prerequisite items")
    if counts["total_items"] <= counts["Concept"]:
        raise ValueError("import plan did not generate graph indexes")

