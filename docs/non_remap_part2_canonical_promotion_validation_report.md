# Non-ReMap Part 2 canonical promotion validation report

Kanban QA card: `t_61fabcf3`
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`
Generated UTC: `2026-06-22T21:19:39.630132+00:00`
Canonical promotion performed: **no**

## Verdict

**review-required / partial promotion candidate.** ReMap is explicitly excluded. This validation recommends promoting only tranches whose artifacts are readable, support checks pass, endpoints are compatible, and active schema already supports the relation. Everything with feature-context/candidate/staged-only gates stays non-canonical or deferred.

Recommended `promote_now` set from this QA card:
- BioGRID physical PPI: Protein endpoints anti-join clean against cached canonical protein ids/uniprot_ids; support checks clean; relation protein_interacts_protein is active in schema. Keep evidence class caveat; do not infer complexes.

No canonical KG/GCS writes were made.

## Promotion decision matrix

| Tranche | Decision | Source/review tasks | Reason | Canonical paths if separately promoted |
|---|---|---|---|---|
| IntAct corrected/bounded protein_interacts_protein | `defer` | `t_100231b1`, `t_0964be36` | Accepted recovery staging is bounded (--max-rows 100000/negative max 10000) and lacks canonical node-root endpoint anti-join; not canonical-grade despite clean edge/evidence support. | `gs://jouvencekb/kg/v2/edges/protein_interacts_protein.parquet`<br>`gs://jouvencekb/kg/v2/evidence/protein_interacts_protein.parquet` |
| BioGRID physical PPI | `promote_now` | `t_28f83a7b`, `t_d64b99c0` | Protein endpoints anti-join clean against cached canonical protein ids/uniprot_ids; support checks clean; relation protein_interacts_protein is active in schema. Keep evidence class caveat; do not infer complexes. | `gs://jouvencekb/kg/v2/edges/protein_interacts_protein.parquet`<br>`gs://jouvencekb/kg/v2/evidence/protein_interacts_protein.parquet` |
| BioGRID protein_has_ptm_site / ptm_site split | `defer` | `t_28f83a7b`, `t_d64b99c0` | Counts/support/endpoint checks pass, but active kg_schema.py does not define ptm_site/protein_has_ptm_site yet; promote after schema approval. Complex outputs remain intentionally empty. | `gs://jouvencekb/kg/v2/nodes/ptm_site.parquet`<br>`gs://jouvencekb/kg/v2/edges/protein_has_ptm_site.parquet`<br>`gs://jouvencekb/kg/v2/evidence/protein_has_ptm_site.parquet` |
| miRNA real-source alias/target path | `defer` | `t_f1b51a59`, `t_1734823c`, `t_95bbd18c`, `t_08770b04` | miRTarBase staged counts/support/target gene anti-joins pass, but active kg_schema.py lacks mirna node type and mirna target/regulates relation; docs plan names mirna_regulates_gene rather than current staged mirna_targets_gene. Needs explicit schema naming approval before canonical write. | `gs://jouvencekb/kg/v2/nodes/mirna.parquet`<br>`gs://jouvencekb/kg/v2/edges/mirna_targets_gene.parquet`<br>`gs://jouvencekb/kg/v2/edges/mirna_precursor_produces_mature_mirna.parquet`<br>`gs://jouvencekb/kg/v2/evidence/mirna_targets_gene.parquet` |
| lncRNA GENCODE nodes | `defer` | `t_35dddc93`, `t_e3e2a5a0` | GENCODE lncRNA nodes are plausible staged artifacts but active schema lacks lncrna node type and needs canonical ID policy approval. | `gs://jouvencekb/kg/v2/nodes/lncrna.parquet` |
| LncRNADisease disease edges/candidates | `defer` | `t_35dddc93`, `t_e3e2a5a0` | Active edges are empty; 6598 candidate/rejected rows are gated by license/mapping/schema. Do not promote disease edges. | `gs://jouvencekb/kg/v2/edges/lncrna_associated_disease.parquet`<br>`gs://jouvencekb/kg/v2/evidence/lncrna_associated_disease.parquet` |
| RBP/RNA CLIP ENCORI/POSTAR context | `include_as_feature_context` | `t_89b3ddaf`, `t_010bc1e4` | No active transcript_interacts_protein edges/evidence; 100 candidate rows rejected/context only due missing source-native endpoints / lncRNA schema support. | `gs://jouvencekb/kg/v2/edges/transcript_interacts_protein.parquet`<br>`gs://jouvencekb/kg/v2/evidence/transcript_interacts_protein.parquet` |
| Expression/coexpression feature-context contract | `include_as_feature_context` | `t_c8f1dbc0`, `t_a2820a4e` | Reviewed as feature/context contract only; no approved active causal/mechanistic relation or raw licensed source package. | `feature/context namespace only; no canonical edge path recommended` |
| HPA cellular_component / protein localization | `defer` | `t_4bda37e9`, `t_51714eaf`, `t_41852a2b` | Artifact reads and support/endpoint checks pass, but canonical promotion explicitly blocked pending all-ENSP vs canonical-ENSP policy plus active schema lacks cellular_component/protein_located_in_cellular_component. | `gs://jouvencekb/kg/v2/nodes/cellular_component.parquet`<br>`gs://jouvencekb/kg/v2/edges/protein_located_in_cellular_component.parquet`<br>`gs://jouvencekb/kg/v2/edges/cellular_component_subtype_of_cellular_component.parquet`<br>`gs://jouvencekb/kg/v2/evidence/protein_located_in_cellular_component.parquet`<br>`gs://jouvencekb/kg/v2/evidence/cellular_component_subtype_of_cellular_component.parquet` |
| Complex Portal protein_complex | `defer` | `t_9d94edb6`, `t_c34d9545` | Membership/nested evidence support passes, but active schema lacks protein_complex node and exact relation names differ from overview/plans (protein_part_of_complex vs staged protein_part_of_protein_complex). UniProt isoform policy remains unresolved. | `gs://jouvencekb/kg/v2/nodes/protein_complex.parquet`<br>`gs://jouvencekb/kg/v2/edges/protein_part_of_protein_complex.parquet`<br>`gs://jouvencekb/kg/v2/edges/protein_complex_part_of_protein_complex.parquet`<br>`gs://jouvencekb/kg/v2/evidence/protein_part_of_protein_complex.parquet`<br>`gs://jouvencekb/kg/v2/evidence/protein_complex_part_of_protein_complex.parquet` |
| UniProt PTM sites | `defer` | `t_ef541e0e`, `t_13a70788` | Endpoint/evidence validation passes for staged ptm_site/protein_has_ptm_site, but active schema lacks ptm_site/protein_has_ptm_site and PSI-MOD/isoform handling remains a future review. Disease/phenotype links are diagnostics-only. | `gs://jouvencekb/kg/v2/nodes/ptm_site.parquet`<br>`gs://jouvencekb/kg/v2/edges/protein_has_ptm_site.parquet`<br>`gs://jouvencekb/kg/v2/evidence/protein_has_ptm_site.parquet` |
| OpenTargets/Ensembl gene_paralog_gene | `defer` | `t_e7603b95`, `t_b19c67f8` | Support/endpoint checks pass, but active schema lacks gene_paralog_gene and review retained high-volume/source-order semantics as explicit promotion gate. | `gs://jouvencekb/kg/v2/edges/gene_paralog_gene.parquet`<br>`gs://jouvencekb/kg/v2/evidence/gene_paralog_gene.parquet` |
| Pharmacology/protein-native accepted staged batches | `defer` | `t_19516b59`, `t_ee55140a` | Replacement review accepted five producers only as staged/non-canonical artifacts and recorded a source-control/patch hygiene gate. Relations are active enough to identify canonical paths, but this tester card must not silently promote staged/non-canonical review output without a separate explicit apply/promotion card. | `gs://jouvencekb/kg/v2/edges/molecule_targets_protein.parquet`<br>`gs://jouvencekb/kg/v2/edges/disease_associated_protein.parquet`<br>`gs://jouvencekb/kg/v2/edges/pathway_contains_protein.parquet`<br>`gs://jouvencekb/kg/v2/edges/molecule_synergizes_molecule.parquet`<br>`gs://jouvencekb/kg/v2/edges/molecule_treats_disease.parquet`<br>`gs://jouvencekb/kg/v2/evidence/molecule_targets_protein.parquet`<br>`gs://jouvencekb/kg/v2/evidence/disease_associated_protein.parquet`<br>`gs://jouvencekb/kg/v2/evidence/pathway_contains_protein.parquet`<br>`gs://jouvencekb/kg/v2/evidence/molecule_synergizes_molecule.parquet`<br>`gs://jouvencekb/kg/v2/evidence/molecule_treats_disease.parquet` |
| Sci-Plex cell_type_responds_to_molecule candidate/context downgrade | `include_as_feature_context` | `t_587ab15a` | Validated no active edges/evidence because source obs lacks response/effect metric versus control; keep 14 candidates + 25 rejected as context only. | `gs://jouvencekb/kg/v2/edges/cell_type_responds_to_molecule.parquet`<br>`gs://jouvencekb/kg/v2/evidence/cell_type_responds_to_molecule.parquet` |
| Metadata/features/source coverage batch | `include_as_feature_context` | `t_67465eac`, `t_4de0dfbc` | Superseded live review accepted these as staged/review artifacts with gates; not canonical edge promotion material from this tester card. | `feature/context/report namespace; no canonical edge path recommended by this validation` |
| ReMap tf_binds_enhancer active/full/all-chromosome cards | `defer` | `t_3479936e`, `t_17f2b3d5`, `t_8fff8356`, `t_6d8e46c8`, `t_5738004a` | Explicitly excluded from this non-ReMap validation/promotion candidate by human decision; remains separate step and must not block non-ReMap consideration. | `gs://jouvencekb/kg/v2/edges/tf_binds_enhancer.parquet`<br>`gs://jouvencekb/kg/v2/evidence/tf_binds_enhancer.parquet` |

## Artifact/readback inventory and key checks

### intact
- Remote prefix: `gs://jouvencekb/kg/staging/source-native-expansion/intact-protein-interactions-policy-fixed/runs/20260622T122314Z-bounded100k/`
- Cached files: 9; bytes: 291143217

