# BioCypher / Neo4j comparison for the Jouvence/TxGNN KG

Date: 2026-06-23

Scope: read-only analysis. This report inspected the local Jouvence/TxGNN schema/docs/notebook summaries and public BioCypher/Neo4j documentation. It does not modify canonical KG artifacts.

## Sources inspected

Local Jouvence/TxGNN sources:

- `CLAUDE.md`
- `manage_db/kg_schema.py`
- `manage_db/kg_evidence.py`
- `docs/kg_schema_overview.md`
- `docs/source_measure_edge_matrix.md`
- `docs/source_native_expansion_policy.md`
- `docs/txgnn_access_runbook.md`
- Notebook summaries from `notebooks/11_lamin_kg_schema_explorer.ipynb` and `notebooks/12_node_sequence_text_features_summary.ipynb`

Public references:

- BioCypher home/docs index: https://biocypher.org/
- BioCypher schema configuration reference: https://biocypher.org/BioCypher/reference/schema-config/
- BioCypher schema configuration philosophy: https://biocypher.org/BioCypher/learn/explanation/schema-config-philosophy/
- BioCypher adapters explanation: https://biocypher.org/BioCypher/learn/explanation/adapters/
- BioCypher output overview: https://biocypher.org/BioCypher/reference/outputs/
- BioCypher Neo4j output reference: https://biocypher.org/BioCypher/reference/outputs/neo4j-output/
- BioCypher ontology handling reference: https://biocypher.org/BioCypher/reference/source/ontology/
- BioCypher Neo4j tutorial: https://biocypher.org/BioCypher/learn/tutorials/tutorial_basics_neo4j_offline/tutorial_004_neo4j_offline/
- BioCypher paper: https://www.nature.com/articles/s41587-023-01848-y
- Biolink model docs: https://biolink.github.io/biolink-model/
- Neo4j Cypher manual: https://neo4j.com/docs/cypher-manual/current/introduction/
- Neo4j import docs: https://neo4j.com/docs/operations-manual/current/import/
- Neo4j Graph Data Science algorithms docs: https://neo4j.com/docs/graph-data-science/current/algorithms/

## 1. Executive summary

Recommendation: `pilot only`.

Build a Neo4j projection of the Jouvence/TxGNN KG, but do not replace the current Parquet/GCS canonical layer and do not make Neo4j the source of truth. The KG is already optimized around reproducible Parquet artifacts under `gs://jouvencekb/kg/v2/` with explicit nodes, deduplicated edges, evidence rows, and model feature tables. That design is good for versioned ML export, bulk validation, endpoint anti-joins, and TxGNN/PyG/DGL compatibility.

A Neo4j version would be valuable as an exploratory and serving projection: scientists could browse local neighborhoods, write Cypher without DuckDB/Python, inspect evidence/provenance for a claim, extract disease/drug/gene subgraphs, and eventually run Neo4j Graph Data Science algorithms. The highest-value version is therefore a reproducible export generated from canonical Parquets, scoped first to a biologically useful subset rather than the whole 50M+ node / 90M+ edge KG.

BioCypher overlaps with the desired exporter role: it provides schema configuration, ontology-grounded type mapping, adapters, validation-oriented translation, and output writers including Neo4j. However, Jouvence already has a strong domain schema and source-native evidence doctrine. For the first pilot, a small custom Parquet-to-Neo4j exporter may be simpler and less risky. BioCypher should be evaluated in parallel for whether its schema/config and Neo4j writer reduce long-term maintenance once the mapping rules are stable.

## 2. What our KG is today

### Storage model: Parquet-first canonical layer

The current canonical KG root is `gs://jouvencekb/kg/v2/`, exposed locally through the macOS FUSE path `~/mnt/gcs/jouvencekb-kg/v2/` when mounted. The runbook documents the canonical subdirectories:

- `nodes/`
- `edges/`
- `evidence/`
- `features/`
- `metadata/`
- archive/removed-relation areas

The canonical model is not Neo4j, RDF, or a live graph DB. It is a file-backed, versionable, auditable Parquet layer on GCS, with repo-local cache conventions under `.omoc/gcs-cache/kg-v2/` for targeted validation.

