# Mutation genomic relations promotion policy

Kanban task: `t_60b3e504`
Date: 2026-06-23
Prior staged pilot: `t_3255672c`
Prior pilot report: `docs/proposals/mutation_genomic_direct_edges_staged_pilot.md`
Prior staged remote root: `gs://jouvencekb/kg/v2/staging/source-native-expansion/mutation-genomic-direct-20260622-t_3255672c/`

## Scope

This document decides the canonical promotion policy for three currently staged/deferred mutation-genomic relations:

- `mutation_in_gene`
- `mutation_affects_transcript`
- `mutation_overlaps_enhancer`

This card is policy-only. It must not promote or write canonical KG artifacts.

## Inputs inspected

### Active schema

`manage_db/kg_schema.py` declares the three relations as active schema relations:

| Relation | X -> Y | Direct? | Schema semantics |
| --- | --- | --- | --- |
| `mutation_in_gene` | `mutation -> gene` | yes | Physical/genomic containment only; not L2G/GWAS association or OpenTargets L2G targetId smoke output. |
| `mutation_affects_transcript` | `mutation -> transcript` | yes | Transcript-level consequence such as splicing/UTR/coding-transcript effect; not canonical until bounded source-specific evidence and endpoint policy are selected. |
| `mutation_overlaps_enhancer` | `mutation -> enhancer` | no | Variant-enhancer interval overlap only for variants that also have downstream disease/phenotype/drug-response evidence; overlap itself is contextual, not a standalone causal edge. |

`docs/kg_schema_overview.md` and `docs/relation_coverage_current.md` currently classify all three as `staged-only/deferred`, with no canonical edge/evidence files.

### Current node and canonical edge availability

Current FUSE/bucket inspection found the required node families present:

| Node type | Current rows | Present columns relevant here |
| --- | ---: | --- |
| `mutation` | 2,589,509 | `id`, `hgvs`, `clinvar_id`, `gnomad_id`, `name`, `source` |
| `gene` | 267,830 | `id`, `gene_name`, `biotype`, identifiers/aliases |
| `transcript` | 507,365 | `id`, `ensembl_gene_id`, `protein_id`, `refseq_mrna`, `ccds_id`, `source` |
| `enhancer` | 48,808,144 | `id`, `chromosome`, `start`, `end`, `name`, `source` |

Canonical edge files already present for downstream support gates:

| Relation | Edge rows | Evidence rows |
| --- | ---: | ---: |
| `mutation_associated_gene` | 535,093 | 535,093 |
| `mutation_associated_disease` | 4,656,171 | 4,656,171 |
| `mutation_associated_phenotype` | 164,406 | 169,005 |
| `mutation_affects_molecule_response` | 4,866 | 18,595 |
| `mutation_causes_protein_change` | 177,735 | 177,735 |

Canonical edge/evidence files are absent for `mutation_in_gene`, `mutation_affects_transcript`, and `mutation_overlaps_enhancer`.

### Prior staged pilot

The staged pilot used OpenTargets Platform 26.03 `variant` rows, first 25,000 input variants from one Parquet part, and current KG node/support gates.

Pilot manifest/validation:

| Artifact | Rows |
| --- | ---: |
| Staged mutation nodes | 25,000 |
| `mutation_in_gene` edges/evidence | 1,568,719 / 1,568,719 |
| `mutation_affects_transcript` edges/evidence | 1,568,719 / 1,568,719 |
| `mutation_overlaps_enhancer` edges/evidence | 1,664,278 / 1,664,278 |
| Downstream-supported variants used for enhancer gate | 11,726 |
| Enhancer interval slice scanned after gate | 279,555 |

The validation artifact passed endpoint/evidence support checks for the staged tranche:

- no staged edge rows lacked evidence rows;
- no evidence rows lacked staged edge rows;
- no endpoint anti-join failures against staged mutation nodes and cached/current canonical endpoints.

Important pilot caveat: `mutation_in_gene` and `mutation_affects_transcript` were generated from all OpenTargets `variant.transcriptConsequences[]` rows that had ENSG/ENST endpoints and non-empty consequence IDs. The pilot evidence text contains VEP contexts such as `SO_0001632` downstream-gene variants with large `distance_from_tss`/`distance_from_footprint` values. Those rows are valid VEP consequence context, but they are not strict physical gene containment and are too dense to promote as graph edges as-is.

