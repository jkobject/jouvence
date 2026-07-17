# txgnn-worker disk migration — t_3cf62bd8

Status: `review-required` (migration and bounded smoke validated; destructive cleanup is deliberately not authorized).

## Result

`txgnn-worker` now has the 200 GB `pd-standard` boot disk `txgnn-worker-200gb-t3cf62bd8` in `europe-west1-b` (project `jkobject-1549353370965`). It booted successfully as `txgnn-worker`, passed bounded filesystem/GCS/Lamin read-only smoke checks, and was then stopped. Its final GCP status is `TERMINATED`.

The original 500 GB disk `txgnn-worker` is detached, `READY`, and retained as a rollback disk. Recovery snapshot `txgnn-worker-rollback-t3cf62bd8-20260711` is `READY`; it stores 128,819,265,216 bytes. Neither was deleted.

## Capacity decision

Inspection of the stopped source disk found:

- source root: 485 GiB filesystem, 153 GiB used;
- most material payload: `home/jkobject/txgnn-run` 112,157,581,312 bytes, `home/jkobject/kg` 6,785,703,936 bytes, `home/jkobject/.cache` 46,270,525,440 bytes;
- source uses Ubuntu 22.04.5, one ext4 root (`cloudimg-rootfs`) and a 106 MiB UEFI partition.

200 GB was selected rather than 150 GB. A 200 GB disk gives a 194 GiB ext4 filesystem. It had 169 GiB free (14% used) after migration, making capacity robust to cache rehydration and normal work.

The first full sparse-aware transfer exposed a class of intentionally rebuildable caches whose `sparseData` files have multi-terabyte apparent size despite modest allocated size. The destination consequently omits only paths explicitly classified as caches:

- `/home/jkobject/.cache/`: 46,270,525,440 bytes (LaminDB and uv cache);
- `/home/jkobject/txgnn-run/repo/artifacts/cache/`: 96,410,513,408 bytes, including 96,303,333,376 bytes under the stale/rebuildable ReMap remote-supervisor UDC cache.

These paths are already designated cache locations by project policy and are rebuildable. The complete source remains on the detached old disk and recovery snapshot, so the omission is non-destructive and reversible.

## Migration method and verification

1. Created recovery snapshot before changing attachments.
2. Created a temporary in-zone Ubuntu 22.04 helper, attached the old disk read-only, and inspected it.
3. Created the 200 GB target disk from the original Ubuntu image family version, expanded the GPT/root partition and ext4 filesystem, then mounted source/target root and EFI filesystems.
4. Copied required filesystem content with `rsync -aHAXx --numeric-ids --delete`; copied EFI with `rsync -aHAX --numeric-ids --delete`. The two explicit cache paths above were excluded.
5. Validation evidence before switch:
   - root rsync dry-run delta count: `0`;
   - EFI rsync dry-run delta count: `0`;
   - checksum (`rsync -rcn`) delta count for `home/jkobject/kg`: `0`;
   - checksum (`rsync -rcn`) delta count for `repo/artifacts` excluding cache: `0`;
   - Lamin configuration files matched source/target pairwise by SHA-256 (hash values intentionally not recorded);
   - `e2fsck -fn /dev/sdc1` and `fsck.fat -n /dev/sdc15` completed cleanly.
6. Detached both disks from the helper, attached the target as the worker boot disk, booted the worker, performed smoke checks, stopped it, and deleted the temporary helper.

## Bounded boot smoke evidence

On the new disk:

- `hostname` returned `txgnn-worker`;
- root was `/dev/sda1` ext4, 194 GiB total / 26 GiB used / 169 GiB available;
- `systemctl --failed --no-legend` returned no failed units;
- no prior workload process was found (only normal OS network/unattended-upgrade Python processes);
- in-region `gcloud storage ls gs://jouvencekb/kg/v2/ | head -1` succeeded;
- LaminDB imported and a bounded `Artifact.filter().first()` read query succeeded without a write (`False` result is an empty query result, not an error).

Observation for review: the preserved VM-local Lamin configuration connected to `jkobject/repo`, despite project documentation naming `jkobject/jouvencekb` as the active instance. This existed on the source and was copied unchanged; this migration did not change instance configuration. Confirm intended VM Lamin instance in a separate configuration card before any write-capable Lamin operation.

## GCP identifiers and rollback

- project/zone: `jkobject-1549353370965` / `europe-west1-b`
- VM: `txgnn-worker`, `e2-standard-2`, final state `TERMINATED`
- new boot disk: `txgnn-worker-200gb-t3cf62bd8`, 200 GB, `pd-standard`, attached boot, `autoDelete=false`
- rollback disk: `txgnn-worker`, 500 GB, `pd-standard`, detached and `READY`
- recovery snapshot: `txgnn-worker-rollback-t3cf62bd8-20260711`, source size 500 GB, stored bytes 128,819,265,216, `READY`

Rollback is straightforward while the worker is stopped: detach `txgnn-worker-200gb-t3cf62bd8`, attach the preserved `txgnn-worker` disk as boot, then start the VM. Do not run this unless the new boot disk is diagnosed as faulty.

## Future cleanup manifest (not executed)

No disk/snapshot deletion is authorized by this card.

1. Keep `txgnn-worker` 500 GB rollback disk through independent review and a defined rollback retention period.
2. Keep `txgnn-worker-rollback-t3cf62bd8-20260711` for the same period.
3. After explicit approval, delete the detached 500 GB rollback disk first only if a fresh boot/recovery review remains successful.
4. Retain or separately decide snapshot lifetime; deleting it is a separate destructive approval.
5. Rebuild caches only as required on the VM. Do not resurrect the old ReMap UDC paths blindly; project policy identifies the old UDC cache family as suspect/stale.

## Cost estimate

Estimate uses $0.040/GB-month for `pd-standard` and $0.026/GB-month for snapshot storage; verify current billing SKU/discounts before an accounting decision.

- Before migration: 500 GB disk ≈ **$20.00/month**.
- Current retained-rollback state: 500 GB old disk + 200 GB new disk + 128.819 GB stored snapshot ≈ **$31.35/month**.
- After separately approved deletion of the 500 GB disk while retaining snapshot: ≈ **$11.35/month**, about **$8.65/month** below the original disk-only cost.
- If snapshot is also separately retired later: 200 GB boot disk ≈ **$8.00/month**, about **$12.00/month** below the original disk-only cost.

The temporary helper was deleted, so it has no ongoing cost.
