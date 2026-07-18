"""Sync canonical KG v2 Parquet artifacts into LaminDB's catalog.

Phase-1 sync is intentionally artifact/catalog focused and does not require
``lnschema_txgnn`` activation.  Exact-ID node registry writes stay in
``sync_parquet_nodes_to_lamindb`` and should only run after the schema module is
configured for the active LaminDB instance.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .build_lamindb_kg_manifest import build_manifest, iter_layer_entries, load_manifest, write_manifest
from .sync_parquet_nodes_to_lamindb import _configure_sqlite_timeout, _current_lamin_slug

DEFAULT_LAMIN_INSTANCE = "jkobject/jouvencekb"
DEFAULT_COLLECTION_NAME = "jouvence-kg/v2"
SYNC_TRANSFORM_KEY = "sync_kg_v2_to_lamindb"


@dataclass
class ArtifactSyncResult:
    key: str
    layer: str
    name: str
    status: str
    rows: int | None
    metadata_fingerprint: str | None
    uri: str


@dataclass
class KGArtifactSyncReport:
    dry_run: bool
    lamin_instance: str | None
    collection: str
    artifacts: list[ArtifactSyncResult]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "lamin_instance": self.lamin_instance,
            "collection": self.collection,
            "artifacts": [asdict(item) for item in self.artifacts],
            "summary": {
                "created": sum(1 for item in self.artifacts if item.status == "created"),
                "updated": sum(1 for item in self.artifacts if item.status == "updated"),
                "noop": sum(1 for item in self.artifacts if item.status == "noop"),
                "would_create": sum(1 for item in self.artifacts if item.status == "would_create"),
                "would_update": sum(1 for item in self.artifacts if item.status == "would_update"),
                "error": sum(1 for item in self.artifacts if item.status == "error"),
            },
            "errors": self.errors,
        }


def _connect_lamin(lamin_instance: str | None):
    import lamindb as ln

    if lamin_instance and _current_lamin_slug() != lamin_instance:
        ln.connect(lamin_instance)
    _configure_sqlite_timeout()
    return ln


def _first(model: Any, **kwargs):
    try:
        qs = model.filter(**kwargs)
    except AttributeError:
        qs = model.objects.filter(**kwargs)
    for method in ("one_or_none", "first"):
        if hasattr(qs, method):
            return getattr(qs, method)()
    try:
        return qs[0]
    except Exception:
        return None


def _save(record: Any):
    result = record.save()
    return record if result is None else result


def _ensure_record(model: Any, *, dry_run: bool, defaults: dict[str, Any] | None = None, **lookup):
    existing = _first(model, **lookup)
    if existing is not None or dry_run:
        return existing
    payload = dict(lookup)
    if defaults:
        payload.update(defaults)
    return _save(model(**payload))


def _description(entry: dict[str, Any]) -> str:
    payload = {
        "kg_version": "v2",
        "layer": entry.get("layer"),
        "name": entry.get("name"),
        "rows": entry.get("rows"),
        "bytes": entry.get("bytes"),
        "columns": entry.get("columns", []),
        "metadata_fingerprint": entry.get("metadata_fingerprint"),
        "parquet_schema_hash": entry.get("parquet_schema_hash"),
        "metadata": entry.get("metadata", {}),
    }
    return "Canonical Jouvence KG artifact\n" + json.dumps(payload, sort_keys=True)


def _description_has_fingerprint(record: Any, fingerprint: str | None) -> bool:
    if not fingerprint:
        return False
    return fingerprint in str(getattr(record, "description", ""))


def _ensure_ulabels(ln: Any, names: list[str], *, dry_run: bool) -> list[Any]:
    labels: list[Any] = []
    model = getattr(ln, "ULabel", None)
    if model is None:
        return labels
    for name in names:
        label = _ensure_record(model, dry_run=dry_run, name=name)
        if label is not None:
            labels.append(label)
    return labels


def _attach_many(manager: Any, records: list[Any]) -> None:
    if manager is None or not records:
        return
    add = getattr(manager, "add", None)
    if add is None:
        return
    for record in records:
        try:
            add(record)
        except TypeError:
            add(*records)
            return


def _ensure_features(ln: Any, entry: dict[str, Any], artifact: Any, *, dry_run: bool) -> None:
    model = getattr(ln, "Feature", None)
    if model is None:
        return
    records = []
    for column in entry.get("columns", []):
        feature = _ensure_record(
            model,
            dry_run=dry_run,
            name=f"kg/v2/{entry['layer']}/{entry['name']}:{column}",
            defaults={"dtype": _lamin_feature_dtype(entry.get("dtypes", {}).get(column))},
        )
        if feature is not None:
            records.append(feature)
    _attach_many(getattr(artifact, "features", None), records)


def _lamin_feature_dtype(dtype: str | None) -> str:
    """Map PyArrow/Pandas dtype text to LaminDB's Feature dtype vocabulary."""

    text = (dtype or "").lower()
    if any(token in text for token in ("int", "uint")):
        return "int"
    if any(token in text for token in ("float", "double", "decimal")):
        return "float"
    if "bool" in text:
        return "bool"
    if "timestamp" in text or "datetime" in text:
        return "datetime"
    if text == "date" or text.startswith("date32") or text.startswith("date64"):
        return "date"
    if "struct" in text or "map" in text or "list" in text or "large_list" in text:
        return "object"
    return "str"