## High-level recommendation

Do not promote the pilot as-is.

The pilot is useful as a staged source-gap/context audit, but not as a canonical graph tranche. It over-expands VEP transcript consequences into one edge per variant/transcript/gene consequence row. For canonical KG edges, split the policy into:

1. strict, bounded graph assertions; and
2. broad VEP annotation context stored as evidence/feature context, not as canonical graph edges.

Recommended canonical build behavior:

| Relation | Promote pilot as-is? | Canonical action | Rationale |
| --- | --- | --- | --- |
| `mutation_in_gene` | no | Rebuild with stricter physical-containment policy; keep broad VEP `targetId` context staged/feature-context. | OpenTargets VEP `targetId` includes upstream/downstream and consequence target semantics; it is not always physical containment. |
| `mutation_affects_transcript` | no | Rebuild bounded transcript consequence edges with allowed consequence classes and canonical endpoint policy. | All-transcript VEP expansion is very dense; only transcript-local/coding/splice/UTR/noncoding-transcript effects should become graph edges. |
| `mutation_overlaps_enhancer` | no | Keep current exact-overlap outputs staged/context/feature unless a new policy selects stronger allele-specific regulatory or enhancer-activity evidence. | Coordinate overlap is contextual and very dense. Existing disease/phenotype/drug-response support is only a triage gate, not regulatory causality or enhancer activity evidence. |

## Relation-specific policies

### 1. `mutation_in_gene`

#### Canonical meaning

`mutation_in_gene` means physical/genomic containment of a mutation within the genomic span of a gene or one of the gene's transcript-local regions.

It must not mean:

- OpenTargets L2G/GWAS locus-to-gene prediction;
- statistical or functional association between a variant and a gene;
- arbitrary VEP `transcriptConsequences[].targetId` when the consequence is upstream/downstream/distant;
- a broad "variant has any VEP consequence row targeting this ENSG" feature.

Those non-containment meanings belong in other places:

- `mutation_associated_gene` for L2G/GWAS/statistical/functional association;
- broad VEP `targetId` context in feature/evidence side tables or a future explicitly named relation if the schema is extended.

#### Physical containment vs VEP consequence target semantics

OpenTargets `variant.transcriptConsequences[].targetId` is not sufficient by itself for `mutation_in_gene`.

Why:

- `targetId` identifies the gene targeted by a VEP transcript consequence record.
- VEP consequence records can include transcript/gene-neighborhood classes such as upstream/downstream variants.
- The pilot sample contains rows with `SO_0001632` downstream-gene consequence and large distances from TSS/footprint while still emitting `mutation_in_gene` edges.
- Such rows are source-native VEP context, but they are not physical containment.

Canonical rule:

A row may become `mutation_in_gene` only if at least one of these is true:

1. independent coordinate containment: mutation chromosome/position overlaps an accepted gene interval for the same ENSG; or
2. VEP consequence class is transcript/gene-local, excluding upstream/downstream/intergenic/regulatory-neighborhood classes, and the ENSG endpoint exists in canonical `nodes/gene.parquet`.

Recommended implementation preference:

- Prefer independent coordinate containment against an Ensembl/GTF-derived gene interval table, because current `nodes/gene.parquet` does not contain coordinates.
- Use VEP consequence rows as supporting evidence only after filtering to transcript/gene-local classes.
- Preserve VEP metadata in evidence: `variant_id`, HGVS, chromosome, position, ref/alt, `targetId`, `transcriptId`, consequence IDs/names, impact, biotype, canonical/MANE/APPRIS flags when available, distance fields, release, source record ID.

#### Allowed classes for `mutation_in_gene`

For VEP-derived containment support, include transcript/gene-local classes such as:

- coding/protein-altering consequences: `transcript_ablation`, `splice_acceptor_variant`, `splice_donor_variant`, `stop_gained`, `frameshift_variant`, `stop_lost`, `start_lost`, `inframe_insertion`, `inframe_deletion`, `missense_variant`, `protein_altering_variant`, `synonymous_variant`, `coding_sequence_variant`;
- transcript-local noncoding/splice/UTR consequences: `splice_region_variant`, `5_prime_UTR_variant`, `3_prime_UTR_variant`, `non_coding_transcript_exon_variant`, `intron_variant`, `NMD_transcript_variant`, `non_coding_transcript_variant`, `mature_miRNA_variant` when represented as an ENST/gene-local transcript consequence.