| Parquet | Rows | Bytes |
|---|---:|---:|
| `edges/protein_interacts_protein.parquet` | 34515 | 214679 |
| `evidence/protein_interacts_protein.parquet` | 46425 | 161717975 |
| `evidence/protein_interacts_protein_negative.parquet` | 496 | 1230777 |
| `reports/rejected_rows.parquet` | 53575 | 127023680 |

### biogrid
- Remote prefix: `gs://jouvencekb/kg/staging/source-native-expansion/biogrid-ptm-xref/`
- Cached files: 13; bytes: 18510623

| Parquet | Rows | Bytes |
|---|---:|---:|
| `biogrid-categorized-20260622/audit/biogrid_ptm_refseq_mapping_accepted.parquet` | 13845 | 295134 |
| `biogrid-categorized-20260622/audit/biogrid_ptm_refseq_mapping_rejected.parquet` | 71934 | 894261 |
| `biogrid-categorized-20260622/audit/biogrid_ptmtab_refseq_rejections_by_reason.parquet` | 84898 | 621866 |
| `biogrid-categorized-20260622/edges/protein_has_ptm_site.parquet` | 28169 | 333877 |
| `biogrid-categorized-20260622/edges/protein_interacts_protein.parquet` | 3550 | 30420 |
| `biogrid-categorized-20260622/evidence/protein_has_ptm_site.parquet` | 62096 | 14486461 |
| `biogrid-categorized-20260622/evidence/protein_interacts_protein.parquet` | 12288 | 895996 |
| `biogrid-categorized-20260622/nodes/ptm_site.parquet` | 28169 | 926799 |

### mirna
- Remote prefix: `gs://jouvencekb/kg/staging/source-native-expansion/mirna-targets-real/`
- Cached files: 15; bytes: 100649833

| Parquet | Rows | Bytes |
|---|---:|---:|
| `edges/mirna_precursor_produces_mature_mirna.parquet` | 1707 | 25005 |
| `edges/mirna_targets_gene.parquet` | 351958 | 887835 |
| `edges/mirna_targets_transcript.parquet` | 0 | 3908 |
| `evidence/mirna_targets_gene.parquet` | 868896 | 98953393 |
| `evidence/mirna_targets_transcript.parquet` | 0 | 23663 |
| `mappings/transcript_mirbase_aliases.parquet` | 644 | 42540 |
| `mappings/transcript_mirbase_aliases_rejected.parquet` | 0 | 7178 |
| `mappings/transcript_mirbase_mapping_needs_review.parquet` | 2508 | 48268 |
| `nodes/mirna.parquet` | 3929 | 130955 |
| `reports/mirtarbase_targets_rejected.parquet` | 25237 | 514030 |

### lncrna
- Remote prefix: `gs://jouvencekb/kg/staging/source-native-expansion/lncrna-l2f-gencode-lncrnadisease-20260622/`
- Cached files: 9; bytes: 15510246

| Parquet | Rows | Bytes |
|---|---:|---:|
| `candidates/lncrna_associated_disease.parquet` | 6598 | 2439870 |
| `edges/lncrna_associated_disease.parquet` | 0 | 4355 |
| `nodes/lncrna.parquet` | 197208 | 9445429 |
| `reports/gencode_lncrna_gene_summary.parquet` | 37576 | 1170160 |
| `reports/rejected_or_needs_review.parquet` | 6598 | 2439870 |

### rbp_clip
- Remote prefix: `gs://jouvencekb/kg/v2/staging/rbp-rna-clip-encori-pilot-20260622T135045Z/`
- Cached files: 7; bytes: 91006

| Parquet | Rows | Bytes |
|---|---:|---:|
| `edges/transcript_interacts_protein.parquet` | 0 | 3956 |
| `evidence/transcript_interacts_protein.parquet` | 0 | 11363 |
| `reports/candidate_clip_evidence.parquet` | 100 | 33106 |
| `reports/rejected_rows.parquet` | 100 | 33975 |

### hpa
- Remote prefix: `gs://jouvencekb/kg/staging/hpa-cellular-components-2026-06-22-rebuild-t_51714eaf/`
- Cached files: 8; bytes: 12942667

| Parquet | Rows | Bytes |
|---|---:|---:|
| `edges/cellular_component_subtype_of_cellular_component.parquet` | 14 | 5416 |
| `edges/protein_located_in_cellular_component.parquet` | 276356 | 1150292 |
| `evidence/cellular_component_subtype_of_cellular_component.parquet` | 14 | 13394 |
| `evidence/protein_located_in_cellular_component.parquet` | 536967 | 11743982 |
| `nodes/cellular_component.parquet` | 60 | 13449 |

### complex_portal
- Remote prefix: `gs://jouvencekb/kg/staging/complex-portal-protein-complexes-2026-06-22/`
- Cached files: 7; bytes: 5172886

| Parquet | Rows | Bytes |
|---|---:|---:|
| `edges/protein_complex_part_of_protein_complex.parquet` | 117 | 6333 |
| `edges/protein_part_of_protein_complex.parquet` | 625 | 11545 |
| `evidence/protein_complex_part_of_protein_complex.parquet` | 117 | 123221 |
| `evidence/protein_part_of_protein_complex.parquet` | 625 | 546533 |
| `mappings/complex_portal_participants_rejected.parquet` | 9359 | 3403122 |
| `nodes/protein_complex.parquet` | 2498 | 1076654 |

### uniprot_ptm
- Remote prefix: `gs://jouvencekb/kg/staging/uniprot-ptm-sites-2026-06-22/`
- Cached files: 6; bytes: 12481456

| Parquet | Rows | Bytes |
|---|---:|---:|
| `diagnostics/ptm_site_disease_link_candidates.parquet` | 8 | 10671 |
| `edges/protein_has_ptm_site.parquet` | 92578 | 1215681 |
| `evidence/protein_has_ptm_site.parquet` | 173491 | 7780373 |
| `nodes/ptm_site.parquet` | 92578 | 3472200 |

### gene_paralog
- Remote prefix: `gs://jouvencekb/kg/staging/source-native-expansion/gene_paralog_gene/opentargets-target-homologues-20260622/`
- Cached files: 3; bytes: 253277718

| Parquet | Rows | Bytes |
|---|---:|---:|
| `edges/gene_paralog_gene.parquet` | 3544825 | 6704400 |
| `evidence/gene_paralog_gene.parquet` | 3544825 | 246570040 |

### sciplex
- Remote prefix: `gs://jouvencekb/kg/staging/cell_type_molecule_candidate_context_sciplex2_20260622_t_63ca49a0/`
- Cached files: 8; bytes: 65189

| Parquet | Rows | Bytes |
|---|---:|---:|
| `candidates/cell_type_responds_to_molecule_sciplex2_candidates.parquet` | 14 | 18275 |
| `candidates/cell_type_responds_to_molecule_sciplex2_rejected.parquet` | 25 | 18992 |
| `edges/cell_type_responds_to_molecule.parquet` | 0 | 3908 |
| `evidence/cell_type_responds_to_molecule.parquet` | 0 | 11182 |
| `nodes/cell_type.parquet` | 1 | 1756 |
| `nodes/molecule.parquet` | 2 | 1650 |

## Mechanical validation checks

