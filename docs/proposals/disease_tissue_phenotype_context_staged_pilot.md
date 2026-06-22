# Disease/tissue/phenotype context staged pilot (t_3ff983e0)

Status: staged-only; no canonical promotion without review.

## What was staged

Builder: `manage_db/build_staged_disease_tissue_context.py`

Local artifact:

```text
.omoc/staging/disease-tissue-phenotype-context-20260622-t_3ff983e0/
```

Remote artifact:

```text
gs://jouvencekb/kg/staging/source-native-expansion/disease-tissue-phenotype-context/t_3ff983e0/disease-tissue-phenotype-context-20260622-t_3ff983e0/
```

Counts from `reports/validation.json`:

- `disease_manifests_in_tissue`: 19 staged edges, 29 evidence rows.
- `phenotype_observed_in_tissue`: 0 staged edges/evidence rows.
- `disease_comorbid_disease`: 0 staged edges/evidence rows.
- Source audit rows: 25.
- Rejected candidates: 2 HPA cancer-type labels.

`manage_db.audit_edge_evidence` passed for all three staged relation files:

- `disease_manifests_in_tissue`: 19 edges, 29 evidence rows, 0 unsupported edges, 0 evidence without edge.
- empty audited files for `phenotype_observed_in_tissue` and `disease_comorbid_disease` also pass edge/evidence support.

## Source audit decisions

### Human Protein Atlas / Pathology Atlas cancer context

Source table: `https://www.proteinatlas.org/download/proteinatlas.tsv.zip` (`proteinatlas.tsv`), Cancer prognostics columns.

Accepted only where a cancer-type column has an explicit reviewed disease endpoint and a direct tissue/organ endpoint. The source predicate is preserved in evidence as:

```text
Cancer prognostics column denotes TCGA/validation cancer type context
```

Evidence rows preserve the HPA column name as `source_record_id`, source dataset/release, mapping confidence, non-empty/prognostic gene-row counts, and the raw mapping payload in `text_span` JSON.

Rejected HPA candidates:

- `Cervical Squamous Cell Carcinoma and Endocervical Adenocarcinoma`: composite TCGA label combines two disease concepts; no single disease endpoint staged.
- `Head and Neck Squamous Cell Carcinoma`: disease endpoint exists, but the source label spans multiple anatomical sites; no single UBERON tissue endpoint staged.

### HPO / HPOA / UBERON

HPO audit sources:

- `hp.obo`
- `phenotype.hpoa`
- `uberon/basic.obo`

Decision: no `phenotype_observed_in_tissue` edges. `hp.obo` has anatomy-like phenotype names but no direct HPO phenotype→UBERON tissue relationship/xref in the audited source. `phenotype.hpoa` directly supports disease→phenotype annotations, not phenotype→tissue observations. The pilot explicitly avoids the forbidden inference path disease→phenotype plus phenotype anatomy.

UBERON is used only as a tissue endpoint vocabulary/mapping support for the HPA disease→tissue context.

### Comorbidity

Decision: no `disease_comorbid_disease` edges. No clean accessible/licensable EHR/co-occurrence source was identified during this staged pilot. The builder emits empty staged edge/evidence files plus a source-audit `no_edge` row rather than synthesizing comorbidity from shared annotations.

## Validation commands

```bash
uv run python -m py_compile manage_db/build_staged_disease_tissue_context.py
uv run --group dev pytest tests/test_build_staged_disease_tissue_context.py tests/test_kg_schema_cleanup.py -q
uv run python -m manage_db.build_staged_disease_tissue_context \
  --node-root .omoc/gcs-cache/kg-v2/nodes \
  --cache-dir .omoc/gcs-cache/kg-v2/raw \
  --output-dir .omoc/staging/disease-tissue-phenotype-context-20260622-t_3ff983e0 \
  --fetch-audit-sources
uv run python -m manage_db.audit_edge_evidence \
  .omoc/staging/disease-tissue-phenotype-context-20260622-t_3ff983e0 \
  --relations disease_manifests_in_tissue phenotype_observed_in_tissue disease_comorbid_disease \
  --json
```

Observed targeted tests: `12 passed in 0.23s`.

Remote validation readback:

```text
REMOTE_VALIDATION_OK True edges 19 evidence 29 source_audit 25
```

## Residual risks / reviewer notes

- HPA `proteinatlas.tsv` does not expose a separate pathology/tissue disease annotation file on the current download page; this pilot uses Cancer prognostics cancer-type columns as direct cancer tissue-context evidence. Review should decide whether that is acceptable for `disease_manifests_in_tissue` or should remain a source-audit-only artifact.
- `Breast Invasive Carcinoma` is mapped to the existing broad `MONDO:0007254` breast cancer node (`broad_parent_for_tcga_label`) because no exact breast invasive carcinoma node was found in the current disease parquet. This is intentionally visible in evidence mapping metadata.
- Empty relation files are present for audited no-edge relations so reviewers can verify that the pilot considered but did not populate them.