Exclude from `mutation_in_gene` even if `targetId` is present:

- `upstream_gene_variant`;
- `downstream_gene_variant`;
- `intergenic_variant`;
- enhancer/promoter/TF-binding/regulatory-region neighborhood annotations unless there is explicit gene body overlap;
- L2G/GWAS/eQTL target predictions.

#### Promotion decision

- Do not promote the pilot as-is.
- Rebuild full-scale only after adding or selecting a trusted gene coordinate source and applying the allowed-class filter.
- If no coordinate table is available in the build environment, build a staged candidate from filtered VEP transcript-local classes only and keep it staged until coordinate anti-join/containment validation is available.

### 2. `mutation_affects_transcript`

#### Canonical meaning

`mutation_affects_transcript` means a mutation has a source-native transcript-level consequence on a concrete ENST transcript endpoint.

It should capture transcript-local effects: coding, splice, UTR, exon/intron, NMD, or noncoding transcript consequences. It should not capture broad nearby-gene context.

#### Endpoint policy

Canonical endpoint requirements:

1. `x_id` must exist in canonical `nodes/mutation.parquet` or be introduced as part of the same promoted tranche with validated mutation nodes.
2. `y_id` must be an ENST identifier present in canonical `nodes/transcript.parquet`.
3. The transcript endpoint must come directly from OpenTargets/VEP `transcriptConsequences[].transcriptId`, not from gene expansion.
4. Edge rows must deduplicate to one `mutation -> transcript` graph assertion per relation; multiple consequence rows or sources for the same pair belong in evidence rows.
5. Evidence must preserve the consequence class list, impact, transcript biotype, canonical flags, source release, and source record ID.

Density-control endpoint rule:

- For canonical graph promotion, default to Ensembl canonical/MANE/APPRIS-principal transcripts when those flags are available from VEP/source metadata.
- If MANE/APPRIS is unavailable in the source fields, use `is_ensembl_canonical == true` as the first canonical endpoint filter.
- All noncanonical transcript consequence rows may be retained as evidence/feature context or staged-only output, but should not be promoted as graph edges until a downstream model need justifies all-transcript density.
- If a clinically/downstream-supported mutation has no canonical transcript consequence after filtering, keep its VEP rows in feature context and do not invent a transcript edge.

#### Allowed consequence classes

Allowed for canonical `mutation_affects_transcript`:

High/moderate coding or protein-altering transcript consequences:

- `transcript_ablation`
- `splice_acceptor_variant`
- `splice_donor_variant`
- `stop_gained`
- `frameshift_variant`
- `stop_lost`
- `start_lost`
- `transcript_amplification`
- `inframe_insertion`
- `inframe_deletion`
- `missense_variant`
- `protein_altering_variant`

Low-impact but transcript-local consequences:

- `splice_region_variant`
- `incomplete_terminal_codon_variant`
- `start_retained_variant`
- `stop_retained_variant`
- `synonymous_variant`
- `coding_sequence_variant`

Transcript-local noncoding consequences:

- `5_prime_UTR_variant`
- `3_prime_UTR_variant`
- `non_coding_transcript_exon_variant`
- `intron_variant`
- `NMD_transcript_variant`
- `non_coding_transcript_variant`
- `mature_miRNA_variant`, only when the endpoint is an existing ENST transcript and not a separate mature-miRNA node concept.

Excluded from canonical `mutation_affects_transcript`:

- `upstream_gene_variant`
- `downstream_gene_variant`
- `intergenic_variant`
- generic regulatory-region/enhancer/promoter/TF-binding context that does not alter the transcript sequence/splicing/UTR/intron/exon annotation itself
- rows lacking ENST endpoint support in canonical transcript nodes

#### Variant gate

The build can be full-scale over all current canonical mutation nodes if the endpoint/consequence filters keep graph density acceptable. If full-scale counts are still too large, use this bounded gate for canonical promotion:

- include mutations already present in at least one downstream canonical relation: `mutation_associated_disease`, `mutation_associated_phenotype`, `mutation_affects_molecule_response`, `mutation_associated_gene`, or `mutation_causes_protein_change`;
- keep all other VEP transcript consequence rows staged/feature-context until there is a consumer that needs them as graph edges.

#### Promotion decision

