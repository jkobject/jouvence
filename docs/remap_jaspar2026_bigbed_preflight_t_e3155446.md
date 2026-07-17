# ReMap JASPAR2026 bigBed local-pinning preflight

Task: `t_e3155446`  
Status: `blocked_no_go`; pre-download/source/pinning/disk gate only. No 196GB download was started, no Mac-local bigBed streaming was performed, and no canonical KG paths were written.

## Scope and inputs read

Read-only context used:

- `docs/remap_speed_audit_t_2fb6aaea.md`
- `artifacts/staged/t_2fb6aaea/reports/remap_speed_audit_summary.json`
- `artifacts/staged/t_2fb6aaea/reports/remap_speed_benchmark_remote.json`
- `artifacts/staged/t_83e0ceef/build_remap_motif_threshold_compact_rescue.py`

The accepted ReMap builder streams overlaps with:

- `bigBedToBed -bed=<tile_bed> -udcDir=<udc> https://hgdownload.soe.ucsc.edu/gbdb/hg38/jaspar/JASPAR2026.bb /dev/stdout`
- source constant: `UCSC_JASPAR_BIGBED = "https://hgdownload.soe.ucsc.edu/gbdb/hg38/jaspar/JASPAR2026.bb"`
- release constant: `JASPAR_RELEASE = "JASPAR2026_CORE_vertebrates_non-redundant"`

## Remote preflight evidence

Command surface:

- `gcloud compute ssh txgnn-worker --zone=europe-west1-b --command ...`

Observed on `2026-07-04T00:11:47Z`:

- `hostname=txgnn-worker`
- repo/home filesystem: `/dev/root`, `485G` size, `92G` used, `394G` available, `19%` used
- GCE disk size from `gcloud compute instances list`: `500GB`

Active ReMap processes were present, so this card must not proceed to a download or benchmark:

- `run_remote_remap.py --tile-size 500 --min-ucsc-score 500 --resume --max-tiles 100 --stop-after-seconds 7200`
- remote run directory: `/home/jkobject/txgnn-run/repo/artifacts/reports/remote_supervisor/remap/20260703T230152Z_tiles3977_rows1984826_max100/`
- active child: `bigBedToBed -bed=/home/jkobject/txgnn-run/repo/artifacts/staged/t_1bc29376/source_cache/remap2022_crm_chr3_rows114001_114500.bed -udcDir=/home/jkobject/txgnn-run/repo/artifacts/cache/remote_supervisor/remap/20260703T230152Z_tiles3977_rows1984826_max100/udc https://hgdownload.soe.ucsc.edu/gbdb/hg38/jaspar/JASPAR2026.bb /dev/stdout`

## Source metadata pin

Source URL:

- `https://hgdownload.soe.ucsc.edu/gbdb/hg38/jaspar/JASPAR2026.bb`

Remote `HEAD` returned:

- HTTP status: `200 OK`
- `Last-Modified: Sun, 18 Jan 2026 18:21:24 GMT`
- `ETag: "2dad9d4c08-648ada4577100"`
- `Accept-Ranges: bytes`
- `Content-Length: 196186295304`
- CORS/range headers: `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Headers: Range`

A one-byte range header probe returned:

- HTTP status: `206 Partial Content`
- `Content-Range: bytes 0-0/196186295304`
- `Content-Length: 1`

The UCSC directory listing at `https://hgdownload.soe.ucsc.edu/gbdb/hg38/jaspar/` lists:

- `JASPAR2026.bb`, last modified `2026-01-18 10:21`, size `183G`

The JASPAR 2026 CORE download index at `https://jaspar.elixir.no/download/data/2026/CORE/` is reachable and includes vertebrate non-redundant PFM releases such as:

- `JASPAR2026_CORE_vertebrates_non-redundant_pfms_jaspar.zip`
- `JASPAR2026_CORE_vertebrates_non-redundant_pfms_meme.zip`
- `JASPAR2026_CORE_vertebrates_non-redundant_pfms_transfac.zip`

## Disk gate

The source object is `196,186,295,304` bytes, about `182.77 GiB`.

