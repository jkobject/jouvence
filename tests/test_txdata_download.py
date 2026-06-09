from __future__ import annotations

from urllib.error import HTTPError

import txdata_download


def test_list_opentargets_datasets_falls_back_to_output_layout(monkeypatch) -> None:
    calls: list[str] = []

    def fake_list(url: str) -> list[str]:
        calls.append(url)
        if url.endswith("/output/etl/parquet/"):
            raise HTTPError(url, 404, "Not Found", {}, None)
        return ["../", "target/", "disease/", "manifest.json"]

    monkeypatch.setattr(txdata_download, "_list_ftp_dir", fake_list)

    datasets = txdata_download.list_opentargets_datasets("26.03")

    assert datasets == ["disease", "target"]
    assert calls == [
        "https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/etl/parquet/",
        "https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/",
    ]
