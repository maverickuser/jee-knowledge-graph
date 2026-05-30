import json
from pathlib import Path
from typing import Iterable

from jee_knowledge_graph.models import ConceptCatalog, MicroConceptRecord


def load_expert_concepts_jsonl(path: str | Path) -> ConceptCatalog:
    records = list(_read_jsonl_records(Path(path)))
    return ConceptCatalog(records=[MicroConceptRecord.model_validate(record) for record in records])


def _read_jsonl_records(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as concept_file:
        for line_number, line in enumerate(concept_file, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} contains invalid JSON") from exc
