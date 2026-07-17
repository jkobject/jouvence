# TxGNN git reviewability migration decision — `t_4cab4a2f`

Date: 2026-06-24
Workspace inspected: `/Users/jkobject/.openclaw/workspace/work/txgnn`
Reference: `docs/repo_cleanup_t_859cbca4.md`

Execution update (2026-07-17): the migration is complete. The existing `jkobject/TxGNN` worktree metadata is attached directly to `/Users/jkobject/.openclaw/workspace/work/txgnn`; ignored artifacts remain in place, and no second canonical checkout under `~/code` is maintained. The observations and commands below describe the pre-migration state and are retained as historical evidence.

## Decision

TxGNN should use the existing dedicated GitHub repository, not a new ad-hoc repo and not the shared OpenClaw workspace parent repo.

- GitHub repo: `https://github.com/jkobject/TxGNN`
- Default branch observed: `main`
- Canonical local worktree: `/Users/jkobject/.openclaw/workspace/work/txgnn`
- Parallel task worktrees: `/Users/jkobject/.openclaw/worktrees/txgnn/<branch-or-task-id>/`

Rationale:

1. `work/txgnn` has no `.git`, so Git falls through to parent repo `/Users/jkobject/.openclaw/workspace`.
2. Parent workspace status is not reliable because invalid nested `.git` directories under `work/` break discovery.
3. A public canonical repo already exists at `jkobject/TxGNN`; creating another repo would split history/review surface.
4. The artifact workspace contains local caches/staged outputs that should not be committed wholesale.

## Evidence gathered

Commands/results observed during this card:

```text
$ git -C /Users/jkobject/.openclaw/workspace/work/txgnn rev-parse --show-toplevel
/Users/jkobject/.openclaw/workspace

$ git -C /Users/jkobject/.openclaw/workspace status --short
fatal: 'work/jkobject.github.io/.git' not recognized as a git repository

$ gh repo view jkobject/TxGNN --json nameWithOwner,url,isPrivate,defaultBranchRef,description
nameWithOwner=jkobject/TxGNN, url=https://github.com/jkobject/TxGNN, isPrivate=false, defaultBranchRef.name=main
```

Nested `.git` inventory under `/Users/jkobject/.openclaw/workspace/work`:

| Path | State |
|---|---|
| `work/cv/.git` | valid-looking Git dir: `HEAD`, `config`, `index`, `packed-refs` present |
| `work/fedica-skill/.git` | valid-looking Git dir: `HEAD`, `config`, `index`, `packed-refs` present |
| `work/jkobject.github.io/.git` | invalid/incomplete: missing `HEAD`, `config`, `index`, `packed-refs` |
| `work/orchestration-setups/.git` | invalid/incomplete: missing `HEAD`, `config`, `index`, `packed-refs` |
| `work/papers/.git` | invalid/incomplete: missing `HEAD`, `config`, `index`, `packed-refs` |
| `work/pert-gym/.git` | valid-looking Git dir: `HEAD`, `config`, `index` present; no `packed-refs`, which is allowed |
| `work/river/.git` | valid-looking Git dir: `HEAD`, `config`, `index`, `packed-refs` present |
| `work/scPRINT/.git` | valid-looking Git dir: `HEAD`, `config`, `index`, `packed-refs` present |

Non-mutating tests showed that excluding only `work/jkobject.github.io` is insufficient: Git then hits `work/papers/.git`. Therefore the workspace-parent status problem is a broader invalid-nested-git hygiene issue, not a TxGNN-only problem.

## Safe handling plan for invalid sibling `.git` directories

Do not delete invalid nested `.git` directories directly. They may contain objects worth preserving even though they are not valid repositories.

Recommended implementation sequence:

```bash
set -euo pipefail
ROOT=/Users/jkobject/.openclaw/workspace
STAMP=20260624-t_4cab4a2f
REPORT_DIR=/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/reports
mkdir -p "$REPORT_DIR"

python3 - <<'PY' > "$REPORT_DIR/${STAMP}_invalid_nested_git_manifest.json"
from pathlib import Path
import hashlib, json, os
root = Path('/Users/jkobject/.openclaw/workspace/work')
rows = []
for gd in sorted(root.glob('*/.git')):
    if not gd.is_dir():
        continue
    required = {name: (gd / name).exists() for name in ['HEAD', 'config', 'index', 'packed-refs']}
    valid_minimal = required['HEAD'] and required['config']
    total_files = 0
    total_bytes = 0
    sample_hashes = []
    for p in gd.rglob('*'):
        if p.is_file():
            total_files += 1
            total_bytes += p.stat().st_size
            if len(sample_hashes) < 20:
                h = hashlib.sha256(p.read_bytes()).hexdigest()
                sample_hashes.append({'path': str(p.relative_to(gd)), 'sha256': h, 'bytes': p.stat().st_size})
    rows.append({
        'project': str(gd.parent),
        'git_path': str(gd),
        'required_files': required,
        'valid_minimal': valid_minimal,
        'total_files': total_files,
        'total_bytes': total_bytes,
        'sample_hashes': sample_hashes,
    })
print(json.dumps(rows, indent=2))
PY

# Quarantine only invalid nested .git dirs. This preserves project files and preserves the invalid git object dirs.
for project in jkobject.github.io orchestration-setups papers; do
  src="$ROOT/work/$project/.git"
  dst="$ROOT/work/$project/.git.invalid-$STAMP"
  test -d "$src"
  test ! -e "$dst"
  mv "$src" "$dst"
done

# Verification: parent status should no longer fail because of invalid nested .git dirs.
git -C "$ROOT" status --short --branch
```

