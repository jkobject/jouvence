import subprocess
import sys
import textwrap

import pytest


def _skip_if_lnschema_txgnn_is_not_configured() -> None:
    result = _run_import_probe(
        """
        from lamindb_setup import settings

        modules = set(getattr(settings.instance, "modules", set()) or set())
        normalized = {module.replace("lnschema_", "").replace("_", "-") for module in modules}
        is_configured = (
            "lnschema_txgnn" in modules
            or "txgnn" in modules
            or "txgnn" in normalized
        )
        raise SystemExit(0 if is_configured else 1)
        """
    )
    if result.returncode == 1:
        pytest.skip("active LaminDB instance is not configured with lnschema_txgnn")
    assert result.returncode == 0, result.stderr + result.stdout


def _run_import_probe(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_manage_db_lnschema_txgnn_aliases_top_level_schema_module_first() -> None:
    _skip_if_lnschema_txgnn_is_not_configured()

    result = _run_import_probe(
        """
        import manage_db.lnschema_txgnn as package_path
        import lnschema_txgnn as top_level

        assert package_path is top_level
        assert package_path.Paper is top_level.Paper
        assert package_path.Paper.__module__ == "lnschema_txgnn.models"
        """
    )

    assert result.returncode == 0, result.stderr + result.stdout


def test_manage_db_lnschema_txgnn_aliases_top_level_schema_module_after_canonical_import() -> None:
    _skip_if_lnschema_txgnn_is_not_configured()

    result = _run_import_probe(
        """
        import lnschema_txgnn as top_level
        import manage_db.lnschema_txgnn as package_path

        assert package_path is top_level
        assert package_path.Paper is top_level.Paper
        assert package_path.Paper.__module__ == "lnschema_txgnn.models"
        """
    )

    assert result.returncode == 0, result.stderr + result.stdout
