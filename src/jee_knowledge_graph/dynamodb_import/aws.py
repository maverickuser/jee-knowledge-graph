import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jee_knowledge_graph.dynamodb_import.builder import stale_item_filter


def aws_clients():
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for live DynamoDB imports") from exc
    return boto3.resource("dynamodb"), boto3.client("s3")


def write_items(table, items: list[dict]) -> None:
    with table.batch_writer(overwrite_by_pkeys=["PK", "SK"]) as batch:
        for item in items:
            batch.put_item(Item=item)


def verify_written_items(table, items: list[dict]) -> None:
    missing: list[str] = []
    for item in items:
        response = table.get_item(Key={"PK": item["PK"], "SK": item["SK"]}, ProjectionExpression="PK")
        if "Item" not in response:
            missing.append(f"{item['PK']} / {item['SK']}")
    if missing:
        raise RuntimeError(f"DynamoDB import verification failed for {len(missing)} items")


def upload_artifacts(s3, bucket: str, graph_version: str, paths: list[Path]) -> None:
    for path in paths:
        key = f"graph-imports/{graph_version}/artifacts/{path.name}"
        s3.upload_file(str(path), bucket, key)


def put_report(s3, bucket: str, graph_version: str, report: dict) -> None:
    s3.put_object(
        Bucket=bucket,
        Key=f"graph-import-reports/{graph_version}/import-report.json",
        Body=json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def delete_stale_versions(table, active_graph_version: str, inactive_retention_days: int) -> int:
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