### Layers: nodes / edges / evidence / features

`docs/kg_schema_overview.md` and `manage_db/kg_schema.py` define 15 active node types:

- `paper`, `gene`, `transcript`, `protein`, `pathway`, `molecule`, `mutation`, `disease`, `cell_type`, `tissue`, `phenotype`, `cell_line`, `organism`, `dataset`, `enhancer`

Each node type has a primary identifier namespace and optional cross-reference columns. Examples:

- gene: Ensembl `ENSG...`
- transcript: Ensembl `ENST...`
- protein: Ensembl Protein `ENSP...`
- disease: EFO
- molecule: ChEMBL
- phenotype: HP
- tissue: UBERON
- cell type: CL
- mutation: dbSNP / variant identifiers
- enhancer: ENCODE/OpenTargets interval IDs

Edges are stored one relation per Parquet file under `edges/`, with a baseline contract:

```text
x_id, x_type, y_id, y_type, relation, display_relation, source, credibility, ...metadata
```

Evidence is stored separately under `evidence/{relation}.parquet`. `manage_db/kg_evidence.py` defines evidence columns including:

```text
edge_key, relation, x_id, x_type, y_id, y_type,
evidence_type, source, source_dataset, source_record_id,
paper_id, dataset_id, study_id, evidence_score, effect_size,
p_value, direction, confidence_interval, predicate, text_span,
section, extraction_method, license, release, created_at
```

Feature tables are under `features/` and are explicitly not biological graph assertions. Notebook 12 documents sequence, textual summary, and molecule fingerprint tables. Current accepted/promoted feature examples include `protein_sequence`, `transcript_sequence`, `molecule_fingerprint`, and multiple textual-summary tables. `gene_sequence` / `gene_genomic_interval` remains deferred because a gene-level genomic sequence must not be a transcript-derived placeholder.

### Relation semantics and provenance/evidence design

The core design is source-native and evidence-rich:

- Relation names should describe the broad biological assertion and endpoint type.
- Source-specific predicates, scores, assays, study IDs, papers, releases, and provenance live in evidence rows rather than in hyper-fragmented relation names.
- Gene-level rows stay in gene relations; they are not projected into protein relations through xrefs.
- Protein relations are used only for direct protein/isoform evidence or direct protein measurements.
- Edges are deduplicated graph assertions; evidence rows are the many-to-one support/provenance layer.
- Non-causal predictions/correlations are allowed only when honestly typed as predictive, correlative, association, candidate, or context-specific evidence/metadata.

Examples from the current schema/docs:

- `gene_interacts_gene` remains broad for current OpenTargets/TxGNN gene endpoints. Product IDs or roles in evidence metadata are not enough to create `protein_interacts_protein`, `tf_regulates_gene`, or transcript-specific relations.
- `molecule_targets_gene` is used when source-native target endpoint is gene/OpenTargets target; `molecule_targets_protein` is reserved for direct protein/isoform endpoints.
- `tissue_expresses_protein` is direct HPA protein evidence, not RNA-to-protein projection.
- `enhancer_regulates_gene` is a non-causal/context-specific ENCODE-rE2G prediction edge with model/biosample provenance in evidence.

### Current strengths

- Strong reproducibility: canonical artifacts are explicit Parquet files in a stable GCS path.
- Clear endpoint policy: avoids accidental gene→protein/transcript projection.
- Rich provenance: evidence layer preserves source-specific nuance without relation-name explosion.
- ML compatibility: graph assertions and features are well suited for PyG `HeteroData` / DGL export and TxGNN workflows.
- Bulk validation: DuckDB/PyArrow/Parquet workflows can run endpoint anti-joins, row counts, and edge/evidence support audits.
- Low lock-in: Parquet is portable and cheap to mirror/cache.

### Current limitations

- Interactive graph exploration is less accessible for scientists who do not want to write Python/DuckDB.
- Neighborhood inspection and path queries are awkward compared with a graph DB/browser.
- Evidence/provenance inspection requires joining edge/evidence Parquets manually.
- Serving subgraphs to dashboards or analysts requires custom code.
- Graph algorithms are available through Python/PyG/DGL, but not through a turnkey graph database algorithm interface.
- Lamin custom schema integration is not fully active in the instance: notebook 11 notes that `lnschema_txgnn` is not configured in LaminDB, so Lamin is not currently the canonical graph schema surface.

