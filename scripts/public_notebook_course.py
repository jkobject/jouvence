"""Chaptered curriculum content for the generated public Jouvence notebooks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

CellFactory = Callable[[str], Any]


def chapter(
    md: CellFactory,
    code: CellFactory,
    heading: str,
    lesson: str,
    first_code: str,
    interpretation: str,
    second_code: str,
    checkpoint: str,
) -> list[Any]:
    """Build one pedagogical chapter from five independently meaningful cells."""

    return [
        md(f"## {heading}\n\n{lesson}"),
        code(f"# {heading}: run the bounded example and inspect its typed output.\n{first_code}"),
        md(f"### Interpretation\n\n{interpretation}"),
        code(second_code),
        md(f"### Checkpoint\n\n{checkpoint}"),
    ]


def course_notebooks(md: CellFactory, code: CellFactory, setup: Callable[..., Any]) -> dict[str, list[Any]]:
    """Return the six ordered, fixture-executable public notebook curricula."""

    notebooks: dict[str, list[Any]] = {}

    cells = [
        md("""# 01 — Set up Jouvence and navigate its data model

This first lesson starts from a clean clone. It explains local setup, bounded fixture and live access, cloud identity and requester-pays, then follows one biological question across nodes, assertions, and source evidence. The course is read-only: no cell writes canonical data, and a bounded sample does not prove absence or completeness."""),
        setup(),
    ]
    cells += chapter(
        md, code,
        "Install the project and select its kernel",
        "Jouvence uses Python 3.11 or newer and `uv` for a reproducible environment. From the repository root, install notebook dependencies and register or select the Python kernel created for this project. Running from the root also makes relative documentation and fixture paths predictable.",
        """setup_commands = [
    "uv sync --group dev --group notebooks --group gnn",
    "uv run python -m ipykernel install --user --name jouvence --display-name 'Jouvence (uv)'",
    "uv run python scripts/verify_data_quickstart.py --mode fixture",
]
print("Run these in a terminal from REPO_ROOT:")
print("\\n".join(f"  {command}" for command in setup_commands))""",
        "The notebook kernel and the shell environment must refer to the same checkout. A successful fixture quickstart validates imports and Parquet mechanics without requiring a cloud account, credentials, network access, or a billing project.",
        """runtime = {
    "python": sys.version.split()[0],
    "repository": str(REPO_ROOT),
    "mode": MODE,
    "fixture_exists": Path(KG_ROOT).exists() if MODE == "fixture" else None,
}
print(runtime)""",
        "Confirm that the repository path is this checkout and that fixture mode is selected before continuing. Notebook 02 reuses the same environment for embeddings.",
    )
    cells += chapter(
        md, code,
        "Choose fixture or bounded live mode",
        "Fixture mode is deterministic and synthetic; it is the default for learning and CI. Live mode reads named objects from canonical Parquet only after the caller opts in with `JOUVENCE_DATA_MODE=live`. Live access is bounded and read-only, never a full-KG scan from a laptop.",
        """mode_contract = {
    "fixture": "local synthetic examples; no cloud access",
    "live": "named canonical GCS objects; caller credentials and billing required",
}
assert MODE in mode_contract, f"Unsupported JOUVENCE_DATA_MODE={MODE!r}"
print(MODE, "—", mode_contract[MODE])""",
        "Fixture rows illustrate schemas and joins but are not release cardinalities or biological findings. A live bounded prefix is real data, yet it is still not a completeness query: a missing row may lie outside the selected row groups.",
        """if MODE == "live" and not BILLING_PROJECT:
    raise RuntimeError("Live mode requires the caller-owned JOUVENCE_BILLING_PROJECT")
print({"live_opt_in": MODE == "live", "row_ceiling": 10_000, "read_only": True})""",
        "Use fixture mode first. Switch to live mode only for a named table and a clear question, then keep limits small and selected columns narrow.",
    )
    cells += chapter(
        md, code,
        "Understand ADC, IAM, requester-pays, and quota",
        "Application Default Credentials (ADC) are the local identity discovered by Google client libraries. Authentication proves who the caller is; IAM authorization decides whether that identity may read an object; requester-pays attributes request and egress charges to a caller-owned billing project; quota attribution determines which project consumes API quota. These are four separate gates.",
        """cloud_layers = [
    ("authentication", "gcloud auth application-default login", "establish caller identity"),
    ("authorization", "bucket IAM objectViewer grant", "allow object get/list"),
    ("billing", "billing-enabled caller project", "pay requester-pays charges"),
    ("quota", "serviceusage.services.use", "consume enabled API quota"),
]
import pandas as pd
display(pd.DataFrame(cloud_layers, columns=["gate", "example", "purpose"]))""",
        "A valid ADC token does not imply bucket authorization, and bucket authorization does not imply permission to charge a billing project. Error messages should be mapped to the failed gate rather than worked around with embedded credentials.",
        """safe_cloud_commands = [
    "gcloud projects create <caller-owned-project>",
    "gcloud billing projects link <caller-owned-project> --billing-account=<caller-billing-account>",
    "gcloud services enable storage.googleapis.com --project=<caller-owned-project>",
    "gcloud auth application-default login",
    "export JOUVENCE_BILLING_PROJECT=<caller-owned-project>",
]
print("Illustrative commands; substitute only your own authorized project:\\n" + "\\n".join(safe_cloud_commands))""",
        "Never paste a credential, access token, service-account JSON, maintainer project ID, or billing account into a notebook. The maintainer must separately grant your identity read-only bucket access.",
    )
    cells += chapter(
        md, code,
        "Troubleshoot live access without increasing scope",
        "Fail closed and diagnose layer by layer. `401` usually indicates authentication; `403` may indicate bucket IAM or `serviceusage.services.use`; requester-pays errors indicate missing billing attribution; API-disabled errors require enabling the Cloud Storage JSON API in the caller project.",
        """troubleshooting = pd.DataFrame([
    {"symptom": "no ADC", "check": "gcloud auth application-default print-access-token", "gate": "authentication"},
    {"symptom": "object 403", "check": "maintainer read-only grant for exact identity", "gate": "authorization"},
    {"symptom": "requester pays", "check": "JOUVENCE_BILLING_PROJECT and billing enabled", "gate": "billing"},
    {"symptom": "service disabled/quota", "check": "storage.googleapis.com and serviceusage.services.use", "gate": "quota"},
])
display(troubleshooting)""",
        "Do not solve a permission failure by switching to a broader identity or by downloading the bucket. Keep the test to one named object and use `scripts/verify_data_quickstart.py --mode live` as the bounded preflight.",
        """print({
    "preflight": "uv run python scripts/verify_data_quickstart.py --mode live",
    "canonical_root": str(PUBLIC_KG_ROOT),
    "forbidden_on_laptop": ["all-relation scan", "bulk download", "full PyG build", "full embedding scan"],
})""",
        "If the exact read remains blocked, return to fixture mode and report the failing gate. Do not infer that Jouvence data is absent or public just because one identity cannot read it.",
    )
    cells += chapter(
        md, code,
        "Navigate topology, evidence, metadata, features, and proof",
        "`nodes/` stores typed entities; `edges/` stores deduplicated graph assertions; `evidence/` stores source records supporting those assertions; `metadata/` catalogs datasets and provenance objects; `features/` stores text, sequence, numeric, or embedding signals; optional `proof/` records reproducible derivations. Only nodes and edges define default adjacency.",
        """surface_contract = pd.DataFrame([
    ("nodes/", "stable typed entities", True),
    ("edges/", "deduplicated assertions", True),
    ("evidence/", "source-specific support", False),
    ("metadata/", "catalog and provenance objects", False),
    ("features/", "model/context signals", False),
    ("proof/", "deterministic derivation records", False),
], columns=["surface", "purpose", "changes_adjacency"])
display(surface_contract)""",
        "A feature being canonical does not automatically authorize it for training. Its coverage, lineage, license, and leakage policy still govern use. Likewise, proof justifies a transformation but is not necessarily a model feature.",
        """catalog = parquet_catalog(KG_ROOT, billing_project=BILLING_PROJECT)
