# Block 1 audit: `gene_interacts_gene` subdatabases and split candidates

Date: 2026-06-21

Canonical KG root: `gs://jouvencekb/kg/v2`

Local files audited:

- `.omoc/gcs-cache/kg-v2/edges/gene_interacts_gene.parquet`
- `.omoc/gcs-cache/kg-v2/evidence/gene_interacts_gene.parquet`
- `.omoc/gcs-cache/kg-v2/raw/opentargets-26.03/interaction/*.parquet`

Generated audit tables: `.omoc/reports/block1_gene_interacts_gene_audit_tables.md`

Audit script: `.omoc/scripts/audit_gene_interacts_gene.py`

## Summary decision

Do not split the current canonical `gene_interacts_gene` rows into new active relations yet.

The canonical edge/evidence layer is currently gene-endpointed (`ENSG`↔`ENSG` for OpenTargets evidence, `NCBI`↔`NCBI` for legacy TxGNN edges). The OpenTargets raw `interaction` source does contain product-level interaction identifiers in `intA`/`intB` (`ENSP...`, UniProt accessions, and a few RNA-like `URS...` identifiers), but the canonical graph endpoints are gene IDs and the current evidence table does not preserve enough source-native assertion detail to safely promote relation-specific graph edges without a documented endpoint policy and source-specific backfill.

Conservative action:

- Keep `gene_interacts_gene` as the active broad relation.
- Preserve subdatabase detail in `evidence/gene_interacts_gene.parquet` via `predicate`, `direction`, score, roles, and `text_span` JSON.
- Treat `protein_interacts_protein`, `tf_regulates_gene`, `tf_binds_enhancer`, `transcript_interacts_protein`, and `transcript_interacts_gene` as possible future source-native relations only after a dedicated raw-source backfill that exposes protein/transcript/regulatory endpoints directly.

## Access path used

The A0 runbook says to prefer targeted GCS copy + DuckDB when the macOS FUSE mount is absent. I followed that path.

```bash
mkdir -p .omoc/gcs-cache/kg-v2/{edges,evidence,raw}

gcloud storage cp \
  gs://jouvencekb/kg/v2/edges/gene_interacts_gene.parquet \
  .omoc/gcs-cache/kg-v2/edges/gene_interacts_gene.parquet

gcloud storage cp \
  gs://jouvencekb/kg/v2/evidence/gene_interacts_gene.parquet \
  .omoc/gcs-cache/kg-v2/evidence/gene_interacts_gene.parquet

gcloud storage cp \
  'gs://jouvencekb/kg/scratch/opentargets-26.03/interaction/*.parquet' \
  .omoc/gcs-cache/kg-v2/raw/opentargets-26.03/interaction/
```

No separate `interaction_evidence` path was found under the checked scratch OpenTargets 26.03 tree; the available raw dataset for this audit was `interaction/`.

## Canonical edge file

SQL:

```sql
select source, count(*) as n
from read_parquet('.omoc/gcs-cache/kg-v2/edges/gene_interacts_gene.parquet')
group by 1
order by n desc;
```

Counts:

| source | rows |
|---|---:|
| OpenTargets | 6,781,887 |
| TxGNN | 642,150 |
| total | 7,424,037 |

Schema:

```sql
describe select *
from read_parquet('.omoc/gcs-cache/kg-v2/edges/gene_interacts_gene.parquet');
```

Columns:

- `x_id`, `x_type`
- `y_id`, `y_type`
- `relation`
- `display_relation`
- `source`
- `credibility`

Endpoint namespace summary:

```sql
select
  case
    when starts_with(x_id, 'ENSG') then 'ENSG'
    when contains(x_id, ':') then split_part(x_id, ':', 1)
    else 'other'
  end as x_namespace,
  case
    when starts_with(y_id, 'ENSG') then 'ENSG'
    when contains(y_id, ':') then split_part(y_id, ':', 1)
    else 'other'
  end as y_namespace,
  count(*) as n
from read_parquet('.omoc/gcs-cache/kg-v2/edges/gene_interacts_gene.parquet')
group by 1,2
order by n desc;
```

Counts:

| x namespace | y namespace | rows |
|---|---|---:|
| ENSG | ENSG | 6,781,887 |
| NCBI | NCBI | 642,150 |

Interpretation: the OpenTargets edge layer is gene-level (`ENSG`↔`ENSG`), not protein-level, even when source rows carry `intA`/`intB` product identifiers in evidence/raw metadata.