```json
{
  "biogrid": {
    "audit_rows": {
      "ptmtab_refseq_rejections_by_reason": 84898,
      "refseq_mapping_accepted": 13845,
      "refseq_mapping_rejected": 71934
    },
    "builder_report": {
      "canonical_writes": false,
      "complexes": {
        "explicit_biogrid_complex_files_found": [],
        "policy": "No protein_complex nodes or protein_part_of_complex edges are staged from TAB3 pairwise/system rows. Requires explicit BioGRID complex file with stable complex IDs/names/members.",
        "staged_membership_edges": 0,
        "staged_nodes": 0
      },
      "physical_interactions": {
        "complex_like_tab3_counts_not_complex_nodes": {
          "Affinity Capture-Luminescence": 1665,
          "Affinity Capture-MS": 211425,
          "Affinity Capture-Western": 102082,
          "Co-fractionation": 28047,
          "Co-localization": 5897,
          "Co-purification": 5385,
          "Proximity Label-MS": 52226,
          "Reconstituted Complex": 44938
        },
        "counts": {
          "route:excluded": 540401,
          "route:protein_interacts_protein": 12288,
          "tab3_rows_seen": 552689
        },
        "exclusion_reasons": {
          "endpoint_mapping_failed:ambiguous_source_protein_accession_mapping:ambiguous_source_protein_accession_mapping": 2297,
          "endpoint_mapping_failed:ambiguous_source_protein_accession_mapping:no_source_protein_accession_mapping": 13432,
          "endpoint_mapping_failed:ambiguous_source_protein_accession_mapping:ok": 3495,
          "endpoint_mapping_failed:no_source_protein_accession_mapping:ambiguous_source_protein_accession_mapping": 13504,
          "endpoint_mapping_failed:no_source_protein_accession_mapping:no_source_protein_accession_mapping": 194301,
          "endpoint_mapping_failed:no_source_protein_accession_mapping:ok": 45114,
          "endpoint_mapping_failed:ok:ambiguous_source_protein_accession_mapping": 3649,
          "endpoint_mapping_failed:ok:no_source_protein_accession_mapping": 47184,
          "excluded_non_protein_or_peptide_system": 3837,
          "non_human_endpoint": 212246,
          "not_physical": 60,
          "self_interaction_collapsed": 1282
        },
        "experimental_system_counts": {
          "": 60,
          "Affinity Capture-Luminescence": 1665,
          "Affinity Capture-MS": 211425,
          "Affinity Capture-RNA": 9379,
          "Affinity Capture-Western": 102082,
          "Biochemical Activity": 14401,
          "Co-crystal Structure": 4384,
          "Co-fractionation": 28047,
          "Co-localization": 5897,
          "Co-purification": 5385,
          "Cross-Linking-MS (XL-MS)": 13989,
          "FRET": 2407,
          "Far Western": 992,
          "PCA": 5130,
          "Protein-RNA": 1603,
          "Protein-peptide": 2746,
          "Proximity Label-MS": 52226,
          "Reconstituted Complex": 44938,
          "Surface Display": 12,
          "Thermal Shift Assay": 1,
          "Two-hybrid": 45920
        },
        "source_members": [
          "BIOGRID-MV-Physical-5.0.258.tab3.txt"
        ],
        "source_zip": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/biogrid_audit/BIOGRID-MV-Physical-5.0.258.tab3.zip"
      },
      "protein_mapping": {
        "refseq": 13845,
        "uniprot": 60652
      },
      "ptms": {
        "counts": {
          "ptmrel_rows_seen": 73388,
          "ptmtab_excluded_missing_site_fields": 45247,
          "ptmtab_excluded_no_refseq_protein_mapping": 891839,
          "ptmtab_excluded_non_human": 129157,
          "ptmtab_rows_seen": 1128339
        },
        "modification_counts_for_staged_sites": {
          "Neddylation": 318,
          "Phosphorylation": 4680,
          "Ubiquitination": 57098
        },
        "ptm_relationship_counts_report_only": {
          "PTM": 57835,
          "catalytic": 11978,
          "regulatory": 3575
        },
        "ptm_relationship_edge_policy": "report_only_until protein_modifies_ptm_site/event schema is finalized",
        "source_members": [
          "BIOGRID-PTM-5.0.258.ptmtab.txt",
          "BIOGRID-PTM-RELATIONSHIPS-5.0.258.ptmrel.txt"
        ],
        "source_zip": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/biogrid_audit/BIOGRID-PTMS-5.0.258.ptm.zip"
      },
      "refseq_mapping_audit": {
        "added_refseq_mappings": 13845,
        "ambiguous_refseq_mappings": 224,
        "refseq_with_uniprot_mapping": 85779,
        "source": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/biogrid_audit/HUMAN_9606_idmapping.dat.gz",
        "status": "loaded",
        "unique_uniprot_to_ensp": 60652
      },
      "source_release": "BIOGRID-5.0.258",
      "stage": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/staging/biogrid-categorized-20260622",
      "system_split_category_counts_report_only": {
        "complex_like_tab3_counts_not_complex_nodes": {
          "Affinity Capture-Luminescence": 2872,
          "Affinity Capture-MS": 978998,
          "Affinity Capture-Western": 144970,
          "Co-fractionation": 154885,
          "Co-localization": 10096,
          "Co-purification": 8683,
          "Proximity Label-MS": 232004,
          "Reconstituted Complex": 70636
        },
        "counts": {
          "route:excluded": 1960266,
          "route:genetic_excluded": 887841,
          "route:protein_interacts_protein": 52136,
          "tab3_rows_seen": 2900243
        },
        "exclusion_reasons": {
          "endpoint_mapping_failed:ambiguous_source_protein_accession_mapping:ambiguous_source_protein_accession_mapping": 4248,
          "endpoint_mapping_failed:ambiguous_source_protein_accession_mapping:no_source_protein_accession_mapping": 40627,
          "endpoint_mapping_failed:ambiguous_source_protein_accession_mapping:ok": 10933,
          "endpoint_mapping_failed:no_source_protein_accession_mapping:ambiguous_source_protein_accession_mapping": 45898,
          "endpoint_mapping_failed:no_source_protein_accession_mapping:no_source_protein_accession_mapping": 690903,
          "endpoint_mapping_failed:no_source_protein_accession_mapping:ok": 175403,
          "endpoint_mapping_failed:ok:ambiguous_source_protein_accession_mapping": 12873,
          "endpoint_mapping_failed:ok:no_source_protein_accession_mapping": 190149,
          "excluded_non_protein_or_peptide_system": 38038,
          "genetic_interaction_not_protein_mechanism": 887841,
          "non_human_endpoint": 748979,
          "not_physical": 390,
          "self_interaction_collapsed": 1825
        },
        "experimental_system_counts": {
          "": 390,
          "Affinity Capture-Luminescence": 2872,
          "Affinity Capture-MS": 978998,
          "Affinity Capture-RNA": 60091,
          "Affinity Capture-Western": 144970,
          "Biochemical Activity": 27985,
          "Co-crystal Structure": 5055,
          "Co-fractionation": 154885,
          "Co-localization": 10096,
          "Co-purification": 8683,
          "Cross-Linking-MS (XL-MS)": 33540,
          "Dosage Growth Defect": 2433,
          "Dosage Lethality": 2573,
          "Dosage Rescue": 8864,
          "FRET": 3886,
          "Far Western": 1357,
          "Negative Genetic": 568282,
          "PCA": 27628,
          "Phenotypic Enhancement": 19682,
          "Phenotypic Suppression": 22079,
          "Positive Genetic": 195206,
          "Protein-RNA": 12468,
          "Protein-peptide": 7351,
          "Proximity Label-MS": 232004,
          "Reconstituted Complex": 70636,
          "Surface Display": 12,
          "Synthetic Growth Defect": 33725,
          "Synthetic Haploinsufficiency": 379,
          "Synthetic Lethality": 21758,
          "Synthetic Rescue": 12860,
          "Thermal Shift Assay": 1,
          "Two-hybrid": 229494
        },
        "source_members": [
          "BIOGRID-SYSTEM-Affinity_Capture-Luminescence-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Affinity_Capture-MS-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Affinity_Capture-RNA-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Affinity_Capture-Western-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Biochemical_Activity-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Co-crystal_Structure-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Co-fractionation-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Co-localization-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Co-purification-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Cross-Linking-MS_(XL-MS)-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Dosage_Growth_Defect-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Dosage_Lethality-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Dosage_Rescue-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-FRET-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Far_Western-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Negative_Genetic-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-PCA-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Phenotypic_Enhancement-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Phenotypic_Suppression-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Positive_Genetic-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Protein-RNA-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Protein-peptide-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Proximity_Label-MS-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Reconstituted_Complex-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Surface_Display-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Synthetic_Growth_Defect-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Synthetic_Haploinsufficiency-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Synthetic_Lethality-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Synthetic_Rescue-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Thermal_Shift_Assay-5.0.258.tab3.txt",
          "BIOGRID-SYSTEM-Two-hybrid-5.0.258.tab3.txt"
        ],
        "source_zip": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/biogrid_audit/BIOGRID-SYSTEM-5.0.258.tab3.zip"
      },
      "validation": {
        "duckdb_available": true,
        "ppi_edges_without_evidence": 0,
        "ppi_evidence_class_counts": [
          {
            "evidence_class": "complex_or_cofractionation_association",
            "row_count": 10301
          },
          {
            "evidence_class": "binary_physical",
            "row_count": 1615
          },
          {
            "evidence_class": "biochemical_or_ptm_like_activity",
            "row_count": 372
          }
        ],
        "ppi_evidence_without_edges": 0,
        "ppi_x_endpoint_antijoin": 0,
        "ppi_y_endpoint_antijoin": 0,
        "protein_has_ptm_site_edge_rows": 28169,
        "protein_has_ptm_site_evidence_rows": 62096,
        "protein_interacts_protein_edge_rows": 3550,
        "protein_interacts_protein_evidence_rows": 12288,
        "ptm_edges_without_evidence": 0,
        "ptm_evidence_without_edges": 0,
        "ptm_node_duplicate_ids": 0,
        "ptm_protein_endpoint_antijoin": 0,
        "ptm_site_endpoint_antijoin": 0,
        "ptm_site_node_rows": 28169
      },
      "xref_mapping_tables": {
        "accepted_refseq_mapping_rows": 13845,
        "accepted_refseq_mapping_table": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/staging/biogrid-categorized-20260622/audit/biogrid_ptm_refseq_mapping_accepted.parquet",
        "policy": "protein-accession-native RefSeq protein -> UniProt HUMAN_9606 idmapping -> canonical ENSP protein node; no gene-only projection",
        "ptmtab_refseq_rejection_rows": 84898,
        "ptmtab_refseq_rejection_table": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/staging/biogrid-categorized-20260622/audit/biogrid_ptmtab_refseq_rejections_by_reason.parquet",
        "rejected_refseq_mapping_rows": 71934,
        "rejected_refseq_mapping_table": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/staging/biogrid-categorized-20260622/audit/biogrid_ptm_refseq_mapping_rejected.parquet"
      }
    },
    "ppi": {
      "duplicate_edges": 0,
      "edge_rows": 3550,
      "edges_without_evidence": 0,
      "evidence_class_counts": {
        "k": "v"
      },
      "evidence_rows": 12288,
      "evidence_without_edge": 0,
      "x_protein_antijoin_id_or_uniprot": 0,
      "y_protein_antijoin_id_or_uniprot": 0
    },
    "ptm": {
      "duplicate_edges": 0,
      "edge_rows": 28169,
      "edges_without_evidence": 0,
      "evidence_rows": 62096,
      "evidence_without_edge": 0,
      "node_rows": 28169,
      "x_protein_antijoin_id_or_uniprot": 0,
      "y_ptm_node_antijoin": 0
    }
  },
  "complex_portal": {
    "nodes": {
      "protein_complex": 2498
    },
    "protein_complex_part_of_protein_complex": {
      "duplicate_edges": 0,
      "edge_rows": 117,
      "edges_without_evidence": 0,
      "evidence_rows": 117,
      "evidence_without_edge": 0
    },
    "protein_part_of_protein_complex": {
      "duplicate_edges": 0,
      "edge_rows": 625,
      "edges_without_evidence": 0,
      "evidence_rows": 625,
      "evidence_without_edge": 0,
      "x_protein_antijoin_id_or_uniprot": 0,
      "y_complex_antijoin": 0
    },
    "rejected_participants": 9359,
    "validation": {
      "artifacts": {
        "membership_edges": ".omoc/staging/complex-portal-protein-complexes-2026-06-22/edges/protein_part_of_protein_complex.parquet",
        "membership_evidence": ".omoc/staging/complex-portal-protein-complexes-2026-06-22/evidence/protein_part_of_protein_complex.parquet",
        "nested_edges": ".omoc/staging/complex-portal-protein-complexes-2026-06-22/edges/protein_complex_part_of_protein_complex.parquet",
        "nested_evidence": ".omoc/staging/complex-portal-protein-complexes-2026-06-22/evidence/protein_complex_part_of_protein_complex.parquet",
        "nodes": ".omoc/staging/complex-portal-protein-complexes-2026-06-22/nodes/protein_complex.parquet",
        "rejected_participants": ".omoc/staging/complex-portal-protein-complexes-2026-06-22/mappings/complex_portal_participants_rejected.parquet"
      },
      "canonical_promotion": false,
      "canonical_promotion_recommendation": "Do not promote canonically yet. Review UniProt\u2192ENSP ambiguity rejects, add schema NodeType/Relation definitions, and approve relation naming before promotion.",
      "checks": {
        "membership_complex_endpoint_antijoin": {
          "missing_complex_ids": [],
          "missing_count": 0,
          "ok": true
        },
        "membership_edge_evidence_support": {
          "edges_without_evidence": [],
          "edges_without_evidence_count": 0,
          "evidence_without_edge": [],
          "evidence_without_edge_count": 0,
          "ok": true
        },
        "membership_edges_unique": {
          "duplicate_rows": 0,
          "ok": true
        },
        "nested_complex_endpoint_antijoin": {
          "missing_complex_ids": [],
          "missing_count": 0,
          "ok": true
        },
        "nested_edge_evidence_support": {
          "edges_without_evidence_count": 0,
          "evidence_without_edge_count": 0,
          "ok": true
        },
        "nested_edges_explicit_only": {
          "note": "nested edges are emitted only from participant tokens whose parsed identifier is CPX-*",
          "ok": true
        },
        "no_member_disease_projection": {
          "note": "Disease field is preserved only as protein_complex node raw disease_xrefs; no disease/phenotype edges are emitted.",
          "ok": true
        },
        "node_ids_unique": {
          "duplicate_rows": 0,
          "ok": true
        },
        "protein_endpoint_mapping": {
          "mapping_supplied": true,
          "ok": true,
          "policy": "accepted only source UniProt accessions with exactly one nodes/protein.uniprot_id match; ambiguous and unmapped participants are materialized as rejects",
          "rejected_reason_counts": {
            "uniprot_maps_to_multiple_protein_nodes": 8299,
            "uniprot_unmapped_to_protein_node": 207,
            "unsupported_participant_namespace": 853
          }
        }
      },
      "counts": {
        "nested_complex_edges": 117,
        "nested_complex_evidence": 117,
        "protein_complex_nodes": 2498,
        "protein_part_of_protein_complex_edges": 625,
        "protein_part_of_protein_complex_evidence": 625,
        "rejected_participants": 9359
      },
      "created_at": "2026-06-22T13:51:49.077223+00:00",
      "gcs_artifacts": {
        "membership_edges": "gs://jouvencekb/kg/staging/complex-portal-protein-complexes-2026-06-22/edges/protein_part_of_protein_complex.parquet",
        "membership_evidence": "gs://jouvencekb/kg/staging/complex-portal-protein-complexes-2026-06-22/evidence/protein_part_of_protein_complex.parquet",
        "nested_edges": "gs://jouvencekb/kg/staging/complex-portal-protein-complexes-2026-06-22/edges/protein_complex_part_of_protein_complex.parquet",
        "nested_evidence": "gs://jouvencekb/kg/staging/complex-portal-protein-complexes-2026-06-22/evidence/protein_complex_part_of_protein_complex.parquet",
        "nodes": "gs://jouvencekb/kg/staging/complex-portal-protein-complexes-2026-06-22/nodes/protein_complex.parquet",
        "rejected_participants": "gs://jouvencekb/kg/staging/complex-portal-protein-complexes-2026-06-22/mappings/complex_portal_participants_rejected.parquet"
      },
      "gcs_staging_root": "gs://jouvencekb/kg/staging/complex-portal-protein-complexes-2026-06-22",
      "inputs": {
        "complextab": ".omoc/raw/complex_portal/2026-01-14/9606.tsv",
        "manifest": {
          "cached_path": ".omoc/raw/complex_portal/2026-01-14/9606.tsv",
          "downloaded_at": "2026-06-22T13:51:45.169634+00:00",
          "headers": {
            "Content-Length": "5292514",
            "Content-Type": "text/tab-separated-values",
            "ETag": "\"50c1e2-64857de097555\"",
            "Last-Modified": "Wed, 14 Jan 2026 12:01:24 GMT"
          },
          "release": "2026-01-14",
          "source": "complex_portal",
          "url": "https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/9606.tsv"
        },
        "node_root": "gs://jouvencekb/kg/v2",
        "protein_nodes": ""
      },
      "mapping_stats": {
        "ambiguous_uniprot_accessions": 19736,
        "mapping_supplied": true,
        "protein_node_rows": 233869,
        "source": "gs://jouvencekb/kg/v2/nodes/protein.parquet",
        "unique_uniprot_accessions": 60652
      },
      "ok": true,
      "output_dir": ".omoc/staging/complex-portal-protein-complexes-2026-06-22",
      "source": "complex_portal",
      "source_counts": {
        "complex_rows": 2498,
        "mapped_protein_participants": 625,
        "nested_complex_participants": 117,
        "rejected_uniprot_maps_to_multiple_protein_nodes": 8299,
        "rejected_uniprot_unmapped_to_protein_node": 207,
        "rejected_unsupported_participant_namespace": 853
      },
      "source_release": "2026-01-14",
      "source_url": "https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/9606.tsv",
      "staging_only": true,
      "warnings": []
    }
  },
  "gene_paralog": {
    "duplicate_edges": 0,
    "edge_rows": 3544825,
    "edges_without_evidence": 0,
    "evidence_rows": 3544825,
    "evidence_without_edge": 0,
    "report": {
      "accepted_human_paralog_records_before_endpoint_filter": 3552225,
      "accepted_policy": {
        "ortholog_leakage": "all non-human target species rejected before edge/evidence materialization",
        "query": "OpenTargets target.id must be human Ensembl gene ENSG",
        "self_edges": "rejected",
        "target": "homologues entries with speciesId == '9606', targetGeneId ENSG, homologyType containing 'paralog'"
      },
      "artifacts": {
        "edges": ".omoc/staging/opentargets_gene_paralogs/edges/gene_paralog_gene.parquet",
        "evidence": ".omoc/staging/opentargets_gene_paralogs/evidence/gene_paralog_gene.parquet",
        "gcs_root": "gs://jouvencekb/kg/staging/source-native-expansion/gene_paralog_gene/opentargets-target-homologues-20260622",
        "report": ".omoc/staging/opentargets_gene_paralogs/reports/gene_paralog_gene_report.json"
      },
      "canonical_promotion_recommendation": "Do not promote yet. Keep as separate staged genetic tranche until reviewer confirms relation naming, evidence schema extension for homology metadata, and export-time symmetry handling.",
      "confidence_counts": {
        "0": 95861,
        "1": 169308,
        "NULL": 3552234
      },
      "counts": {
        "edges_source_order": 3544825,
        "evidence_rows": 3544825,
        "missing_gene_endpoint_ids": 0,
        "unique_unordered_pairs": 1772804,
        "unordered_pairs_with_both_directions": 1772021
      },
      "created_at": "2026-06-22T13:50:26.620605+00:00",
      "homologue_records_observed": 3817403,
      "homology_type_counts": {
        "gene_split": 9,
        "ortholog_many2many": 59531,
        "ortholog_one2many": 37112,
        "ortholog_one2one": 168526,
        "other_paralog": 3485497,
        "within_species_paralog": 66728
      },
      "non_human_paralog_species_counts": {},
      "rejected_counts": {
        "non_dict_homologue": 0,
        "non_ensg_query": 0,
        "non_ensg_target": 0,
        "non_human_target_species": 0,
        "non_paralog_homology_type": 265178,
        "noncanonical_gene_endpoint": 7400,
        "self_edge": 0
      },
      "relation": "gene_paralog_gene",
      "source": "OpenTargets/target.homologues",
      "source_release": "26.03",
      "source_rows": 78691,
      "species_counts_top50": {
        "10090|Mouse": 25421,
        "10116|Norway rat - BN/NHsdMcwi": 23795,
        "10141|Guinea Pig": 19976,
        "6239|Caenorhabditis elegans (Nematode, N2)": 23996,
        "7227|Drosophila melanogaster - (Fruit fly)": 20337,
        "7955|Zebrafish": 21044,
        "8364|Tropical clawed frog": 18355,
        "9544|Macaque": 23085,
        "9598|Chimpanzee": 25396,
        "9606|Human": 3552234,
        "9615|Dog": 22097,
        "9823|Pig": 21850,
        "9986|Rabbit": 19817
      },
      "symmetry_policy": {
        "export_recommendation": "add reverse edges only in downstream graph export if the consumer requires directed adjacency; keep evidence on source-order assertions and mark reverse rows as derived",
        "rationale": "OpenTargets target.homologues can contain reciprocal records but percent identities are query/target oriented; duplicating at storage time would double-count evidence and obscure source row provenance.",
        "staged_storage": "source_order_only"
      },
      "validation": {
        "cross_species_ortholog_leakage_pass": true,
        "duplicate_directed_edges": 0,
        "evidence_without_edge": 0,
        "gene_endpoint_antijoin_pass": true,
        "missing_gene_endpoint_ids_sample": []
      }
    },
    "x_gene_antijoin": 0,
    "y_gene_antijoin": 0
  },
  "hpa": {
    "cellular_component_subtype": {
      "duplicate_edges": 0,
      "edge_rows": 14,
      "edges_without_evidence": 0,
      "evidence_rows": 14,
      "evidence_without_edge": 0
    },
    "independent_validation": {
      "blocker_rows": [
        {
          "go_id": "",
          "hpa_label": "Annulus",
          "id": "HPA_SL:annulus",
          "mapping_confidence": "hpa_local",
          "mapping_method": "hpa_local_fallback",
          "name": "Annulus",
          "uniprot_sl_id": ""
        },
        {
          "go_id": "GO:0036064",
          "hpa_label": "Basal body",
          "id": "GO:0036064",
          "mapping_confidence": "exact_manual",
          "mapping_method": "manual_hpa_go_override",
          "name": "ciliary basal body",
          "uniprot_sl_id": ""
        },
        {
          "go_id": "",
          "hpa_label": "Connecting piece",
          "id": "HPA_SL:connecting_piece",
          "mapping_confidence": "hpa_local",
          "mapping_method": "hpa_local_fallback",
          "name": "Connecting piece",
          "uniprot_sl_id": ""
        },
        {
          "go_id": "",
          "hpa_label": "Mitotic chromosome",
          "id": "HPA_SL:mitotic_chromosome",
          "mapping_confidence": "hpa_local",
          "mapping_method": "hpa_local_fallback",
          "name": "Mitotic chromosome",
          "uniprot_sl_id": ""
        },
        {
          "go_id": "",
          "hpa_label": "Nucleoli rim",
          "id": "HPA_SL:nucleoli_rim",
          "mapping_confidence": "hpa_local",
          "mapping_method": "hpa_local_fallback",
          "name": "Nucleoli rim",
          "uniprot_sl_id": ""
        },
        {
          "go_id": "",
          "hpa_label": "Primary cilium",
          "id": "HPA_SL:primary_cilium",
          "mapping_confidence": "hpa_local",
          "mapping_method": "hpa_local_fallback",
          "name": "Primary cilium",
          "uniprot_sl_id": ""
        },
        {
          "go_id": "",
          "hpa_label": "Rods & Rings",
          "id": "HPA_SL:rods_rings",
          "mapping_confidence": "hpa_local",
          "mapping_method": "hpa_local_fallback",
          "name": "Rods & Rings",
          "uniprot_sl_id": ""
        }
      ],
      "counts": {
        "cellular_component_nodes": 60,
        "distinct_hpa_labels": 59,
        "go_mapped_nodes": 40,
        "hierarchy_edges": 14,
        "hierarchy_evidence": 14,
        "hpa_local_nodes": 18,
        "protein_location_edges": 276356,
        "protein_location_evidence": 536967
      },
      "hierarchy_predicates": [
        "located_in",
        "part_of",
        "subtype_of"
      ],
      "hierarchy_rows_touching_primary_cilium": [
        {
          "credibility": 3,
          "display_relation": "subtype of",
          "relation": "cellular_component_subtype_of_cellular_component",
          "source": "GO/HPA",
          "x_id": "GO:0097542",
          "x_type": "cellular_component",
          "y_id": "HPA_SL:primary_cilium",
          "y_type": "cellular_component"
        },
        {
          "credibility": 3,
          "display_relation": "subtype of",
          "relation": "cellular_component_subtype_of_cellular_component",
          "source": "GO/HPA",
          "x_id": "GO:0035869",
          "x_type": "cellular_component",
          "y_id": "HPA_SL:primary_cilium",
          "y_type": "cellular_component"
        }
      ],
      "independent_checks": {
        "audit_fields_present": [
          "ambiguous_hpa_distinct_protein_component_edges",
          "ambiguous_hpa_expanded_protein_rows",
          "ambiguous_hpa_label_assignments",
          "ambiguous_hpa_source_rows",
          "current_policy",
          "promotion_recommendation",
          "top_ambiguous_uniprots_in_hpa_rows"
        ],
        "blocker_rows_with_rejected_or_alt_go_ids": 0,
        "component_endpoint_missing": 0,
        "hierarchy_broad_predicates": 0,
        "hierarchy_edges_without_evidence": 0,
        "hierarchy_evidence_without_edge": 0,
        "location_edges_without_evidence": 0,
        "location_evidence_without_edge": 0,
        "protein_endpoint_missing": 0
      },
      "manifest_path": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/staging/hpa-cellular-components-2026-06-22-rebuild-t_51714eaf/manifest.json",
      "output_dir": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/staging/hpa-cellular-components-2026-06-22-rebuild-t_51714eaf",
      "promotion_recommendation": "review canonical ENSP policy before promotion: all ENSP isoforms preserves accession crossrefs but can multiply HPA evidence; canonical ENSP only reduces expansion but needs an approved canonical-protein selector",
      "validation_checks": {
        "component_endpoint_antijoin": {
          "missing_component_nodes": 0
        },
        "evidence_support": {
          "edges_without_evidence": 0,
          "evidence_without_edge": 0
        },
        "go_term_semantics": {
          "invalid_go_node_examples": [],
          "invalid_go_nodes": 0
        },
        "hierarchy_semantics": {
          "broad_context_edges": 0
        },
        "protein_endpoint_antijoin": {
          "missing_protein_nodes": 0
        }
      },
      "validation_path": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/staging/hpa-cellular-components-2026-06-22-rebuild-t_51714eaf/validation.json"
    },
    "manifest": {
      "created_at": "2026-06-22T14:29:10.707551+00:00",
      "license_note": "HPA data should be attributed and exact release terms rechecked before canonical promotion; GO and UniProt mappings are cached for reproducibility.",
      "node_type": "cellular_component",
      "output_dir": ".omoc/staging/hpa-cellular-components-2026-06-22-rebuild-t_51714eaf",
      "relations": [
        "protein_located_in_cellular_component",
        "cellular_component_subtype_of_cellular_component"
      ],
      "source_policy": "HPA subcellular/secretome labels mapped to GO CC where feasible with HPA local fallback IDs; protein endpoints resolved only through canonical nodes/protein.parquet UniProt xrefs; no gene-to-protein projection; no generic all-cells-have-component assertions.",
      "staging_only": true,
      "validation": {
        "checks": {
          "component_endpoint_antijoin": {
            "missing_component_nodes": 0
          },
          "evidence_support": {
            "edges_without_evidence": 0,
            "evidence_without_edge": 0
          },
          "go_term_semantics": {
            "invalid_go_node_examples": [],
            "invalid_go_nodes": 0
          },
          "hierarchy_semantics": {
            "broad_context_edges": 0
          },
          "protein_endpoint_antijoin": {
            "missing_protein_nodes": 0
          }
        },
        "counts": {
          "cellular_component_nodes": 60,
          "distinct_hpa_labels": 59,
          "go_mapped_nodes": 40,
          "hierarchy_edges": 14,
          "hierarchy_evidence": 14,
          "hpa_local_nodes": 18,
          "protein_location_edges": 276356,
          "protein_location_evidence": 536967
        },
        "label_counts": {
          "Acrosome": 220,
          "Actin filaments": 504,
          "Aggresome": 38,
          "Annulus": 98,
          "Basal body": 876,
          "Calyx": 138,
          "Cell Junctions": 650,
          "Centriolar satellite": 438,
          "Centrosome": 1000,
          "Cleavage furrow": 4,
          "Connecting piece": 178,
          "Cytokinetic bridge": 464,
          "Cytoplasmic bodies": 146,
          "Cytosol": 10352,
          "End piece": 370,
          "Endoplasmic reticulum": 1120,
          "Endosomes": 32,
          "Equatorial segment": 162,
          "Flagellar centriole": 228,
          "Focal adhesion sites": 290,
          "Golgi apparatus": 2504,
          "Immunoglobulin genes": 142,
          "Intermediate filaments": 292,
          "Intracellular and membrane": 609,
          "Kinetochore": 16,
          "Lipid droplets": 80,
          "Lysosomes": 40,
          "Microtubule ends": 14,
          "Microtubules": 684,
          "Mid piece": 678,
          "Midbody": 106,
          "Midbody ring": 46,
          "Mitochondria": 2224,
          "Mitotic chromosome": 156,
          "Mitotic spindle": 320,
          "Nuclear bodies": 1228,
          "Nuclear membrane": 578,
          "Nuclear speckles": 984,
          "Nucleoli": 2192,
          "Nucleoli fibrillar center": 642,
          "Nucleoli rim": 300,
          "Nucleoplasm": 12334,
          "Perinuclear theca": 136,
          "Peroxisomes": 48,
          "Plasma membrane": 4464,
          "Primary cilium": 908,
          "Primary cilium tip": 258,
          "Primary cilium transition zone": 190,
          "Principal piece": 714,
          "Rods & Rings": 34,
          "Secreted - unknown location": 113,
          "Secreted in brain": 76,
          "Secreted in female reproductive system": 38,
          "Secreted in male reproductive system": 121,
          "Secreted in other tissues": 283,
          "Secreted to blood": 778,
          "Secreted to digestive system": 92,
          "Secreted to extracellular matrix": 234,
          "Vesicles": 4868
        },
        "mapping_sources": {
          "go_release": "releases/2026-05-19",
          "hpa_release": "HPA 25.1",
          "uniprot_subcell_release": "current"
        },
        "protein_mapping": {
          "ambiguous_uniprot_accessions": 19736,
          "hpa_uniprot_expansion_audit": {
            "ambiguous_hpa_distinct_protein_component_edges": 272493,
            "ambiguous_hpa_expanded_protein_rows": 529877,
            "ambiguous_hpa_label_assignments": 49842,
            "ambiguous_hpa_source_rows": 12630,
            "current_policy": "all ENSP protein nodes linked to an HPA UniProt accession are emitted as protein localization edges",
            "promotion_recommendation": "review canonical ENSP policy before promotion: all ENSP isoforms preserves accession crossrefs but can multiply HPA evidence; canonical ENSP only reduces expansion but needs an approved canonical-protein selector",
            "top_ambiguous_uniprots_in_hpa_rows": [
              [
                "Q5JQC4",
                12
              ],
              [
                "P68431",
                10
              ],
              [
                "Q9ULZ0",
                6
              ],
              [
                "P62807",
                5
              ],
              [
                "P0C0S8",
                5
              ],
              [
                "P0DN86",
                3
              ],
              [
                "Q71DI3",
                3
              ],
              [
                "A1L429",
                3
              ],
              [
                "Q99666",
                2
              ],
              [
                "O95925",
                2
              ],
              [
                "Q9BTE6",
                2
              ],
              [
                "P43362",
                2
              ],
              [
                "Q02325",
                2
              ],
              [
                "Q92843",
                2
              ],
              [
                "Q9BQ83",
                2
              ],
              [
                "P84243",
                2
              ],
              [
                "Q15415",
                2
              ],
              [
                "Q96LI6",
                2
              ],
              [
                "Q9UBD0",
                2
              ],
              [
                "Q96QH8",
                2
              ]
            ]
          },
          "protein_node_rows": 233995,
          "uniprot_accessions": 80388
        },
        "source_rows": {
          "hpa_rows": 20162,
          "hpa_rows_with_subcellular_or_secretome_label": 15010,
          "hpa_rows_without_protein_mapping": 291,
          "top_unmapped_uniprots": [
            [
              "<missing_uniprot>",
              282
            ],
            [
              "Q6ZVL6",
              1
            ],
            [
              "Q96G42",
              1
            ],
            [
              "Q9BVW6",
              1
            ],
            [
              "Q9BV90",
              1
            ],
            [
              "C9JG80",
              1
            ],
            [
              "A6NDB9",
              1
            ],
            [
              "P0DP08",
              1
            ],
            [
              "Q8NFD4",
              1
            ],
            [
              "Q6ZMK1",
              1
            ]
          ]
        }
      }
    },
    "nodes": {
      "cellular_component": 60
    },
    "protein_located_in_cellular_component": {
      "duplicate_edges": 0,
      "edge_rows": 276356,
      "edges_without_evidence": 0,
      "evidence_rows": 536967,
      "evidence_without_edge": 0,
      "x_protein_antijoin_id_or_uniprot": 0,
      "y_component_antijoin": 0
    },
    "validation": {
      "checks": {
        "component_endpoint_antijoin": {
          "missing_component_nodes": 0
        },
        "evidence_support": {
          "edges_without_evidence": 0,
          "evidence_without_edge": 0
        },
        "go_term_semantics": {
          "invalid_go_node_examples": [],
          "invalid_go_nodes": 0
        },
        "hierarchy_semantics": {
          "broad_context_edges": 0
        },
        "protein_endpoint_antijoin": {
          "missing_protein_nodes": 0
        }
      },
      "counts": {
        "cellular_component_nodes": 60,
        "distinct_hpa_labels": 59,
        "go_mapped_nodes": 40,
        "hierarchy_edges": 14,
        "hierarchy_evidence": 14,
        "hpa_local_nodes": 18,
        "protein_location_edges": 276356,
        "protein_location_evidence": 536967
      },
      "label_counts": {
        "Acrosome": 220,
        "Actin filaments": 504,
        "Aggresome": 38,
        "Annulus": 98,
        "Basal body": 876,
        "Calyx": 138,
        "Cell Junctions": 650,
        "Centriolar satellite": 438,
        "Centrosome": 1000,
        "Cleavage furrow": 4,
        "Connecting piece": 178,
        "Cytokinetic bridge": 464,
        "Cytoplasmic bodies": 146,
        "Cytosol": 10352,
        "End piece": 370,
        "Endoplasmic reticulum": 1120,
        "Endosomes": 32,
        "Equatorial segment": 162,
        "Flagellar centriole": 228,
        "Focal adhesion sites": 290,
        "Golgi apparatus": 2504,
        "Immunoglobulin genes": 142,
        "Intermediate filaments": 292,
        "Intracellular and membrane": 609,
        "Kinetochore": 16,
        "Lipid droplets": 80,
        "Lysosomes": 40,
        "Microtubule ends": 14,
        "Microtubules": 684,
        "Mid piece": 678,
        "Midbody": 106,
        "Midbody ring": 46,
        "Mitochondria": 2224,
        "Mitotic chromosome": 156,
        "Mitotic spindle": 320,
        "Nuclear bodies": 1228,
        "Nuclear membrane": 578,
        "Nuclear speckles": 984,
        "Nucleoli": 2192,
        "Nucleoli fibrillar center": 642,
        "Nucleoli rim": 300,
        "Nucleoplasm": 12334,
        "Perinuclear theca": 136,
        "Peroxisomes": 48,
        "Plasma membrane": 4464,
        "Primary cilium": 908,
        "Primary cilium tip": 258,
        "Primary cilium transition zone": 190,
        "Principal piece": 714,
        "Rods & Rings": 34,
        "Secreted - unknown location": 113,
        "Secreted in brain": 76,
        "Secreted in female reproductive system": 38,
        "Secreted in male reproductive system": 121,
        "Secreted in other tissues": 283,
        "Secreted to blood": 778,
        "Secreted to digestive system": 92,
        "Secreted to extracellular matrix": 234,
        "Vesicles": 4868
      },
      "mapping_sources": {
        "go_release": "releases/2026-05-19",
        "hpa_release": "HPA 25.1",
        "uniprot_subcell_release": "current"
      },
      "protein_mapping": {
        "ambiguous_uniprot_accessions": 19736,
        "hpa_uniprot_expansion_audit": {
          "ambiguous_hpa_distinct_protein_component_edges": 272493,
          "ambiguous_hpa_expanded_protein_rows": 529877,
          "ambiguous_hpa_label_assignments": 49842,
          "ambiguous_hpa_source_rows": 12630,
          "current_policy": "all ENSP protein nodes linked to an HPA UniProt accession are emitted as protein localization edges",
          "promotion_recommendation": "review canonical ENSP policy before promotion: all ENSP isoforms preserves accession crossrefs but can multiply HPA evidence; canonical ENSP only reduces expansion but needs an approved canonical-protein selector",
          "top_ambiguous_uniprots_in_hpa_rows": [
            [
              "Q5JQC4",
              12
            ],
            [
              "P68431",
              10
            ],
            [
              "Q9ULZ0",
              6
            ],
            [
              "P62807",
              5
            ],
            [
              "P0C0S8",
              5
            ],
            [
              "P0DN86",
              3
            ],
            [
              "Q71DI3",
              3
            ],
            [
              "A1L429",
              3
            ],
            [
              "Q99666",
              2
            ],
            [
              "O95925",
              2
            ],
            [
              "Q9BTE6",
              2
            ],
            [
              "P43362",
              2
            ],
            [
              "Q02325",
              2
            ],
            [
              "Q92843",
              2
            ],
            [
              "Q9BQ83",
              2
            ],
            [
              "P84243",
              2
            ],
            [
              "Q15415",
              2
            ],
            [
              "Q96LI6",
              2
            ],
            [
              "Q9UBD0",
              2
            ],
            [
              "Q96QH8",
              2
            ]
          ]
        },
        "protein_node_rows": 233995,
        "uniprot_accessions": 80388
      },
      "source_rows": {
        "hpa_rows": 20162,
        "hpa_rows_with_subcellular_or_secretome_label": 15010,
        "hpa_rows_without_protein_mapping": 291,
        "top_unmapped_uniprots": [
          [
            "<missing_uniprot>",
            282
          ],
          [
            "Q6ZVL6",
            1
          ],
          [
            "Q96G42",
            1
          ],
          [
            "Q9BVW6",
            1
          ],
          [
            "Q9BV90",
            1
          ],
          [
            "C9JG80",
            1
          ],
          [
            "A6NDB9",
            1
          ],
          [
            "P0DP08",
            1
          ],
          [
            "Q8NFD4",
            1
          ],
          [
            "Q6ZMK1",
            1
          ]
        ]
      }
    }
  },
  "intact": {
    "duplicate_edges": 0,
    "edge_rows": 34515,
    "edges_without_evidence": 0,
    "endpoint_antijoin_scope": "no canonical node-root in accepted bounded artifact; not counted as canonical-grade endpoint validation",
    "evidence_rows": 46425,
    "evidence_without_edge": 0,
    "negative_evidence_rows": 496,
    "policy_validation_summary": {
      "active_evidence_mi0914_only": 0,
      "active_evidence_with_mi0914_any": 0,
      "active_self_loop_edges": 10,
      "active_self_loop_evidence_rows": 18,
      "active_self_loop_policy_counts": {
        "accepted_explicit_homodimer_support": 18
      },
      "artifact": ".omoc/staging/intact-protein-interactions-policy-fixed-20260622T122314Z-bounded100k",
      "edge_rows": 34515,
      "evidence_rows": 46425,
      "negative_evidence_rows": 496,
      "ok": true,
      "rejected_mi0914_only_rows": 28198,
      "rejected_rows": 53575,
      "rejected_self_loop_payloads_with_raw_mitab": 19,
      "rejected_self_loop_requires_homodimer_support_rows": 19,
      "rejected_self_loop_rows_with_source_ids": 19,
      "rejected_source_payload_missing_raw_mitab": 0
    },
    "rejected_rows": 53575,
    "validation": {
      "checks": {
        "duplicate_policy": {
          "duplicate_edges": 0,
          "ok": true,
          "policy": "undirected pairs sorted after endpoint mapping and deduplicated for edges; evidence remains row-level",
          "self_loops": [
            "O00206",
            "P29972-1",
            "P42224-2",
            "Q01105-2",
            "Q01196",
            "Q16760-2",
            "Q92838-1",
            "Q92838-3",
            "Q9Y371-2",
            "UBIQ_HUMAN"
          ]
        },
        "evidence_fields": {
          "missing_payload_fields": {
            "confidence_values": 0,
            "detection_method": 0,
            "feature_side_table_refs": 0,
            "interaction_type": 0,
            "participant_identification_method_a": 0,
            "participant_identification_method_b": 0,
            "publication_ids": 0,
            "selected_interactor_a_namespace": 0,
            "selected_interactor_b_namespace": 0,
            "source_database": 0,
            "source_interactor_a_id": 0,
            "source_interactor_b_id": 0,
            "taxid_interactor_a": 0,
            "taxid_interactor_b": 0
          },
          "ok": true,
          "positive_evidence_rows_marked_negative": []
        },
        "evidence_support": {
          "ok": true,
          "unsupported_edges": []
        }
      },
      "edge_rows": 34515,
      "evidence_rows": 46425,
      "mapping_supplied": false,
      "negative_evidence_rows": 496,
      "ok": true,
      "rejected_rows": 53575,
      "source_counts": {
        "accepted_evidence_rows": 46425,
        "input_rows": 100946,
        "negative_rows": 946,
        "rejected_interaction_type_association_too_broad": 18684,
        "rejected_interaction_type_not_allowlisted": 3106,
        "rejected_non_human_or_cross_species": 23733,
        "rejected_non_protein_interactor_type": 6460,
        "rejected_self_loop_requires_homodimer_support": 19,
        "rejected_unsupported_endpoint_namespace": 1573
      },
      "warnings": [
        "No node_root supplied; endpoint anti-join was limited to UniProt namespace checks and staged IDs are UniProt accessions. Supply --node-root for canonical protein node validation."
      ]
    }
  },
  "lncrna": {
    "active_edges": {
      "lncrna_associated_disease": 0
    },
    "candidate_edges": {
      "lncrna_associated_disease": 6598
    },
    "nodes": {
      "lncrna": 197208
    },
    "rejected_or_needs_review": 6598,
    "source_audit": [
      {
        "chosen_for_pilot": true,
        "decision": "use as first safe lncRNA node catalog source",
        "download_url": "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_48/gencode.v48.long_noncoding_RNAs.gtf.gz",
        "endpoint_resolvability": "ENSG/ENST IDs can be anti-joined to cached KG transcript/gene nodes",
        "license_status": "GENCODE/Ensembl public data; redistribution requires Ensembl/GENCODE attribution/citation; safe for staged internal pilot",
        "purpose": "lncrna nodes",
        "schema_status": "GTF with gene/transcript features and gene_id/transcript_id/gene_name/gene_type/transcript_type tags",
        "source": "GENCODE",
        "version": "GENCODE human release 48, GRCh38, long_noncoding_RNAs GTF"
      },
      {
        "chosen_for_pilot": false,
        "decision": "do not block GENCODE node pilot; add RNAcentral xrefs in a follow-up once exact mapping file is pinned",
        "download_url": "https://rnacentral.org/help/public-database (current release FTP/static mappings; exact GENCODE mapping endpoint not resolved by this run)",
        "endpoint_resolvability": "defer until exact mapping export resolves ENST/ENSG to URS",
        "license_status": "RNAcentral states CC0 for RNAcentral data",
        "purpose": "lncrna xrefs / possible primary RNA IDs",
        "schema_status": "database mapping endpoint for GENCODE/RNAcentral returned 404 for probed paths; use after exact file path is pinned",
        "source": "RNAcentral",
        "version": "current_release unresolved in automated probe"
      },
      {
        "chosen_for_pilot": true,
        "decision": "stage as candidate disease-association evidence; do not promote unresolved disease rows",
        "download_url": "http://www.rnanut.net/lncrnadisease/static/download/website_causal_data.tsv",
        "endpoint_resolvability": "lncRNA symbols can map to GENCODE node gene_symbol; disease names are only partially resolvable against cached disease node names/IDs",
        "license_status": "download is public; explicit redistribution/commercial license not found in probed pages, so keep staged/candidate pending review",
        "purpose": "lncrna_associated_disease candidates",
        "schema_status": "TSV fields include ncRNA Symbol, ncRNA Category, Species, Disease Name, Sample, Dysfunction Pattern, Validated Method, Description, Clinical Application, Causality, Causal Description, PubMed ID",
        "source": "LncRNADisease v3",
        "version": "LncRNADisease v3 website_causal_data.tsv as downloaded at build time"
      },
      {
        "chosen_for_pilot": false,
        "decision": "defer until exact downloadable export and terms are available",
        "download_url": "https://bio-bigdata.hrbmu.edu.cn/Lnc2Cancer/ / bio-bigdata mirror",
        "endpoint_resolvability": "not assessed because exact export was not reachable",
        "license_status": "not verified",
        "purpose": "lncrna disease/cancer associations",
        "schema_status": "home/download probes returned 404/403/connection failure in this run",
        "source": "Lnc2Cancer",
        "version": "not pinned"
      },
      {
        "chosen_for_pilot": false,
        "decision": "unsafe for pilot from this environment",
        "download_url": "http://www.lncrna2target.org/ (domain redirected to unrelated site in this run)",
        "endpoint_resolvability": "not assessed",
        "license_status": "not verified",
        "purpose": "lncrna_regulates_gene perturbation/regulation",
        "schema_status": "not reachable; redirect to unrelated alittledelightful.com",
        "source": "LncRNA2Target",
        "version": "not pinned"
      },
      {
        "chosen_for_pilot": false,
        "decision": "defer until site/export is reachable",
        "download_url": "http://bio-annotation.cn/lnctard/",
        "endpoint_resolvability": "not assessed",
        "license_status": "not verified",
        "purpose": "lncrna_regulates_gene curated regulation",
        "schema_status": "connection refused in this run",
        "source": "LncTarD / LncTarD 2.0",
        "version": "not pinned"
      },
      {
        "chosen_for_pilot": false,
        "decision": "second-stage source after support-type and license audit; do not promote massive predicted interaction sets blindly",
        "download_url": "https://ngdc.cncb.ac.cn/lncbook/downloads (e.g. LncBookv2.0_GENCODEv47_GRCh38.gtf.gz, lncRNA_LncBookv2.1_GRCh38.gtf.gz, lncrna_rbp_LncBook2.0.csv.gz)",
        "endpoint_resolvability": "likely ENST/GENCODE for catalog; RBP/protein endpoint mapping requires schema audit",
        "license_status": "terms/citation need manual review before redistribution/promotion",
        "purpose": "lncrna catalog and lncRNA-protein/miRNA interactions",
        "schema_status": "download links reachable; interaction support/predicted-vs-experimental columns not inspected in this pilot",
        "source": "LncBook 2.x",
        "version": "download page exposes v1.9/v2.0/v2.1 and GENCODE v47/v34 files"
      },
      {
        "chosen_for_pilot": false,
        "decision": "defer; use only experimental direct interaction subset if source-of-source provenance is clear",
        "download_url": "NGDC/NPInter pages; probed legacy direct file returned server 505 and home returned 404",
        "endpoint_resolvability": "not assessed",
        "license_status": "not verified",
        "purpose": "lncrna-protein or ncRNA interaction subset",
        "schema_status": "not reachable via probed direct URL",
        "source": "NPInter v5",
        "version": "not pinned"
      },
      {
        "chosen_for_pilot": false,
        "decision": "defer interactions; ceRNA/correlation modules explicitly excluded from active mechanism edges",
        "download_url": "https://rnasysu.com/encori/rbpClipRNA.php?source=lncRNA and moduleDownload.php?source=rbpClipRNA&type=txt&value=hg38;lncRNA;all;1;0;MALAT1",
        "endpoint_resolvability": "RBP-lncRNA endpoints require RBP/protein and lncRNA schema audit",
        "license_status": "ENCORI page terms need review; page is public and API documented",
        "purpose": "RBP-lncRNA / miRNA-lncRNA / ceRNA context",
        "schema_status": "module/API reachable but examples are query-scoped, not a bulk pinned export",
        "source": "ENCORI/starBase",
        "version": "web/API current at probe time; exact bulk export not pinned"
      }
    ],
    "validation": {
      "created_at": "2026-06-22T13:50:41+00:00",
      "endpoint_validation": {
        "active_edge_endpoint_anti_join": {
          "checked": true,
          "missing_x": 0,
          "missing_y": 0,
          "note": "no active edges materialized unless --allow-unreviewed-edges is set"
        },
        "lncrna_gene_vs_cached_gene_nodes": {
          "checked": true,
          "missing_count": 1680,
          "note": "existing gene node cache is NCBI-centric; ENSG direct ID anti-join expected to miss",
          "sample_missing": [
            "ENSG00000056678",
            "ENSG00000196299",
            "ENSG00000203463",
            "ENSG00000206232",
            "ENSG00000206296",
            "ENSG00000206446",
            "ENSG00000206504",
            "ENSG00000206508",
            "ENSG00000215523",
            "ENSG00000220890",
            "ENSG00000223364",
            "ENSG00000223405",
            "ENSG00000223454",
            "ENSG00000223557",
            "ENSG00000223577",
            "ENSG00000223661",
            "ENSG00000223747",
            "ENSG00000223827",
            "ENSG00000223868",
            "ENSG00000224056"
          ]
        },
        "lncrna_transcript_vs_cached_transcript_nodes": {
          "checked": true,
          "missing_count": 6286,
          "sample_missing": [
            "ENST00000304890",
            "ENST00000324858",
            "ENST00000340373",
            "ENST00000354576",
            "ENST00000366281",
            "ENST00000376242",
            "ENST00000378770",
            "ENST00000383511",
            "ENST00000383616",
            "ENST00000383625",
            "ENST00000393394",
            "ENST00000395280",
            "ENST00000400508",
            "ENST00000407772",
            "ENST00000411477",
            "ENST00000411485",
            "ENST00000411514",
            "ENST00000411600",
            "ENST00000411692",
            "ENST00000411707"
          ]
        }
      },
      "evidence_support": {
        "candidate_rows_have_pmid_or_description": true,
        "candidate_rows_have_source_record_id": true,
        "edge_rows_supported_by_candidate_rows": true
      },
      "node_counts": {
        "lncrna_gene_records": 37576,
        "lncrna_transcript_nodes": 197208,
        "unique_biotypes": {
          "TEC": 1128,
          "lncRNA": 195156,
          "retained_intron": 924
        },
        "unique_gene_symbols": 36998
      },
      "ok": true,
      "output": ".omoc/staging/source-native-expansion/lncrna-l2f-gencode-lncrnadisease-20260622",
      "policy": {
        "canonical_promotion_recommendation": "Do not promote canonical lncRNA disease edges yet. Promote GENCODE lncrna nodes after schema review; keep LncRNADisease rows as candidates until license terms and disease name-to-MONDO/MeSH mapping are reviewed.",
        "ceRNA_correlation_policy": "ceRNA/correlation-only rows are excluded from active mechanism edges; disease associations are not converted to lncrna_regulates_gene."
      },
      "raw_files": {
        ".omoc/source-cache/lncrna-l2f/raw/gencode.v48.long_noncoding_RNAs.gtf.gz": {
          "bytes": 13327329,
          "sha256": "7b6bc2edf9029dd1f5fc064246fb025f22577a40b824c4be25ce4793ab8d5ebc",
          "url": "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_48/gencode.v48.long_noncoding_RNAs.gtf.gz"
        },
        ".omoc/source-cache/lncrna-l2f/raw/website_causal_data.tsv": {
          "bytes": 7781291,
          "sha256": "defbc976caa1d7c2267835addd32cef37a81b5c1bd103d1ca9ac482954772c1f",
          "url": "http://www.rnanut.net/lncrnadisease/static/download/website_causal_data.tsv"
        }
      },
      "relation_counts": {
        "active_edge_rows": 0,
        "allow_unreviewed_edges": false,
        "candidate_rows": 6598,
        "disease_name_map_entries": 83968,
        "human_lncrna_causal_rows": 6598,
        "needs_review_or_rejected_rows": 6598,
        "raw_causal_rows": 9719,
        "unique_disease_names": 305,
        "unique_lncrna_symbols": 1688,
        "unique_symbols_with_single_gencode_transcript": 19707
      }
    }
  },
  "mirna": {
    "build_summary": {
      "counts": {
        "alias_rows": 644,
        "mirna_node_rows": 3929,
        "mirna_targets_gene_edges": 351958,
        "mirna_targets_gene_evidence": 868896,
        "mirna_targets_transcript_edges": 0,
        "mirna_targets_transcript_evidence": 0,
        "missing_gene_targets": 42950,
        "missing_transcript_targets": 0,
        "processing_edge_rows": 1707,
        "rejected_alias_rows": 0,
        "skipped_target_rows": 42950,
        "source_mapping_rows": 644,
        "target_source_rows": 911846,
        "transcript_rows": 507365
      },
      "created_at": "2026-06-22T10:21:44.236101+00:00",
      "endpoint_anti_joins": {
        "gene_nodes_checked": true,
        "gene_targets_missing_from_gene_nodes": 42950,
        "mirna_nodes_checked": true,
        "processing_edges_missing_x_mirna_nodes": 0,
        "processing_edges_missing_y_mirna_nodes": 0,
        "transcript_nodes_checked": true,
        "transcript_targets_missing_from_transcript_nodes": 0
      },
      "inputs": {
        "gene_nodes_path": ".omoc/gcs-cache/kg-v2/nodes/gene.parquet",
        "mirna_catalog_path": ".omoc/source-cache/mirna-real/prepared/mirbase_catalog.parquet",
        "source_audit_path": ".omoc/source-cache/mirna-real/prepared/source_audit.json",
        "target_source_paths": [
          ".omoc/source-cache/mirna-real/prepared/mirtarbase_targets_gene_normalized.parquet"
        ],
        "transcript_mirbase_mapping_path": ".omoc/source-cache/mirna-real/prepared/transcript_mirbase_mapping.parquet",
        "transcript_nodes_path": ".omoc/gcs-cache/kg-v2/nodes/transcript.parquet"
      },
      "output_dir": ".omoc/staging/mirna-targets-real-2026-06-22",
      "policy": {
        "aliases_require_true_one_to_one": true,
        "canonical_writes": false,
        "no_gene_to_transcript_forcing": true,
        "transcript_targets_require_existing_enst": true
      },
      "source_gate": {
        "approved_for_staged_source_backed_sample": true,
        "audit_path": ".omoc/source-cache/mirna-real/prepared/source_audit.json",
        "deferred_sources": [
          {
            "approval_status": "defer",
            "endpoint_policy": "expected gene-level MTIs, but not ingested in this tranche",
            "license_checked": false,
            "license_note": "Homepage/download-data form inspected; static bulk data URL not identified in this run. Defer ingestion until terms/direct export are confirmed.",
            "name": "DIANA-TarBase v8",
            "schema_checked": false,
            "url": "https://dianalab.e-ce.uth.gr/html/diana/web/index.php?r=tarbasev8%2Fdownloaddataform"
          }
        ],
        "sources": [
          {
            "approval_status": "approved",
            "endpoint_policy": "catalog and precursor/mature source-native identifiers; not target evidence",
            "license_checked": true,
            "license_note": "miRBase public download; cite miRBase. Terms require citation, no credential gate observed for miRNA.dat.",
            "name": "miRBase miRNA.dat",
            "schema_checked": true,
            "url": "https://mirbase.org/download/miRNA.dat"
          },
          {
            "approval_status": "approved",
            "endpoint_policy": "ENST transcript to miRBase/RNAcentral aliases only when BioMart gives direct xrefs",
            "license_checked": true,
            "license_note":
```

