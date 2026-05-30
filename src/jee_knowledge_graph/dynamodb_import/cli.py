import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from jee_knowledge_graph.dynamodb_import.constants import (
    DEFAULT_DIAGNOSTIC_EDGES,
    DEFAULT_DRY_RUN_OUTPUT,
    DEFAULT_NODES,
    DEFAULT_RELATIONSHIPS,
    DEFAULT_REPORT_OUTPUT,
)
from jee_knowledge_graph.dynamodb_import.file_io import write_jsonl
from jee_knowledge_graph.dynamodb_import.publisher import build_import_plan, publish_import_plan


def main() -> int:
    args = _parse_args()
    import_plan = build_import_plan(
        nodes_path=args.nodes,
        relationships_path=args.relationships,
        diagnostic_edges_path=args.diagnostic_edges,
        graph_version=args.graph_version,
        created_at=_utc_now(),
    )

    if args.dry_run:
        _write_dry_run_outputs(args.output, args.report_output, import_plan)
        print(f"Dry run wrote {len(import_plan['items'])} DynamoDB items to {args.output}")
        print(f"Dry run wrote import report to {args.report_output}")
        return 0

    deleted = publish_import_plan(
        table_name=args.table_name,
        artifact_bucket=args.artifact_bucket,
        graph_version=args.graph_version,
        nodes_path=args.nodes,
        relationships_path=args.relationships,
        diagnostic_edges_path=args.diagnostic_edges,
        import_plan=import_plan,
        delete_stale=args.delete_stale_versions,
        inactive_retention_days=args.inactive_retention_days,
    )
    if args.delete_stale_versions:
        print(f"Deleted {deleted} stale inactive DynamoDB items.")

    print(
        "Imported graph version "
        f"{args.graph_version}: {len(import_plan['items'])} items, "
        f"{import_plan['report']['counts']['concepts']} concepts."
    )
    return 0


def _parse_args() -> argparse.Namespace:
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
    return parser.parse_args()


def _write_dry_run_outputs(output: Path, report_output: Path, import_plan: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output, import_plan["items"])
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(
        json.dumps(import_plan["report"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()