## 3. What BioCypher provides

### Schema/config model

BioCypher uses a `schema_config.yaml` file as the central graph contract. The schema configuration reference says the file defines which entities and relationships are included and how they are represented, while aligning with biomedical ontologies such as Biolink where useful. It bridges ontology grounding with project-specific pragmatic choices.

Important implications for Jouvence:

- BioCypher can express a selected project KG view, not necessarily the entire universe of possible biomedical entities.
- Class/type names can be grounded in ontological concepts but mapped into property graph labels and relation types.
- This is conceptually similar to `manage_db/kg_schema.py`, but YAML/config-driven rather than Python dataclass/enums.

### Ontology mapping / Biolink-style semantics

BioCypher is designed around ontology-backed KG construction. Its ontology handling docs describe an ontological backbone that can be built from a single resource or hybridized from multiple resources, with head/tail ontologies fused at specified points. The schema configuration docs explicitly mention alignment with biomedical ontologies like Biolink.

For Jouvence, this could help:

- map `gene`, `protein`, `molecule`, `disease`, `phenotype`, `pathway`, etc. onto Biolink-like categories;
- document why Jouvence relation names are broad while evidence captures source predicates;
- expose a more standard semantic layer to external users.

But it also creates a modeling risk: Jouvence has deliberate source-native endpoint rules that may not exactly match generic Biolink predicates. BioCypher should not be allowed to over-normalize away those decisions.

### Output adapters, especially Neo4j

BioCypher’s output docs state that development was initially centered around Neo4j because of OmniPath’s migration to a Neo4j backend, while BioCypher now treats itself as an abstraction of biomedical KG building and supports multiple output formats. The docs list output backends including Neo4j, SQLite, PostgreSQL, NetworkX, tabular, RDF, OWL, and ArangoDB.

The Neo4j output page states that BioCypher supports Neo4j 4.4.x and 5.x and can work in offline mode with files for Neo4j admin import or online mode via the Neo4j Python driver. The tutorial “Hands-on Protein Graphs with BioCypher and Neo4j” demonstrates building a small protein graph and importing/interacting with it in Neo4j.

This overlaps strongly with a Jouvence Neo4j projection, especially if we want:

- generated Neo4j import CSVs;
- labels/relationship types derived from schema config;
- repeatable export from adapters;
- future alternative outputs from the same mapping.

### Validation/provenance support

BioCypher’s value is not only output writing. Its translation layer and ontology/schema configuration can validate that adapter-provided records conform to expected node/edge classes and mappings. BioCypher adapters are Python programs that connect data sources to BioCypher core while following interoperability design principles.

For Jouvence, this can be useful as an exporter validation layer, but it is not a full replacement for existing promotion gates:

- BioCypher can help validate type mappings and output contracts.
- Jouvence still needs domain-specific endpoint anti-joins, edge/evidence support audits, source-native policies, and no-fabricated-evidence rules.

### Where it overlaps with or differs from our current pipeline

Overlap:

- Both want an explicit schema of biomedical node and edge types.
- Both value ontology grounding and controlled mappings.
- Both separate source adapters/build steps from graph output.
- Both can target Neo4j/property-graph output.

Differences:

- Jouvence’s canonical truth is already Parquet/GCS; BioCypher is more of a framework for constructing/exporting KGs from adapters.
- Jouvence’s current schema is Python-code-first (`manage_db/kg_schema.py`), while BioCypher’s schema is YAML/config-first.
- Jouvence has a bespoke evidence layer with many source/provenance fields keyed to deduplicated edge assertions. BioCypher can carry properties/provenance, but the Jouvence evidence-row pattern needs an explicit mapping choice.
- Jouvence’s key risk is semantic drift from source-native endpoint policies; BioCypher’s generic ontology alignment could help documentation but could also push toward overly standard predicates if misused.

## 4. Gap analysis table