display(catalog[["layer", "path", "rows", "row_groups", "columns"]])
print("Catalog counts describe this selected root; fixture counts are illustrative only.")""",
        "Use the catalog to discover names and schemas before reading rows. Never guess a relation or embedding path when a manifest or catalog can identify it.",
    )
    cells += chapter(
        md, code,
        "Follow stable IDs, edge keys, and evidence multiplicity",
        "Canonical human genes use Ensembl `ENSG...` IDs. Symbols, HGNC, NCBI Gene, UniProt, and source-native identifiers remain aliases or provenance. An edge key represents one assertion over relation and typed endpoints; multiple evidence records may support that key without duplicating topology.",
        """root = str(KG_ROOT).rstrip("/")
genes = read_bounded_parquet(f"{root}/nodes/gene.parquet", limit=4, billing_project=BILLING_PROJECT)
edges = read_bounded_parquet(f"{root}/edges/disease_associated_gene.parquet", limit=10, billing_project=BILLING_PROJECT)
evidence = read_bounded_parquet(f"{root}/evidence/disease_associated_gene.parquet", limit=20, billing_project=BILLING_PROJECT)
display(genes[[column for column in ["id", "gene_name", "hgnc_id", "ncbi_gene_id", "uniprot_id"] if column in genes]])""",
        "Join assertions to evidence on `relation, x_id, x_type, y_id, y_type` or the validated edge key—not row position. Evidence count measures records represented, not automatically strength, independence, causality, or consensus.",
        """edge_keys = ["relation", "x_id", "x_type", "y_id", "y_type"]
joined = edges.merge(evidence, on=edge_keys, how="left", suffixes=("_assertion", "_evidence"), validate="one_to_many")
display(joined[[*edge_keys, "source_assertion", "source_evidence", "source_record_id"]].head(8))""",
        "Observed source assertions and controlled inferences must stay distinguishable in evidence or inferred-evidence surfaces. Do not relabel protein observations as RNA measurements or infer causal direction from association alone.",
    )
    cells += chapter(
        md, code,
        "Answer one bounded question and state its limits",
        "We finish by asking which fixture diseases have represented TP53 association assertions and attached evidence. The reusable helper performs a local bounded join, labels entities, and preserves evidence summaries. This is the same reasoning path to adapt for another exact stable identifier.",
        """from manage_db.public_notebooks import diseases_with_gene_evidence
if MODE == "fixture":
    answer = diseases_with_gene_evidence(KG_ROOT, "ENSG00000141510", limit=20)
    display(answer)
else:
    answer = pd.DataFrame()
    print("For live work, first stage only reviewed bounded objects; the local DuckDB helper never scans the full remote KG.")""",
        "What this means: the selected graph represents source-backed associations. What this does not mean: TP53 causes each disease, altering TP53 will treat it, evidence rows are independent, or omitted diseases are absent. Scores remain source-specific rather than calibrated clinical probabilities.",
        """summary = {
    "question": "Which represented diseases have TP53 association evidence?",
    "rows_returned": len(answer),
    "mode": MODE,
    "bounded": True,
    "next_notebook": "02_nodes_features_and_embeddings.ipynb",
}
print(summary)""",
        "Proceed to Notebook 02 to inspect versioned embeddings, or Notebook 03 to deepen the evidence join. Preserve the exact-ID, bounded-read, and interpretation-boundary habits throughout the course.",
    )
    notebooks["01_data_model_and_use_cases.ipynb"] = cells

    cells = [
        md("""# 02 — Embeddings as an inspectable data product

Embeddings are versioned feature artifacts, not magic coordinates. This lesson discovers accepted immutable releases from a manifest, loads one bounded shard, keeps vectors aligned with IDs, computes cosine diagnostics, and draws colorblind-safe projections. Fixture vectors are synthetic and illustrative; proximity is not functional equivalence."""),
        setup(),
    ]
    cells += chapter(
        md, code,
        "Discover accepted immutable releases instead of guessing paths",
        "A consumable embedding release declares state, immutability, modality, model, source hashes, coverage, license, and shard paths. Fixture mode provides a synthetic accepted manifest. Live mode requires `JOUVENCE_EMBEDDING_MANIFEST_URI` pointing to an explicitly reviewed manifest; there is no mutable latest-path default.",
        """from manage_db.public_notebooks import discover_embedding_releases
if MODE == "fixture":
    EMBEDDING_MANIFEST = Path(KG_ROOT) / "features" / "embeddings" / "manifest.json"
else:
    EMBEDDING_MANIFEST = os.environ.get("JOUVENCE_EMBEDDING_MANIFEST_URI")
    if not EMBEDDING_MANIFEST:
        raise RuntimeError("Set JOUVENCE_EMBEDDING_MANIFEST_URI to an accepted immutable release manifest")
