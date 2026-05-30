from pathlib import Path
from typing import Any

from jee_knowledge_graph.dynamodb_import.aws import (
    aws_clients,
    delete_stale_versions,
    put_report,
    upload_artifacts,
    verify_written_items,
    write_items,
)
from jee_knowledge_graph.dynamodb_import.builder import (
    build_active_control_item,
    build_dynamodb_items,
)
from jee_knowledge_graph.dynamodb_import.file_io import load_jsonl, source_artifacts
from jee_knowledge_graph.dynamodb_import.reporting import build_import_report


def build_import_plan(
    *,
    nodes_path: Path,
    relationships_path: Path,
    diagnostic_edges_path: Path,
    graph_version: str,
    created_at: str,
) -> dict[str, Any]:
    nodes = load_jsonl(nodes_path)
    relationships = load_jsonl(relationships_path)
    diagnostic_edges = load_jsonl(diagnostic_edges_path)
    artifacts = source_artifacts([nodes_path, relationships_path, diagnostic_edges_path])

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
        source_artifacts=artifacts,
    )
    active_control_item = build_active_control_item(report)
    return {"items": items, "report": report, "active_control_item": active_control_item}


def publish_import_plan(
    *,
    table_name: str,
    artifact_bucket: str,
    graph_version: str,
    nodes_path: Path,
    relationships_path: Path,
    diagnostic_edges_path: Path,
    import_plan: dict[str, Any],
    delete_stale: bool,
    inactive_retention_days: int,
) -> int:
    dynamodb, s3 = aws_clients()
    table = dynamodb.Table(table_name)
    upload_artifacts(
        s3=s3,
        bucket=artifact_bucket,
        graph_version=graph_version,
        paths=[nodes_path, relationships_path, diagnostic_edges_path],
    )
    write_items(table, import_plan["items"])
    verify_written_items(table, import_plan["items"])
    table.put_item(Item=import_plan["active_control_item"])
    put_report(
        s3=s3,
        bucket=artifact_bucket,
        graph_version=graph_version,
        report=import_plan["report"],
    )
    if not delete_stale:
        return 0
    return delete_stale_versions(
        table=table,
        active_graph_version=graph_version,
        inactive_retention_days=inactive_retention_days,
    )

