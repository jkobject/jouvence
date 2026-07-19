# Human ENSG gene migration candidate — `t_8b9cdabc`

Status: **staged-only; review-required; canonical not modified**

## Scope and policy

This candidate rewrites the full canonical KG snapshot to the human gene identifier contract in [`guides/kg-architecture-and-evidence.md`](guides/kg-architecture-and-evidence.md): canonical human `gene` nodes and endpoints use Ensembl stable gene IDs (`ENSG...`); NCBI Gene IDs remain aliases and provenance; ambiguous and unavailable mappings fail closed.

The staged builder reads an immutable local copy of all canonical `nodes/`, `edges/`, and `evidence/` Parquets. It does not accept a GCS destination and cannot promote. The candidate is isolated at:

`gs://jouvencekb/kg/staging/human-ensg-gene-migration/t_8b9cdabc/ncbi-2e5f37c-genehist-ab8a3a8/`

The canonical prefix `gs://jouvencekb/kg/v2` was generation-inventoried before and after the build. All 76 source objects retained the same generation, size, MD5, CRC32C, and update timestamp.

## Authoritative mapping inputs

| Input | SHA-256 | Candidate copy |
| --- | --- | --- |
| NCBI `gene2ensembl.gz` | `2e5f37ccb896e111ec09db415f9ef2c881518447778f687fabb12ed24f7c0f18` | `metadata/sources/gene2ensembl.gz` |
| NCBI `gene_history.gz` | `ab8a3a8463bb8b68b7861df86a701c17bbcb3e3b10ee9da1a431c2d4e0bf3fdd` | `metadata/sources/gene_history.gz` |

The mapping table is `metadata/ncbi_gene_to_human_ensg.parquet`. Of 27,610 NCBI gene IDs present in the KG:

- 25,148 have an accepted direct one-to-one human ENSG mapping;
- 18 retired IDs resolve through one unambiguous replacement;
- 25 are ambiguous one-to-many;
- 2,404 are unmapped;
- 10 have a retired replacement with no accepted ENSG mapping;
- 5 are retired without a replacement.

Only `accepted_1to1` and `retired_replaced_1to1` are rewritten. Every other status is quarantined or excluded with its reason.

## Audit and candidate result

The source `gene` table had 267,830 rows: 81,715 existing human ENSG nodes, 27,610 NCBI nodes, and 158,505 non-human Ensembl nodes. The human-only candidate has 81,715 `gene` rows, all ENSG, and 25,097 human ENSG nodes carry one or more NCBI aliases.

Across every relation type, the source had 725,891 NCBI `x` endpoint occurrences, 2,574,911 NCBI `y` endpoint occurrences, and 161,675 non-human ortholog `y` occurrences. The orthology relation and its evidence are excluded by explicit human-only policy; Open Targets orthology ingestion is disabled by default unless a caller deliberately requests cross-species staging.

| Surface | Source rows | Candidate rows | Quarantined | Exact-identity rows deduplicated | Policy-excluded orthology |
| --- | ---: | ---: | ---: | ---: | ---: |
| Edges | 101,744,668 | 99,903,239 | 40,513 | 1,639,241 | 161,675 |
| Evidence | 76,565,213 | 76,401,411 | 2,127 | 0 | 161,675 |

Deduplication retains one deterministic graph assertion for each exact `(relation, x_id, y_id)` identity. Source evidence multiplicity remains intact and is re-keyed to the canonical edge identity. Quarantine Parquets preserve every unresolved row plus `quarantine_reason`.

## Validation and rollback contract

`metadata/promotion_rollback_manifest.json` records source and candidate row counts, relation-level migration/quarantine/dedup counts, source and candidate SHA-256 inventories, source GCS generations, mapping hashes, and validation output. Its staged SHA-256 is `73cdf159f4e28eb4942e9a9184e1f4901c8f8025d75663be038cb62c3d91b26d` before GCS upload metadata generation.

The final validation is `ok: true` with:

- zero non-ENSG candidate `gene` IDs;
- zero `NCBI:` or non-human Ensembl gene endpoints in edges or evidence;
- zero duplicate graph edge identities;
- zero endpoint anti-join misses for every relation and node type;
- zero evidence identities without a matching edge;
- exact source generation equality before and after staging.

Promotion remains prohibited until reviewer acceptance. A promoter must verify the staged manifest and object hashes, snapshot or generation-pin the current canonical prefix again, and use the normal atomic review/promotion path. Rollback means restoring the 76 canonical source object generations listed in `metadata/canonical_source_generations.json`; the staged builder never overwrote those objects.
