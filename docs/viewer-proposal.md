# Jouvence-Graph Viewer — product and architecture proposal

**Status:** product proposal + fixture-backed interaction prototype  
**Public preview:** [`viewer.html`](viewer.html)  
**Canonical data:** unchanged under `gs://jouvencekb/kg/v2`

## 1. Product goal

Build a local-first, GeneCards-like entity viewer for every Jouvence-Graph node type. A scientist should be able to search by canonical ID, name or reference ID; open a node dossier; inspect source-backed features, direct edges and evidence; traverse linked nodes; review ranked long-range connections and putative links; retain an explicit navigation trail; and export the dossier plus trail as Markdown, CSV or PDF.

The viewer is an inspection and hypothesis-navigation product. It is **not** a new source of truth, a graph editor, a claim that every ranked connection is causal, or a replacement for the canonical Parquet/evidence contracts.

## 2. Product posture

The useful pattern from GeneCards is the **entity dossier**: stable identity at the top, dense but scannable sections, links to related biological entities, source-level references, and exportable research context. The Jouvence-Graph version should be original and graph-native:

- all 15 canonical node types are first-class, not only genes;
- every relation can expose its evidence rows and source identifiers;
- observed edges, long-range retrieval and inferred hypotheses are visually and semantically separate;
- a right-hand trail records only navigation through node links, not unrelated search jumps;
- data access is local-first and read-only;
- the public site hosts product documentation and a fixture demo, while real data stays behind a user-run localhost backend.

## 3. State-of-the-art comparison

| Pattern | Useful idea | Why it is not sufficient alone | Adopted decision |
|---|---|---|---|
| GeneCards entity pages | Searchable, sectioned entity dossier with aliases, disorders, drugs, pathways and references | Gene-centric; not designed around typed heterogeneous adjacency, inferred layers or KG snapshot manifests | Reuse the dossier/navigation principle across every node type |
| Open Targets GraphQL/UI | Entity search and resolvable target/disease/drug associations; field-level API queries | Its public API is optimized for individual entities and recommends bulk downloads for systematic use; Jouvence adds many node/relation families and source-native evidence contracts | Similar entity API shape, backed by Jouvence query sidecars rather than repeated upstream calls |
| BioThings Explorer | Multi-hop biomedical query paths with explicit semantic inputs/outputs | Federated APIs vary in availability, latency and release timing; they are not Jouvence’s reproducible snapshot | Reuse explicit path provenance, but execute against one immutable Jouvence snapshot |
| Neo4j/browser graph explorers | Convenient Cypher and neighborhood browsing | Duplicates canonical storage, does not solve requester-pays, evidence multiplicity or PyG contracts, and is costly for 100M+ edge rows | No Neo4j dependency; optional generated projection remains possible later |
| DuckDB + Parquet | Excellent local columnar analytics, predicate pushdown and simple packaging | Raw canonical files are not all partitioned/indexed for point lookup; remote scans would be wasteful | DuckDB for local query execution against a derived viewer bundle |
| DuckDB-Wasm | Zero-install browser analytics | Browser credentials and requester-pays are unsafe/awkward; multi-hundred-MB evidence files and 48M enhancers are not browser workloads | Do not use it for production data access; keep credentials in a localhost Python process |

References:

- Open Targets GraphQL documentation: <https://platform-docs.opentargets.org/data-access/graphql-api>
- Open Targets API implementation: <https://github.com/opentargets/platform-api>
- DuckDB GCS documentation: <https://duckdb.org/docs/stable/guides/network_cloud_storage/gcs_import.html>
- BioThings Explorer paper: <https://pmc.ncbi.nlm.nih.gov/articles/PMC10153288/>

## 4. Recommended architecture

```text
Browser on localhost
  └── static Jouvence UI (HTML/CSS/JS)
        └── JSON API on 127.0.0.1 only
              ├── LocalDataSource(root=/path/to/kg/v2)
              └── GCSDataSource(root=gs://jouvencekb/kg/v2,
                                requester_pays=<consumer project>,
                                ADC from host)
                    └── immutable viewer query bundle
                          ├── snapshot.json
                          ├── search.duckdb
                          ├── nodes/*.parquet
                          ├── adjacency/*.parquet (hash/prefix partitioned)
                          ├── evidence-index/*.parquet
                          ├── long-range/*.parquet
                          └── inferred/*.parquet + derivation manifests
```

### Why a localhost backend

A normal browser must not receive Google credentials or unrestricted filesystem access. The packaged command should bind only to `127.0.0.1`, open the user’s browser, and keep Application Default Credentials in the host process.

Proposed command:

```bash
# Local canonical root or downloaded viewer bundle
uv run jouvence-viewer --data-root /path/to/kg/v2

# Requester-pays GCS

gcloud auth application-default login
uv run jouvence-viewer \
  --data-root gs://jouvencekb/kg/v2 \
  --billing-project <consumer-project>
```

