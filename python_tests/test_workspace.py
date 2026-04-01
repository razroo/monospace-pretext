from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fontTools.ttLib import TTFont

from test_generator import PYTHON_CLI, REPO_ROOT, build_fixture_font


class WorkspacePipelineTests(unittest.TestCase):
    def test_workspace_init_and_build_emit_font_ufo_and_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_font = tmp_path / "fixture.ttf"
            workspace = tmp_path / "fixture-workspace"
            output_dir = tmp_path / "artifacts"
            build_fixture_font(source_font)

            subprocess.run(
                [
                    sys.executable,
                    str(PYTHON_CLI),
                    "init-workspace",
                    str(source_font),
                    "--workspace",
                    str(workspace),
                ],
                check=True,
                cwd=REPO_ROOT,
            )

            self.assertTrue((workspace / "project.yaml").exists())
            self.assertTrue((workspace / "sources" / "original.ttf").exists())
            self.assertTrue((workspace / "sources" / "fixture-source.ufo").exists())
            self.assertTrue((workspace / "policies" / "glyph-classes.yaml").exists())
            self.assertTrue((workspace / "policies" / "rules.yaml").exists())
            self.assertTrue((workspace / "policies" / "overrides.yaml").exists())

            subprocess.run(
                [
                    sys.executable,
                    str(PYTHON_CLI),
                    "build-workspace",
                    str(workspace),
                    "--output-dir",
                    str(output_dir),
                ],
                check=True,
                cwd=REPO_ROOT,
            )

            output_font = output_dir / "fixture-mono.ttf"
            output_ufo = output_dir / "fixture-mono.ufo"
            output_woff2 = output_dir / "fixture-mono.woff2"
            proof_path = workspace / "proof" / "index.html"

            self.assertTrue(output_font.exists())
            self.assertTrue(output_ufo.exists())
            self.assertTrue(output_woff2.exists())
            self.assertTrue(proof_path.exists())

            generated = TTFont(output_font)
            metrics = generated["hmtx"].metrics
            self.assertEqual(metrics["space"][0], metrics["A"][0])
            self.assertEqual(metrics["A"][0], metrics["i"][0])
            self.assertEqual(generated["post"].isFixedPitch, 1)

            proof_html = proof_path.read_text(encoding="utf-8")
            self.assertIn("../../artifacts/fixture-mono.ttf", proof_html)
            self.assertIn("../sources/original.ttf", proof_html)


if __name__ == "__main__":
    unittest.main()
