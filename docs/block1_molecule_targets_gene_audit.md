# Block 1 audit — `molecule_targets_gene` evidence and protein-target policy

_Date: 2026-06-21_

## Summary

Canonical files audited from `gs://jouvencekb/kg/v2`, copied into the repo-local cache per `docs/txgnn_access_runbook.md`:

- `.omoc/gcs-cache/kg-v2/edges/molecule_targets_gene.parquet`
- `.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet`

Findings:

1. `edges/molecule_targets_gene.parquet` and `evidence/molecule_targets_gene.parquet` both contain `41,239` rows.
2. Edge/evidence support is complete in both directions: `0` edges without evidence and `0` evidence rows without a matching edge.
3. All audited rows are gene-endpoint rows:
   - OpenTargets: `CHEMBL` molecule -> `ENSG` gene, `14,559` rows.
   - TxGNN: `DrugBank`/`CTD` molecule -> `NCBI` gene, `26,680` rows.
4. OpenTargets rows are correctly separated as `source='OpenTargets'`, `source_dataset='drug_mechanism_of_action'`, with action type preserved as edge `action_type` and evidence `predicate`/`direction`.
5. OpenTargets evidence still carries the stale relation token `molecule_targets_protein` inside `source_record_id`; the supported relation and endpoints are nevertheless `molecule_targets_gene` / gene-level.
6. TxGNN evidence rows have blank `source_dataset` and stale `predicate='molecule_targets_protein'`, `direction='molecule_targets_protein'`, and stale source-record relation tokens despite gene-level endpoints.
7. No current row justifies populating `molecule_targets_protein`: no protein/isoform endpoint IDs were present in either the edge or evidence files. Do not project `ENSG`/`NCBI` gene targets to protein.

Recommendation: keep all current rows in `molecule_targets_gene`; clean evidence provenance; create/populate `molecule_targets_protein` only in a future tranche with source-native molecule -> protein/isoform endpoints.

## Access and files

Commands used:

```bash
mkdir -p .omoc/gcs-cache/kg-v2/{edges,evidence,raw}
gcloud storage cp \
  gs://jouvencekb/kg/v2/edges/molecule_targets_gene.parquet \
  .omoc/gcs-cache/kg-v2/edges/molecule_targets_gene.parquet
gcloud storage cp \
  gs://jouvencekb/kg/v2/evidence/molecule_targets_gene.parquet \
  .omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet
```

The FUSE mount was not required; this follows the copy-to-cache fallback in `docs/txgnn_access_runbook.md`.

## Physical schemas

### Edge schema

```text
x_id              VARCHAR
x_type            VARCHAR
y_id              VARCHAR
y_type            VARCHAR
relation          VARCHAR
display_relation  VARCHAR
source            VARCHAR
credibility       BIGINT
action_type       VARCHAR
```

### Evidence schema

```text
edge_key              VARCHAR
relation              VARCHAR
x_id                  VARCHAR
x_type                VARCHAR
y_id                  VARCHAR
y_type                VARCHAR
evidence_type         VARCHAR
source                VARCHAR
source_dataset        VARCHAR
source_record_id      VARCHAR
paper_id              VARCHAR
dataset_id            VARCHAR
study_id              VARCHAR
evidence_score        DOUBLE
effect_size           DOUBLE
p_value               DOUBLE
direction             VARCHAR
confidence_interval   VARCHAR
predicate             VARCHAR
text_span             VARCHAR
section               VARCHAR
extraction_method     VARCHAR
license               VARCHAR
release               VARCHAR
created_at            VARCHAR
```

## Counts

```sql
select source, count(*) n, count(distinct x_id) molecules, count(distinct y_id) genes
from read_parquet('.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet')
group by 1
order by n desc;
```

| source | rows | distinct molecules | distinct genes |
| --- | ---: | ---: | ---: |
| TxGNN | 26,680 | 6,432 | 3,487 |
| OpenTargets | 14,559 | 5,045 | 1,550 |
| **Total** | **41,239** | | |

Support check:

```sql
with e as (
  select relation, x_id, y_id
  from read_parquet('.omoc/gcs-cache/kg-v2/edges/molecule_targets_gene.parquet')
), v as (
  select relation, x_id, y_id
  from read_parquet('.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet')
)
select 'edges_without_evidence' check_name, count(*) n
from e left join v using (relation, x_id, y_id)
where v.x_id is null
union all
select 'evidence_without_edge', count(*)
from v left join e using (relation, x_id, y_id)
where e.x_id is null;
```

| check | rows |
| --- | ---: |
| edges_without_evidence | 0 |
| evidence_without_edge | 0 |

## Endpoint namespaces

```sql
select
  source,
  x_type,
  case
    when x_id like 'CHEMBL%' then 'CHEMBL'
    when x_id like 'DB%' then 'DrugBank'
    when x_id like 'CTD:%' then 'CTD'
    else regexp_extract(x_id, '^([^:]+)', 1)
  end as x_family,
  y_type,
  case
    when y_id like 'ENSG%' then 'ENSG'
    when y_id like 'NCBI:%' then 'NCBI'
    else regexp_extract(y_id, '^([^:]+)', 1)
  end as y_family,
  count(*) n
from read_parquet('.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet')
group by all
order by source, n desc;
```

| source | x_type | x_family | y_type | y_family | rows |
| --- | --- | --- | --- | --- | ---: |
| OpenTargets | molecule | CHEMBL | gene | ENSG | 14,559 |
| TxGNN | molecule | DrugBank | gene | NCBI | 25,468 |
| TxGNN | molecule | CTD | gene | NCBI | 1,212 |

Interpretation: all current endpoints are molecule -> gene. No audited row has `y_type='protein'`, UniProt, ENSP, isoform, or other protein-native endpoint namespace.

## OpenTargets `drug_mechanism_of_action` rows

OpenTargets rows are already separated from TxGNN rows:

```sql
select source_dataset, predicate, direction, count(*) n
from read_parquet('.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet')
where source = 'OpenTargets'
group by all
order by n desc;
```

Top action types:

| action type | rows |
| --- | ---: |
| INHIBITOR | 6,566 |
| ANTAGONIST | 1,854 |
| AGONIST | 1,657 |
| BLOCKER | 1,541 |
| POSITIVE ALLOSTERIC MODULATOR | 989 |
| MODULATOR | 451 |
| BINDING AGENT | 290 |
| POSITIVE MODULATOR | 196 |
| STABILISER | 151 |
| PARTIAL AGONIST | 141 |

Full long tail observed: `ACTIVATOR`, `DISRUPTING AGENT`, `HYDROLYTIC ENZYME`, `NEGATIVE ALLOSTERIC MODULATOR`, `OPENER`, `EXOGENOUS PROTEIN`, `ANTISENSE INHIBITOR`, `INVERSE AGONIST`, `CROSS-LINKING AGENT`, `RELEASING AGENT`, `OTHER`, `RNAI INHIBITOR`, `SUBSTRATE`, `ALLOSTERIC ANTAGONIST`, `EXOGENOUS GENE`, `VACCINE ANTIGEN`, `DEGRADER`, `NEGATIVE MODULATOR`, `PROTEOLYTIC ENZYME`, `GENE EDITING NEGATIVE MODULATOR`.

Top mechanism labels are currently preserved on the edge as `display_relation`, not explicitly in evidence:

```sql
select display_relation, action_type, count(*) n
from read_parquet('.omoc/gcs-cache/kg-v2/edges/molecule_targets_gene.parquet')
where source='OpenTargets'
group by 1,2
order by n desc
limit 25;
```

Examples:

| mechanism label (`display_relation`) | action_type | rows |
| --- | --- | ---: |
| Tubulin inhibitor | INHIBITOR | 1,110 |
| GABA-A receptor; anion channel positive allosteric modulator | POSITIVE ALLOSTERIC MODULATOR | 912 |
| Sodium channel alpha subunit blocker | BLOCKER | 820 |
| 80S Ribosome inhibitor | INHIBITOR | 546 |
| Voltage-gated potassium channel blocker | BLOCKER | 280 |

OpenTargets cleanup plan:

- Keep relation as `molecule_targets_gene` because the builder explicitly filters `targets[].id` to `ENSG*` and emits `y_type='gene'`.
- Keep `source='OpenTargets'` and `source_dataset='drug_mechanism_of_action'`.
- Keep action type in `predicate`; using the same value in `direction` is acceptable only if downstream treats `direction` as action/effect direction for pharmacology. Prefer documenting this, or leave `direction` blank and rely on `predicate` if `direction` is meant only for up/down/protective/risk semantics.
- Preserve mechanism label explicitly in evidence. With the current fixed evidence schema, the least disruptive path is to store a compact JSON object in `text_span`, e.g. `{"mechanism_of_action":"Tubulin inhibitor","target_id_namespace":"ENSG","action_type":"INHIBITOR"}`. If evidence schema extension is allowed later, add explicit columns instead.
- Fix stale `source_record_id` relation token from `...:molecule_targets_protein:...` to `...:molecule_targets_gene:...` when rebuilding evidence. Current prefix observed for all OpenTargets rows:
  `OpenTargets:drug_mechanism_of_action:molecule_targets_protein`.
- Preserve source release when available, e.g. `26.03`, in `release` or `dataset_id`/dataset node metadata. Current evidence `release` is blank.
- If confidence/score exists in a future raw MoA snapshot, map it to `evidence_score`; current audited edge/evidence files have `evidence_score` null for all rows.

Relevant builder code in `manage_db/ingest_opentargets.py` already aligns with the gene-level policy:

```python
# Emit gene-level edge (Ensembl); protein resolution is deferred
edge_rows.append(_make_edge(
    x_id=chembl_id, x_type=NodeType.MOLECULE.value,
    y_id=gene_id,   y_type=NodeType.GENE.value,
    relation="molecule_targets_gene",
    display_relation=moa_label or action or "targets",
    source=SOURCE_NAME,
    credibility=Credibility.ESTABLISHED_FACT,
    action_type=action,
))
```

## TxGNN rows

TxGNN evidence summary:

```sql
select source_dataset, predicate, direction, count(*) n
from read_parquet('.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet')
where source = 'TxGNN'
group by all
order by n desc;
```

| source_dataset | predicate | direction | rows |
| --- | --- | --- | ---: |
| blank | molecule_targets_protein | molecule_targets_protein | 26,680 |

TxGNN endpoint families:

| molecule family | gene family | rows |
| --- | --- | ---: |
| DrugBank | NCBI | 25,468 |
| CTD | NCBI | 1,212 |

Observed examples:

```text
CTD:C000228  -> NCBI:7157
CTD:C001870  -> NCBI:285590
DB12010      -> NCBI:* rows in edge/evidence aggregate
```

TxGNN cleanup plan:

- Keep rows in `molecule_targets_gene`; endpoints are molecule -> NCBI gene.
- Set stale `predicate` from `molecule_targets_protein` to the source-native TxData relation where recoverable:
  - likely `drug_protein` for DrugBank-derived rows;
  - likely `exposure_protein` or CTD-specific exposure/chemical-gene source for CTD rows if the original TxGNN/TxData source table distinguishes them.
- If raw source detail cannot be recovered from the canonical edge file alone, use a conservative normalized predicate such as `targets_gene` and put the original legacy token in `text_span` JSON, e.g. `{"legacy_relation":"molecule_targets_protein"}`.
- Populate `source_dataset` instead of leaving it blank. Minimum useful split from current IDs:
  - `TxGNN/drug_protein` or `TxGNN/DrugBank` for `DB* -> NCBI:*` rows;
  - `TxGNN/CTD` or a more precise CTD source dataset for `CTD:* -> NCBI:*` rows.
- Fix `source_record_id` relation token from `TxGNN:molecule_targets_protein:<x>:<y>` to include the canonical relation and recovered source dataset, e.g. `TxGNN:drug_protein:molecule_targets_gene:<x>:<y>`.
- Do not use `direction='molecule_targets_protein'`. Either leave `direction` blank for generic target assertions or use a real source action/effect direction if the raw source provides one.
- Keep `evidence_score` null unless raw TxGNN/TxData source provides an actual confidence/score.

