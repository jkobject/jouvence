# TxGNN Ralph systemd loop

Last verified: 2026-06-11T12:15Z

The non-overlapping OMOC/Ralph continuation loop for goal `G002` is installed as a user systemd timer:

- Service: `~/.config/systemd/user/txgnn-ralph-loop.service`
- Timer: `~/.config/systemd/user/txgnn-ralph-loop.timer`
- Entrypoint: `.omoc/bin/txgnn-ralph-loop.sh`
- Repo working directory: `/home/ubuntu/.openclaw/workspace/work/txgnn`
- Team: `txgnn-kg-ralph`
- Goal: `G002`

Operational properties verified on 2026-06-11:

- `txgnn-ralph-loop.timer` is `enabled` and `active`.
- The service invokes `.omoc/bin/txgnn-ralph-loop.sh` from the repo.
- The script exits without overlap when `.omoc/txgnn-ralph-loop.lock` is already held (`flock -n`).
- The script checks `/mnt/gcs/jouvencekb` before launching a tick and attempts to start `gcsfuse-jouvencekb.service` if missing.
- The script stops early when OMOC reports no actionable pending/in-progress/blocked tasks; if only failed blocker records remain, it reports the failed/blocker count and exits without launching another tick.
- Each tick writes a report under `.omoc/reports/txgnn-ralph-loop-<timestamp>.final`.

Current unit resource limits are for the Ralph loop itself, not the final model smoke:

- `CPUQuota=200%`
- `MemoryMax=8G`
- `TimeoutStartSec=12h`

The final tiny TxGNN model smoke remains separately constrained by `AGENTS.md` Phase 9 to `CPUQuota=200%` and `MemoryMax=4G`.