- Do not promote the pilot as-is.
- Rebuild with allowed consequence classes and canonical transcript endpoint filters.
- Promote only after reporting full-scale candidate counts before/after filters and validating endpoint/evidence support.

### 3. `mutation_overlaps_enhancer`

Status update from reviewer `t_289a2e9b` / tofix card `t_59b13c08`: the downstream-gated exact-overlap smoke tranche is **not canonical edge material**. Mechanical endpoint/evidence QA passed, but the evidence is non-causal interval context and extremely dense: `1,670,937` deduplicated edges from one `25,000`-variant smoke part. Treat existing `mutation_overlaps_enhancer` artifacts as staged/context/feature only unless a new reviewed policy selects stronger source-native regulatory semantics.

#### Canonical meaning

`mutation_overlaps_enhancer` means a mutation coordinate overlaps an existing canonical enhancer interval.

It is not causal by itself. It should not imply that the mutation changes enhancer activity, regulates the enhancer target gene, or causes a disease. Those interpretations require separate evidence.

#### Context gate policy

Keep the downstream-association gate used in the pilot only for staged/context/feature construction. It is not sufficient for canonical edge promotion.

A mutation may be considered for staged/contextual `mutation_overlaps_enhancer` only if it has at least one current downstream support edge in an accepted mutation relation, initially:

- `mutation_associated_disease`
- `mutation_associated_phenotype`
- `mutation_affects_molecule_response`
- optionally `mutation_associated_gene` and/or `mutation_causes_protein_change` as additional downstream/functional support if approved for the build.

Do not build a genome-wide all-variant enhancer overlap graph. With 48,808,144 enhancer interval nodes and millions of mutation nodes, unbounded coordinate overlap would be graph-noise-heavy and storage-heavy. Even bounded downstream-gated overlap remains contextual until stronger regulatory evidence is selected.

#### Enhancer endpoint policy

- `y_id` must exist in canonical `nodes/enhancer.parquet`.
- Use exact coordinate overlap against current canonical enhancer intervals.
- Preserve enhancer interval coordinates and source in evidence.
- Preserve mutation coordinate/ref/alt/HGVS and source release in evidence.
- For staged/context artifacts, deduplicate one row per `mutation -> enhancer`; multiple interval/source records supporting the same endpoint pair belong in evidence/context rows.

#### Required stronger rule for promotion

A canonical promotion rule must replace the downstream-association-only gate with direct allele-specific regulatory/enhancer-activity evidence or an explicitly source-native regulatory assertion, for example:

- MPRA/CRE perturbation evidence for the variant;
- fine-mapped causal credible set plus enhancer-activity or enhancer-target evidence with calibrated regulatory semantics;
- eQTL/caQTL/ATAC-QTL linking the variant to enhancer activity or target expression with clear provenance;
- source-native variant-to-regulatory-feature assertions with a calibrated score.

Until such evidence is selected and reviewed, keep downstream-gated exact overlap out of canonical `kg/v2/edges` and store it only as staged/context/feature material.

#### Promotion decision

- Do not promote the pilot sample or the current downstream-gated exact-overlap smoke tranche as-is.
- Do not run a full-scale canonical `mutation_overlaps_enhancer` promotion from coordinate overlap alone.
- Keep downstream-gated exact overlap staged/context/feature unless a new policy selects stronger allele-specific regulatory/enhancer-activity evidence.
- If pursuing a new canonical candidate, document the source-native regulatory predicate, density controls, endpoint anti-joins, duplicate-key checks, edge/evidence support audits, and explicit separation from L2G/GWAS association relations before canonical writes.
- Keep unbounded all-variant overlap as feature-context/staged only.

## Full-scale bounded rebuild plan

### Phase 0 - Source and schema preparation

1. Use OpenTargets Platform 26.03 or the current approved release consistently.
2. Use the canonical KG root as the source of current node/edge availability: `gs://jouvencekb/kg/v2` or FUSE `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`.
3. Do not use `.omoc` as source of truth; generated reports may live there, but bucket/FUSE is authoritative.
4. Materialize or select a gene-coordinate source for strict `mutation_in_gene` containment. If unavailable, stage `mutation_in_gene` rather than promoting it.
5. Define a consequence-class lookup table with included/excluded SO IDs and human-readable labels.

### Phase 1 - Candidate extraction

