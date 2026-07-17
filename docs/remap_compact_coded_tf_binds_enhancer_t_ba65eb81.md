# Compact coded ReMap/CRM `tf_binds_enhancer` support prototype

Kanban task: `t_ba65eb81`  
Status: `review-required`; bounded prototype; no canonical writes.

## What changed conceptually

The earlier 24.45B number came from the full CRM validation's TF x CRM interval x enhancer candidate support product: `24453482386` rows if every assignment were written as a conventional edge/evidence row. That is a naive materialization artifact for the corrected representation. The compact-coded design stores per-enhancer integer arrays such as `support_codes=[1,2,8,...]` and resolves those codes through a dictionary table. Queries can still expand arrays on demand, but the stored artifact is not a permanent 24.45B-row table.

## Prototype outputs

- Enhancer arrays: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_ba65eb81/features/tf_binds_enhancer_enhancer_support_codes.parquet`
- Support-code dictionary: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_ba65eb81/features/tf_binds_enhancer_support_code_dictionary.parquet`
- Per-TF summary: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_ba65eb81/features/tf_binds_enhancer_support_code_tf_summary.parquet`
- Context/evidence-class summary: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_ba65eb81/features/tf_binds_enhancer_support_code_context_summary.parquet`
- Query examples: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_ba65eb81/reports/query_examples.sql`
- JSON report: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_ba65eb81/reports/remap_compact_coded_support_report.json`

## Prototype counts

- enhancer rows: 1,199
- support-code dictionary rows: 2,199
- support-code assignments stored inside arrays: 2,199
- distinct TF genes: 305
- observed ReMap peak codes: 600
- CRM aggregate/reconstructed codes: 1,050
- motif codes: 549

## Context-slot coverage

The bounded inputs preserve direct schema slots for `cell_line`, `tissue`, `cell_type`, antibody, and protein metadata, but those direct slots are currently null in this compact prototype. Query examples therefore include both exact direct-slot predicates and coverage-count queries, and use `remap_biotype` / `context_note` as the honest fallback context dimensions available in the bounded data.

```json
{
  "cell_line_nonnull": 0,
  "tissue_nonnull": 0,
  "cell_type_nonnull": 0,
  "antibody_target_nonnull": 0,
  "antibody_id_nonnull": 0,
  "antibody_lot_nonnull": 0,
  "protein_accession_nonnull": 0,
  "antibody_or_protein_nonnull": 0,
  "remap_source_accession_nonnull": 1040,
  "remap_biotype_nonnull": 1040,
  "remap_accession_or_biotype_codes": 1040,
  "context_note_nonnull": 1519,
  "support_class_nonnull": 2199,
  "support_class_counts": {
    "crm_interval_tf_support": 750,
    "observed_peak_support": 600,
    "motif_support": 440,
    "bounded_crm_reconstructed_support": 300,
    "motif_predicted_support": 109
  }
}
```

Example enhancer rows:

```text
                     enhancer_id  support_code_count                                                                                                                                                                                                                                                                                                                                                                                                                                                support_codes                                                        tf_symbols
2ee5d793fe949f6d7a42350e77d431de                  74 [2084, 2085, 2086, 2087, 2088, 2089, 2090, 2091, 2092, 2093, 2094, 2095, 2096, 2097, 2098, 2099, 2100, 2101, 2102, 2103, 2104, 2105, 2106, 2107, 2108, 2109, 2110, 2111, 2112, 2113, 2114, 2115, 2116, 2117, 2118, 2119, 2120, 2121, 2122, 2123, 2124, 2125, 2126, 2127, 2128, 2143, 2144, 2145, 2146, 2147, 2148, 2149, 2150, 2151, 2152, 2153, 2154, 2155, 2156, 2157, 2158, 2159, 2160, 2161, 2162, 2163, 2164, 2165, 2166, 2167, 2168, 2169, 2175, 2176]        [ERF, ERG, GATA3, GRHL2, HIC1, KLF4, TEAD4, ZEB2, ZSCAN29]
b2592fe136672577524294adef0e2578                  70                         [1938, 1939, 1940, 1941, 1942, 1943, 1944, 1945, 1946, 1947, 1948, 1949, 1950, 1951, 1952, 1953, 1954, 1955, 1956, 1957, 1958, 1959, 1960, 1961, 1962, 1963, 2044, 2045, 2046, 2047, 2048, 2049, 2050, 2051, 2052, 2053, 2054, 2055, 2056, 2057, 2058, 2059, 2060, 2061, 2062, 2063, 2064, 2065, 2066, 2067, 2068, 2069, 2070, 2071, 2072, 2073, 2074, 2075, 2076, 2077, 2078, 2079, 2080, 2081, 2082, 2083, 2129, 2130, 2131, 2132]        [ERF, ERG, GATA3, GRHL2, HIC1, KLF4, ZBTB26, ZEB2, ZNF189]
cbc1102e07b8296332968063493fe865                  45                                                                                                                                                                               [1987, 1988, 1989, 1990, 1991, 1992, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030, 2031]                        [ERF, ERG, GATA3, GRHL2, HIC1, KLF4, ZEB1]
43452d249aeeffea37a528d727cfee34                  44                                                                                                                                                                                     [1981, 1982, 1983, 1984, 1985, 1986, 2032, 2033, 2034, 2035, 2036, 2037, 2038, 2039, 2040, 2041, 2042, 2043, 2170, 2171, 2172, 2177, 2178, 2179, 2180, 2181, 2182, 2183, 2184, 2185, 2186, 2187, 2188, 2189, 2190, 2191, 2192, 2193, 2194, 2195, 2196, 2197, 2198, 2199] [ERF, ERG, GATA3, HIC1, KLF4, TEAD4, ZBTB26, ZEB1, ZEB2, ZSCAN29]
468ac972cb0fa746fafba94db81ea25c                  32                                                                                                                                                                                                                                                             [1796, 1797, 1798, 1799, 1800, 1801, 1802, 1803, 1804, 1805, 1806, 1807, 1808, 1809, 1810, 1811, 1812, 1813, 1814, 1815, 1816, 1817, 1818, 1819, 1820, 1821, 1822, 1823, 1824, 1825, 1826, 1827]                                                     [ATF2, STAT3]
```

