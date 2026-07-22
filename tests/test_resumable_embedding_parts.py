import json
from pathlib import Path

import numpy as np
import pandas as pd

from manage_db.resumable_embedding_parts import can_skip_valid_part


def test_resume_rejects_part_when_runtime_encoder_identity_drifts(tmp_path: Path) -> None:
    embedding = tmp_path / "part.parquet"
    skipped = tmp_path / "skipped.parquet"
    meta = tmp_path / "part.json"
    pd.DataFrame(
        [
            {
                "embedding_key": "e1",
                "node_id": "ENSG1",
                "source_feature_key": "f1",
                "source_feature_hash": "h1",
                "embedding_dim": 2,
                "embedding": np.asarray([1.0, 0.0], dtype=np.float32),
                "source_row_index": 0,
                "window_count": 1,
            }
        ]
    ).to_parquet(embedding)
    pd.DataFrame(columns=["row_index", "node_id", "reason"]).to_parquet(skipped)
    expected = {
        "row_start": 0,
        "row_end": 1,
        "encoder_identity": "real_huggingface_remote_code",
        "resolved_revision": "pinned",
        "transformers_version": "4.55.4",
        "source_sha256": "source",
    }
    poisoned = dict(expected, encoder_identity="deterministic_test_encoder")
    meta.write_text(json.dumps(poisoned))

    valid, checks = can_skip_valid_part(
        embedding,
        skipped,
        meta,
        expected=expected,
        expected_dim=2,
        skipped_required_columns=["row_index", "node_id", "reason"],
    )

    assert not valid
    assert not checks["metadata_matches_expected"]
