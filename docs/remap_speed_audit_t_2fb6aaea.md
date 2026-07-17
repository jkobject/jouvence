# ReMap speed audit: safe throughput improvements

Task: `t_2fb6aaea`  
Status: `review-required`; audit report plus bounded `txgnn-worker` benchmark only; no canonical writes; live `t_1bc29376` supervisor/output was not modified.

## 2026-07-03 policy correction

After the first local benchmark attempt, the CTO watchdog intervened: ReMap chunks/benchmarks are VM-only, and further benchmarking must run on `txgnn-worker` with bounded remote scratch/fresh UDC rather than Mac-local UCSC bigBed streaming. The local measurements below are retained as diagnostic evidence only and should not be treated as accepted validation for changing the live workflow.

Remote preflight on `txgnn-worker` succeeded, but a live ReMap continuation was already running:

- host: `txgnn-worker`
- active command: `/home/jkobject/txgnn-run/repo/artifacts/reports/remote_supervisor/remap/20260703T115847Z_tiles3277_rows1635634_max100/run_remote_remap.py --tile-size 500 --min-ucsc-score 500 --resume --max-tiles 100 --stop-after-seconds 7200`
- active `bigBedToBed` child at inspection: `chr2_rows241501_242000` / `chr2_rows242001_242500`
- live progress at inspection: 3,366 / 6,669 tiles, 1,680,134 / 3,327,980 CRM rows, 89 processed in this invocation, elapsed wall ~6,201s

I waited until that active max100 continuation exited cleanly (`rc=0`) before launching the remote benchmark, so no concurrent ReMap benchmark ran against the live writer/streamer.

## Accepted bounded remote benchmarks (`txgnn-worker`)

Command/script:

- copied updated script to `/home/jkobject/txgnn-run/repo/artifacts/staged/t_2fb6aaea/remap_speed_benchmark.py`
- remote command after process guard: `uv run python artifacts/staged/t_2fb6aaea/remap_speed_benchmark.py --include-adjacent-warm`
- local copy of remote report: `artifacts/staged/t_2fb6aaea/reports/remap_speed_benchmark_remote.json`
- remote report: `/home/jkobject/txgnn-run/repo/artifacts/staged/t_2fb6aaea/reports/remap_speed_benchmark.json`

Benchmark region: chr11 CRM rows 54,001 onward, `min_ucsc_score=500`, fresh task-local UDC except the intentional warm-cache comparisons.

| Variant | Tile rows | UDC policy | Wall seconds | CRM rows/sec | Raw hits | Raw hits/sec | Retained assignments | Notes |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `baseline_500_fresh` | 500 | fresh UDC | 40.21 | 12.43 | 1,463,040 | 36,386 | 1,052 | Remote accepted baseline for this bounded region. |
| `baseline_500_warm_same_udc` | 500 | same exact tile, same UDC | 2.27 | 220.31 | 1,463,040 | 649,458 | 1,052 | Proves exact repeated byte ranges are cacheable; not representative of forward progress. |
| `tile_1000_fresh` | 1,000 | fresh UDC | 82.56 | 12.11 | 2,936,873 | 35,575 | 1,726 | Linear/slightly slower than 500 fresh; no useful tile-size speedup. |
| `adjacent_500_warm_same_udc` | 500 | next 500 CRM rows, same UDC as baseline | 43.98 | 11.37 | 1,473,833 | 33,516 | 674 | Adjacent forward-progress tile does not benefit materially from warmed UDC. |

Remote validation:

- `hostname` verified `txgnn-worker`.
- Preflight refused to run if `run_remote_remap.py` or `bigBedToBed` was still active.
- Canonical negative check passed: `test ! -e edges/tf_binds_enhancer.parquet && test ! -e evidence/tf_binds_enhancer.parquet` -> `canonical-negative-remote-ok`.
- Remote task-local sizes after run: `1.1M artifacts/staged/t_2fb6aaea`, `64M artifacts/cache/t_2fb6aaea`.

## Scope

The current accepted full-run path is:

- `artifacts/staged/t_1bc29376/build_remap_motif_threshold_compact_full_run.py`
- importing accepted reducer `artifacts/staged/t_83e0ceef/build_remap_motif_threshold_compact_rescue.py`
- per tile: write a CRM BED, run `bigBedToBed -bed=<tile_bed> -udcDir=<udc> https://hgdownload.soe.ucsc.edu/gbdb/hg38/jaspar/JASPAR2026.bb /dev/stdout`, stream all overlaps, then Python-filter `score >= 500` and CRM-regulator matches before writing compact Parquet shards.