def _ensure_collection(ln: Any, name: str, *, dry_run: bool):
    model = getattr(ln, "Collection", None)
    if model is None:
        return None
    existing = _first(model, key=name)
    if existing is not None or dry_run:
        return existing
    # LaminDB 2.2 Collection uses ``key`` (not ``name``) and its constructor
    # expects an ``artifacts`` argument even for an initially empty collection.
    try:
        return _save(
            model(
                artifacts=[],
                key=name,
                description="Canonical Jouvence KG v2 artifact collection",
            )
        )
    except Exception:
        # Artifact registration is the acceptance-critical phase-1 catalog.  If
        # empty Collection creation is unavailable in a LaminDB release, continue
        # with Artifacts/ULabels/Features and let a later sync attach a collection.
        return None


def _sync_one_artifact(ln: Any, entry: dict[str, Any], collection: Any, *, dry_run: bool) -> ArtifactSyncResult:
    artifact_model = ln.Artifact
    key = entry["key"]
    existing = _first(artifact_model, key=key)
    desc = _description(entry)
    fingerprint = entry.get("metadata_fingerprint")
    if existing is None:
        status = "would_create" if dry_run else "created"
        artifact = None
        if not dry_run:
            artifact = _save(artifact_model(entry["uri"], key=key, description=desc))
    else:
        artifact = existing
        if _description_has_fingerprint(existing, fingerprint):
            status = "noop"
        else:
            status = "would_update" if dry_run else "updated"
            if not dry_run:
                setattr(artifact, "description", desc)
                _save(artifact)

    if artifact is not None and not dry_run:
        labels = _ensure_ulabels(ln, entry.get("labels", []), dry_run=False)
        _attach_many(getattr(artifact, "ulabels", None), labels)
        _ensure_features(ln, entry, artifact, dry_run=False)
        if collection is not None:
            _attach_many(getattr(collection, "artifacts", None), [artifact])

    return ArtifactSyncResult(
        key=key,
        layer=entry.get("layer", ""),
        name=entry.get("name", ""),
        status=status,
        rows=entry.get("rows"),
        metadata_fingerprint=fingerprint,
        uri=entry.get("uri", ""),
    )


