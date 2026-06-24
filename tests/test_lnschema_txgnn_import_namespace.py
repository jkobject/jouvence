import subprocess
import sys
import textwrap


def _run_import_probe(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_manage_db_lnschema_txgnn_aliases_top_level_schema_module_first() -> None:
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
