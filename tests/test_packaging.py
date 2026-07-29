"""Build the distribution and verify runtime data files are installable."""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from t20_mcp.config import LISP_DIR

ROOT = Path(__file__).resolve().parent.parent


def test_source_dispatcher_path_exists() -> None:
    assert (LISP_DIR / "mcp_dispatch.lsp").is_file()


def test_built_archives_include_dispatcher_and_tangent_templates(tmp_path: Path) -> None:
    subprocess.run(
        ["uv", "build", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        wheel_files = set(archive.namelist())
        extracted = tmp_path / "extracted"
        archive.extractall(extracted)
    assert "t20_mcp/lisp_code/mcp_dispatch.lsp" in wheel_files
    assert "t20_mcp/lisp_templates/tangent/_prelude.lsp" in wheel_files
    assert "t20_mcp/lisp_templates/tangent/opening.lsp" in wheel_files

    source_archive = next(tmp_path.glob("*.tar.gz"))
    with tarfile.open(source_archive, "r:gz") as archive:
        source_files = archive.getnames()
    assert any(name.endswith("/lisp-code/mcp_dispatch.lsp") for name in source_files)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(extracted)
    installed_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from t20_mcp.config import LISP_DIR; "
                "path = LISP_DIR / 'mcp_dispatch.lsp'; "
                "assert path.is_file(), path; "
                "print(path)"
            ),
        ],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "t20_mcp" in installed_probe.stdout
    assert "lisp_code" in installed_probe.stdout