## Schema compatibility gate

```json
{
  "active_schema_node_types": {
    "cell_type": true,
    "cellular_component": false,
    "gene": true,
    "lncrna": false,
    "mirna": false,
    "molecule": true,
    "protein": true,
    "protein_complex": false,
    "ptm_site": false,
    "transcript": true
  },
  "active_schema_relations": {
    "cell_type_responds_to_molecule": true,
    "cellular_component_subtype_of_cellular_component": false,
    "disease_associated_protein": true,
    "gene_paralog_gene": false,
    "lncrna_associated_disease": false,
    "mirna_regulates_gene": false,
    "mirna_targets_gene": false,
    "molecule_synergizes_molecule": true,
    "molecule_targets_protein": true,
    "pathway_contains_protein": true,
    "protein_complex_part_of_protein_complex": false,
    "protein_has_ptm_site": false,
    "protein_interacts_protein": true,
    "protein_located_in_cellular_component": false,
    "protein_part_of_protein_complex": false,
    "transcript_interacts_protein": true
  },
  "note": "Active kg_schema.py currently lacks several Part 2 node types/relations that are only planned in docs/later_node_edge_families_plan.md; staged artifacts using absent schema elements are not promote_now candidates."
}
```

## Pharmacology / metadata-feature local artifacts