Review gate for this sibling fix:

- Confirm the manifest exists and lists file counts/bytes for every invalid `.git` dir.
- Confirm only `.git` directories were renamed; no site/source/artifact files under the project roots were moved.
- Confirm `git -C /Users/jkobject/.openclaw/workspace status --short --branch` no longer fails.
- Confirm `jkobject.github.io` content still exists; if the site repo is needed, reclone it cleanly from its GitHub remote into the same path or a proper worktree after preserving local content.

## TxGNN migration commands

Use a proper clone/worktree of the existing GitHub repo and copy only reviewable source/docs/config deltas from the artifact workspace.

```bash
set -euo pipefail
SRC=/Users/jkobject/.openclaw/workspace/work/txgnn
BASE=/Users/jkobject/.openclaw/worktrees/txgnn
REPO=$BASE/repo
BRANCH=migrate/artifact-workspace-20260624-t_4cab4a2f

mkdir -p "$BASE"
if [ ! -d "$REPO/.git" ]; then
  git clone https://github.com/jkobject/TxGNN.git "$REPO"
fi
cd "$REPO"
git fetch origin
git checkout main
git pull --ff-only origin main
git checkout -B "$BRANCH"

# Copy reviewable project files. Keep caches, virtualenvs, staged KG artifacts, generated agent state, and legacy .omoc out of Git.
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '.pytest_cache/' \
  --exclude '__pycache__/' \
  --exclude '.omoc/' \
  --exclude '.omx/' \
  --exclude '.tmp/' \
  --exclude 'TxGNN.egg-info/' \
  --exclude 'artifacts/cache/' \
  --exclude 'artifacts/staged/' \
  --exclude 'artifacts/legacy_omoc_20260624_t_859cbca4/' \
  --exclude 'gs:/' \
  "$SRC"/ "$REPO"/

# Inspect before committing. If artifacts/reports are too bulky/noisy, keep only migration docs and small JSON manifests.
git status --short
git diff --stat
```

If the diff is sane:

```bash
uv run python -m py_compile manage_db/kg_schema.py manage_db/kg_evidence.py manage_db/backfill_edge_evidence.py manage_db/ingest_opentargets.py manage_db/kg_queries.py manage_db/build_pyg_export.py scripts/txgnn_kanban_watchdog.py
uv run --group dev pytest tests/test_kg_schema_cleanup.py tests/test_kg_evidence.py tests/test_backfill_edge_evidence.py -q
python scripts/txgnn_kanban_watchdog.py --json

git add AGENTS.md TODO.md todo.d docs manage_db scripts tests pyproject.toml uv.lock README.md REPORT.md .gitignore
# Add small artifacts/reports manifests only if reviewers need them; never add staged KG payloads by default.
git commit -m "Migrate TxGNN workspace deltas into reviewable repo branch"
git push -u origin "$BRANCH"
gh pr create --base main --head "$BRANCH" --title "Migrate TxGNN workspace deltas into reviewable repo branch" --body-file docs/git_reviewability_migration_t_4cab4a2f.md
```

## Review gates before accepting migration

1. `git status --short` in `/Users/jkobject/.openclaw/worktrees/txgnn/repo` is clean after commit.
2. PR diff excludes `.venv/`, `.omoc/`, `.omx/`, `.tmp/`, `artifacts/staged/`, `artifacts/cache/`, GCS/FUSE mirrors, and generated Python caches.
3. PR diff includes current boot/process docs: `AGENTS.md`, `TODO.md`, `todo.d/`, and relevant `docs/` reports.
4. Py compile gate passes for changed Python modules/scripts.
5. Targeted tests pass or failures are explicitly triaged as pre-existing/environmental.
6. `scripts/txgnn_kanban_watchdog.py --json` exits `0` and reports no missing review routes.
7. A reviewer profile approves the PR/diff before `main` is updated.

## Operational rule after migration

- New TxGNN code/docs work should happen in `/Users/jkobject/.openclaw/worktrees/txgnn/<branch-or-task-id>/` or the canonical clone path, not directly in `/Users/jkobject/.openclaw/workspace/work/txgnn`.
- `work/txgnn` may remain as an artifact/source-of-truth scratch mirror during transition, but every durable code/doc change must be replayed into a branch and PR.
- Large KG artifacts remain in GCS or `artifacts/staged/<task-id>/`; they are referenced by manifests/reports rather than committed wholesale.
