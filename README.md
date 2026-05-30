# JEE Knowledge Graph

Standalone project for JEE concept dependency graph data, extraction scripts, and validation tools.

## Layout

- `src/jee_knowledge_graph`: Pydantic models and JSONL loaders.
- `scripts`: Physics extraction, enrichment, graph export, and syllabus coverage utilities.
- `data/concepts`: Draft and enriched Physics concept graph inputs and generated graph JSONL.
- `docs/concept-dependency-graph.md`: Workflow and review guidance.
- `tests/concepts`: Unit tests for graph models and scripts.

## Run Tests

```powershell
$env:PYTHONPATH='src'
poetry run python -m unittest discover tests
```