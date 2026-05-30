# Concept Dependency Graph Inputs

The Concept Dependency Graph stores syllabus concepts and prerequisite links. It
does not store questions or solutions. Its purpose is to support diagnoses such
as: the student missed concept X because prerequisite Y is weak.

## Expert Concept Breakdown

Each micro-concept should be small enough to test with one question step. Store
records as JSONL so sources can be reviewed and loaded incrementally.

Required fields:

- `id`: stable dotted identifier.
- `subject`: Physics, Mathematics, Organic Chemistry, Physical Chemistry, or
  Inorganic Chemistry.
- `chapter`: canonical chapter name.
- `topic`: canonical topic name.
- `micro_concept`: smallest testable concept name.
- `definition`: what the concept means.
- `testable_skill`: what a question can ask the student to do.
- `prerequisites`: direct prerequisite concepts with type and reason.
- `common_confusions`: predictable mistakes with diagnostic signals.
- `status`: `draft`, `reviewed`, or `approved`.

Optional fields:

- `formulas`
- `aliases`
- `source_refs`
- `difficulty`

Use [expert_concepts.sample.jsonl](../data/concepts/expert_concepts.sample.jsonl)
as the input template.

## Physics Source Extraction

Local Physics PDFs can be converted into reviewable source inputs without
committing full textbook text. The extractor stores document inventory and
heading candidates only.

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe scripts\extract_physics_concept_sources.py `
  --source-dir 'C:\Users\Saurabh\Downloads\physics' `
  --output-dir data\concepts\physics_sources `
  --include-kind reference_book `
  --include-kind ncert_physics_english `
  --include-kind jee_syllabus `
  --include-name concepts_of_physics `
  --include-name ps.pdf `
  --include-name syllabus `
  --max-pages 20

.\.venv\Scripts\python.exe scripts\build_physics_hierarchy_candidates.py `
  --input data\concepts\physics_sources\heading_candidates.jsonl `
  --output data\concepts\physics_sources\hierarchy_candidates.jsonl

.\.venv\Scripts\python.exe scripts\prepare_physics_concept_extraction_tasks.py `
  --input data\concepts\physics_sources\hierarchy_candidates.jsonl `
  --output data\concepts\physics_sources\concept_extraction_tasks.jsonl

.\.venv\Scripts\python.exe scripts\generate_physics_concept_graph_input.py `
  --input data\concepts\physics_sources\hierarchy_candidates.jsonl `
  --concept-output data\concepts\physics_concepts.draft.jsonl `
  --edge-output data\concepts\physics_prerequisite_edges.draft.jsonl

.\.venv\Scripts\python.exe scripts\apply_physics_prerequisite_overlay.py `
  --concept-input data\concepts\physics_concepts.draft.jsonl `
  --concept-overlay-input data\concepts\physics_atomic_concepts_overlay.jsonl `
  --overlay-input data\concepts\physics_prerequisite_overlay.jsonl `
  --concept-output data\concepts\physics_concepts.enriched.jsonl `
  --edge-output data\concepts\physics_prerequisite_edges.enriched.jsonl

.\.venv\Scripts\python.exe scripts\filter_diagnostic_prerequisite_edges.py `
  --input data\concepts\physics_prerequisite_edges.enriched.jsonl `
  --output data\concepts\physics_prerequisite_edges.diagnostic.jsonl

.\.venv\Scripts\python.exe scripts\export_physics_graph_jsonl.py `
  --concept-input data\concepts\physics_concepts.enriched.jsonl `
  --edge-input data\concepts\physics_prerequisite_edges.enriched.jsonl `
  --node-output data\concepts\graph\physics_nodes.jsonl `
  --relationship-output data\concepts\graph\physics_relationships.jsonl

.\.venv\Scripts\python.exe scripts\validate_physics_syllabus_coverage.py `
  --coverage data\concepts\jee_advanced_physics_syllabus_2026_coverage.json `
  --nodes data\concepts\graph\physics_nodes.jsonl `
  --output data\concepts\graph\physics_syllabus_coverage_report.json

.\.venv\Scripts\python.exe scripts\import_physics_graph_to_dynamodb.py `
  --table-name jee-knowledge-graph `
  --artifact-bucket jee-knowledge-graph-artifacts `
  --graph-version physics-2026-05-30T120000Z `
  --dry-run

.\.venv\Scripts\python.exe scripts\prepare_high_yield_micro_concept_split_tasks.py `
  --concepts data\concepts\physics_concepts.enriched.jsonl `
  --output data\concepts\physics_sources\high_yield_micro_concept_split_tasks.jsonl

.\.venv\Scripts\python.exe scripts\extract_local_syllabus_text.py `
  --input 'C:\Users\Saurabh\Downloads\physics\syllabus (1).pdf' `
  --text-output data\concepts\physics_sources\syllabus_ocr.txt `
  --status-output data\concepts\physics_sources\syllabus_extraction_status.json
```

Generated artifacts:

- `inventory.json`: source documents, page counts, extracted pages, and notes.
- `heading_candidates.jsonl`: chapter/section headings extracted from source indexes.
- `hierarchy_candidates.jsonl`: NCERT chapter/topic hierarchy grouped from headings.
- `concept_extraction_tasks.jsonl`: chapter-level LLM tasks for drafting
  micro-concepts and direct prerequisites in the Expert Concept Breakdown schema.