releases = discover_embedding_releases(EMBEDDING_MANIFEST, billing_project=BILLING_PROJECT)
display(releases)""",
        "Discovery filters out staged, rejected, or mutable artifacts by default. A path being readable does not make its science accepted. In particular, no rejected or staged genomic-gene candidate is presented as canonical here.",
        """required_release_fields = {"release_id", "state", "immutable", "modality", "license", "coverage", "shard_uri"}
assert required_release_fields.issubset(releases.columns)
assert releases["state"].eq("accepted").all() and releases["immutable"].eq(True).all()
print("accepted immutable shards:", len(releases))""",
        "Before loading vectors, inspect the release state, immutable identity, encoder revision, preprocessing, license, coverage denominator, and task-specific leakage policy.",
    )
    cells += chapter(
        md, code,
        "Choose modality for the scientific question",
        "Gene text, genomic-gene sequence, transcript nucleotide, protein sequence, molecule structure, and ontology/text embeddings encode different source surfaces. Text captures documentation semantics; sequence captures molecular patterns; structure captures chemistry. Keep modalities separate and fuse downstream only with an explicit policy.",
        """modality_guide = pd.DataFrame([
    ("gene text", "gene summaries and ontology-linked prose", "annotation circularity"),
    ("genomic gene", "genomic sequence context", "length/species/build effects"),
    ("transcript nucleotide", "isoform cDNA or UTR", "isoform selection"),
    ("protein sequence", "amino-acid sequence", "paralogy and domain composition"),
    ("molecule structure", "SMILES/graph/fingerprint", "stereochemistry and salts"),
    ("ontology/text", "labels, definitions, hierarchy prose", "label leakage"),
], columns=["modality", "signal", "risk"])
display(modality_guide)""",
        "Text similarity and sequence modality similarity are not interchangeable. Two genes can share textual disease annotations without sequence homology, or share domains without equivalent biological roles. License and source-release compatibility may also differ by modality.",
        """selected = releases.query("modality == 'text'").copy()
if selected.empty:
    raise RuntimeError("No accepted immutable text release is available in the selected manifest")
release = selected.iloc[0]
print(release[["release_id", "modality", "license", "coverage", "shard_uri"]].to_dict())""",
        "State the modality before interpreting a neighbor list. Do not call a generic vector simply a gene embedding when the source is specifically text, sequence, structure, or an ontology description.",
    )
    cells += chapter(
        md, code,
        "Load a bounded shard and preserve row alignment",
        "The loader caps rows and validates required columns. Matrix extraction checks dimensions and finite values, while returning metadata in exactly the same row order. Stable ID lookup then maps biological identifiers to matrix positions without positional guessing.",
        """from manage_db.public_notebooks import (
    extract_embedding_matrix,
    load_bounded_embedding_sample,
    lookup_embedding_id,
)
sample = load_bounded_embedding_sample(release["shard_uri"], limit=100, billing_project=BILLING_PROJECT)
matrix, embedding_metadata = extract_embedding_matrix(sample)
print({"rows": matrix.shape[0], "dimensions": matrix.shape[1], "metadata_rows": len(embedding_metadata)})
display(embedding_metadata.head())""",
        "Nonfinite vectors fail closed because they poison distances and projections. Zero vectors remain detectable through their norm and should be excluded or handled explicitly; they must not silently masquerade as missing source-backed signal.",
        """query_id = "ENSG00000012048"
query_position = lookup_embedding_id(embedding_metadata, query_id)
assert embedding_metadata.iloc[query_position]["node_id"] == query_id
print({"query_id": query_id, "row_position": query_position, "vector": matrix[query_position].round(3).tolist()})""",
        "Always carry aligned metadata—ID, node type, model, and release—with the matrix. A bare NumPy array cannot support auditable biological interpretation.",
    )
    cells += chapter(
        md, code,
        "Join labels and diagnose coverage, missingness, and norms",
        "Coverage is defined against a named population, not against rows that happened to load. We join stable IDs to fixture labels and compare represented IDs with the selected node tables. Vector norms reveal zero rows and scale outliers before cosine or projection analysis.",
        """node_frames = []
for node_type in ("gene", "disease", "molecule"):
    frame = read_bounded_parquet(f"{str(KG_ROOT).rstrip('/')}/nodes/{node_type}.parquet", limit=100, billing_project=BILLING_PROJECT)
    frame = frame[["id", "name"]].assign(node_type=node_type)
    node_frames.append(frame)
labels = pd.concat(node_frames, ignore_index=True).rename(columns={"id": "node_id", "name": "label"})
embedding_metadata = embedding_metadata.merge(labels, on=["node_id", "node_type"], how="left", validate="one_to_one")
embedding_metadata["vector_norm"] = __import__("numpy").linalg.norm(matrix, axis=1)
display(embedding_metadata[["node_id", "node_type", "label", "vector_norm"]])""",
        "Missing labels indicate a failed or incomplete identity join, while missing vectors indicate coverage gaps. Neither should be repaired with fabricated biological vectors. A model-side fallback may support execution only when it is declared as fallback rather than source-backed coverage.",
        """import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(7, 3.5))
ax.bar(embedding_metadata["node_id"], embedding_metadata["vector_norm"], color="#0072B2")
ax.set(title="Fixture vector-norm diagnostic", ylabel="L2 norm", xlabel="stable entity ID")
ax.tick_params(axis="x", rotation=75)
fig.tight_layout()
assert len(ax.patches) == len(embedding_metadata)
plt.show()""",
        "The plot must have one bar per aligned row. Fixture norms are synthetic diagnostics, not evidence that one entity is biologically stronger or better represented.",
    )
    cells += chapter(
        md, code,
        "Compute pair similarity and nearest neighbors",
        "Cosine compares vector direction after normalization. It is useful for retrieval within one compatible release, but it ignores magnitude and inherits encoder, corpus, preprocessing, and coverage biases. We inspect both one pair and the full bounded similarity distribution.",
        """from manage_db.public_notebooks import cosine_neighbors, pairwise_cosine
similarity = pairwise_cosine(matrix)
brca1 = lookup_embedding_id(embedding_metadata, "ENSG00000012048")
brca2 = lookup_embedding_id(embedding_metadata, "ENSG00000139618")
print("BRCA1–BRCA2 cosine:", round(float(similarity[brca1, brca2]), 4))
neighbors = cosine_neighbors(matrix, embedding_metadata, "ENSG00000012048", limit=5)
display(neighbors[["node_id", "node_type", "label", "cosine_similarity"]])""",
        "High proximity is not functional equivalence, causal interaction, interchangeability, or treatment evidence. It means only that this encoder placed the selected source payloads near one another under cosine distance.",
        """import numpy as np