Evidence-class summary:

```text
                   evidence_class  support_code_assignments  distinct_enhancers  distinct_codes
           crm_aggregated_support                       750                 384             750
            observed_binding_peak                       600                 543             600
                    motif_support                       440                  34             440
crm_reconstructed_binding_support                       300                 283             300
          motif_predicted_support                       109                  38             109
```

## Proposed schema

### `features/tf_binds_enhancer_compact_support_codes/enhancer_support_codes_chr*.parquet`

One row per enhancer interval/node:

- `enhancer_id`, `chromosome`, `enhancer_start`, `enhancer_end`
- `support_codes: list<int64>`: all support atoms for the enhancer
- class-specific arrays: `crm_support_codes`, `observed_peak_support_codes`, `motif_support_codes`, `motif_predicted_codes`
- summary arrays: `tf_gene_ids`, `tf_symbols`, `source_task_ids`
- `leakage_policy`

### `features/tf_binds_enhancer_compact_support_codes/support_code_dictionary.parquet`

One row per support code:

- `support_code`, `relation`, `evidence_class`, `support_class`
- TF endpoint metadata: `tf_gene_id`, `tf_symbol`, optional `protein_accession`
- ReMap metadata: `remap_source_accession`, `remap_biotype`, `remap_biotype_description`, `source_record_id`, coordinates, source/release
- antibody/protein/context slots: `antibody_target`, `antibody_id`, `antibody_lot`, `cell_line`, `tissue`, `cell_type`, `context_note`
- motif slots: `motif_source`, `motif_id`, `motif_name`, `motif_threshold`
- confidence/provenance: `confidence_score`, `confidence_note`, `evidence_semantics`, `leakage_policy`

### Optional summaries

- `tf_binds_enhancer_support_code_tf_summary.parquet`: support-code counts by TF/evidence class.
- `tf_binds_enhancer_support_code_context_summary.parquet`: assignment/enhancer/code counts by evidence class or context.

## Query examples

See `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_ba65eb81/reports/query_examples.sql` for DuckDB examples covering:

1. enhancer -> TF/support metadata;
2. TF -> enhancers;
3. context-slot coverage counts for cell_line/tissue/cell_type/antibody/protein plus ReMap fallback context;
4. support_class and ReMap biotype/context filters;
5. explicit direct cell_line/tissue/cell_type predicate shape, expected to return zero rows for the bounded artifact when direct slots are null;
6. explicit antibody/protein predicate shape with fallback to ReMap accession/biotype when those direct slots are absent;
7. motif and motif-only support filters;
8. default training leakage exclusion.

## Leakage/training policy

exclude compact ReMap/CRM/motif support codes from supervised labels and default training graph topology for tf_binds_enhancer, enhancer_regulates_gene, disease/drug prediction, or overlapping regulatory targets unless a future split policy explicitly prevents source/interval/context leakage.

Recommendation: canonical-review this first as `features/tf_binds_enhancer_compact_support_codes/` (feature/evidence-support namespace), not as `edges/tf_binds_enhancer.parquet`. Derive active training edges only in a later reviewed reducer that sets explicit thresholds/support classes and guarantees no regulatory-evidence leakage across train/test/label construction.