The UI may collect the path or billing-project string, but never a token, service-account JSON, HMAC secret or raw credential. GCS mode must fail closed if ADC or the billing project is missing.

### Why a derived query bundle is mandatory

The canonical layout is optimized for reproducible data and ML export, not random point queries. `nodes/enhancer.parquet` has roughly 48.8M rows; `evidence/gene_interacts_gene.parquet` is roughly 483MB. A universal search or neighborhood page must not scan these objects for each keystroke.

The bundle is a **reproducible read-only index**, not a second scientific truth. It must carry:

- canonical KG snapshot ID and source object generations/checksums;
- bundle schema version and builder commit;
- exact included node/relation/evidence/inferred datasets;
- row counts and validation reports;
- no fields that silently promote inferred links to observed edges.

## 5. Query bundle contracts

### Search index

`search.duckdb` contains one normalized row per searchable alias/reference:

```text
node_type, node_id, display_name, alias, alias_kind,
normalized_alias, source, rank_weight
```

Search order:

1. exact canonical ID;
2. exact external reference ID;
3. exact symbol/name;
4. prefix match;
5. full-text token match.

Enhancers and mutations should default to exact ID or genomic-region lookup; fuzzy full-text over tens of millions of coordinate-like IDs is not useful.

### Direct adjacency

Partition a generated adjacency sidecar by stable hash prefix of `node_id`, storing both directions without changing biological direction:

```text
anchor_id, anchor_type, neighbor_id, neighbor_type,
relation, display_relation, anchor_role, edge_key,
source, credibility, score
```

`anchor_role` is `x` or `y`; it allows display from either endpoint while preserving the canonical relation direction.

### Evidence index

Evidence remains separate. Point lookup uses `edge_key` where present and the full typed tuple as fallback:

```text
edge_key, relation, x_id, x_type, y_id, y_type,
source, source_dataset, source_record_id, paper_id,
study_id, evidence_score, effect_size, p_value,
direction, predicate, license, release
```

The API paginates evidence and never treats evidence-row count as independent-study count.

### Long-range connections

“Top-5 long-range” must not mean an unconstrained shortest-path query. The product should expose four separately ranked, precomputed lists per anchor:

- diseases;
- genes/proteins (displayed separately when endpoint semantics differ);
- molecules;
- phenotypes.

Every row must include:

```text
target_id, target_type, score, ranker_id, ranker_version,
path_length, support_path, support_relations,
observed_overlap, snapshot_id, caveats
```

MVP ranker: deterministic bounded 2–3 hop path score using relation allowlists, degree penalties and evidence credibility. Later rankers may include accepted embeddings or GNN outputs, but each result must name the ranker and must not be labeled causal by default.

### Putative links

Read only from accepted `edges_inferred/` or staged review artifacts explicitly enabled by manifest. Display:

- `inferred_obvious`, `inferred_weak`, or `do_not_infer` policy class;
- template ID/version;
- support path and support edge hashes;
- overlap with observed canonical edges;
- leakage caveat;
- a **Hypothesis — not observed** badge.

No UI action can promote a link into canonical data.

## 6. API proposal

All endpoints are read-only and bounded.

| Endpoint | Purpose | Hard bound |
|---|---|---:|
| `POST /api/session/connect` | Validate local path or GCS billing configuration and open a snapshot | one bounded manifest/footer probe |
| `GET /api/session` | Data source, snapshot, query-bundle status, cost warning | — |
| `GET /api/search?q=&types=&limit=` | Universal search | max 25 |
| `GET /api/nodes/{type}/{id}` | Identity, aliases and node attributes | one node |
| `GET /api/nodes/{type}/{id}/features` | Feature sidecars grouped by feature kind | max 100 rows/kind |
| `GET /api/nodes/{type}/{id}/edges` | Direct adjacency grouped by relation | max 50/relation, cursor pagination |
| `GET /api/edges/{edge_key}/evidence` | Evidence rows and references | max 100/page |
| `GET /api/nodes/{type}/{id}/long-range` | Top-k by requested target type | fixed k ≤ 5/type |
| `GET /api/nodes/{type}/{id}/putative` | Manifest-enabled inferred hypotheses | max 25 |
| `POST /api/export` | Markdown, CSV bundle or printable HTML/PDF | current dossier + trail only |

Every response includes `snapshot_id`, `data_mode`, `truncated`, and relevant manifest/ranker versions.

## 7. Information architecture

### Global shell

- Jouvence-Graph brand and return-to-site link;
- universal search with type filters and keyboard navigation;
- explicit data-source status (`Fixture`, `Local`, or `GCS requester-pays`);
- current snapshot ID;
- export menu.

### Node dossier

1. **Identity:** type, canonical ID, display name, description, aliases and external IDs.
2. **Features:** text/sequence/chemical/context sidecars, with source and release.
3. **Direct connections:** relation-grouped linked entities; direction preserved.
4. **Evidence:** expandable per edge, source rows, scores, predicates, papers/studies and external URLs.
5. **Long-range:** four top-5 lists with ranker, score, path length and path reveal.
6. **Putative links:** visually separate hypotheses with template and leakage labels.
7. **History sidebar:** only the current link-following trail.

