# TxGNN `/home/ubuntu/data` cleanup log

2026-06-11 Ralph/systemd tick migrated archived TxGNN agent reports and the first
verified local scratch archives away from `/home/ubuntu/data`.

## Repo-local report migration

- Source removed: `/home/ubuntu/data/txgnn-agent-reports`
- New repo path: `.omoc/reports/archived-agent-reports/`
- Verification: source and destination `sha256sum` manifests matched before
  removing the source directory.

## GCS local-data archive

Archive root:
`/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0907Z/`

Verified and removed local source directories:

| directory | regular files | bytes |
| --- | ---: | ---: |
| `txgnn-bounded-promotion-staging` | 5 | 107,297,906 |
| `txgnn-drug-molecule-scratch` | 56 | 191,405,954 |
| `txgnn-known-variants-scratch` | 109 | 1,031,578,461 |
| `txgnn-gwas-join-scratch` | 414 | 3,982,439,582 |

The archived `txgnn-gwas-join-scratch/opentargets/evidence_gwas_credible_sets`
symlink was rewritten from an absolute `/home/ubuntu/data/...` target to a
relative archive-internal symlink pointing at
`../../txgnn-known-variants-scratch/opentargets/evidence_gwas_credible_sets`.

## Second verified archive pass (2026-06-11T0940Z)

Archive root:
`/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0940Z/`

Verified with deterministic `.tar.zst` archives, `sha256sum`, and `zstd -t`;
then removed local source directories. Manifest: `manifest.tsv` in the archive
root.

| directory | regular files | bytes | sha256 |
| --- | ---: | ---: | --- |
| `txgnn-opentargets-phase5` | 9 | 72,163,588 | `69b3004b6dfb515bac68c238b60a0982bb1f9816c4cace40908311df7b2eec63` |
| `txgnn-variant-combined-scratch` | 9 | 230,836,253 | `13cf23370fbe0a0c1300b66eb9d979a93e835577ea983c8d8643bb1513c8167d` |
| `txgnn-target-go-scratch` | 63 | 249,222,964 | `d69be2671cbe4c7e03139eab349677f1211590d95450b403728fdb62b3a8955f` |
| `txgnn-variant-gwas-promotion-scratch` | 41 | 251,367,651 | `ff0a343ccf514aa76d5e9f6a48afe758a553dc2b6cf92379d2e56ae185af0548` |
| `txgnn-phase4-audit` | 215 | 378,808,068 | `cbb63d30ca13e8dff951763eb71f28561ee1f771a4be2e7a462c8d24505c4e2f` |
| `txgnn-ot-phase45` | 171 | 634,076,701 | `c119ae524d88465754d9c7edb4a30d2ec0d1b3d68592ccc189c2cd36c89b182d` |
| `txgnn-variants-scratch` | 544 | 3,486,498,845 | `cb15247ca4c8a62be3752bc2e0d5dde08c4292f94a1248091b237ad38c3c107f` |
| `txgnn-literature` | 5,219 | 9,343,276,661 | `0fa98abc50b6a378aa50fbd44451c9bbe80aeb98ec3af052866ec4585c9aca3c` |

## Current local TxGNN data state

As of the 2026-06-11T0940Z pass, `find /home/ubuntu/data -maxdepth 1 -type d -name 'txgnn*'` returns no project data directories. Do not create new TxGNN/Jouvence work data under `/home/ubuntu/data`; use repo-local `.omoc/reports` for small reports and `gs://jouvencekb` via `/mnt/gcs/jouvencekb` for KG/scratch/large artifacts.
