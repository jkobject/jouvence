#!/usr/bin/env bash
set -euo pipefail

LEASE_ID=${1:?lease id required}
GENERATION=${2:?generation required}
EXPECTED_COMMIT=${3:?expected repository commit required}
TASK_ROOT=/home/jkobject/t_03bf9e27
REPO="$TASK_ROOT/repo"
HEARTBEAT="$TASK_ROOT/payload-heartbeat.json"
BUILDER_OUT="$TASK_ROOT/full-output"
CANDIDATE_DIR="$TASK_ROOT/candidate"
GCS_ROOT=gs://jouvencekb/kg/staging/gene-genomic-sequence-embeddings-20260721-t_03bf9e27
SOURCE_ORIGIN=gs://jouvencekb/kg/staging/gene-genomic-sequence-20260625-t_720528ea

write_heartbeat() {
  "$REPO/.venv/bin/python" - "$HEARTBEAT" "$LEASE_ID" "$GENERATION" <<'PY'
import json, os, sys
from datetime import UTC, datetime
from pathlib import Path
path, lease_id, generation = sys.argv[1:]
payload = {
    "kind": "payload",
    "gcp_project_id": "jkobject-1549353370965",
    "instance": "txgnn-worker",
    "instance_id": "4268456364292488510",
    "zone": "europe-west1-b",
    "task": "t_03bf9e27",
    "lease_id": lease_id,
    "generation": int(generation),
    "at": datetime.now(UTC).isoformat(),
    "payload_pid": os.getppid(),
}
tmp = Path(path + ".tmp")
tmp.write_text(json.dumps(payload, sort_keys=True) + "\n")
os.replace(tmp, path)
PY
}

heartbeat_loop() {
  while kill -0 "$PAYLOAD_PID" 2>/dev/null; do
    write_heartbeat
    sleep 30
  done
}

[[ "$(hostname)" == "txgnn-worker" ]]
[[ ! -e /Users/jkobject/mnt/gcs ]]
[[ "$(curl -fsS -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/id)" == "4268456364292488510" ]]
export HERMES_KANBAN_TASK=t_03bf9e27
export PYTHONPATH="$REPO"
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
cd "$REPO"
[[ "$(git rev-parse HEAD)" == "$EXPECTED_COMMIT" ]]
[[ "$(.venv/bin/python -c 'import transformers; print(transformers.__version__)')" == "4.55.4" ]]

PAYLOAD_PID=$$
write_heartbeat
heartbeat_loop &
HEARTBEAT_PID=$!
trap 'kill "$HEARTBEAT_PID" 2>/dev/null || true; wait "$HEARTBEAT_PID" 2>/dev/null || true' EXIT

rm -rf "$BUILDER_OUT" "$CANDIDATE_DIR" "$TASK_ROOT/readback"
.venv/bin/python -m manage_db.build_gene_genomic_sequence_embeddings \
  --source-root "$TASK_ROOT/source" \
  --output-dir "$BUILDER_OUT" \
  --no-limit \
  --batch-size 16 \
  --part-size 4096 \
  --max-nucleotides-per-window 1000 \
  --window-stride 1000 \
  --device cpu \
  --clean

.venv/bin/python -m manage_db.finalize_gene_genomic_embedding_candidate \
  --task-root "$TASK_ROOT" \
  --builder-output "$BUILDER_OUT" \
  --source-root "$TASK_ROOT/source" \
  --canonical-gene "$TASK_ROOT/preflight/gene.parquet" \
  --candidate-dir "$CANDIDATE_DIR" \
  --gcs-root "$GCS_ROOT" \
  --source-origin-root "$SOURCE_ORIGIN" \
  --repository-commit "$(git rev-parse HEAD)"