def sync_manifest_to_lamindb(
    manifest: dict[str, Any],
    *,
    lamin_instance: str | None = DEFAULT_LAMIN_INSTANCE,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    dry_run: bool = True,
) -> KGArtifactSyncReport:
    ln = None if dry_run else _connect_lamin(lamin_instance)
    collection = None if dry_run else _ensure_collection(ln, collection_name, dry_run=False)
    results: list[ArtifactSyncResult] = []
    errors: list[str] = []
    if dry_run:
        # For dry-run without credentials, classify against an empty catalog.  Unit
        # tests can call the lower-level helpers with fakes for existing records.
        for entry in iter_layer_entries(manifest):
            results.append(
                ArtifactSyncResult(
                    key=entry["key"],
                    layer=entry.get("layer", ""),
                    name=entry.get("name", ""),
                    status="would_create",
                    rows=entry.get("rows"),
                    metadata_fingerprint=entry.get("metadata_fingerprint"),
                    uri=entry.get("uri", ""),
                )
            )
    else:
        for entry in iter_layer_entries(manifest):
            try:
                results.append(_sync_one_artifact(ln, entry, collection, dry_run=False))
            except Exception as exc:  # keep syncing other artifacts; report exact failures
                errors.append(f"{entry.get('key')}: {exc}")
                results.append(
                    ArtifactSyncResult(
                        key=entry.get("key", ""),
                        layer=entry.get("layer", ""),
                        name=entry.get("name", ""),
                        status="error",
                        rows=entry.get("rows"),
                        metadata_fingerprint=entry.get("metadata_fingerprint"),
                        uri=entry.get("uri", ""),
                    )
                )
    return KGArtifactSyncReport(
        dry_run=dry_run,
        lamin_instance=lamin_instance,
        collection=collection_name,
        artifacts=results,
        errors=errors,
    )


def list_registered_metadata(manifest_or_report: dict[str, Any]) -> dict[str, Any]:
    """Return a compact smoke-test view by layer and key.

    This works for both a manifest and a sync report, letting users validate that
    nodes/edges/evidence/features are discoverable without live LaminDB writes.
    """

    entries = manifest_or_report.get("layers") or manifest_or_report.get("artifacts") or []
    by_layer: dict[str, list[dict[str, Any]]] = {"nodes": [], "edges": [], "evidence": [], "features": []}
    for entry in entries:
        layer = entry.get("layer")
        if layer not in by_layer:
            continue
        by_layer[layer].append(
            {
                "key": entry.get("key"),
                "name": entry.get("name"),
                "rows": entry.get("rows"),
                "uri": entry.get("uri"),
                "metadata_fingerprint": entry.get("metadata_fingerprint"),
            }
        )
    for layer in by_layer:
        by_layer[layer] = sorted(by_layer[layer], key=lambda item: item["key"] or "")
    return by_layer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--kg-root", help="Build a fresh manifest from this KG root")
    src.add_argument("--manifest", help="Use an existing manifest JSON")
    parser.add_argument("--write", action="store_true", help="Actually create/update LaminDB records; default is dry-run")
    parser.add_argument("--lamin-instance", default=DEFAULT_LAMIN_INSTANCE)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--manifest-output", help="Optional path to write a freshly-built manifest")
    parser.add_argument("--public-root", default=None, help="Canonical URI root to record when --kg-root scans a local/FUSE mirror")
    parser.add_argument("--report-output", help="Optional path to write the sync report JSON")
    parser.add_argument("--list-metadata", action="store_true", help="Print node/edge/evidence/features discovery view")
    parser.add_argument("--hash-content", action="store_true", help="When building a manifest, sha256 each Parquet file")
    args = parser.parse_args(argv)

    if args.manifest:
        manifest = load_manifest(args.manifest)
    else:
        built = build_manifest(args.kg_root, hash_content=args.hash_content, public_root=args.public_root)
        manifest = built.to_dict()
        if args.manifest_output:
            write_manifest(built, args.manifest_output)

    if args.list_metadata:
        print(json.dumps(list_registered_metadata(manifest), indent=2, sort_keys=True))

    report = sync_manifest_to_lamindb(
        manifest,
        lamin_instance=args.lamin_instance,
        collection_name=args.collection,
        dry_run=not args.write,
    )
    report_payload = report.to_dict()
    if args.report_output:
        Path(args.report_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_output).write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report_payload, indent=2, sort_keys=True))
    return 1 if report.errors else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