upper = similarity[np.triu_indices_from(similarity, k=1)]
fig, ax = plt.subplots(figsize=(6, 3.5))
ax.hist(upper, bins=min(10, max(3, len(upper) // 3)), color="#009E73", edgecolor="white")
ax.set(title="Bounded pairwise cosine distribution", xlabel="cosine similarity", ylabel="pair count")
assert len(ax.patches) > 0 and np.isfinite(upper).all()
fig.tight_layout()
plt.show()""",
        "Inspect the distribution before choosing a neighbor cutoff. Small fixture distributions are illustrative and should never be used as production thresholds.",
    )
    cells += chapter(
        md, code,
        "Project vectors with UMAP or a deterministic PCA fallback",
        "Two-dimensional projections are lossy visual summaries. The helper uses UMAP when installed and otherwise a deterministic documented PCA fallback. We use a colorblind-safe palette, label axes and method, and annotate a few stable IDs rather than implying exact cluster boundaries.",
        """from manage_db.public_notebooks import project_embedding_matrix
coordinates, projection_method = project_embedding_matrix(matrix, method="auto", random_state=17)
projection = embedding_metadata.copy()
projection[["x", "y"]] = coordinates
print({"projection": projection_method, "shape": coordinates.shape, "fallback": "pca" if projection_method == "pca" else None})""",
        "UMAP preserves selected local neighborhoods stochastically; PCA preserves directions of greatest linear variance. Their axes are not biological dimensions. The PCA fallback makes clean environments executable and reproducible without pretending the methods are equivalent.",
        """palette = {"gene": "#0072B2", "disease": "#D55E00", "molecule": "#009E73"}
fig, ax = plt.subplots(figsize=(7, 5))
for node_type, group in projection.groupby("node_type", sort=True):
    ax.scatter(group["x"], group["y"], label=node_type, color=palette[node_type], s=60, alpha=0.85)
annotation_offsets = {
    "ENSG00000139618": (-38, 8),
    "ENSG00000012048": (5, -13),
    "ENSG00000141510": (5, 5),
    "ENSG00000146648": (5, -11),
}
for row in projection.head(4).itertuples():
    ax.annotate(
        row.label or row.node_id,
        (row.x, row.y),
        xytext=annotation_offsets.get(row.node_id, (5, 5)),
        textcoords="offset points",
        fontsize=8,
    )
ax.set(title=f"Synthetic fixture embedding — {projection_method.upper()}", xlabel="component 1", ylabel="component 2")
ax.legend(title="entity type")
ax.margins(x=0.15, y=0.15)
assert len(ax.collections) == projection["node_type"].nunique()
fig.tight_layout()
plt.show()""",
        "For larger interactive work, replace annotations with hover labels while retaining stable IDs and release metadata. Continue to Notebook 03 for source evidence; never treat visual clusters as validated function classes.",
    )
    notebooks["02_nodes_features_and_embeddings.ipynb"] = cells

    cells = [
        md("""# 03 — Relations, evidence, provenance, and biological questions

This lesson separates graph assertions from their source records, performs bounded joins by typed edge identity, and asks a concrete TP53 question. Every result is interpreted as represented provenance-aware association—not causality, efficacy, safety, or a completeness claim."""),
        setup(),
    ]
    cells += chapter(md, code, "Read assertions separately from evidence", "An edge table contains one deduplicated assertion per typed endpoint pair and relation. Its evidence table contains one or more source records with predicates, scores, studies, assays, releases, and provenance. The two surfaces have different row identities and cardinalities.", """root = str(KG_ROOT).rstrip("/")
edges = read_bounded_parquet(f"{root}/edges/disease_associated_gene.parquet", limit=20, billing_project=BILLING_PROJECT)
evidence = read_bounded_parquet(f"{root}/evidence/disease_associated_gene.parquet", limit=50, billing_project=BILLING_PROJECT)
print({"assertions": len(edges), "evidence_rows": len(evidence)})
display(edges.head())""", "A relation name should express the accepted source-native biological assertion. Assay, source predicate, score, and context refine evidence; they should not proliferate relation names or silently redefine endpoint meaning.", """evidence_columns = [column for column in ["edge_key", "source", "source_dataset", "source_record_id", "predicate", "evidence_score", "release"] if column in evidence]
display(evidence[evidence_columns].head(10))""", "Compare row identities before joining. Evidence multiplicity can exceed assertion count without creating duplicate topology.")
    cells += chapter(md, code, "Construct and validate typed edge identity", "The portable join key is relation plus both stable IDs and both endpoint types. Some tables also materialize a deterministic edge key. Row order is never a valid join contract because writers, filters, and Parquet row groups may reorder data.", """EDGE_IDENTITY = ["relation", "x_id", "x_type", "y_id", "y_type"]
assert set(EDGE_IDENTITY).issubset(edges) and set(EDGE_IDENTITY).issubset(evidence)
print(edges[EDGE_IDENTITY].drop_duplicates().to_string(index=False))""", "Typed endpoints prevent an identifier string from being interpreted in the wrong namespace. Canonical human gene endpoints use ENSG IDs; aliases remain lookup or provenance fields rather than parallel canonical nodes.", """assert not edges.duplicated(EDGE_IDENTITY).any()
multiplicity = evidence.groupby(EDGE_IDENTITY, dropna=False).size().rename("evidence_rows").reset_index()
display(multiplicity.sort_values("evidence_rows", ascending=False))""", "A duplicate edge identity is a topology error; multiple evidence rows for one identity are expected when distinct source records support the assertion.")
    cells += chapter(md, code, "Join bounded prefixes without claiming completeness", "The reusable helper reads selected columns from bounded prefixes of one edge and evidence object and validates a one-to-many merge. It is designed for inspection, not full evidence parity or absence testing.", """from manage_db.public_notebooks import bounded_edge_evidence_join
joined = bounded_edge_evidence_join(KG_ROOT, "disease_associated_gene", edge_limit=10, evidence_limit=50, billing_project=BILLING_PROJECT)
display(joined.head(10))""", "A bounded join may omit evidence that lies outside the selected prefix. Therefore zero joined rows means only that the bounded windows did not overlap; it does not prove that canonical evidence is absent.", """join_summary = joined.groupby("source_assertion", dropna=False).agg(assertion_evidence_pairs=("source_record_id", "size"), evidence_sources=("source_evidence", "nunique"))
display(join_summary)""", "Use full parity audits only in reviewed worker workflows. Public notebooks remain laptop-safe and never expand scope to settle an absence question.")
    cells += chapter(md, code, "Ask a bounded TP53–disease question", "We query the fixture for diseases attached to TP53 (`ENSG00000141510`), join disease labels, and summarize represented evidence. Exact stable IDs make the question reproducible despite ambiguous gene symbols.", """from manage_db.public_notebooks import diseases_with_gene_evidence
if MODE == "fixture":
    answer = diseases_with_gene_evidence(KG_ROOT, "ENSG00000141510", limit=20)
else:
    answer = pd.DataFrame()
    print("Live helper requires an explicitly staged bounded local subset.")
display(answer)""", "The returned source and score describe records in this selected graph. They are not calibrated probabilities of disease causation, target validity, clinical success, or patient benefit.", """if not answer.empty:
    answer_plot = answer.sort_values("max_evidence_score")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.barh(answer_plot["disease_name"], answer_plot["max_evidence_score"], color="#0072B2")
    ax.set(xlabel="maximum source-specific fixture score", title="Represented TP53 associations")
    fig.tight_layout(); plt.show()""", "Treat the chart as a transparent view of selected source scores. Do not rank therapies or patients from this association plot.")
    cells += chapter(md, code, "Distinguish observed assertions from controlled inference", "Observed and inferred edges may share a broad endpoint relation when they assert the same biology, but provenance must preserve support mode and derivation. An inferred gene-expression assertion from a protein-product observation must not be mislabeled as an RNA measurement.", """semantics = pd.DataFrame([
    ("observed", "source record directly asserts relation", "evidence/"),
    ("inferred", "reviewed mapping or rule derives relation", "evidence_inferred/ or proof/"),
    ("context", "useful signal without accepted topology", "features/ or metadata/"),
], columns=["status", "meaning", "surface"])
display(semantics)""", "Inference must fail closed when endpoint mapping, direction, sign, or context is unknown or conflicting. Coordinate overlap, co-mention, or generic association alone does not establish regulation or causality.", """forbidden_inferences = [
    "association score → causal direction",
    "RNA expression → observed protein expression",
    "coordinate overlap → observed regulation",
    "unknown pair → biological negative",
]
print("Do not infer:\\n- " + "\\n- ".join(forbidden_inferences))""", "When interpretation depends on an inference, locate its evidence or proof policy before using it as topology or supervision.")
    cells += chapter(md, code, "Record provenance and interpretation boundaries", "A reproducible answer records mode, root, relation, exact IDs, row limits, source releases, and helper version. This context allows another scientist to reproduce the bounded inspection and understand what was not queried.", """provenance_record = {
    "mode": MODE,
    "root": str(KG_ROOT),
    "relation": "disease_associated_gene",
    "query_gene": "ENSG00000141510",
    "edge_limit": 10,
    "evidence_limit": 50,
    "read_only": True,
}
print(json.dumps(provenance_record, indent=2))""", "What this means: selected source records support represented graph assertions. What this does not mean: evidence sources are independent, coverage is complete, the association is causal, or intervention is effective and safe.", """print({
    "next_for_catalog_queries": "04_lamindb_equivalent_queries.ipynb",
    "next_for_graph_tensors": "05_sampled_pyg_heterodata.ipynb",
    "status_vocabulary": "bounded fixture inspection",
})""", "Use Notebook 04 to compare the canonical Parquet data plane with the currently partial LaminDB catalog mirror.")
    notebooks["03_relations_evidence_and_questions.ipynb"] = cells

    cells = [
        md("""# 04 — Canonical Parquet and equivalent LaminDB queries

Canonical Parquet is Jouvence's working data plane. LaminDB is a queryable registry/catalog mirror at the exact instance `jkobject/jouvencekb`, but its ingestion is currently partial and external access is blocked pending repair and grants. This notebook remains useful in fixture mode and makes live Lamin access a separate read-only opt-in."""),
        setup(),
    ]
    cells += chapter(md, code, "Separate the canonical data plane from the catalog mirror", "Parquet under the reviewed canonical root holds node, edge, evidence, metadata, feature, and optional proof objects. LaminDB indexes exact entities and generic edge/evidence records for discovery. It does not redefine canonical truth or make incomplete ingestion equivalent to absence.", """comparison = pd.DataFrame([
    ("canonical Parquet", "reviewed object paths", "working data plane", "bounded named reads"),
    ("LaminDB", "jkobject/jouvencekb", "partial catalog mirror", "exact-ID/filter queries"),
], columns=["surface", "identity", "role", "public pattern"])
display(comparison)""", "A Lamin row should correspond to canonical identity and provenance, but current coverage is partial. Parquet remains the fallback for truth when a Lamin query is empty or access is unavailable.", """catalog = parquet_catalog(KG_ROOT, billing_project=BILLING_PROJECT)
display(catalog.groupby("layer").agg(tables=("path", "count"), rows_in_selected_root=("rows", "sum")))""", "Fixture catalog totals are synthetic. Live catalog discovery should use committed inventories or named objects rather than an all-relation remote scan.")
    cells += chapter(md, code, "Configure only the exact read-only Lamin instance", "The accepted instance slug is `jkobject/jouvencekb`. Live access requires a caller's own LaminHub account and an explicit `JOUVENCE_LAMIN_LIVE=1`; the helper verifies the connected slug before querying and exposes no create, update, delete, or sync operations.", """from manage_db.public_notebooks import LAMIN_INSTANCE
LIVE_LAMIN = os.environ.get("JOUVENCE_LAMIN_LIVE", "0") == "1"
print({"required_instance": LAMIN_INSTANCE, "live_opt_in": LIVE_LAMIN, "write_capability": False})""", "At present, a fresh external collaborator is blocked because authenticated instance/storage access is not yet reproducible. `lamin login` alone is not proof that the remote database object and permissions work.", """future_read_only_setup = [
    "uv run lamin login",
    "uv run lamin connect jkobject/jouvencekb",
    "export JOUVENCE_LAMIN_LIVE=1",
]
print("Run only after the maintainer confirms repaired read access:\\n" + "\\n".join(future_read_only_setup))""", "Never connect to a similarly named instance, run `lamin disconnect` as a workaround, re-upload a database, or write registries from this public course.")
    cells += chapter(md, code, "Perform the canonical Parquet exact-ID lookup", "We first answer through the data plane. The local fixture helper joins TP53 association assertions, disease labels, and evidence. This result is the reference for understanding the equivalent registry query shape.", """from manage_db.public_notebooks import diseases_with_gene_evidence
if MODE == "fixture":
    parquet_answer = diseases_with_gene_evidence(KG_ROOT, "ENSG00000141510", limit=20)
else:
    parquet_answer = pd.DataFrame()
    print("Use an explicitly staged bounded subset for the local exact-ID helper.")
display(parquet_answer)""", "The query is exact-ID and bounded. It does not search aliases, fuzzy labels, or every relation. Expand the biological question deliberately rather than widening the storage scan.", """parquet_contract = {
    "gene_id": "ENSG00000141510",
    "relation": "disease_associated_gene",
    "limit": 20,
    "canonical_truth": True if MODE == "live" else "synthetic fixture",
}
print(parquet_contract)""", "Record the exact relation and identifier so an equivalent Lamin query can be compared semantically rather than only by row count.")
    cells += chapter(md, code, "Express equivalent node, edge, and evidence filters in LaminDB", "LaminDB uses typed node registries and generic KG edge/evidence registries. The public helpers constrain exact node IDs, one relation, optional typed endpoints, deterministic ordering, and a row limit.", """from manage_db.public_notebooks import query_lamindb_edges, query_lamindb_evidence, query_lamindb_node
if LIVE_LAMIN:
    lamin_node = query_lamindb_node("gene", "ENSG00000141510", limit=1)
    lamin_edges = query_lamindb_edges(relation="disease_associated_gene", x_id="ENSG00000141510", limit=20)
    lamin_evidence = query_lamindb_evidence(relation="disease_associated_gene", x_id="ENSG00000141510", limit=50)
else:
    lamin_node = lamin_edges = lamin_evidence = pd.DataFrame()
    print("Lamin query skipped; fixture mode needs no LaminHub account.")""", "The node lookup validates the appropriate stable-ID field for each registry. Edge and evidence filters retain relation and endpoints. They are equivalent in scientific intent to the Parquet question, not necessarily in current row coverage.", """print({"node_rows": len(lamin_node), "edge_rows": len(lamin_edges), "evidence_rows": len(lamin_evidence)})
if LIVE_LAMIN:
    display(lamin_node); display(lamin_edges.head()); display(lamin_evidence.head())""", "An empty result is a query outcome, not a biological conclusion. Check mirror coverage and canonical Parquet before asserting absence.")
    cells += chapter(md, code, "Compare identities while tolerating partial coverage", "When both surfaces are available, compare relation and typed endpoint identities—not database primary keys or row order. Differences should be classified as expected partial ingestion, query mismatch, stale mirror, or a true integrity problem requiring review.", """identity_columns = ["relation", "x_id", "x_type", "y_id", "y_type"]
comparison_plan = {
    "keys": identity_columns,
    "expected_current_state": "partial LaminDB coverage",
    "absence_rule": "Lamin-empty never proves canonical absence",
}
print(json.dumps(comparison_plan, indent=2))""", "Do not hide mismatch by filling synthetic rows or promoting physical counts as accepted coverage. A complete parity claim requires a separately reviewed exact-ID audit with mismatch zero.", """if LIVE_LAMIN and not lamin_edges.empty and not parquet_answer.empty:
    lamin_disease_ids = set(lamin_edges["y_id"].astype(str))
    parquet_disease_ids = set(parquet_answer["disease_id"].astype(str))
    print({"only_parquet": sorted(parquet_disease_ids - lamin_disease_ids), "only_lamin": sorted(lamin_disease_ids - parquet_disease_ids)})
else:
    print("Cross-surface parity not claimed in this environment.")""", "Label the outcome precisely: fixture demonstration, bounded live lookup, partial mirror result, or blocked access—never simply “database complete.”")
    cells += chapter(md, code, "Troubleshoot safely and choose the truthful fallback", "Separate LaminHub authentication, instance authorization, storage/database-object availability, schema version, and mirror coverage. A failure at one layer should not trigger writes, a new instance, or a broad canonical scan.", """lamin_troubleshooting = pd.DataFrame([
    ("login required", "authenticate with caller account", "no shared token"),
    ("instance denied", "request read access", "do not change slug"),
    ("database object missing", "maintainer repair required", "do not re-upload"),
    ("empty query", "compare bounded canonical Parquet", "mirror may be partial"),
    ("schema mismatch", "report versions and query", "do not mutate registries"),
], columns=["symptom", "next check", "safety boundary"])
display(lamin_troubleshooting)""", "The truthful fallback is canonical Parquet through bounded named reads. Fixture mode remains the universally executable teaching path while live external Lamin access is blocked.", """print({
    "fallback": "canonical Parquet",
    "current_lamin_status": "partial and external-blocked",
    "next_notebook": "05_sampled_pyg_heterodata.ipynb",
    "canonical_writes": False,
})""", "Continue to Notebook 05 to see how bounded Parquet entities and assertions become a typed PyG sample without claiming a production/full export.")
    notebooks["04_lamindb_equivalent_queries.ipynb"] = cells

    cells = [
        md("""# 05 — Build and inspect a sampled PyG HeteroData

This lesson converts the deterministic fixture into a bounded heterogeneous graph using the repository's tested exporter. It inspects node maps, relation-wise edge indices, reverse-edge identity, feature coverage, and declared fallbacks. The artifact is an executable sample—not a production/full KG materialization or model-quality result."""),
        setup(pyg=True),
    ]
    cells += chapter(md, code, "Map the KG contract to PyG concepts", "Each node type owns an index space and feature matrix. Each typed relation `(source_type, relation, target_type)` owns a separate edge index. Stable-ID node maps and edge-row maps must travel with tensors so positions remain auditable.", """pyg_contract = pd.DataFrame([
    ("nodes/<type>", "data[node_type].x", "node_id ↔ node_index"),
    ("edges/<relation>", "data[(src, rel, dst)].edge_index", "edge_key ↔ edge_pos"),
    ("reverse relation", "separate edge type", "forward_edge_pos"),
    ("features/", "x or sidecar", "coverage/fallback mask"),
], columns=["KG surface", "PyG representation", "identity sidecar"])
display(pyg_contract)""", "A monolithic `HeteroData` pickle is appropriate only for bounded pilots. Production design is relation-wise, sidecar-first, memory-mapped, and staged to worker-local storage.", """print({"sample_node_types": ["gene", "disease", "molecule"], "sample_relations": ["disease_associated_gene", "molecule_targets_gene"], "bounded": True})""", "Before building, name the selected node types, relations, limits, and feature policy. Selection is part of the scientific artifact.")
    cells += chapter(md, code, "Build the deterministic bounded export", "The helper delegates to the tested exporter with strict endpoint validation, reverse edges, capped nodes and assertions, an explicit build name, and a deterministic fallback seed. Live full-KG export is refused in this laptop course.", """from manage_db.public_notebooks import build_sampled_pyg
if MODE != "fixture":
    raise RuntimeError("Use only an explicitly staged bounded local subset; never build the full KG on a laptop")
PYG_ROOT = CACHE / "pyg-course-sample"
result = build_sampled_pyg(KG_ROOT, PYG_ROOT, max_nodes_per_type=100, max_edges_per_relation=200)
print({"node_counts": result.node_counts, "edge_counts": result.edge_counts})""", "A successful export proves that the selected schemas and endpoints can produce tensors. It does not prove full-scale memory behavior, training stability, useful representations, or biomedical validity.", """manifest = json.loads((PYG_ROOT / "manifest.json").read_text())
print(json.dumps({key: manifest.get(key) for key in ["build_name", "node_counts", "edge_counts", "include_reverse_edges"]}, indent=2))""", "Keep the manifest with every exported sample. Counts without source identity, limits, and feature policy are not a reproducible graph artifact.")
    cells += chapter(md, code, "Load HeteroData and inspect node maps", "The loader reconstructs the bounded tensor object. Node maps connect tensor positions back to biological IDs; losing them makes retrieval, evaluation, and error analysis unreliable.", """from manage_db.public_notebooks import load_sampled_pyg
data = load_sampled_pyg(PYG_ROOT)
print(data)
print("node types:", data.node_types)""", "Node index zero in one type is unrelated to index zero in another type. Every relation edge index is interpreted in its source and target type-specific spaces.", """for node_type in data.node_types:
    store = data[node_type]
    print(node_type, {"nodes": store.num_nodes, "x_shape": tuple(store.x.shape), "finite": bool(store.x.isfinite().all())})""", "Verify node counts, feature dimensions, and finite values before running any model. Then use persisted maps—not DataFrame row assumptions—to recover stable IDs.")
    cells += chapter(md, code, "Inspect relation-wise edge indices and reverse identity", "Each relation has a `2 × E` integer edge index. Reverse edges support bidirectional message passing but reuse forward biological identity; they do not create new evidence or a second biological assertion.", """for edge_type in data.edge_types:
    edge_index = data[edge_type].edge_index
    print(edge_type, {"shape": tuple(edge_index.shape), "min": int(edge_index.min()), "max": int(edge_index.max())})""", "The same relation name can only be interpreted with its source and target types. Bounds must be checked against the corresponding node counts, not a global node total.", """for src, relation, dst in data.edge_types:
    edge_index = data[(src, relation, dst)].edge_index
    assert edge_index.shape[0] == 2
    assert int(edge_index[0].max()) < data[src].num_nodes
    assert int(edge_index[1].max()) < data[dst].num_nodes
print("all sampled edge indices respect typed node bounds")""", "A reverse relation is a computational view. Do not attach independent source provenance or count it as additional canonical topology.")
    cells += chapter(md, code, "Audit feature coverage and declared fallbacks", "Each node type should distinguish source-backed available, absent, deferred, and fallback states. Joined source vectors remain source-backed only for covered rows; a deterministic or learned fallback enables execution but is not biological evidence.", """metadata_path = PYG_ROOT / "heterodata" / "full_graph.metadata.json"
export_metadata = json.loads(metadata_path.read_text())
feature_policy = export_metadata.get("node_embedding_policy", {})
print(json.dumps(feature_policy, indent=2))""", "Availability does not mean complete coverage. Zero-filling can hide absence and change geometry, so missing rows need an explicit coverage or fallback mask and a manifest policy.", """coverage_rows = []
for node_type in data.node_types:
    store = data[node_type]
    coverage_rows.append({"node_type": node_type, "rows": store.num_nodes, "feature_dim": store.x.shape[1], "all_finite": bool(store.x.isfinite().all())})
display(pd.DataFrame(coverage_rows))""", "When adapting this sample, report source-backed row coverage separately from fallback row coverage. Never describe the fallback seed as a foundation embedding.")
    cells += chapter(md, code, "Run structural invariants and state the boundary", "A trustworthy sample has nonempty selected stores, finite features, in-range edge indices, deterministic counts, and manifests/maps that remain beside tensors. These checks establish software integrity for this bounded artifact.", """assert set(data.node_types) == {"gene", "disease", "molecule"}
assert all(data[node_type].num_nodes > 0 for node_type in data.node_types)
assert all(data[edge_type].edge_index.shape[1] > 0 for edge_type in data.edge_types)
print("bounded HeteroData structural checks: PASS")""", "What this means: Jouvence's typed fixture can be exported and loaded through the real PyG pipeline. What this does not mean: a full production export exists, all node features are source-backed, training is stable, or a prediction is valid.", """print({
    "artifact": str(PYG_ROOT),
    "status": "bounded exporter smoke passed",
    "production_full_done": False,
    "next_notebook": "06_sampled_ml_use_cases.ipynb",
})""", "Proceed to Notebook 06 for retrieval, neighborhood inspection, split design, negative sampling, metrics, and error analysis on this same honest smoke boundary.")
    notebooks["05_sampled_pyg_heterodata.ipynb"] = cells

    cells = [
        md("""# 06 — Retrieval, neighborhoods, and a link-prediction smoke

The final lesson combines three workflows on deterministic fixture data: embedding retrieval, relation-neighborhood inspection, and a tiny PyG link-prediction run. The emphasis is experimental design—split leakage, unknown negatives, metrics, and error analysis—not benchmark performance or therapeutic recommendation."""),
        setup(pyg=True),
    ]
    cells += chapter(md, code, "Define the scientific task before selecting data", "A useful workflow names the target relation, prediction unit, intended generalization regime, allowed input features, temporal/source cutoff, and evaluation population. Storage convenience should not decide the split.", """task_card = {
    "target_relation": "disease_associated_gene",
    "prediction_unit": "typed gene–disease pair",
    "generalization": "software smoke on fixture only",
    "input_policy": "fixture features with declared fallback",
    "forbidden_claim": "clinical target recommendation",
}
print(json.dumps(task_card, indent=2))""", "A random edge split often leaves the same entities, near-duplicate evidence, and ontology neighbors in train and test. Zero-shot disease or prospective evaluation requires entity-, time-, or source-aware splitting.", """split_options = pd.DataFrame([
    ("random edge", "pipeline smoke", "shared entities/evidence leakage"),
    ("held-out disease", "zero-shot disease", "ontology/text leakage"),
    ("temporal", "prospective claim", "post-cutoff metadata leakage"),
    ("source-held-out", "cross-source robustness", "duplicate assertions across sources"),
], columns=["split", "question", "principal risk"])
display(split_options)""", "Choose a split that matches the deployment claim, then audit every embedding and metadata field against that split.")
    cells += chapter(md, code, "Retrieve representation neighbors for inspection", "Retrieval surfaces entities whose vectors are close under one accepted modality. It is useful for candidate inspection and error analysis, but it is not itself link prediction and does not establish a biological relation.", """from manage_db.public_notebooks import nearest_embeddings
embedding_uri = Path(KG_ROOT) / "features" / "embeddings" / "text" / "fixture.parquet"
neighbors = nearest_embeddings(embedding_uri, "ENSG00000012048", limit=5)
display(neighbors)""", "The neighbor list inherits the synthetic fixture encoder. Proximity is not functional equivalence, interaction, causality, or therapeutic interchangeability; compare modalities and inspect source payloads before interpretation.", """print({"query": "ENSG00000012048", "retrieved": len(neighbors), "metric": "cosine", "modality": "synthetic text fixture"})""", "Use Notebook 02's norm, distribution, coverage, and projection diagnostics before relying on a retrieval threshold.")
    cells += chapter(md, code, "Inspect typed neighborhoods without inflating evidence", "A relation neighborhood summarizes represented adjacency. Degree can identify hubs or sampling artifacts, while evidence must be inspected separately so many source records do not become duplicate graph edges.", """edge_uri = Path(KG_ROOT) / "edges" / "disease_associated_gene.parquet"
edge_sample = read_bounded_parquet(edge_uri, limit=100)
degree = edge_sample.groupby("x_id").size().rename("sampled_disease_degree").sort_values(ascending=False)
display(degree)""", "Degree in this fixture is a property of the tiny selected graph. In live bounded prefixes it is not global degree, and in either mode it does not measure causal importance or targetability.", """evidence_uri = Path(KG_ROOT) / "evidence" / "disease_associated_gene.parquet"
evidence_sample = read_bounded_parquet(evidence_uri, limit=100)
evidence_counts = evidence_sample.groupby("x_id").size().rename("sampled_evidence_rows")
display(pd.concat([degree, evidence_counts], axis=1).fillna(0))""", "Keep adjacency degree and evidence multiplicity in separate columns and interpretations. Neither is a clinical ranking.")
    cells += chapter(md, code, "Build the sample and run deterministic link prediction", "The repository smoke creates a bounded PyG export, deterministic train/validation/test partitions, sampled unknown pairs, and a tiny model run. Fixed seeds make software behavior repeatable; they do not make fixture metrics scientifically meaningful.", """from manage_db.public_notebooks import build_sampled_pyg, run_sampled_ml
if MODE != "fixture":
    raise RuntimeError("Train only on an explicitly staged bounded subset with a reviewed leakage policy")
PYG_ROOT = CACHE / "pyg-ml-course-sample"
build_sampled_pyg(KG_ROOT, PYG_ROOT, max_nodes_per_type=100, max_edges_per_relation=200)
smoke = run_sampled_ml(PYG_ROOT, seed=13)
print({"status": smoke["status"], "split_counts": smoke["split_counts"]})""", "Negative samples are unobserved or unknown pairs under the selected graph, not proven biological negatives. False-negative contamination is especially likely in incomplete biomedical KGs.", """metrics = pd.Series(smoke["metrics"], name="value").to_frame()
display(metrics)
print(json.dumps(smoke["validation"], indent=2))""", "A two-epoch fixture result is only a runtime smoke. Do not compare its values with publications, call it model validation, or use it for drug-repurposing decisions.")
    cells += chapter(md, code, "Match metrics to imbalance and decision costs", "AUROC can look optimistic under extreme class imbalance; average precision exposes positive retrieval quality; ranking metrics such as Hits@K and MRR require a documented candidate set and filtering policy; calibration matters when scores are interpreted probabilistically.", """metric_guide = pd.DataFrame([
    ("AUROC", "pair ordering", "can hide low precision under imbalance"),
    ("average precision", "positive retrieval", "depends on prevalence/candidate set"),
    ("Hits@K / MRR", "ranking", "requires filtered candidate protocol"),
    ("calibration", "probability-like decisions", "needs representative held-out data"),
], columns=["metric", "use", "caveat"])
display(metric_guide)""", "No single metric validates biomedical utility. Report confidence intervals across seeds or splits, baselines, candidate denominators, and decision-relevant error costs for any real experiment.", """reported_boundary = {
    "epochs": 2,
    "fixture": True,
    "benchmark": False,
    "biological_validation": False,
    "therapeutic_recommendation": False,
}
print(reported_boundary)""", "For this course, the only accepted conclusion is that the bounded code path executes and returns finite structured outputs.")
    cells += chapter(md, code, "Perform error analysis and close the course honestly", "Error analysis joins high-scoring mistakes back to stable IDs, node labels, relation evidence, feature coverage, and split provenance. Look for hubs, duplicates, source overlap, missing features, ontology leakage, and false-negative candidates before changing the model.", """error_checklist = [
    "map tensor positions back to stable IDs",
    "inspect source evidence and release cutoff",
    "check feature coverage and fallback masks",
    "look for duplicate or near-duplicate entities",
    "review unknown negatives as possible false negatives",
    "stratify by node degree and modality coverage",
]
print("Error-analysis checklist:\\n- " + "\\n- ".join(error_checklist))""", "What this means: retrieval, neighborhood, export, splitting, and a tiny training loop are executable together. What this does not mean: the model generalizes, full-KG training is done, scores are calibrated, or any candidate is effective or safe.", """course_summary = {
    "notebooks_completed": 6,
    "data_plane": "fixture by default; bounded named live reads only",
    "model_status": "bounded training smoke passed",
    "production_full_done": False,
    "clinical_use": False,
}
print(json.dumps(course_summary, indent=2))""", "Return to Notebook 01 for access and data identity, Notebook 02 for embedding diagnostics, Notebook 03 for evidence, Notebook 04 for LaminDB, or Notebook 05 for tensor contracts. Those boundaries are part of the result, not disclaimers to omit.")
    notebooks["06_sampled_ml_use_cases.ipynb"] = cells

    return notebooks