This audit used isolated task-local benchmark dirs under:

- `artifacts/staged/t_2fb6aaea/benchmarks/`
- `artifacts/cache/t_2fb6aaea/benchmarks/`

It did not write canonical KG paths and did not touch `artifacts/staged/t_1bc29376` outputs/checkpoints.

## Prior local diagnostic benchmarks (not accepted as VM-policy validation)

Command/script:

- `uv run python artifacts/staged/t_2fb6aaea/remap_speed_benchmark.py`
- one additional adjacent-tile probe recorded in `artifacts/staged/t_2fb6aaea/reports/remap_speed_benchmark_adjacent_warm.json`

Benchmark region: chr11 CRM rows 54,001 onward, `min_ucsc_score=500`.

| Variant | Tile rows | UDC policy | Wall seconds | CRM rows/sec | Raw hits | Raw hits/sec | Retained assignments | Notes |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `baseline_500_fresh` | 500 | fresh UDC | 40.38 | 12.38 | 1,463,040 | 36,240 | 1,052 | Comparable to live 500-row tile shape, but this region is somewhat faster than reported live 58-66s/tile. |
| `baseline_500_warm_same_udc` | 500 | same exact tile, same UDC | 1.28 | 389.80 | 1,463,040 | 1,141,757 | 1,052 | Shows UCSC UDC cache makes exact repeat very fast; not a real continuation workload. |
| `adjacent_500_warm_same_udc` | 500 | next 500 CRM rows, same UDC | 43.45 | 11.51 | 1,473,833 | 33,923 | 674 | No speedup for adjacent tile; cache reuse does not help materially for fresh genomic ranges. |
| `tile_1000_fresh` | 1,000 | fresh UDC | 81.61 | 12.25 | 2,936,873 | 35,988 | 1,726 | Nearly exactly linear with 500-row fresh baseline; fewer tile launches/checkpoints do not move throughput. |

A 2,000-row fresh variant was intentionally not used as evidence: the foreground command was terminated before writing a partial result. The 1,000-row variant already demonstrated linear scaling, so rerunning larger benchmarks would add load without changing the conclusion.

## Findings by candidate lever

### Larger tile size

Not a useful throughput lever at API/function level. On the same chromosome/start region, the accepted remote benchmark measured:

- 500 fresh: 12.43 CRM rows/sec.
- 1,000 fresh: 12.11 CRM rows/sec.

The dominant cost scales with raw overlap volume streamed from `bigBedToBed`/remote bigBed, not with Python tile setup or Parquet write overhead. Larger tiles reduce checkpoint count, but they also increase per-tile failure blast radius and wall time. They should not be used as the primary speed improvement.

### Persistent/reused UDC cache

Mixed and not safe as a blanket optimization.

Accepted remote evidence:

- exact same tile, same UDC: 40.21s -> 2.27s, proving UDC helps repeated byte ranges;
- adjacent tile, same UDC: 40.21s baseline vs 43.98s adjacent, no speedup.

The current supervisor deliberately uses a fresh task-local UDC because the old `artifacts/cache/t_1bc29376/udc` path is suspected-corrupt and is explicitly rejected by current guardrails. Reusing a persistent cache across continuations is only worth considering after a separate reviewed cache-integrity gate and does not appear to improve non-overlapping forward progress much anyway.

### Localizing/pinning `JASPAR2026.bb`

Likely the only high-upside lever, but not safe to implement on this Mac in this card.

Observed source metadata:

- URL: `https://hgdownload.soe.ucsc.edu/gbdb/hg38/jaspar/JASPAR2026.bb`
- HTTP HEAD: status 200; `content-length=196186295304`; `last-modified=Sun, 18 Jan 2026 18:21:24 GMT`; `accept-ranges=bytes`.

A full local copy is about 196 GB. The Mac currently had about 34 GiB free at audit time, so localizing here is unsafe. If pursued, it should be a separate VM/in-region operations card with enough disk, checksum/metadata pinning, UCSC/JASPAR license/source review, and a tiny equivalence benchmark comparing local-file `bigBedToBed` output against the remote URL for the same tile.

