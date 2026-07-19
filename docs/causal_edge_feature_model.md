# Causal semantics as features of existing edges

Status: **authoritative modeling doctrine**  
Decision owner: Jérémie Kalfon  
Decision date: 2026-07-19

## Decision

Jouvence preserves broad, stable biological relation identities. Causal mechanism, direction of effect, pharmacological action, pathogenicity, response polarity, and experimental context are **typed features of those existing edges**, supported by row-level evidence. They are not separate relation names.

For example, Jouvence keeps:

```text
molecule ─molecule_targets_gene→ gene
gene ─disease_associated_gene→ disease
mutation ─mutation_associated_disease→ disease
mutation ─mutation_affects_molecule_response→ molecule
```

It must not create relation families such as:

```text
molecule_inhibits_gene
gene_gof_causes_disease
gene_lof_causes_disease
mutation_confers_drug_resistance
```

unless the endpoint types or the underlying biological assertion genuinely differ from an existing relation. GoF/LoF, inhibitor/agonist, risk/protection, sensitivity/resistance, and similar qualifiers normally belong in columns and evidence.

## Storage contract

### Edge table

`edges/<relation>.parquet` contains one deduplicated `A → B` graph assertion and compact normalized features needed by graph consumers.

Illustrative row:

| x_id | y_id | relation | causal_mechanisms | mechanism_status | effect_directions | evidence_count |
| --- | --- | --- | --- | --- | --- | ---: |
| `ENSG…` | `MONDO…` | `disease_associated_gene` | `[loss_of_function]` | `consensus` | `[risk]` | 6 |

### Evidence table

`evidence/<relation>.parquet` contains every source assertion separately, including raw values, provenance, study and biological context.

Illustrative rows:

| edge_key | causal_mechanism | effect_direction | inheritance_mode | source | source_record_id | context |
| --- | --- | --- | --- | --- | --- | --- |
| `…` | `loss_of_function` | `risk` | `recessive` | `ClinGen` | `…` | `…` |
| `…` | `gain_of_function` | `risk` | `dominant` | `ClinVar` | `…` | `…` |

High-cardinality raw text, PMIDs, assay records, source payloads, populations, doses, times, and biosample details remain in evidence rather than being duplicated into the edge row.

## Aggregation and conflict policy

An edge may have several evidence rows. Each normalized edge feature must carry an explicit aggregation state:

- `single`: one usable assertion;
- `consensus`: several compatible assertions;
- `conflicting`: incompatible assertions exist;
- `unknown`: no usable assertion is available.

A conflict is data, not missingness. It must remain visible, for example:

```text
causal_mechanisms = [gain_of_function, loss_of_function]
mechanism_status = conflicting
```

Inference and downstream consumers must fail closed on `conflicting` or `unknown` whenever a known sign or mechanism is required. They must never select one source silently.

## Normalized feature families

The exact enum contract is versioned and must be derived from source-backed assertions. The following fields are the intended core.

### `molecule_targets_gene` / `molecule_targets_protein`

Compact edge features:

```text
action_types
action_direction
target_modulation
action_status
evidence_count
```

Candidate normalized values include `inhibitor`, `agonist`, `antagonist`, `blocker`, `degrader`, `activator`, and `binder_unknown_effect`. Raw source action strings remain in evidence.

### `disease_associated_gene` / `disease_associated_protein`

Compact edge features:

```text
causal_mechanisms
mechanism_status
effect_directions
effect_direction_status
inheritance_modes
causal_support_level
evidence_count
```

Candidate mechanism values include `loss_of_function`, `gain_of_function`, `dominant_negative`, `haploinsufficiency`, `dosage_gain`, `hypomorphic`, and `unknown`.

The broad relation may also contain non-causal associations. `causal_support_level` must distinguish causal/mechanistic support from statistical association, biomarker, expression, literature, or model-organism evidence.

### `mutation_associated_disease`

Compact edge features may include:

```text
effect_alleles
beta
odds_ratio
effect_directions
clinical_significance
germline_somatic
association_status
evidence_count
```

Evidence retains study locus, cohort/population, confidence interval, source method, disease-specific assertion, and raw effect estimates.

### `mutation_causes_protein_change` / `mutation_affects_transcript`

Compact edge features may include:

```text
variant_consequence_classes
functional_mechanisms
functional_mechanism_status
transcript_or_isoform_context
evidence_count
```

A consequence class such as `missense`, `stop_gained`, `frameshift`, or splice consequence must not be converted automatically into LoF or GoF. Functional mechanism requires explicit source support.

### `mutation_affects_molecule_response`

Compact edge features may include:

```text
response_categories
response_directions
response_status
disease_context_status
evidence_count
```

Required category separation:

- `efficacy`;
- `toxicity`;
- `dosage`;
- `metabolism_pk`.

Directions may include `sensitive`, `resistant`, `increased_efficacy`, `decreased_efficacy`, `increased_toxicity`, `decreased_exposure`, and `unknown`, subject to a reviewed source normalization policy.

## Inference contract

Inference rules consume normalized edge/evidence features; they do not infer from relation names alone.

### Signed treatment or harm

```text
molecule_targets_gene.action_direction
× disease_associated_gene.causal_mechanism/effect_direction
⇒ inferred molecule_treats_disease or molecule_contraindicates_disease
```

Only compatible, source-backed signs may yield a candidate. Missing or conflicting polarity yields zero.

### Allelic triangulation

```text
drug target action
× explicit variant functional mechanism
× disease-specific effect direction
⇒ inferred signed drug–disease effect
```

Generic amino-acid change, genomic containment, LD alone, or proximity is not a functional sign.

### Pharmacogenomic drug–disease candidate

The requested endpoint remains a direct inferred `molecule → disease` edge. Only efficacy/benefit-compatible evidence with compatible disease context may produce `molecule_treats_disease`. Resistance, toxicity, dosage, pharmacokinetics, missing disease context, or conflicting direction must not be laundered into treatment.

## Current inference scope decisions

- C1 variant–protein–disease remains a staged hypothesis/coverage-repair lane, with direct protein consequence and disease-specific evidence required.
- C2 variant–gene–disease is restricted to direct coding/pathogenic, splice, or colocalized-eQTL/explicit-L2G support. Simple containment, LD-only, or nearest-gene assignment is excluded.
- C3 variant–enhancer–gene–disease is removed entirely from v1.
- C4, H3, H4, ontology closures, HPO propagation, gene→transcript→protein product derivation, and Reactome closure are out of scope.
- H1 signed drug–target–disease and direct pharmacogenomic C5 remain fail-closed until the required edge features are materially present and reviewed.

## Validation requirements

Any enrichment of existing edge/evidence tables must prove:

1. relation names and endpoint identities are unchanged;
2. edge row identity and edge/evidence pairing are conserved;
3. normalized enums are versioned and source-backed;
4. null, `single`, `consensus`, `conflicting`, and `unknown` counts are reported;
5. evidence conflicts cannot be overwritten by direct or alias fields;
6. graph loaders remain backward-compatible with optional feature columns;
7. toxicity/PK does not become efficacy, and generic consequence does not become LoF/GoF;
8. outputs are staged and independently reviewed before canonical promotion;
9. inference outputs remain under `edges_inferred/` and `evidence_inferred/`, never observed `edges/`.

## Source priorities

Before rerunning signed inference, prioritize at most three source-native enrichments:

1. pharmacological action/modulation on `molecule_targets_gene/protein`;
2. causal mechanism and disease-direction support on `disease_associated_gene/protein`;
3. effect direction and qualified response on `mutation_associated_disease` and `mutation_affects_molecule_response`.

Candidate sources include OpenTargets action type and direction-of-effect, credible-set effect fields, ClinVar/UniProt variants, ClinGen dosage sensitivity, CIViC, and disease-specific contraindication sources. SIGNOR causalTab may provide directed signed regulatory evidence, but its semantics must still be represented as features/evidence of an approved broad relation rather than relation-name proliferation.

## Status discipline

A documented contract is not a materialized dataset. Use these labels precisely:

- `contract documented`;
- `source fields audited`;
- `staged feature enrichment built`;
- `independently validated`;
- `canonical promoted`;
- `signed inference rerun`.

Do not claim scientific novelty from absence in Jouvence. Anti-join inferred candidates against canonical observed edges, relevant staged source-native lanes, and direct evidence inventories before calling a link missing.