### Navigation semantics

- Selecting a result from the search bar starts a **new trail** with that node as `Search start`.
- Clicking an entity hyperlink inside the dossier appends a step containing source node, relation/path label and target node.
- Clicking a prior history item returns there and truncates later steps; it does not create a duplicate step.
- Browser back/forward mirrors dossier state.
- Trails are stored only in session state by default; no server-side tracking.

## 8. Export contract

- **Markdown:** one human-readable dossier with YAML frontmatter (`snapshot_id`, node, export time, ranker versions) and a `Navigation trail` section.
- **CSV:** a ZIP containing `node.csv`, `features.csv`, `edges.csv`, `evidence.csv`, `long_range.csv`, `putative_links.csv`, `history.csv`, and `manifest.json`. One flattened mega-CSV would destroy semantics.
- **PDF:** print-optimized rendering of the currently loaded dossier plus history. The first implementation can use browser print-to-PDF; a backend renderer is unnecessary unless deterministic batch exports become a requirement.

All exports label observed, retrieved/ranked and inferred rows distinctly.

## 9. Data-source onboarding states

### Local

Ask for the KG root or viewer-bundle path. Validate:

- path exists and is readable;
- expected snapshot/bundle manifest exists;
- paths resolve inside the configured root (no arbitrary file endpoint);
- required nodes/edges directories exist;
- schema version is supported.

If the user points at raw canonical Parquet without a query bundle, offer a local index build and show estimated disk/time before starting.

### GCS requester-pays

Ask for the consumer billing project only. Then:

1. verify ADC without printing identity details;
2. instantiate `gcsfs.GCSFileSystem(project=billing_project, requester_pays=billing_project, token='google_default')`;
3. perform one bounded manifest/footer probe;
4. display a cost warning and snapshot details;
5. cache only the small immutable viewer bundle under the user cache directory.

Do not route remote reads through macOS GCS-FUSE. Do not scan full canonical relations from the Mac.

## 10. Technology recommendation

### MVP

- **Backend:** Python 3.11, FastAPI, Pydantic, DuckDB, PyArrow, gcsfs/fsspec.
- **Frontend:** static semantic HTML, existing Jouvence CSS tokens, small dependency-free JavaScript modules.
- **Packaging:** `uv run jouvence-viewer`; later expose a console script.
- **State:** in-memory session + browser URL/history; no user database.
- **Exports:** client-generated Markdown/CSV ZIP; print CSS for PDF.

### Not recommended for MVP

- Neo4j, Elasticsearch or ClickHouse deployment;
- browser-side GCS credentials;
- DuckDB-Wasm over canonical remote files;
- live unbounded BFS over the full KG;
- on-demand GNN inference from the laptop;
- public hosted API paid by the project.

## 11. Delivery phases and gates

### Phase 0 — accepted product contract

- approve this IA and navigation semantics;
- decide whether proteins are a fifth long-range category or grouped with genes in the UI;
- fix the first ranker contract and accepted inferred artifact set.

### Phase 1 — fixture-complete local viewer

- backend reads the existing deterministic public fixture;
- all endpoints, page sections, history and exports work;
- Playwright validates search-vs-link history behavior;
- no fixture result is presented as live KG evidence.

### Phase 2 — local canonical path

- build/query bundle from a bounded local test snapshot;
- exact search across all node types;
- direct adjacency and evidence pagination;
- manifests and snapshot IDs visible everywhere.

### Phase 3 — requester-pays GCS

- build immutable query bundle on `txgnn-worker`;
- publish it under a versioned GCS prefix after independent review;
- validate ADC + consumer billing project and bounded cache behavior;
- prove one dossier does not trigger an all-relation scan.

### Phase 4 — long-range and inferred layers

- publish deterministic top-k artifacts with ranking manifests;
- add accepted inferred layers, derivation paths and leakage labels;
- evaluate latency and biological usefulness on a reviewed entity set.

### Phase 5 — public release

- package CLI and docs;
- security review for localhost binding, path traversal and export injection;
- accessibility/mobile review;
- public landing link changes from `Preview` to `Open viewer` only after real local/GCS modes pass.

## 12. Acceptance criteria

- Search resolves canonical IDs and aliases across every canonical node type without unbounded scans.
- Node pages distinguish node attributes, features, observed adjacency, evidence, ranked long-range context and inferred hypotheses.
- Every linked entity is navigable and link navigation alone appends to the trail.
- Search starts a new trail; history navigation truncates rather than duplicates.
- Markdown, CSV bundle and PDF include snapshot/ranker metadata and the trail.
- Missing GCS billing project or ADC fails closed with an actionable message.
- No credentials reach browser storage, logs or exports.
- Remote point queries use the reviewed query bundle; canonical GCS is not scanned interactively.
- All outputs remain read-only and no inferred candidate is written into observed canonical surfaces.
