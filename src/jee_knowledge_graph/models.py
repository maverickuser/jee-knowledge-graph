from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DependencyType = Literal["conceptual", "procedural", "mathematical", "formula", "representation"]
EdgeQuality = Literal["source_order", "curated", "expert_reviewed", "validated_by_questions"]
ReviewStatus = Literal["draft", "reviewed", "approved"]


def _non_blank(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be blank")
    return normalized


class Prerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: str
    type: DependencyType
    reason: str
    concept_id: str | None = None
    required: bool = True
    quality: EdgeQuality = "source_order"

    @field_validator("concept", "reason", "concept_id")
    @classmethod
    def strip_optional_text(cls, value: str | None, info):
        if value is None:
            return value
        return _non_blank(value, info.field_name)


class CommonConfusion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confusion: str
    diagnostic_signal: str
    root_gap: str

    @field_validator("confusion", "diagnostic_signal", "root_gap")
    @classmethod
    def strip_text(cls, value: str, info) -> str:
        return _non_blank(value, info.field_name)


class PrerequisiteEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_concept_id: str
    to_prerequisite_id: str
    relation: Literal["REQUIRES"] = "REQUIRES"
    dependency_type: DependencyType
    required: bool = True
    reason: str
    status: ReviewStatus = "draft"
    source: str = "manual"
    quality: EdgeQuality = "curated"

    @field_validator("from_concept_id", "to_prerequisite_id", "reason", "source")
    @classmethod
    def strip_edge_text(cls, value: str, info) -> str:
        return _non_blank(value, info.field_name)


class MicroConceptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    subject: str
    chapter: str
    topic: str
    micro_concept: str
    definition: str
    testable_skill: str
    formulas: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    prerequisites: list[Prerequisite] = Field(default_factory=list)
    common_confusions: list[CommonConfusion] = Field(default_factory=list)
    difficulty: Literal["foundation", "easy", "medium", "hard", "advanced"] = "medium"
    status: ReviewStatus = "draft"

    @field_validator(
        "id",
        "subject",
        "chapter",
        "topic",
        "micro_concept",
        "definition",
        "testable_skill",
    )
    @classmethod
    def strip_required_text(cls, value: str, info) -> str:
        return _non_blank(value, info.field_name)

    @field_validator("formulas", "aliases", "source_refs")
    @classmethod
    def strip_text_lists(cls, values: list[str], info) -> list[str]:
        return [_non_blank(value, info.field_name) for value in values]

    @model_validator(mode="after")
    def require_diagnostic_fields_for_approved_records(self) -> "MicroConceptRecord":
        if self.status == "approved" and self.difficulty != "foundation":
            if not self.prerequisites:
                raise ValueError("approved non-foundation records require at least one prerequisite")
            if not self.testable_skill:
                raise ValueError("approved records require a testable skill")
        return self


class ConceptCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[MicroConceptRecord]

    @model_validator(mode="after")
    def validate_catalog(self) -> "ConceptCatalog":
        self._validate_unique_ids()
        self._validate_prerequisite_references()
        self._validate_no_required_cycles()
        return self

    def by_id(self) -> dict[str, MicroConceptRecord]:
        return {record.id: record for record in self.records}

    def _validate_unique_ids(self) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for record in self.records:
            if record.id in seen:
                duplicates.add(record.id)
            seen.add(record.id)
        if duplicates:
            raise ValueError(f"duplicate concept ids: {', '.join(sorted(duplicates))}")

    def _validate_prerequisite_references(self) -> None:
        ids = {record.id for record in self.records}
        missing: list[str] = []
        for record in self.records:
            for prerequisite in record.prerequisites:
                if prerequisite.concept_id and prerequisite.concept_id not in ids:
                    missing.append(f"{record.id} -> {prerequisite.concept_id}")
        if missing:
            raise ValueError(f"unknown prerequisite concept ids: {', '.join(missing)}")

    def _validate_no_required_cycles(self) -> None:
        graph: dict[str, list[str]] = defaultdict(list)
        for record in self.records:
            for prerequisite in record.prerequisites:
                if prerequisite.required and prerequisite.concept_id:
                    graph[record.id].append(prerequisite.concept_id)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str, path: list[str]) -> None:
            if node in visiting:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                raise ValueError(f"required prerequisite cycle: {' -> '.join(cycle)}")
            if node in visited:
                return

            visiting.add(node)
            for neighbor in graph[node]:
                visit(neighbor, path + [neighbor])
            visiting.remove(node)
            visited.add(node)

        for record in self.records:
            visit(record.id, [record.id])