### Parallelism

Potentially useful but operationally risky. The builder writes separate tile checkpoint/output files, so independent tiles are structurally parallelizable, but safe parallelism still needs:

- separate UDC dirs per worker or a verified shared-UDC concurrency policy;
- atomic checkpoint/output semantics under concurrent writers;
- process guards so parallel jobs do not overlap with the current live supervisor;
- VM/network politeness limits for UCSC range requests;
- resume/report aggregation that cannot double-count or corrupt partial outputs.

This should not be patched into the live supervisor without a reviewed bounded parallel-supervisor card. A low parallelism of 2 across non-overlapping chromosomes/tiles is a plausible next experiment on `txgnn-worker`, not from the Mac foreground.

### Earlier `score >= 500` filtering

No safe function-level improvement found. The current stream receives BED-like rows from `bigBedToBed`; score is only available after each row is emitted. The reducer already applies score filtering before CRM-regulator matching and before support-code materialization. Unless UCSC tooling has an indexed/filtering option for score predicates (not used here), there is no earlier filter point in this API path.

### Pandas/Parquet overhead

Not the bottleneck for this density. Fresh 500-row tile writes are ~64 KB compact all-CRM, ~43 KB nonzero, ~43 KB dictionary, while runtime is ~40s streaming ~1.46M raw hits. Python row streaming/overlap checks may matter, but Parquet output size and write overhead are small compared with the `bigBedToBed` stream.

## Recommendation

Do not change the current live supervisor for this run.

Safe speedup path:

1. Keep the live run serial/fresh-UDC unless a separate reviewed operations gate changes it.
2. Do not run additional speed probes unless a `txgnn-worker` process guard confirms no active related ReMap writer/streamer.
3. Create/queue a dedicated `txgnn-worker` card to test a local pinned `JASPAR2026.bb` copy, because remote range streaming is the likely bottleneck and the file is too large for the Mac disk state.
4. If local bigBed is validated equivalent, benchmark serial local-file tiles first; only then test parallelism=2 with isolated UDC/cache dirs and atomic checkpoint validation.
5. Keep tile size at 500 for current resume reliability unless remote VM evidence says otherwise; local diagnostic evidence did not show a tile-size throughput gain.

## Artifacts

- Benchmark script: `artifacts/staged/t_2fb6aaea/remap_speed_benchmark.py`
- Remote benchmark JSON: `artifacts/staged/t_2fb6aaea/reports/remap_speed_benchmark_remote.json`
- Partial remote benchmark JSON: `artifacts/staged/t_2fb6aaea/reports/remap_speed_benchmark_remote_partial.json`
- Summary JSON: `artifacts/staged/t_2fb6aaea/reports/remap_speed_audit_summary.json`
- Prior local diagnostic JSON: `artifacts/staged/t_2fb6aaea/reports/remap_speed_benchmark_partial.json`
- Adjacent warm-cache benchmark JSON: `artifacts/staged/t_2fb6aaea/reports/remap_speed_benchmark_adjacent_warm.json`
- This report: `docs/remap_speed_audit_t_2fb6aaea.md`

## Validation evidence

- Remote `txgnn-worker` preflight initially found an active live ReMap continuation; I waited until it exited cleanly (`rc=0`) before launching the benchmark.
- Accepted remote bounded benchmark completed on `txgnn-worker` with no concurrent ReMap process active.
- Local `ps` preflight found no local `bigBedToBed`/ReMap process before the now-policy-invalid local diagnostic benchmark; the CTO watchdog later killed that local benchmark and instructed remote-only recovery.
- `df -h .` showed only ~34 GiB free, so localizing a 196 GB bigBed on the Mac was rejected.
- All completed benchmark variants wrote only under task-local `artifacts/staged/t_2fb6aaea` and `artifacts/cache/t_2fb6aaea` paths.
- No canonical KG path was written.

## Residual risks

- Benchmarks used one chr11 region; absolute seconds vary by genomic density and network behavior. Relative evidence is still enough to reject larger tile size and adjacent UDC reuse as primary speedups.
- The 2,000-row fresh probe terminated before result capture and is excluded from conclusions.
- The reported UDC apparent size is sparse-file-sensitive; `du -sh` reported ~64 MB actual disk use for the remote cache after completed probes.