- `physics_concepts.draft.jsonl`: draft concept nodes in `MicroConceptRecord`
  format, generated from the extracted Physics hierarchy.
- `physics_prerequisite_edges.draft.jsonl`: explicit draft `REQUIRES` edges
  between generated concept nodes.
- `physics_prerequisite_overlay.jsonl`: curated prerequisite edges for common
  JEE Physics dependency patterns.
- `physics_atomic_concepts_overlay.jsonl`: reviewed atomic concept records that
  refine broad source-derived topics into diagnostic-grade micro-concepts.
- `physics_concepts.enriched.jsonl`: draft concept nodes after applying the
  curated prerequisite and atomic concept overlays.
- `physics_prerequisite_edges.enriched.jsonl`: final draft graph-edge input for
  downstream graph loading.
- `physics_prerequisite_edges.diagnostic.jsonl`: diagnostic-safe `REQUIRES`
  edges filtered to curated, expert-reviewed, or question-validated quality.
- `graph/physics_nodes.jsonl`: graph-loader nodes for `Subject`, `Chapter`,
  `Topic`, and `MicroConcept`.
- `graph/physics_relationships.jsonl`: graph-loader relationships for
  `HAS_CHAPTER`, `HAS_TOPIC`, `HAS_MICRO_CONCEPT`, and `REQUIRES`.
- `jee_advanced_physics_syllabus_2026_coverage.json`: mapping from official
  JEE Advanced Physics syllabus areas to generated graph chapters.
- `graph/physics_syllabus_coverage_report.json`: validation report proving
  mapped official syllabus areas are represented in the graph chapters.
- `graph/dynamodb_import_preview.jsonl`: dry-run DynamoDB write items for a
  versioned Physics graph import.
- `graph/dynamodb_import_report.json`: dry-run report with artifact checksums,
  generated item counts, and the graph version that would be activated.
- `physics_sources/high_yield_micro_concept_split_tasks.jsonl`: LLM-ready tasks
  for splitting high-yield broad topics into atomic one-step micro-concepts.
- `physics_sources/syllabus_extraction_status.json`: local syllabus extraction,
  OCR dependency, OCR failure, or no-extractable-content status.

The local syllabus extractor first tries embedded text, then uses Poppler
`pdftoppm` plus Tesseract OCR. If OCR tools run but produce no text, the status
file records render metadata so a blank or unusable PDF is not confused with a
missing dependency. Provide a valid text syllabus file or a non-blank syllabus
PDF before treating the local syllabus PDF itself as extracted source material.
The included coverage mapping is grounded against the official JEE Advanced 2026
syllabus PDF from `jeeadv.ac.in`.

Most generated concept and edge files are still `draft` quality. Source-order
edges provide broad chapter sequencing; overlay edges add explicit conceptual,
procedural, mathematical, formula, and representation prerequisites for common
JEE Physics dependency patterns. Reviewed atomic overlays can be treated as
safer diagnostic seeds, but the remaining draft topic records should still be
expert-reviewed before being treated as hard diagnostic truth.

Use `physics_prerequisite_edges.diagnostic.jsonl` when the diagnostic agent
needs safer prerequisite root-cause candidates. It excludes source-order-only
edges.

Use `import_physics_graph_to_dynamodb.py --dry-run` before a live publish to
preview the exact DynamoDB items. A live import writes all items for the new
`graph_version`, verifies them, and only then updates `GRAPH#physics` /
`ACTIVE` so failed imports do not replace the currently active graph.

## GitHub Actions

The CI workflow runs Ruff, unit tests, a DynamoDB import dry run, and Terraform
format/validation on pushes and pull requests.

The CD workflow is manually triggered. It validates the repo, applies the
DynamoDB/S3/IAM write-path Terraform, then publishes a graph version. It also
runs automatically after CI succeeds on `main`. Configure these GitHub settings
before running CD:

- Secret `AWS_ROLE_TO_ASSUME`: IAM role ARN trusted by GitHub OIDC.
- Variable `TERRAFORM_STATE_BUCKET`: pre-existing S3 bucket for Terraform state.
- Optional variable `AWS_REGION`: defaults to `ap-south-1`.
- Optional variable `GRAPH_TABLE_NAME`: defaults to `jee-knowledge-graph`.
- Optional variable `GRAPH_ARTIFACT_BUCKET_NAME`: leave empty to use the
  Terraform-derived bucket name.

The destroy workflow is manually triggered only. It requires typing
`destroy-jee-knowledge-graph` and disables DynamoDB deletion protection plus S3
artifact bucket retention for that destroy run.

## Review Rules

- Prefer official JEE syllabus names for chapter and topic boundaries.
- Use textbook and prep-book indexes to split broad topics into micro-concepts.
- Keep prerequisites direct; do not attach every ancestor concept.
- Include a reason for each prerequisite so diagnosis can explain the root gap.
- Include a diagnostic signal for each common confusion.
- Treat LLM-generated records as `draft` until reviewed.