| Dimension | Current Jouvence/TxGNN KG | BioCypher-style KG / Neo4j projection | Gap / decision |
| --- | --- | --- | --- |
| Schema expressivity | Python dataclasses/enums define node types, relation endpoints, relation kind/direct flags, notes, and lifecycle status. | YAML schema config grounds entities/relations in ontology concepts and maps them to output labels/types. | Jouvence is already expressive. BioCypher adds config portability and standardized ontology grounding, but would duplicate schema unless generated from `kg_schema.py` or kept strictly synchronized. |
| Provenance/evidence | Dedicated `evidence/{relation}.parquet` layer with `source_dataset`, `source_record_id`, PMIDs, studies, scores, predicates, releases, etc. | Properties on nodes/edges and/or extra evidence nodes/edges can represent provenance; BioCypher can pass record properties through adapters. | Need explicit evidence mapping. Loading all evidence rows as relationship properties may explode duplicates; evidence nodes or sampled evidence are safer for Neo4j. |
| Ontology alignment | Primary namespaces are explicit: Ensembl, ENSP, EFO, CL, UBERON, ChEMBL, HP, Reactome/GO, etc.; bionty/pertdb used in parts. | BioCypher emphasizes ontology backbone and Biolink-like schema alignment. | BioCypher could improve external semantic readability, but should not override source-native endpoint policies. |
| Reproducibility | Strong: canonical Parquets under GCS, targeted caches, validation reports, promotion gates. | Good if exports are deterministic from canonical Parquets + versioned configs. Weak if Neo4j is edited manually. | Neo4j must be a generated projection, never manually curated source of truth. |
| Querying/serving | Python/DuckDB/PyArrow; good for bulk analytics, less friendly for graph browsing. | Neo4j Browser/Bloom/Neodash/Cypher provide interactive querying and dashboards. | Neo4j adds real value for exploration and scientist-facing access. |
| Graph algorithms | PyG/DGL-oriented ML export; Python algorithms possible. | Neo4j Graph Data Science provides centrality, community detection, similarity, pathfinding, embeddings, etc. | GDS is useful for exploratory graph analytics, but TxGNN training should still export from canonical Parquet/PyG. |
| ML export / TxGNN compatibility | Native priority: PyG `HeteroData` preferred, DGL fallback; features under `features/`. | Neo4j can export query results/subgraphs, but property graph import does not directly solve TxGNN training. | Neo4j is complementary, not a replacement for ML export. |
| Operational complexity | GCS Parquet + local cache + validation scripts; low server ops. | Neo4j requires DB sizing, import, indexes/constraints, backups, access control, monitoring, and schema migration. | Start with bounded pilot. Whole-KG Neo4j may be expensive and operationally distracting. |

## 5. Neo4j version benefits

### Interactive exploration

A Neo4j projection would let a scientist open a disease, molecule, or gene and traverse local neighborhoods without knowing the Parquet layout. This is particularly useful for questions such as:

- Which molecules target genes associated with a disease?
- Which tissues express proteins targeted by a candidate molecule?
- Which evidence supports this disease-gene or molecule-target assertion?

### Cypher queries for scientists

Cypher is easier to teach for graph questions than Python/DuckDB joins across multiple Parquet files. Example queries follow the recommended projection mapping in section 7.

Example 1 — find candidate repurposing paths from disease to molecule through disease genes and drug targets:

```cypher
MATCH (d:Disease {id: 'EFO:0000305'})<-[:DISEASE_ASSOCIATED_GENE]-(g:Gene)<-[:MOLECULE_TARGETS_GENE]-(m:Molecule)
RETURN m.id AS molecule_id,
       m.name AS molecule_name,
       g.id AS gene_id,
       g.gene_name AS gene_symbol
LIMIT 50;
```

Example 2 — inspect evidence for a specific molecule→gene target edge:

```cypher
MATCH (m:Molecule {id: 'CHEMBL941'})-[r:MOLECULE_TARGETS_GENE]->(g:Gene)
OPTIONAL MATCH (r)-[:SUPPORTED_BY]->(ev:Evidence)
RETURN m.id, g.id, r.credibility,
       ev.source AS source,
       ev.source_dataset AS dataset,
       ev.predicate AS predicate,
       ev.evidence_score AS score,
       ev.paper_id AS paper
ORDER BY score DESC
LIMIT 25;
```