Current root filesystem free space (`394G`) is technically larger than the object, but this is not enough for a conservative ops gate because a safe workflow should preserve root-disk headroom and allow at least one `.part`/resume/checksum/equivalence workflow plus task-local artifacts and UDC/cache scratch.

Recommended gate before any download:

- target filesystem free space: at least `450 GiB`, or use a dedicated attached data disk with at least `500 GiB` free;
- no active `run_remote_remap.py` or `bigBedToBed` processes;
- reviewer/CTO comment explicitly authorizing the full source download after this preflight;
- target path must be worker-local, not `/Users/jkobject/mnt/gcs`, not macOS FUSE, and not canonical KG.

Suggested target path after authorization:

- worker-root option: `/home/jkobject/txgnn-run/repo/artifacts/cache/t_e3155446/sources/JASPAR2026.bb`
- preferred durable capacity option if attached: `/mnt/remap-cache/sources/JASPAR2026/JASPAR2026.bb`

## Pinning and validation strategy

Before download:

1. Re-run `HEAD` and require the same `Content-Length`, `Last-Modified`, and `ETag` recorded above.
2. Confirm `pgrep -af 'run_remote_remap.py|bigBedToBed'` is empty except the guard shell itself.
3. Confirm `df -BG <target_fs>` reports at least the required free-space threshold.

After authorized download:

1. Save the file and compute `sha256sum JASPAR2026.bb > JASPAR2026.bb.sha256`.
2. Record `stat -c '%n %s %y' JASPAR2026.bb` and require size `196186295304`.
3. Re-run `HEAD`; compare URL, `Content-Length`, `ETag`, and `Last-Modified` against the pre-download pin.
4. Run a tiny equivalence gate using fresh task-local UDC dirs:
   - one `bigBedToBed` call against the remote URL;
   - one `bigBedToBed` call against the local file;
   - compare raw emitted rows and reducer outputs by row count and hash before making any speed claim.

## Exact command skeleton for a later reviewed download card

Do not run this until a reviewer/CTO authorizes it and the active ReMap writer is gone.

```bash
gcloud compute ssh txgnn-worker --zone=europe-west1-b --command '
set -euo pipefail
hostname
pgrep -af "run_remote_remap.py|bigBedToBed" && exit 20 || true
df -BG /home/jkobject/txgnn-run/repo
curl -sSIL --max-time 60 https://hgdownload.soe.ucsc.edu/gbdb/hg38/jaspar/JASPAR2026.bb
'
```

```bash
gcloud compute ssh txgnn-worker --zone=europe-west1-b --command '
set -euo pipefail
cd /home/jkobject/txgnn-run/repo
mkdir -p artifacts/cache/t_e3155446/sources
curl -fL --continue-at - --remote-time \
  -o artifacts/cache/t_e3155446/sources/JASPAR2026.bb.part \
  https://hgdownload.soe.ucsc.edu/gbdb/hg38/jaspar/JASPAR2026.bb
mv artifacts/cache/t_e3155446/sources/JASPAR2026.bb.part \
  artifacts/cache/t_e3155446/sources/JASPAR2026.bb
test "$(stat -c %s artifacts/cache/t_e3155446/sources/JASPAR2026.bb)" = "196186295304"
sha256sum artifacts/cache/t_e3155446/sources/JASPAR2026.bb \
  > artifacts/cache/t_e3155446/sources/JASPAR2026.bb.sha256
cat artifacts/cache/t_e3155446/sources/JASPAR2026.bb.sha256
'
```

## Go/no-go

No-go / blocked for the later full-download equivalence/speed card.

Reasons:

1. Active ReMap writer/streamer processes are currently present on `txgnn-worker`.
2. Conservative disk threshold is not met on the observed root filesystem (`394G` free now; require at least `450 GiB` free or a dedicated attached disk with at least `500 GiB` free).
3. The task body explicitly forbids starting the 196GB download without an accepted reviewer/CTO authorization after this source/pinning/disk gate.

Machine-readable report:

- `artifacts/staged/t_e3155446/reports/jaspar2026_bigbed_preflight.json`
