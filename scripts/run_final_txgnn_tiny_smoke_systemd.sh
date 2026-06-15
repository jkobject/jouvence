#!/usr/bin/env bash
set -euo pipefail

# Reproducible runner for scripts/final_txgnn_tiny_smoke.py.
#
# Why this exists:
# - The KG/LaminDB tooling currently pins NumPy 2.x for pandas/LaminDB work.
# - DGL 2.1.0's prebuilt GraphBolt wheel is compatible with torch up to 2.2.1
#   and expects NumPy 1.x at runtime.
# - Therefore this model smoke intentionally pins a legacy-compatible runtime in
#   the project venv, then uses `uv run --no-sync` so uv does not immediately
#   re-sync NumPy back to the KG tooling lock.
#
# This script creates only temporary local scratch data through the Python smoke
# script. It does not mutate canonical GCS or LaminDB.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UNIT="${UNIT:-hermes-final-txgnn-tiny-smoke-$(date -u +%Y%m%dT%H%M%SZ)}"
REPORT="${REPORT:-.omoc/reports/${UNIT}.txt}"
mkdir -p "$(dirname "$REPORT")"

export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

printf 'Preparing TxGNN legacy model-smoke runtime...\n' | tee "$REPORT"
uv pip install 'numpy==1.26.4' 'torch==2.2.1' 'torchdata==0.7.1' 'dgl==2.1.0' 2>&1 | tee -a "$REPORT"

printf '\nRunning final TxGNN tiny smoke under systemd limits...\n' | tee -a "$REPORT"
systemd-run --user --unit="$UNIT" --wait --collect \
  -p CPUQuota=200% \
  -p MemoryMax=4G \
  --working-directory="$ROOT" \
  bash -lc "uv run --no-sync python scripts/final_txgnn_tiny_smoke.py" 2>&1 | tee -a "$REPORT"

printf '\nSystemd journal tail for %s.service:\n' "$UNIT" | tee -a "$REPORT"
journalctl --user -u "$UNIT.service" --no-pager -o cat | tail -240 | tee -a "$REPORT"

printf '\nReport: %s\n' "$REPORT"