Note: if relationship-to-node evidence links are awkward in Neo4j because relationships cannot have outgoing relationships, use an explicit assertion node pattern `(m)-[:HAS_ASSERTION]->(a:EdgeAssertion)-[:ASSERTS_TARGET]->(g)` or store `edge_key` on the relationship and query evidence by `edge_key`.

Example 3 — find disease genes with tissue/protein expression support through central dogma:

```cypher
MATCH (d:Disease {id: 'EFO:0000305'})<-[:DISEASE_ASSOCIATED_GENE]-(g:Gene)
MATCH (g)-[:GENE_HAS_TRANSCRIPT]->(:Transcript)-[:TRANSCRIPT_ENCODES_PROTEIN]->(p:Protein)
MATCH (t:Tissue)-[:TISSUE_EXPRESSES_PROTEIN]->(p)
RETURN g.id AS gene_id,
       g.gene_name AS gene_symbol,
       p.id AS protein_id,
       t.id AS tissue_id,
       t.name AS tissue_name
LIMIT 100;
```

Example 4 — extract an enhancer regulatory neighborhood with evidence scores:

```cypher
MATCH (e:Enhancer)-[r:ENHANCER_REGULATES_GENE]->(g:Gene {id: 'ENSG00000139618'})
WHERE coalesce(r.score, r.evidence_score, 0.0) >= 0.2
RETURN e.id AS enhancer_id,
       g.id AS gene_id,
       r.source AS source,
       r.biosample AS biosample,
       coalesce(r.score, r.evidence_score) AS score
ORDER BY score DESC
LIMIT 50;
```

### Subgraph extraction

Neo4j can act as a scientist-facing subgraph extraction tool: write a Cypher query, export a local neighborhood, then hand it back to Python for notebooks, PyG experiments, visualization, or review. This is especially useful for bounded disease areas, molecule-target neighborhoods, or evidence audits.

### Evidence/provenance inspection

The current evidence layer is strong but requires manual joins. Neo4j can make evidence visible in one query/browser session. The important design choice is whether to store evidence as:

1. selected relationship properties for simple use;
2. separate `Evidence` nodes keyed by `edge_key` for rich row-level provenance;
3. source/dataset/paper nodes connected to assertion nodes;
4. a hybrid: relationship has summary counts/top fields; full evidence is a separate node/table link.

For Jouvence, the hybrid is probably best for a pilot: keep graph browsing fast while enabling drill-down.

### Dashboard/browser use

Neo4j Browser, Bloom, and Neodash-style dashboards could expose common workflows:

- disease → causal genes → targetable molecules;
- molecule → targets → disease/phenotype/tissue context;
- enhancer → gene → disease context;
- relation evidence counts by source/release;
- QA dashboards for unsupported edges or source coverage.

### Graph algorithms / GDS possibilities

Neo4j GDS could be useful for:

- PageRank/centrality in disease or molecule neighborhoods;
- community detection over PPI/gene interaction subsets;
- node similarity for molecule/gene/disease neighborhoods;
- pathfinding between drugs, genes, pathways, and diseases;
- graph embeddings as exploratory features.

This should be considered exploratory analytics, not a replacement for TxGNN/PyG training.

### Integration with BioCypher

BioCypher could be the reproducible exporter if it can represent Jouvence’s schema/evidence mapping cleanly. A BioCypher layer may be especially attractive if we want multiple downstream projections: Neo4j now, RDF/OWL/tabular later, all from one schema/config.

## 6. Neo4j risks/costs

### Duplication from Parquet canonical truth

The biggest risk is creating two sources of truth. If scientists edit Neo4j directly or if Neo4j imports are not reproducible, the system will drift. Policy should be strict:

- canonical truth remains `gs://jouvencekb/kg/v2/` Parquet;
- Neo4j is read-only/generated for users;
- every Neo4j database has metadata recording KG version/root, export script version, schema hash, included relations/features/evidence policy, import timestamp, and row counts.

### Schema drift