| Batch | Exists | Files | Notable Parquet counts |
|---|---:|---:|---|
| `opentargets_clinical_drug_evidence` | True | 13 | evidence/molecule_treats_disease.parquet: 481, readback/molecule_treats_disease.parquet: 481 |
| `molecule_synergizes_evidence` | True | 2 | - |
| `disease_associated_protein` | True | 8 | diagnostics/rejected_source_rows.parquet: 26959, edges/disease_associated_protein.parquet: 3243, evidence/disease_associated_protein.parquet: 35839 |
| `reactome_pathway_contains_protein` | True | 7 | edges/pathway_contains_protein.parquet: 15436, evidence/pathway_contains_protein.parquet: 18068, evidence_canonical/pathway_contains_protein.parquet: 18068, mappings/reactome_pathway_contains_protein_rejected.parquet: 141046 |
| `molecule_targets_protein_chembl` | True | 9 | edges/molecule_targets_protein.parquet: 2119, evidence/molecule_targets_protein.parquet: 2132, source_rows/molecule_targets_protein.parquet: 2132 |
| `cellosaurus_cell_line_metadata` | True | 11 | edges/cell_line_derived_from_cell_type.parquet: 65, edges/cell_line_models_disease.parquet: 983, evidence/cell_line_derived_from_cell_type.parquet: 65, evidence/cell_line_models_disease.parquet: 1218 |
| `cell_line_assays` | True | 9 | edges/cell_line_expresses_protein.parquet: 3083, edges/cell_line_gene_essentiality.parquet: 1433992, edges/cell_line_responds_to_molecule.parquet: 11040, evidence/cell_line_expresses_protein.parquet: 3090, evidence/cell_line_gene_essentiality.parquet: 1433992, evidence/cell_line_responds_to_molecule.parquet: 11713 |
| `disease_tissue_phenotype_context` | True | 12 | edges/disease_comorbid_disease.parquet: 0, edges/disease_manifests_in_tissue.parquet: 19, edges/phenotype_observed_in_tissue.parquet: 0, evidence/disease_comorbid_disease.parquet: 0, evidence/disease_manifests_in_tissue.parquet: 29, evidence/phenotype_observed_in_tissue.parquet: 0, reports/rejected_candidates.parquet: 2, reports/source_audit.parquet: 25 |
| `textual_summary_features` | True | 9 | features/disease_textual_summary.parquet: 26395, features/gene_textual_summary.parquet: 212029, features/molecule_textual_summary.parquet: 22230, features/pathway_textual_summary.parquet: 37492, features/protein_textual_summary.parquet: 228, features/tissue_textual_summary.parquet: 11942 |
| `paper_dataset_provenance` | True | 18 | edges/dataset_contains_cell_line.parquet: 1183, edges/dataset_contains_cell_type.parquet: 100, edges/dataset_contains_disease.parquet: 0, edges/dataset_contains_molecule.parquet: 1000, edges/dataset_contains_tissue.parquet: 27, edges/paper_cites_paper.parquet: 16, edges/paper_produced_dataset.parquet: 4, evidence/dataset_contains_cell_line.parquet: 1183 |
| `cell_type_context_relations` | True | 6 | edges/cell_type_found_in_tissue.parquet: 958, edges/cell_type_subtype_of_cell_type.parquet: 4526, evidence/cell_type_found_in_tissue.parquet: 958, evidence/cell_type_subtype_of_cell_type.parquet: 4526 |