1. Read all OpenTargets `variant` parts for the approved release.
2. Normalize mutation IDs to current canonical mutation ID format.
3. Keep only variants that either already exist in canonical `nodes/mutation.parquet` or are introduced in the same staged tranche with validated mutation nodes.
4. Explode `transcriptConsequences[]` only once into a normalized intermediate feature table with columns such as:
   - `variant_id`
   - `chromosome`, `position`, `reference_allele`, `alternate_allele`, `hgvs_id`
   - `target_id` / ENSG
   - `transcript_id` / ENST
   - `consequence_ids`, consequence labels
   - `impact`
   - `biotype`
   - `is_ensembl_canonical`, MANE/APPRIS fields if present
   - `distance_from_tss`, `distance_from_footprint`
   - source release and source record ID

### Phase 2 - Relation-specific filtering

`mutation_in_gene`:

1. Require canonical mutation and gene endpoints.
2. Prefer coordinate containment against gene intervals.
3. If VEP-derived, require transcript/gene-local allowed classes and exclude upstream/downstream/intergenic/regulatory-neighborhood classes.
4. Deduplicate to one edge per `mutation -> gene`.
5. Preserve all accepted support rows in evidence.

`mutation_affects_transcript`:

1. Require canonical mutation and transcript endpoints.
2. Require ENST from source-native `transcriptConsequences[].transcriptId`.
3. Require allowed consequence class.
4. Apply canonical/MANE/APPRIS endpoint filter for graph edges; keep all-transcript context outside canonical edges unless explicitly approved.
5. Deduplicate to one edge per `mutation -> transcript`.
6. Preserve each accepted consequence row in evidence.

`mutation_overlaps_enhancer` staged/context build only:

1. Build the mutation support set from current downstream mutation relations only for staged/context/feature artifacts.
2. Restrict coordinate overlap to supported mutations.
3. Join point/interval coordinates to current enhancer intervals.
4. Require canonical enhancer endpoints.
5. Deduplicate to one edge per `mutation -> enhancer`.
6. Preserve interval and gate details in evidence.
7. Do not treat the resulting exact-overlap table as a canonical edge candidate without a separate stronger regulatory-evidence policy.

### Phase 3 - Validation gates

Before any canonical promotion:

1. Write staged artifacts only.
2. Validate endpoint anti-joins for mutation/gene/transcript/enhancer endpoints.
3. Validate every edge has at least one evidence row and every evidence row has an edge.
4. Run `manage_db.audit_edge_evidence` or equivalent relation-specific audit.
5. Report full-scale counts before/after each filter:
   - input variants;
   - canonical mutation matches;
   - exploded transcript consequence rows;
   - rows after consequence filtering;
   - rows after canonical transcript filtering;
   - rows after downstream support gate;
   - raw and deduplicated edge counts;
   - evidence counts;
   - endpoint anti-join counts.
6. Update `docs/relation_coverage_current.md` and `docs/kg_schema_overview.md` only after review approval.

## Final promotion matrix

| Relation | Safe to promote now? | Required next action | Canonical acceptance condition |
| --- | --- | --- | --- |
| `mutation_in_gene` | No | Rebuild staged full-scale with strict physical containment; keep broad VEP target context out of graph edges. | Gene coordinate containment or transcript/gene-local VEP class only; no upstream/downstream/L2G rows; endpoint/evidence audit passes. |
| `mutation_affects_transcript` | No | Rebuild staged full-scale with allowed consequence classes and canonical transcript endpoint policy. | ENST endpoint exists; consequence is coding/splice/UTR/intron/exon/NMD/noncoding-transcript local; canonical/MANE/APPRIS filter applied or count-based exception approved; endpoint/evidence audit passes. |
| `mutation_overlaps_enhancer` | No | Keep exact-overlap outputs staged/context/feature unless a new policy selects stronger allele-specific regulatory or enhancer-activity evidence. | A canonical candidate must use source-native regulatory semantics, density controls, endpoint anti-joins, duplicate-key checks, edge/evidence support audits, and explicit separation from L2G/GWAS association relations. |

## Review conclusion

The staged pilot should remain staged/source-gap context. It proves that endpoint/evidence wiring is possible, but it also demonstrates why canonical graph promotion needs stricter semantics and density controls. For `mutation_in_gene` and `mutation_affects_transcript`, the next implementation card may be a staged full-scale bounded rebuild. For `mutation_overlaps_enhancer`, do not promote downstream-gated exact overlap unless a new reviewed regulatory-evidence policy is selected first.
