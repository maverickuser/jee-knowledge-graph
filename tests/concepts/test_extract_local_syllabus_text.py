import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch

from scripts.extract_local_syllabus_text import (
    OcrExtractionResult,
    _missing_ocr_tools,
    _resolve_tool,
    extract_syllabus_status,
)


class ExtractLocalSyllabusTextTest(unittest.TestCase):
    @patch("scripts.extract_local_syllabus_text.Path.exists", return_value=False)
    @patch("scripts.extract_local_syllabus_text.shutil.which", return_value=None)
    def test_missing_ocr_tools_reports_tesseract(self, _which, _exists):
        missing = _missing_ocr_tools()

        self.assertIn("tesseract", missing)
        self.assertIn("pdftoppm", missing)

    @patch("scripts.extract_local_syllabus_text.Path.exists", return_value=True)
    def test_resolve_tool_prefers_scoop_shim(self, _exists):
        resolved = _resolve_tool("pdftoppm")

        self.assertEqual(Path(resolved).parts[-3:], ("scoop", "shims", "pdftoppm.exe"))

    @patch("scripts.extract_local_syllabus_text._extract_embedded_text", return_value="")
    @patch("scripts.extract_local_syllabus_text._missing_ocr_tools", return_value=[])
    @patch(
        "scripts.extract_local_syllabus_text._extract_ocr_text",
        side_effect=subprocess.CalledProcessError(
            7,
            ["pdftoppm", "input.pdf", "out"],
            output="",
            stderr="render failed",
        ),
    )
    def test_ocr_command_failure_returns_status(
        self,
        _extract_ocr_text,
        _missing_tools,
        _extract_embedded_text,
    ):
        status = extract_syllabus_status(Path(__file__), Path("unused.txt"))

        self.assertEqual("ocr_failed", status["status"])
        self.assertEqual(7, status["exit_code"])
        self.assertEqual("render failed", status["stderr"])

    @patch("scripts.extract_local_syllabus_text._extract_embedded_text", return_value="")
    @patch("scripts.extract_local_syllabus_text._missing_ocr_tools", return_value=[])
    @patch(
        "scripts.extract_local_syllabus_text._extract_ocr_text",
        return_value=OcrExtractionResult(
            text="",
            rendered_page_count=1,
            rendered_image_bytes=33210,
        ),
    )
    def test_ocr_no_text_returns_render_metadata(
        self,
        _extract_ocr_text,
        _missing_tools,
        _extract_embedded_text,
    ):
        status = extract_syllabus_status(Path(__file__), Path("unused.txt"))

        self.assertEqual("ocr_produced_no_text", status["status"])
        self.assertEqual(1, status["rendered_page_count"])
        self.assertEqual(33210, status["rendered_image_bytes"])


if __name__ == "__main__":
    unittest.main()