Jouvence schema changes frequently as source-native policies are refined. A separate BioCypher YAML or Neo4j import mapping can drift from `manage_db/kg_schema.py`. Reduce this by either:

- generating the Neo4j/BioCypher schema from `manage_db/kg_schema.py`; or
- adding tests that compare the YAML/export mapping against `RELATIONS` and `NODE_TYPES`.

### Import size/performance

The KG has tens of millions of nodes and about 95M documented edges in current summaries. Whole-graph Neo4j import will need careful sizing, indexes, disk, memory, and import batching. Some relations are huge, especially enhancer/regulatory and expression layers. A direct all-evidence import can become much larger than the edge graph.

### Evidence row explosion

Evidence rows can outnumber edges substantially. Example: `gene_interacts_gene` has 7.4M edges and 14.3M OpenTargets/interaction evidence rows in the documented Block 1 validation state. `enhancer_regulates_gene` has about 48.8M edges and 48.8M evidence/support rows. Loading every evidence row as a node in an all-KG Neo4j database could dominate storage and query performance.

Mitigation:

- pilot only selected evidence rows/fields;
- relationship stores `evidence_count`, `source_count`, `top_source_dataset`, `max_evidence_score`, maybe `edge_key`;
- full evidence drill-down can read Parquet by `edge_key` or only materialize evidence for pilot relations.

### Relation naming strategy

Neo4j relationship types are conventionally uppercase (`MOLECULE_TARGETS_GENE`). Jouvence relation names are snake_case and semantically deliberate. The mapping must be one-to-one and reversible:

- Parquet `molecule_targets_gene` → Neo4j `:MOLECULE_TARGETS_GENE`, relationship property `relation='molecule_targets_gene'`.
- Do not collapse relation names into generic `:RELATED_TO`.
- Do not split relations by evidence predicate unless the canonical schema changes.

### Deployment/backup/security

Neo4j adds operational responsibilities:

- server deployment or Desktop/Aura/local Docker choice;
- auth/users/roles;
- network exposure and TLS if remote;
- backups/snapshots;
- import reproducibility;
- license/cost review for Enterprise/GDS needs;
- data governance around biomedical and source-license constraints.

A local read-only pilot avoids most of this until value is proven.

## 7. Recommended architecture

### Keep Parquet/GCS as canonical truth

Canonical data stays in:

```text
gs://jouvencekb/kg/v2/
  nodes/
  edges/
  evidence/
  features/
  metadata/
```

Neo4j exports should be versioned projections with a manifest, for example:

```text
gs://jouvencekb/kg/exports/neo4j/<export_id>/
  manifest.json
  schema_mapping.yaml
  nodes/*.csv
  relationships/*.csv
  evidence/*.csv        # optional, scoped
  import_command.sh
  validation_report.json
```

### Neo4j node mapping

Recommended labels:

| Parquet node type | Neo4j label | Required properties |
| --- | --- | --- |
| `gene` | `:Gene` | `id`, `node_type='gene'`, `name`/`gene_name`, xrefs where present |
| `transcript` | `:Transcript` | `id`, `node_type`, parent gene/protein xrefs where present |
| `protein` | `:Protein` | `id`, `node_type`, `uniprot_id`, xrefs |
| `molecule` | `:Molecule` | `id`, `node_type`, `name`, `smiles`, `inchikey` when present |
| `disease` | `:Disease` | `id`, `node_type`, `name`, MONDO/OMIM/etc. xrefs |
| `phenotype` | `:Phenotype` | `id`, `node_type`, `name`, xrefs |
| `pathway` | `:Pathway` | `id`, `node_type`, `name`, GO/Reactome IDs |
| `tissue` | `:Tissue` | `id`, `node_type`, `name`, UBERON/xrefs |
| `cell_type` | `:CellType` | `id`, `node_type`, `name`, CL/xrefs |
| `cell_line` | `:CellLine` | `id`, `node_type`, `name`, Cellosaurus/xrefs |
| `mutation` | `:Mutation` | `id`, `node_type`, variant IDs |
| `enhancer` | `:Enhancer` | `id`, `node_type`, interval/source fields where present |
| `paper` | `:Paper` | `id`, DOI/PMCID/xrefs |
| `dataset` | `:Dataset` | `id`, source/release/license where present |
| `organism` | `:Organism` | `id`, taxonomy fields |

