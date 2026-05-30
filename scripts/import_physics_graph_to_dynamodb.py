import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_NODES = Path("data/concepts/graph/physics_nodes.jsonl")
DEFAULT_RELATIONSHIPS = Path("data/concepts/graph/physics_relationships.jsonl")
DEFAULT_DIAGNOSTIC_EDGES = Path("data/concepts/physics_prerequisite_edges.diagnostic.jsonl")
DEFAULT_DRY_RUN_OUTPUT = Path("data/concepts/graph/dynamodb_import_preview.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/concepts/graph/dynamodb_import_report.json")
DEFAULT_MAX_CHAIN_DEPTH = 2
DIAGNOSTIC_QUALITIES = {"curated", "expert_reviewed", "validated_by_questions"}
SEARCH_STOP_WORDS = {
    "a",
    "an",
    "and",
    "by",
    "for",
    "in",
    "of",
    "or",
    "the",
    "to",
    "with",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish generated Physics graph JSONL artifacts to DynamoDB."
    )
    parser.add_argument("--table-name", required=True)
    parser.add_argument("--artifact-bucket", required=True)
    parser.add_argument("--graph-version", required=True)
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--relationships", type=Path, default=DEFAULT_RELATIONSHIPS)
    parser.add_argument("--diagnostic-edges", type=Path, default=DEFAULT_DIAGNOSTIC_EDGES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delete-stale-versions", action="store_true")
    parser.add_argument("--inactive-retention-days", type=int, default=30)
    parser.add_argument("--output", type=Path, default=DEFAULT_DRY_RUN_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    args = parser.parse_args()

    import_plan = build_import_plan(
        nodes_path=args.nodes,
        relationships_path=args.relationships,
        diagnostic_edges_path=args.diagnostic_edges,
        graph_version=args.graph_version,
        created_at=_utc_now(),
    )

    if args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        _write_jsonl(args.output, import_plan["items"])
        args.report_output.parent.mkdir(parents=True, exist_ok=True)
        args.report_output.write_text(
            json.dumps(import_plan["report"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Dry run wrote {len(import_plan['items'])} DynamoDB items to {args.output}")
        print(f"Dry run wrote import report to {args.report_output}")
        return 0

    dynamodb, s3 = _aws_clients()
    table = dynamodb.Table(args.table_name)
    _upload_artifacts(
        s3=s3,
        bucket=args.artifact_bucket,
        graph_version=args.graph_version,
        paths=[args.nodes, args.relationships, args.diagnostic_edges],
    )
    _write_items(table, import_plan["items"])
    _verify_written_items(table, import_plan["items"])
    table.put_item(Item=import_plan["active_control_item"])
    _put_report(
        s3=s3,
        bucket=args.artifact_bucket,
        graph_version=args.graph_version,
        report=import_plan["report"],
    )
    if args.delete_stale_versions:
        deleted = _delete_stale_versions(
            table=table,
            active_graph_version=args.graph_version,
            inactive_retention_days=args.inactive_retention_days,
        )
        print(f"Deleted {deleted} stale inactive DynamoDB items.")

    print(
        "Imported graph version "
        f"{args.graph_version}: {len(import_plan['items'])} items, "
        f"{import_plan['report']['counts']['concepts']} concepts."
    )
    return 0


def build_import_plan(
    *,
    nodes_path: Path,
    relationships_path: Path,
    diagnostic_edges_path: Path,
    graph_version: str,
    created_at: str,
) -> dict[str, Any]:
    nodes = _load_jsonl(nodes_path)
    relationships = _load_jsonl(relationships_path)
    diagnostic_edges = _load_jsonl(diagnostic_edges_path)
    source_artifacts = _source_artifacts([nodes_path, relationships_path, diagnostic_edges_path])

    items = build_dynamodb_items(
        nodes=nodes,
        relationships=relationships,
        diagnostic_edges=diagnostic_edges,
        graph_version=graph_version,
        created_at=created_at,
    )
    report = build_import_report(
        items=items,
        nodes=nodes,
        relationships=relationships,
        diagnostic_edges=diagnostic_edges,
        graph_version=graph_version,
        created_at=created_at,
        source_artifacts=source_artifacts,
    )
    active_control_item = build_active_control_item(report)
    return {"items": items, "report": report, "active_control_item": active_control_item}


def build_dynamodb_items(
    *,
    nodes: list[dict],
    relationships: list[dict],
    diagnostic_edges: list[dict],
    graph_version: str,
    created_at: str,
) -> list[dict]:
    concepts = _micro_concepts_by_id(nodes)
    direct_edges = _diagnostic_edges(diagnostic_edges, concepts)
    items: list[dict] = []

    for concept in concepts.values():
        items.append(_concept_item(concept, graph_version, created_at))
        items.append(_chapter_topic_item(concept, graph_version, created_at))
        for token in _search_tokens(concept):
            items.append(_search_token_item(token, concept, graph_version, created_at))

    for edge in direct_edges:
        items.append(_prerequisite_item(edge, concepts, graph_version, created_at, depth=1))
        items.append(_required_by_item(edge, concepts, graph_version, created_at))

    for edge in _depth_two_edges(direct_edges):
        items.append(_prerequisite_item(edge, concepts, graph_version, created_at, depth=2))

    items.append(
        _version_summary_item(
            graph_version=graph_version,
            created_at=created_at,
            node_count=len(nodes),
            relationship_count=len(relationships),
            diagnostic_edge_count=len(direct_edges),
        )
    )
    return _dedupe_items(items)


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
    counts = _count_item_types(items)
    report = {
        "subject": "Physics",
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
    _validate_report(report)
    return report


def build_active_control_item(report: dict) -> dict:
    return {
        "PK": "GRAPH#physics",
        "SK": "ACTIVE",
        "entity_type": "ActiveGraphVersion",
        "subject": "Physics",
        "active_graph_version": report["graph_version"],
        "updated_at": report["created_at"],
        "counts": report["counts"],
        "source_artifacts": report["source_artifacts"],
        "status": report["status"],
    }


def stale_item_filter(item: dict, active_graph_version: str, cutoff: str) -> bool:
    graph_version = item.get("graph_version")
    if not graph_version or graph_version == active_graph_version:
        return False
    created_at = item.get("created_at")
    return isinstance(created_at, str) and created_at < cutoff


def _concept_item(concept: dict, graph_version: str, created_at: str) -> dict:
    return {
        "PK": _concept_pk(graph_version, concept["id"]),
        "SK": "META",
        "entity_type": "Concept",
        "graph_version": graph_version,
        "subject": concept["subject"],
        "created_at": created_at,
        "source_artifact": str(DEFAULT_NODES),
        "concept_id": concept["id"],
        "name": concept["name"],
        "chapter": concept["chapter"],
        "topic": concept["topic"],
        "definition": concept.get("definition", ""),
        "testable_skill": concept.get("testable_skill", ""),
        "formulas": concept.get("formulas", []),
        "aliases": concept.get("aliases", []),
        "source_refs": concept.get("source_refs", []),
        "common_confusions": concept.get("common_confusions", []),
        "difficulty": concept.get("difficulty", ""),
        "status": concept.get("status", ""),
    }


def _chapter_topic_item(concept: dict, graph_version: str, created_at: str) -> dict:
    chapter = _key_token(concept["chapter"])
    topic = _key_token(concept["topic"])
    return {
        "PK": f"GRAPH#physics#VERSION#{graph_version}#CHAPTER#{chapter}",
        "SK": f"TOPIC#{topic}#CONCEPT#{concept['id']}",
        "entity_type": "ChapterTopicConcept",
        "graph_version": graph_version,
        "subject": concept["subject"],
        "created_at": created_at,
        "source_artifact": str(DEFAULT_NODES),
        "concept_id": concept["id"],
        "name": concept["name"],
        "chapter": concept["chapter"],
        "topic": concept["topic"],
    }


def _search_token_item(token: str, concept: dict, graph_version: str, created_at: str) -> dict:
    return {
        "PK": f"GRAPH#physics#VERSION#{graph_version}#TERM#{token}",
        "SK": f"CONCEPT#{concept['id']}",
        "entity_type": "SearchTermConcept",
        "graph_version": graph_version,
        "subject": concept["subject"],
        "created_at": created_at,
        "source_artifact": str(DEFAULT_NODES),
        "token": token,
        "concept_id": concept["id"],
        "name": concept["name"],
        "chapter": concept["chapter"],
        "topic": concept["topic"],
    }


def _prerequisite_item(
    edge: dict,
    concepts: dict[str, dict],
    graph_version: str,
    created_at: str,
    depth: int,
) -> dict:
    prerequisite = concepts[edge["to_prerequisite_id"]]
    return {
        "PK": _concept_pk(graph_version, edge["from_concept_id"]),
        "SK": f"PREREQ#D{depth}#{edge['quality']}#{edge['to_prerequisite_id']}",
        "entity_type": "Prerequisite",
        "graph_version": graph_version,
        "subject": prerequisite["subject"],
        "created_at": created_at,
        "source_artifact": str(DEFAULT_DIAGNOSTIC_EDGES),
        "concept_id": edge["from_concept_id"],
        "prerequisite_id": edge["to_prerequisite_id"],
        "prerequisite_name": prerequisite["name"],
        "dependency_type": edge["dependency_type"],
        "required": edge.get("required", True),
        "reason": edge["reason"],
        "quality": edge["quality"],
        "status": edge.get("status", "draft"),
        "depth": depth,
        "path": edge.get("path", [edge["from_concept_id"], edge["to_prerequisite_id"]]),
    }


def _required_by_item(
    edge: dict,
    concepts: dict[str, dict],
    graph_version: str,
    created_at: str,
) -> dict:
    dependent = concepts[edge["from_concept_id"]]
    return {
        "PK": _concept_pk(graph_version, edge["to_prerequisite_id"]),
        "SK": f"REQUIRED_BY#D1#{edge['from_concept_id']}",
        "entity_type": "RequiredBy",
        "graph_version": graph_version,
        "subject": dependent["subject"],
        "created_at": created_at,
        "source_artifact": str(DEFAULT_DIAGNOSTIC_EDGES),
        "concept_id": edge["to_prerequisite_id"],
        "dependent_concept_id": edge["from_concept_id"],
        "dependent_name": dependent["name"],
        "dependency_type": edge["dependency_type"],
        "required": edge.get("required", True),
        "reason": edge["reason"],
        "quality": edge["quality"],
        "status": edge.get("status", "draft"),
    }


def _version_summary_item(
    *,
    graph_version: str,
    created_at: str,
    node_count: int,
    relationship_count: int,
    diagnostic_edge_count: int,
) -> dict:
    return {
        "PK": f"GRAPH#physics#VERSION#{graph_version}",
        "SK": "SUMMARY",
        "entity_type": "GraphVersionSummary",
        "graph_version": graph_version,
        "subject": "Physics",
        "created_at": created_at,
        "source_artifact": "generated_import_plan",
        "node_count": node_count,
        "relationship_count": relationship_count,
        "diagnostic_edge_count": diagnostic_edge_count,
    }


def _diagnostic_edges(edges: list[dict], concepts: dict[str, dict]) -> list[dict]:
    diagnostic: list[dict] = []
    for edge in edges:
        if edge.get("relation") != "REQUIRES":
            continue
        if edge.get("quality") not in DIAGNOSTIC_QUALITIES:
            continue
        if edge["from_concept_id"] not in concepts or edge["to_prerequisite_id"] not in concepts:
            continue
        diagnostic.append(edge)
    return diagnostic


def _depth_two_edges(edges: list[dict]) -> list[dict]:
    by_from: dict[str, list[dict]] = defaultdict(list)
    direct_pairs = {(edge["from_concept_id"], edge["to_prerequisite_id"]) for edge in edges}
    for edge in edges:
        by_from[edge["from_concept_id"]].append(edge)

    depth_two: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for first in edges:
        middle = first["to_prerequisite_id"]
        for second in by_from.get(middle, []):
            pair = (first["from_concept_id"], second["to_prerequisite_id"])
            if pair in direct_pairs or pair in seen or pair[0] == pair[1]:
                continue
            seen.add(pair)
            depth_two.append(
                {
                    "from_concept_id": pair[0],
                    "to_prerequisite_id": pair[1],
                    "relation": "REQUIRES",
                    "dependency_type": second["dependency_type"],
                    "required": first.get("required", True) and second.get("required", True),
                    "reason": (
                        "Depth-2 prerequisite chain via "
                        f"{middle}: {first['reason']} Then: {second['reason']}"
                    ),
                    "status": "draft",
                    "source": "precomputed_diagnostic_chain",
                    "quality": "diagnostic_chain",
                    "path": [pair[0], middle, pair[1]],
                }
            )
    return depth_two


def _micro_concepts_by_id(nodes: list[dict]) -> dict[str, dict]:
    return {node["id"]: node for node in nodes if node.get("label") == "MicroConcept"}


def _search_tokens(concept: dict) -> set[str]:
    text_parts = [
        concept.get("name", ""),
        concept.get("chapter", ""),
        concept.get("topic", ""),
        concept.get("definition", ""),
        concept.get("testable_skill", ""),
        *concept.get("aliases", []),
    ]
    tokens: set[str] = set()
    for text in text_parts:
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            if len(token) > 1 and token not in SEARCH_STOP_WORDS:
                tokens.add(token)
    return tokens


def _key_token(value: str) -> str:
    return "_".join(re.findall(r"[a-z0-9]+", value.lower()))


def _concept_pk(graph_version: str, concept_id: str) -> str:
    return f"GRAPH#physics#VERSION#{graph_version}#CONCEPT#{concept_id}"


def _dedupe_items(items: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str], dict] = {}
    for item in items:
        by_key[(item["PK"], item["SK"])] = item
    return list(by_key.values())


def _count_item_types(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item["entity_type"]] += 1
    counts["total_items"] = len(items)
    counts["concepts"] = counts["Concept"]
    return dict(counts)


def _validate_report(report: dict) -> None:
    counts = report["counts"]
    if counts.get("Concept", 0) == 0:
        raise ValueError("import plan contains no concept metadata items")
    if counts.get("Prerequisite", 0) == 0:
        raise ValueError("import plan contains no prerequisite items")
    if counts["total_items"] <= counts["Concept"]:
        raise ValueError("import plan did not generate graph indexes")


def _source_artifacts(paths: list[Path]) -> list[dict]:
    artifacts: list[dict] = []
    for path in paths:
        artifacts.append(
            {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    return artifacts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _aws_clients():
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for live DynamoDB imports") from exc
    return boto3.resource("dynamodb"), boto3.client("s3")


def _write_items(table, items: list[dict]) -> None:
    with table.batch_writer(overwrite_by_pkeys=["PK", "SK"]) as batch:
        for item in items:
            batch.put_item(Item=item)


def _verify_written_items(table, items: list[dict]) -> None:
    missing: list[str] = []
    for item in items:
        response = table.get_item(Key={"PK": item["PK"], "SK": item["SK"]}, ProjectionExpression="PK")
        if "Item" not in response:
            missing.append(f"{item['PK']} / {item['SK']}")
    if missing:
        raise RuntimeError(f"DynamoDB import verification failed for {len(missing)} items")


def _upload_artifacts(s3, bucket: str, graph_version: str, paths: list[Path]) -> None:
    for path in paths:
        key = f"graph-imports/{graph_version}/artifacts/{path.name}"
        s3.upload_file(str(path), bucket, key)


def _put_report(s3, bucket: str, graph_version: str, report: dict) -> None:
    s3.put_object(
        Bucket=bucket,
        Key=f"graph-import-reports/{graph_version}/import-report.json",
        Body=json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def _delete_stale_versions(table, active_graph_version: str, inactive_retention_days: int) -> int:
    cutoff = (datetime.now(UTC) - timedelta(days=inactive_retention_days)).isoformat()
    deleted = 0
    scan_kwargs: dict[str, Any] = {
        "ProjectionExpression": "PK, SK, graph_version, created_at",
    }
    while True:
        response = table.scan(**scan_kwargs)
        stale_keys = [
            {"PK": item["PK"], "SK": item["SK"]}
            for item in response.get("Items", [])
            if stale_item_filter(item, active_graph_version, cutoff)
        ]
        with table.batch_writer() as batch:
            for key in stale_keys:
                batch.delete_item(Key=key)
                deleted += 1
        if "LastEvaluatedKey" not in response:
            return deleted
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