The current schema mapping in `manage_db/kg_schema.py` is already compatible with this cleanup:

```python
TXDATA_RELATION_MAP = {
    "target": "molecule_targets_gene",
    "enzyme": "molecule_targets_gene",
    "transporter": "molecule_targets_gene",
    "carrier": "molecule_targets_gene",
    "drug_protein": "molecule_targets_gene",
    "exposure_protein": "molecule_targets_gene",
}
```

The stale evidence was likely produced by backfilling from an already-normalized edge relation while preserving an old source token. Add a TxGNN branch to `manage_db/backfill_edge_evidence.py::_edge_source_metadata` so normalized `molecule_targets_gene` rows from TxGNN emit gene-level predicates and non-blank source datasets.

Suggested pseudo-policy:

```python
if relation == "molecule_targets_gene" and source == "TxGNN":
    if x_id.startswith("DB"):
        source_dataset = source_dataset or "drug_protein"
        predicate = "drug_protein"
    elif x_id.startswith("CTD:"):
        source_dataset = source_dataset or "CTD"
        predicate = "chemical_gene_target"
    else:
        source_dataset = source_dataset or "txdata_molecule_gene_target"
        predicate = "targets_gene"
    direction = ""
```

Treat the exact names above as a cleanup proposal, not a source fact, until the original TxGNN/TxData raw relation table is inspected.

## Split / no-split decision for `molecule_targets_protein`

Decision: **do not populate `molecule_targets_protein` from the current `molecule_targets_gene` rows.**

Reason:

- Current endpoints are all molecule -> gene (`CHEMBL -> ENSG`, `DrugBank/CTD -> NCBI`).
- The source-native OpenTargets builder explicitly accepts only `ENSG` target IDs for this relation.
- The TxGNN rows are normalized from legacy protein-worded relation names but carry NCBI gene endpoints.
- Projecting gene targets to proteins would violate the current KG doctrine and `docs/source_measure_edge_matrix.md`: protein relations require direct protein/isoform endpoints or direct protein measurement/assertion.

Future split gate for `molecule_targets_protein`:

1. Source row must identify a protein/isoform endpoint directly, e.g. UniProt, ENSP, isoform-specific ID, or an equivalent protein-product endpoint retained as protein.
2. `y_type` must be `protein` and anti-join clean against `nodes/protein.parquet`.
3. Evidence must preserve source database, source record ID, protein endpoint namespace, action/mechanism, score/confidence if present, and release.
4. Do not create `molecule_targets_protein.parquet` as a placeholder. Only materialize it when source-backed rows pass the gates.

## Rebuild / validation checklist

When implementing the evidence cleanup:

1. Rebuild `evidence/molecule_targets_gene.parquet` in scratch/staging, not directly in canonical GCS.
2. Preserve row count unless source-detail recovery intentionally expands one edge into multiple evidence rows.
3. Run endpoint and support checks:

```sql
select relation, x_type, y_type, count(*)
from read_parquet('<scratch>/evidence/molecule_targets_gene.parquet')
group by 1,2,3;

with e as (
  select relation, x_id, y_id from read_parquet('<scratch>/edges/molecule_targets_gene.parquet')
), v as (
  select relation, x_id, y_id from read_parquet('<scratch>/evidence/molecule_targets_gene.parquet')
)
select 'edges_without_evidence' check_name, count(*) n
from e left join v using (relation, x_id, y_id)
where v.x_id is null
union all
select 'evidence_without_edge', count(*)
from v left join e using (relation, x_id, y_id)
where e.x_id is null;
```

4. Run project validation gates before promotion:

```bash
uv run python -m py_compile manage_db/kg_schema.py manage_db/kg_evidence.py manage_db/backfill_edge_evidence.py manage_db/ingest_opentargets.py
uv run --group dev pytest tests/test_kg_schema_cleanup.py tests/test_kg_evidence.py tests/test_backfill_edge_evidence.py -q
```

5. Promote to canonical GCS only after review because it overwrites durable KG evidence.
