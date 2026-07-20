# Human ENSG gene migration candidate — `t_8b9cdabc`

Status: **prior production-scale candidate rejected; corrected implementation local-only and
review-required; canonical not modified**

Revision producer: `t_5c938f23`. The earlier 12.6 GB candidate below was built by
`t_8b9cdabc` and is retained only as rejected historical evidence. It is not a corrected
candidate and must not be promoted. A fresh production-scale staged rebuild requires a
separate remote execution lane after lifecycle reauthorization and acceptance of this
implementation.

## Scope and policy

This candidate rewrites the full canonical KG snapshot to the human gene identifier contract in [`guides/kg-architecture-and-evidence.md`](guides/kg-architecture-and-evidence.md): canonical human `gene` nodes and endpoints use Ensembl stable gene IDs (`ENSG...`); NCBI Gene IDs remain aliases and provenance; ambiguous and unavailable mappings fail closed.

The staged builder reads an immutable local copy of all canonical `nodes/`, `edges/`, and `evidence/` Parquets. It does not accept a GCS destination and cannot promote. The rejected historical candidate is isolated at:

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

| Surface | Source rows | Rejected candidate rows | Quarantined | Rows previously labeled deduplicated | Policy-excluded orthology |
| --- | ---: | ---: | ---: | ---: | ---: |
| Edges | 101,744,668 | 99,903,239 | 40,513 | 1,639,241 | 161,675 |
| Evidence | 76,565,213 | 76,401,411 | 2,127 | 0 | 161,675 |

Those counts are not acceptance evidence: the rejected implementation also removed 411,687
pre-existing duplicate rows from relations with no NCBI rewrite. The corrected implementation
copies every unaffected relation byte-for-byte. An affected edge relation fails closed if it
contains a pre-existing duplicate identity. Only post-remap identities with distinct source
endpoint identities may collapse, and every member of such a collision is recorded under
`metadata/collision_lineage/edges/` with canonical endpoints, source endpoints, deterministic
rank, and retained status. Evidence rows are preserved one-for-one after resolved endpoint
rewrites. Quarantine Parquets preserve every unresolved row plus `quarantine_reason`.

## Validation and rollback contract

The corrected builder emits `metadata/deterministic_rebuild_contract.json`. It excludes
wall-clock timestamps and absolute output paths, so two builds from byte-identical inputs must
produce the same contract bytes and candidate Parquet inventory hashes. Per-relation receipts
enforce `source_rows = candidate_rows + quarantine_rows + remap_collision_rows`; collision
receipt rows must equal retained collision identities plus removed collision rows. The outer
`promotion_rollback_manifest.json` records execution paths and time, references the deterministic
contract hash, and always records `canonical_write_performed=false`,
`lamindb_write_performed=false`, and `promotion.authorized=false`.

The old manifest SHA-256
`73cdf159f4e28eb4942e9a9184e1f4901c8f8025d75663be038cb62c3d91b26d`
belongs to the rejected candidate and is not a corrected artifact hash.

The corrected local fixture validation is required to be `ok: true` with:

- zero non-ENSG candidate `gene` IDs;
- zero `NCBI:` or non-human Ensembl gene endpoints in edges or evidence;
- untouched duplicate graph identities preserved byte-for-byte;
- zero pre-existing duplicate identities in any affected relation (fail closed before output);
- zero unreceipted post-remap collision rows;
- zero endpoint anti-join misses for every relation and node type;
- zero evidence identities without a matching edge;
- exact deterministic rebuild-contract equality across two local fixture builds;
- no remote object-store, GCS-FUSE, canonical, or LaminDB write path.

Promotion remains prohibited. The old 76-object generation inventory is historical rollback
evidence for the rejected build, not authorization for reuse. A later remote rebuild must freshly
generation-pin its source snapshot, produce a new immutable staging prefix and hashes, and pass
independent review before a separate promotion path can be considered.
