# TxGNN long-run supervisor safe-watchdog repair — t_971acfd0

## Change

Replaced `/Users/jkobject/.hermes/scripts/txgnn_longrun_supervisor.py` with a monitor-only no-agent watchdog.

Safety invariants now enforced by the script:

- It never calls `subprocess.Popen` and has no `start_lamindb()` / `start_remap()` launch path.
- It treats `/Users/jkobject/mnt/gcs` in any heavy LaminDB/PyG/ReMap/embedding command as a critical Mac-FUSE violation.
- It requires heavy work to be visibly VM/canonical-root guarded (`txgnn-worker` / `gcloud compute ssh` plus `gs://jouvencekb/kg/v2`) before considering command artifacts safe.
- It monitors/report-only for stale stdout/stderr/progress with missing `rc`, failed `rc`, duplicate writer risk, stale legacy supervisor active-run pointers, and optional read-only `txgnn-worker` process checks.
- It writes machine-readable findings to `artifacts/reports/longrun_supervisor/latest_watchdog_report.json`.

## Cron

Updated default-profile cron job `9df80778e58b` (`TxGNN LaminDB/ReMap long-run supervisor`) in `/Users/jkobject/.hermes/cron/jobs.json`:

- `script`: `txgnn_longrun_supervisor.py`
- `no_agent`: `true`
- `enabled`: `true`
- `state`: `scheduled`
- `workdir`: `/Users/jkobject/.openclaw/workspace/work/txgnn`
- prompt updated to explicitly say monitor/report-only and never launch Mac-local heavy jobs.

Backup before edit: `/Users/jkobject/.hermes/cron/jobs.jobs.json.bak-t_971acfd0`.

## Validation

Commands run:

```bash
python3 -m py_compile /Users/jkobject/.hermes/scripts/txgnn_longrun_supervisor.py
python3 /Users/jkobject/.hermes/scripts/txgnn_longrun_supervisor.py --dry-run --skip-vm-check --simulate-t-bc992259
python3 /Users/jkobject/.hermes/scripts/txgnn_longrun_supervisor.py --dry-run --skip-vm-check
python3 /Users/jkobject/.hermes/scripts/txgnn_longrun_supervisor.py
```

Observed dry-run proof for `t_bc992259`:

- `mac_fuse_heavy_launch_artifact`: command artifact used `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`.
- `run_missing_vm_guard`: command artifact lacked `txgnn-worker` / `gs://jouvencekb/kg/v2` guard.
- `stale_stdout_no_rc`: `t_bc992259` had no `rc` file and no stdout/stderr/progress update for >4.4h, exceeding the 2h threshold.

The real cron-mode run exited `0`, emitted an alert, and wrote `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/reports/longrun_supervisor/latest_watchdog_report.json` with `no_local_launches: true` and current stale/unsafe findings.

## Residual risk

The watchdog is intentionally conservative and currently reports historical stale/failed legacy supervisor artifacts as well as the current `t_bc992259` failure mode. This is preferable to silence, but a reviewer may decide to archive/ack old legacy run dirs or add an allowlist after the recovery workflow is accepted.
