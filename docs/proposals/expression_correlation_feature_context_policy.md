# L2-X expression correlation/coexpression feature-context policy

Date: 2026-06-22
Task: `t_c8f1dbc0`
Status: implementation pilot for feature/context storage only; no canonical KG edge promotion.

## Goal

Preserve useful expression correlation, coexpression, predictive association, and disease-module scores without recasting them as causal or mechanistic KG edges. These records are model features/context, not regulatory, physical-interaction, miRNA-target, lncRNA-target, transcript-interaction, or PPI assertions.

## Candidate source audit

| Candidate source family | What it can provide | Current local availability | Source/licensing status | Recommendation |
| --- | --- | --- | --- | --- |
| OpenTargets `interaction` / `interaction_evidence` STRING-like channels | Interaction evidence may include database/channel scores such as coexpression or text-mining sub-evidence, depending on release/source row | Current repo has OpenTargets relation code/docs, but no local raw source row with an audited coexpression-specific subfield found in this tranche | Need release-specific source files and license/provenance fields before any real staged build | Do not promote. If raw fields exist, keep coexpression channel as feature/context or evidence metadata, not `gene_interacts_gene`/PPI. |
| STRING coexpression network / subscore | Gene/protein association score partly based on expression correlation across context; often organism/global, not causal | No local STRING coexpression files found | STRING licensing is non-trivial for redistribution/commercial use; must be explicitly approved | Defer real ingest until license is accepted. If approved, write `features/gene_gene_expression_correlation.parquet` with `evidence_type=correlative` or `predictive`, `predicate=STRING_coexpression`, release/license, and no canonical edge. |
| Public coexpression resources (e.g. COXPRESdb, GTEx-derived correlation matrices, ARCHS4-style correlation) | Gene↔gene correlation in tissue/cell/cohort context, coefficients/scores, sample count/method depending on source | No local raw files found | Varies by source; needs source-specific license and endpoint namespace audit | Good fit for feature/context tables when context and stats are retained. Prefer tissue/cell/cohort-aware sources over global-only dense networks. |
| ENCORI/starBase/ceRNA/lncRNA resources with expression-correlation fields | miRNA/lncRNA/circRNA/transcript↔gene or ceRNA pair correlations, often with p-values and cancer/disease context | No local ENCORI/starBase files found in repo/GCS probe | Web/API/source license and ID mapping must be audited; RNA entity model is still partly pending | Defer real source build. These rows must not populate `mirna_targets_gene`, `lncrna_regulates_gene`, or `transcript_interacts_gene` unless the source also contains direct mechanistic target evidence. Correlation-only rows go to `rna_gene_expression_correlation` or source-specific feature tables. |
| Disease-association-only modules / target-priority scores | Gene↔disease or molecule↔disease predictive/association scores without direct mechanism | OpenTargets association-score family is documented but not staged here | OpenTargets license/provenance likely manageable, but release-specific rows still need audit | Store as `gene_disease_association_score` / `molecule_disease_association_score` features with `evidence_type=association_score` or `predictive`; do not turn into causal disease mechanism edges. |

No safe real source with local audited raw rows and clear redistribution/license status was identified during this tranche. The expected GCS mount `/mnt/gcs/jouvencekb` was not available in this worker environment, so remote/canonical source caches could not be inspected directly. Therefore the code pilot is a local fixture/contract test for schema, validation, and storage behavior only.

## Schema placement recommendation

Promote this tranche as feature/context tables, not active KG relations.

Implemented storage location:

- `features/<feature_table>.parquet`
- helper module: `manage_db/kg_feature_context.py`
- tests: `tests/test_kg_feature_context.py`

Initial allowed feature tables:

| Feature table | Endpoint contract | Intended sources |
| --- | --- | --- |
| `gene_gene_expression_correlation` | gene → gene | STRING coexpression channel, COXPRESdb, GTEx/ARCHS4-style correlations |
| `rna_gene_expression_correlation` | transcript/RNA → gene | ENCORI/starBase/ceRNA/lncRNA expression-correlation-only rows after RNA endpoint policy is approved |
| `gene_disease_association_score` | gene → disease | disease-association-only target-priority modules, OpenTargets association-score family |
| `molecule_disease_association_score` | molecule → disease | non-mechanistic drug/disease predictive scores |
| `cell_line_gene_expression_feature` | cell_line → gene | DepMap/CCLE expression features used for modeling context |

Potential future active relations such as `gene_correlated_with_gene` or `rna_correlated_with_gene` should remain deferred unless a downstream graph loader specifically requires graph edges for non-causal features. If such relations are ever added, they must be visually/lifecycle-distinct from active mechanistic relations and carry `direct=False`, `RelationKind.EXPRESSION` or `METADATA`, and explicit non-causal labels.

## Required columns/context

Feature/context rows preserve:

- endpoint IDs/types: `x_id`, `x_type`, `y_id`, `y_type`;
- explicit non-causal label: `evidence_type` in `correlative`, `non_causal`, `predictive`, `association_score`, `candidate_context`;
- source provenance: `source`, `source_dataset`, `source_record_id`, `release`, `license`;
- context: `context_type`, `context_id`, `context_name` (`tissue`, `cell_type`, `disease`, `cohort`, `biosample`, `cell_line`, or `pan_context`);
- quantitative fields: `correlation_coefficient`, `effect_size`, `p_value`, `q_value`, `score`, `sample_count`;
- method/predicate: `method`, `predicate`.

## Guardrails implemented

`manage_db.kg_feature_context` enforces:

1. Feature records are written under `features/`, never `edges/`.
2. Known table names have explicit endpoint contracts.
3. Rows with wrong endpoint types are rejected.
4. Rows with causal/mechanistic labels such as `mechanistic`, `causal`, `ppi`, `direct_binding`, or `direct_regulation` are rejected.
5. Ambiguous labels such as raw `coexpression` are rejected unless normalized to an explicit non-causal type such as `correlative`.
6. Append mode deduplicates by feature table, endpoint pair, source, source record, context, and method.

## Non-goal examples

Do not use expression-correlation-only evidence to populate:

- `lncrna_regulates_gene`
- `transcript_interacts_gene`
- `mirna_targets_gene`
- `mirna_targets_transcript`
- `tf_regulates_gene`
- `gene_interacts_gene`
- `protein_interacts_protein`

Those relations require source-native mechanism/interaction/target evidence beyond expression correlation.

## Next unblocker for real staged build

A real staged pilot needs one approved source package with:

1. raw downloadable rows available locally or from an approved URL;
2. explicit license/redistribution status;
3. endpoint namespace mapping to existing node types;
4. correlation/effect/p/q/sample/method/context columns identified;
5. release/source-record IDs stable enough for provenance.

Best first candidates:

1. GTEx-derived or other public gene↔gene correlation table with tissue/sample counts and permissive redistribution; or
2. OpenTargets/STRING sub-evidence if the current OpenTargets release exposes coexpression channel columns and license review accepts storing the score as feature/context only.