## Canonical evidence file

SQL:

```sql
select count(*) as n
from read_parquet('.omoc/gcs-cache/kg-v2/evidence/gene_interacts_gene.parquet');
```

Total evidence rows: 14,336,594.

Schema:

```sql
describe select *
from read_parquet('.omoc/gcs-cache/kg-v2/evidence/gene_interacts_gene.parquet');
```

Important columns:

- endpoints: `x_id`, `x_type`, `y_id`, `y_type`
- provenance: `source`, `source_dataset`, `source_record_id`, `release`, `license`, `created_at`
- evidence: `evidence_type`, `evidence_score`, `effect_size`, `p_value`, `direction`, `predicate`, `text_span`, `section`, `extraction_method`

Subdatabase / predicate counts:

```sql
select source, source_dataset, evidence_type, predicate, direction, count(*) as n
from read_parquet('.omoc/gcs-cache/kg-v2/evidence/gene_interacts_gene.parquet')
group by 1,2,3,4,5
order by n desc;
```

| source | source_dataset | evidence_type | predicate | direction | rows |
|---|---|---|---|---|---:|
| OpenTargets | interaction | molecular_interaction | string | undirected | 12,988,596 |
| OpenTargets | interaction | molecular_interaction | intact | undirected | 1,257,806 |
| OpenTargets | interaction | molecular_interaction | reactome | source_ordered | 52,480 |
| OpenTargets | interaction | molecular_interaction | signor | source_ordered | 37,712 |

These re-check the known snapshot counts exactly.

Direction counts:

```sql
select direction, count(*) as n
from read_parquet('.omoc/gcs-cache/kg-v2/evidence/gene_interacts_gene.parquet')
group by 1
order by n desc;
```

| direction | rows |
|---|---:|
| undirected | 14,246,402 |
| source_ordered | 90,192 |

Endpoint namespace summary:

```sql
select
  case
    when starts_with(x_id, 'ENSG') then 'ENSG'
    when contains(x_id, ':') then split_part(x_id, ':', 1)
    else 'other'
  end as x_namespace,
  case
    when starts_with(y_id, 'ENSG') then 'ENSG'
    when contains(y_id, ':') then split_part(y_id, ':', 1)
    else 'other'
  end as y_namespace,
  count(*) as n
from read_parquet('.omoc/gcs-cache/kg-v2/evidence/gene_interacts_gene.parquet')
group by 1,2
order by n desc;
```

| x namespace | y namespace | rows |
|---|---|---:|
| ENSG | ENSG | 14,336,594 |

Representative `text_span` content shows that product-level IDs and roles are preserved as JSON metadata, not graph endpoints:

- STRING: `targetA`/`targetB` are `ENSG...`; `intA`/`intB` are usually `ENSP...`; roles are usually `unspecified role`; `scoring` is populated.
- IntAct: `targetA`/`targetB` are `ENSG...`; `intA`/`intB` are often UniProt accessions; roles are mostly `unspecified role`; `scoring` is populated.
- Reactome: `targetA`/`targetB` are `ENSG...`; `intA`/`intB` are often UniProt accessions; `direction=source_ordered`; `scoring` is null.
- SIGNOR: `targetA`/`targetB` are `ENSG...`; `intA`/`intB` are often UniProt accessions; roles are `regulator` / `regulator target`; `direction=source_ordered`; `scoring` is null.

## Raw OpenTargets `interaction` comparison

Raw files checked:

```text
gs://jouvencekb/kg/scratch/opentargets-26.03/interaction/*.parquet
```

No separate `interaction_evidence` dataset was found in the checked OpenTargets 26.03 scratch prefix.

Raw schema:

- `sourceDatabase`
- `targetA`, `targetB`
- `intA`, `intB`
- `intABiologicalRole`, `intBBiologicalRole`
- `speciesA`, `speciesB`
- `count`
- `scoring`

Raw subdatabase counts:

```sql
select sourceDatabase, count(*) as n
from read_parquet('.omoc/gcs-cache/kg-v2/raw/opentargets-26.03/interaction/*.parquet')
group by 1
order by n desc;
```

| sourceDatabase | raw rows |
|---|---:|
| string | 13,210,738 |
| intact | 1,311,132 |
| reactome | 56,191 |
| signor | 39,992 |
| total | 14,618,053 |

Raw rows passing an `ENSG`↔`ENSG` target filter:

```sql
select sourceDatabase,
  count(*) as raw_n,
  sum(case when starts_with(targetA,'ENSG') and starts_with(targetB,'ENSG') then 1 else 0 end) as ensg_ensg_n,
  sum(case when targetA is null or targetB is null or cast(targetA as varchar)='nan' or cast(targetB as varchar)='nan' then 1 else 0 end) as missing_or_nan_target_n,
  sum(case when starts_with(intA,'ENSP') and starts_with(intB,'ENSP') then 1 else 0 end) as ensp_ensp_n,
  sum(case when starts_with(intA,'URS') or starts_with(intB,'URS') then 1 else 0 end) as has_urs_n
from read_parquet('.omoc/gcs-cache/kg-v2/raw/opentargets-26.03/interaction/*.parquet')
group by 1
order by raw_n desc;
```

| sourceDatabase | raw rows | ENSG↔ENSG target rows | missing/nan target rows | ENSP↔ENSP `int` rows | rows with `URS` in `intA/intB` |
|---|---:|---:|---:|---:|---:|
| string | 13,210,738 | 12,988,596 | 222,132 | 13,210,738 | 0 |
| intact | 1,311,132 | 1,261,854 | 49,278 | 0 | 876 |
| reactome | 56,191 | 54,687 | 1,504 | 0 | 0 |
| signor | 39,992 | 38,464 | 378 | 0 | 1,598 |

Raw role counts relevant to split decisions:

```sql
select sourceDatabase, intABiologicalRole, intBBiologicalRole, count(*) as n
from read_parquet('.omoc/gcs-cache/kg-v2/raw/opentargets-26.03/interaction/*.parquet')
group by 1,2,3
order by sourceDatabase, n desc;
```

High-level results:

- STRING: all 13,210,738 raw rows are `unspecified role` / `unspecified role`.
- IntAct: 1,302,392 / 1,311,132 rows are `unspecified role` / `unspecified role`; smaller classes include enzyme/enzyme target, competitor, acceptor/donor, inhibitor/stimulator, regulator/regulator target, etc.
- Reactome: 45,153 rows are `unspecified role` / `unspecified role`; 5,553 are enzyme→enzyme target and 5,485 are enzyme target→enzyme.
- SIGNOR: 20,155 rows are regulator target→regulator and 19,837 are regulator→regulator target.

Raw scoring availability:

```sql
select
  sourceDatabase,
  count(*) as n,
  sum(case when scoring is not null then 1 else 0 end) as rows_with_scoring,
  min(scoring) as min_scoring,
  max(scoring) as max_scoring,
  avg(scoring) as avg_scoring
from read_parquet('.omoc/gcs-cache/kg-v2/raw/opentargets-26.03/interaction/*.parquet')
group by 1
order by n desc;
```

| sourceDatabase | rows | rows with scoring | min | max | avg |
|---|---:|---:|---:|---:|---:|
| string | 13,210,738 | 13,210,738 | 0.15 | 0.999 | 0.270119 |
| intact | 1,311,132 | 1,311,132 | 0.22 | 1.0 | 0.400675 |
| reactome | 56,191 | 0 | null | null | null |
| signor | 39,992 | 0 | null | null | null |

## Lost or compressed detail vs raw

Detail preserved in canonical evidence:

- OpenTargets subdatabase via `predicate` (`string`, `intact`, `reactome`, `signor`).
- Direction via `direction` (`undirected` or `source_ordered`).
- Scores via `evidence_score` for STRING and IntAct.
- Source roles and product IDs inside `text_span` JSON (`intA`, `intB`, `intABiologicalRole`, `intBBiologicalRole`, `speciesA`, `speciesB`, `sourceDatabase`, `count`, `scoring`).
- Source record key in `source_record_id`, including target IDs, product IDs, and roles.

Detail compressed or not first-class in canonical evidence:

- `intA`/`intB` are not typed endpoint columns; they are JSON metadata in `text_span` and part of `source_record_id`.
- Product endpoint namespace is not explicit. `intA`/`intB` mix `ENSP`, UniProt-like accessions, RefSeq/transcript-like accessions, and a small number of `URS...` RNA identifiers.
- Roles are not normalized into first-class evidence columns; they live inside JSON.
- Raw rows that are not `ENSG`↔`ENSG` target pairs are absent from canonical evidence. This is expected for a gene-endpoint relation but means canonical `gene_interacts_gene` should not be used as the sole source to build transcript/protein-specific relations.

