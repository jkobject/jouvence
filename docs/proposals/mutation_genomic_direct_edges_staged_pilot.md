# Mutation genomic direct edges staged pilot

Task: `t_3255672c`
Date: 2026-06-22
Stage root: `.omoc/staging/mutation-genomic-direct-20260622-t_3255672c`
Remote root: `gs://jouvencekb/kg/v2/staging/source-native-expansion/mutation-genomic-direct-20260622-t_3255672c/`

## Source audit

OpenTargets Platform 26.03 official FTP source directories available at `https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/`:

- `variant`: 25 Parquet parts; used `part-00000-489af5f8-1f32-49c6-88b5-2f5c71927329-c000.snappy.parquet` for this pilot.
- `enhancer_to_gene`: 30 parts; not used as causal enhancer-gene evidence here, only current KG enhancer interval nodes from its prior ingestion were used for coordinate overlap.
- `evidence_eva`: 22 parts, `evidence_eva_somatic`: 3 parts, `evidence_gwas_credible_sets`: 8 parts, `evidence_uniprot_variants`: 5 parts, `pharmacogenomics`: 5 parts, `credible_set`: 200 parts, `so`: 1 part.

Current KG cache used for endpoint/support gates:

- `nodes/gene.parquet`: 267,830 rows.
- `nodes/transcript.parquet`: 507,365 rows.
- `nodes/mutation.parquet`: 2,589,509 rows.
- `nodes/enhancer.parquet`: 48,808,144 rows with `id`, `chromosome`, `start`, `end`, `name`, `source`.
- downstream association support for the enhancer-overlap gate: `mutation_associated_disease` (4,656,171 rows), `mutation_associated_phenotype` (164,406 rows), `mutation_affects_molecule_response` (4,866 rows).

Full machine-readable audit: `.omoc/staging/mutation-genomic-direct-20260622-t_3255672c/source_audit.json`.

## Relation semantics enforced

- `mutation_in_gene`: emitted only from OpenTargets `variant.transcriptConsequences[].targetId` values starting with `ENSG`. This is direct VEP-style consequence/containment metadata from the variant table, not L2G, GWAS credible-set, or association evidence.
- `mutation_affects_transcript`: emitted only from `variant.transcriptConsequences[].transcriptId` values starting with `ENST` and a non-empty `variantFunctionalConsequenceIds` list.
- `mutation_overlaps_enhancer`: emitted only when a bounded variant from the pilot has existing downstream association evidence in current KG disease/phenotype/drug-response mutation relations, then its point coordinate overlaps an existing KG enhancer interval. The overlap itself is contextual/non-causal evidence.

Evidence rows preserve variant ID, HGVS, chr/position/ref/alt, consequence IDs, impact, biotype, transcript/gene/enhancer IDs, enhancer interval coordinates, source release, and source-record IDs. Clinical/study/drug-response context is used as the gate for enhancer overlap via existing canonical mutation association relations; it is not re-expanded into the overlap edge.

## Pilot counts

Input: first 25,000 OpenTargets 26.03 variant rows from part 00000.

- mutation nodes staged: 25,000.
- downstream-supported variants for enhancer-overlap gate: 11,726.
- enhancer interval slice scanned after support gate: 279,555 intervals.
- `mutation_in_gene`: 1,568,719 edges and 1,568,719 evidence rows.
- `mutation_affects_transcript`: 1,568,719 edges and 1,568,719 evidence rows.
- `mutation_overlaps_enhancer`: 1,664,278 edges and 1,664,278 evidence rows.

Validation (`validation.json`) passed:

- all staged edge rows have supporting evidence rows;
- no evidence rows lack staged edge rows;
- no staged mutation/gene/transcript/enhancer endpoint anti-join failures against staged mutation nodes and cached canonical endpoints.

## Promotion recommendation

Keep this tranche staged-only for review. The semantics and endpoint/evidence gates pass, but the pilot shows that full-scale unbounded `mutation_in_gene` / `mutation_affects_transcript` from OpenTargets variant transcript consequences will be extremely dense. Before canonical promotion, choose a bounded policy such as clinically/downstream-supported variants only, MANE/APPRIS/canonical transcript filtering, consequence-class filtering, or feature-table storage for broad VEP context.

`mutation_overlaps_enhancer` should remain bounded to variants with disease/phenotype/drug-response/equivalent downstream association evidence, as implemented here. Do not promote a genome-wide all-variant enhancer-overlap graph.