Add uniqueness constraints/indexes for each label’s `id`, plus optional indexes on frequent xrefs (`gene_name`, `uniprot_id`, `inchikey`, `mondo_id`, etc.) for the pilot.

### Neo4j relationship mapping

For each `edges/{relation}.parquet`:

- relationship type: uppercase relation name, e.g. `:DISEASE_ASSOCIATED_GENE`;
- source label from relation `x_type`;
- target label from relation `y_type`;
- properties:
  - `relation`
  - `display_relation`
  - `source`
  - `credibility`
  - `edge_key = relation + '|' + x_id + '|' + y_id`
  - compact relation-specific fields that are useful for filtering;
  - evidence summary fields if precomputed: `evidence_count`, `source_dataset_count`, `max_evidence_score`, etc.

Keep direction exactly as canonical Jouvence relation direction. Do not reverse `disease_associated_gene` just because the name starts with disease; current docs state it is gene→disease.

### Evidence mapping options

Recommended pilot mapping:

1. Relationship has `edge_key` and summary evidence properties.
2. For selected pilot relations, create `:Evidence` nodes keyed by `evidence_id` or a deterministic hash of relation/x/y/source fields.
3. Since Neo4j relationships cannot connect to nodes, use one of these patterns:
   - preferred for rich evidence: insert an `:EdgeAssertion` node between biological endpoints:
     - `(x)-[:ASSERTS]->(a:EdgeAssertion {edge_key, relation})-[:ASSERTS_TARGET]->(y)`
     - `(a)-[:SUPPORTED_BY]->(ev:Evidence)`
   - simpler browsing: keep direct biological relationship and connect evidence to endpoints with `edge_key` property, querying by `edge_key`.
4. Do not materialize all evidence for huge relations in the first pilot.

For scientist usability, the direct relationship pattern is easier. For correct evidence graph modeling, the assertion-node pattern is cleaner. The pilot can use direct relationships plus evidence drill-down by `edge_key`; if evidence browsing becomes central, move selected relation families to assertion nodes.

### Feature mapping

Feature tables should not become biological relationships. Map them as properties only when small/simple and useful for interactive filtering, or as separate feature nodes/tables when large:

- `molecule_fingerprint`: probably not useful as raw bit-vector properties in Neo4j; keep in Parquet or expose a small summary/hash.
- `protein_sequence` / `transcript_sequence`: avoid storing long sequences as default properties unless the pilot requires them.
- textual summaries: useful as node properties for browser/search if license permits and size is manageable.

### Should BioCypher be used as exporter layer?

For the pilot: custom exporter first, BioCypher evaluation in parallel.

Rationale:

- Jouvence already has source data normalized to canonical Parquets. The pilot’s hard part is not source ingestion; it is selecting a bounded subgraph and mapping evidence/features without exploding the graph.
- A custom DuckDB/PyArrow exporter can be minimal, transparent, and tightly aligned with `manage_db/kg_schema.py`.
- BioCypher adds value if we want a maintained schema-config abstraction, Neo4j admin import generation, ontology grounding, or future RDF/OWL/tabular outputs from the same mapping.

Suggested decision gate:

- Build pilot exporter with a clean mapping manifest.
- In a parallel spike, express the same pilot in BioCypher `schema_config.yaml` and adapter(s).
- Choose BioCypher for long-term if it reduces code and validates mappings without compromising source-native relation semantics.

## 8. Proposed pilot

### Pilot subgraph

Choose a bounded biologically useful subgraph:

Core node types:

- `gene`
- `protein`
- `molecule`
- `disease`
- `pathway`
- `tissue`
- optionally `phenotype`

Core relations:

- `disease_associated_gene`
- `molecule_targets_gene`
- `molecule_treats_disease`
- `molecule_contraindicates_disease`
- `gene_interacts_gene` or a bounded BioGRID/OpenTargets-supported subset
- `gene_has_transcript`
- `transcript_encodes_protein`
- `pathway_contains_gene`
- `tissue_expresses_protein`
- optionally `tissue_expresses_gene`