## Split-candidate decisions

### `protein_interacts_protein`

Decision: do not promote from current canonical `gene_interacts_gene`.

Rationale:

- The canonical OpenTargets graph/evidence endpoints are all `ENSG`↔`ENSG`.
- Raw `intA`/`intB` are product-level for many rows, but they are not normalized endpoint columns in canonical evidence.
- STRING has `ENSP`↔`ENSP` raw `int` IDs, but STRING is partly functional association, not purely physical protein-protein interaction.
- IntAct/Reactome/SIGNOR use UniProt-like `intA`/`intB`, but the raw source here only gives product IDs/roles/count/score; it does not by itself establish a canonical protein node endpoint policy or an active `protein` namespace policy.

Future gate: build `protein_interacts_protein` only from source-native product endpoints after deciding whether endpoints are UniProt accessions, Ensembl proteins, canonical protein products, isoforms, or mapped KG protein nodes. Evidence must retain original gene targets, product IDs, roles, sourceDatabase, score/count, and source record ID.

### `tf_regulates_gene`

Decision: no active split from current evidence.

Rationale:

- SIGNOR has ordered regulator/regulator-target roles and is the strongest candidate for a directed regulatory relation, but the current rows do not identify transcription factors or expression regulation specifically.
- `regulator` in SIGNOR is broader than TF regulation: it includes signaling regulators, enzymes, complexes, and post-translational regulation.
- Promoting `regulator`→`gene` as `tf_regulates_gene` would overclaim the assertion.

Future gate: only split rows where the source explicitly asserts transcription-factor regulation of a gene, or where a vetted TF catalog and action/effect metadata are used to create a specifically labeled relation with evidence that makes the TF classification and regulatory assertion auditable.

### `tf_binds_enhancer`

Decision: no candidates in this relation.

Rationale:

- The audited source is OpenTargets `interaction`, with gene/gene targets and product interaction metadata.
- There are no enhancer/regulatory interval endpoints, genomic coordinates, biosample context, ChIP-seq peaks, motif calls, or enhancer IDs.

Future gate: use ENCODE/ABC/rE2G/ChIP-like regulatory sources, not OpenTargets interaction rows, and preserve cell/tissue/biosample context.

### `transcript_interacts_protein`

Decision: possible raw-source candidate class, but do not promote from current canonical evidence.

Rationale:

- Raw OpenTargets interaction contains a small number of rows with `URS...` identifiers in `intA`/`intB`: 876 IntAct rows and 1,598 SIGNOR rows.
- Canonical evidence has zero `text_span` rows containing `URS`, because canonical evidence only retains `ENSG`↔`ENSG` target-passing rows for this relation.
- The current relation is therefore missing the relevant raw rows needed to build transcript/RNA interaction relations.

Future gate: separately audit raw rows with `URS...`, RefSeq transcript IDs, or other RNA/transcript identifiers, classify endpoint namespaces, and decide whether the assertion is RNA-protein binding, transcript regulation, or another RNA-mediated interaction.

### `transcript_interacts_gene`

Decision: possible raw-source candidate class, but no current canonical split.

Rationale:

- Same issue as `transcript_interacts_protein`: raw `URS...`/transcript-like identifiers exist but are not present in canonical evidence.
- No canonical evidence rows currently expose transcript endpoints.
- A transcript→gene assertion would need a specific biological predicate, not just an `intA`/`intB` identifier mixed into a gene interaction source.

Future gate: audit raw RNA/transcript rows directly and preserve transcript endpoint, gene endpoint, role, sourceDatabase, and assertion type before defining this relation.

## Recommended follow-ups

1. Keep `gene_interacts_gene` active with broad semantics and detailed evidence.
2. Do not create active split Parquets from this canonical relation in Block 1.
3. If protein/transcript splits are desired, create a separate raw-source audit/build task for OpenTargets interaction product endpoints:
   - parse `intA`/`intB` namespace classes;
   - separate `ENSP`, UniProt, RefSeq/transcript-like, and `URS` identifiers;
   - decide endpoint node policy;
   - materialize split evidence first;
   - validate anti-joins against target node tables.
4. Treat SIGNOR as a possible `regulates` source, but not as `tf_regulates_gene` until TF-specific criteria are explicit.
5. Do not use this source for `tf_binds_enhancer`; use enhancer/regulatory datasets with context instead.
