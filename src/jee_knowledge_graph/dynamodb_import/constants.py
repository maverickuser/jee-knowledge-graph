from pathlib import Path


SUBJECT = "Physics"
SUBJECT_KEY = "physics"
DEFAULT_NODES = Path("data/concepts/graph/physics_nodes.jsonl")
DEFAULT_RELATIONSHIPS = Path("data/concepts/graph/physics_relationships.jsonl")
DEFAULT_DIAGNOSTIC_EDGES = Path("data/concepts/physics_prerequisite_edges.diagnostic.jsonl")
DEFAULT_DRY_RUN_OUTPUT = Path("data/concepts/graph/dynamodb_import_preview.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/concepts/graph/dynamodb_import_report.json")
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