## Commands/tests run

```bash
kanban_show t_61fabcf3
gsutil ls -l <10 non-ReMap prefixes>/**
gsutil -m rsync -r <10 non-ReMap prefixes> /tmp/non_remap_part2_validation_t_61fabcf3/gcs/<tranche>
uv run python .omoc/scripts/validate_non_remap_part2_promotion.py -> wrote markdown/json reports; recommended_promotion_count=1
uv run python -m py_compile .omoc/scripts/validate_non_remap_part2_promotion.py manage_db/build_intact_protein_interactions.py manage_db/prepare_real_mirna_sources.py manage_db/build_staged_mirna_targets.py manage_db/build_hpa_cellular_components.py manage_db/build_complex_portal_protein_complexes.py manage_db/build_uniprot_ptm_sites.py manage_db/build_opentargets_gene_paralogs.py manage_db/build_staged_rbp_rna_interactions.py .omoc/scripts/stage_lncrna_l2f.py artifacts/scripts/stage_cell_type_responds_to_molecule_sciplex2.py -> exit 0
uv run --group dev pytest tests/test_build_intact_protein_interactions.py tests/test_biogrid_categorized_stage.py tests/test_prepare_real_mirna_sources.py tests/test_build_staged_mirna_targets.py tests/test_stage_lncrna_l2f.py tests/test_build_staged_rbp_rna_interactions.py tests/test_build_hpa_cellular_components.py tests/test_build_complex_portal_protein_complexes.py tests/test_build_uniprot_ptm_sites.py tests/test_stage_cell_type_responds_to_molecule_sciplex2.py -q -> 34 passed in 1.02s
```

Targeted py_compile/pytest smoke commands were run after report generation; see final Kanban handoff for pass/fail output.
