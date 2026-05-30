import re
from collections import defaultdict

from jee_knowledge_graph.dynamodb_import.constants import (
    DEFAULT_DIAGNOSTIC_EDGES,
    DEFAULT_NODES,
    DIAGNOSTIC_QUALITIES,
    SEARCH_STOP_WORDS,
    SUBJECT,
    SUBJECT_KEY,
)


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


def build_active_control_item(report: dict) -> dict:
    return {
        "PK": f"GRAPH#{SUBJECT_KEY}",
        "SK": "ACTIVE",
        "entity_type": "ActiveGraphVersion",
        "subject": SUBJECT,
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
        "PK": f"GRAPH#{SUBJECT_KEY}#VERSION#{graph_version}#CHAPTER#{chapter}",
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
        "PK": f"GRAPH#{SUBJECT_KEY}#VERSION#{graph_version}#TERM#{token}",
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
        "PK": f"GRAPH#{SUBJECT_KEY}#VERSION#{graph_version}",
        "SK": "SUMMARY",
        "entity_type": "GraphVersionSummary",
        "graph_version": graph_version,
        "subject": SUBJECT,
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
    return f"GRAPH#{SUBJECT_KEY}#VERSION#{graph_version}#CONCEPT#{concept_id}"


def _dedupe_items(items: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str], dict] = {}
    for item in items:
        by_key[(item["PK"], item["SK"])] = item
    return list(by_key.values())