Evidence:

- materialize full evidence for `molecule_targets_gene`, `disease_associated_gene`, and `tissue_expresses_protein` if size is manageable;
- summary-only evidence for large `gene_interacts_gene` subsets;
- preserve `source_dataset`, `source_record_id`, `predicate`, `evidence_score`, `paper_id`, `release`.

Possible biological focus:

- a disease area Jérémie cares about, or a compact disease set from OpenTargets with known drug/target biology;
- include only genes associated with that disease set plus 1-hop drug targets, pathways, and direct protein expression in relevant tissues.

### Success criteria

The pilot succeeds if:

1. It is reproducibly generated from canonical Parquets with a manifest and no manual Neo4j edits.
2. Node/edge counts match exporter expectations and sampled endpoint joins are clean.
3. At least three scientist-facing Cypher workflows work:
   - disease → genes → molecules;
   - molecule → targets → disease/pathway/tissue context;
   - edge → evidence/provenance drill-down.
4. Import time and database size are acceptable on the target machine.
5. Evidence semantics remain faithful: no gene→protein projection, no fabricated evidence, no relation-name fragmentation.
6. A scientist can answer a real subgraph question faster than with Parquet/DuckDB alone.
7. Exporter code is small enough to maintain or clearly benefits from switching to BioCypher.

### Rough implementation steps

1. Define pilot scope:
   - selected diseases or relation subsets;
   - included node/edge/evidence files;
   - evidence materialization policy.
2. Write `docs/neo4j_projection_mapping.md` or `exports/neo4j/schema_mapping.yaml`:
   - label mapping;
   - relationship mapping;
   - property whitelist;
   - evidence policy;
   - indexes/constraints.
3. Implement a read-only Parquet exporter:
   - DuckDB/PyArrow reads from local FUSE/cache;
   - filters pilot subgraph;
   - writes Neo4j admin-import CSVs and manifest.
4. Validate export files:
   - row counts;
   - required properties non-null;
   - relation endpoint label compatibility;
   - sample edge/evidence joins by `edge_key`.
5. Import into local Neo4j 5.x:
   - offline admin import for repeatability;
   - create constraints/indexes;
   - load metadata node with export manifest.
6. Run Cypher smoke tests:
   - queries in section 5;
   - evidence drill-down;
   - performance on common patterns.
7. Optional BioCypher spike:
   - encode the pilot mapping in BioCypher schema config;
   - write minimal adapters over canonical Parquets;
   - compare output, code size, validation errors, and maintainability.
8. Review with Jérémie:
   - decide whether to expand, BioCypher-ize, dashboard, or defer.

## 9. What is missing / open questions for Jérémie

1. Pilot biological scope: which disease area or scientific workflow should the first Neo4j projection serve?
2. Target user: internal agent/debug use, Jérémie in Neo4j Browser, wet-lab/scientist collaborators, or dashboard users?
3. Deployment target: local Mac only, VPS, Neo4j Desktop, Docker, Aura, or another managed setup?
4. Evidence depth: should the pilot load full row-level evidence nodes, only evidence summaries, or hybrid drill-down by `edge_key` back to Parquet?
5. BioCypher preference: should the pilot explicitly test BioCypher, or should we first prove value with a custom exporter?
6. Feature exposure: should textual summaries be included as node properties for browsing/search, and are all relevant licenses acceptable for graph DB redistribution?
7. GDS interest: which algorithms matter first: centrality, communities, similarity, pathfinding, embeddings?
8. Security/access: who is allowed to access the Neo4j instance, and can any source-licensed text/provenance be exposed there?
9. Refresh cadence: one-off snapshot, nightly/weekly projection, or export on demand after canonical promotions?

## Bottom line

Build a Neo4j projection as a bounded pilot now, not a full production mirror. Keep Parquet/GCS as canonical truth. Start with a custom exporter over canonical Parquets because it is likely fastest and safest for Jouvence’s source-native evidence doctrine. Evaluate BioCypher during or immediately after the pilot as a possible long-term exporter/schema layer, especially if ontology-grounded config and multi-output support become more valuable than the extra abstraction cost.
