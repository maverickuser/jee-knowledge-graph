import argparse
from dataclasses import dataclass
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pdfplumber


DEFAULT_INPUT = Path(r"C:\Users\Saurabh\Downloads\physics\syllabus (1).pdf")
DEFAULT_TEXT_OUTPUT = Path("data/concepts/physics_sources/syllabus_ocr.txt")
DEFAULT_STATUS_OUTPUT = Path("data/concepts/physics_sources/syllabus_extraction_status.json")


@dataclass(frozen=True)
class OcrExtractionResult:
    text: str
    rendered_page_count: int
    rendered_image_bytes: int


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract local syllabus PDF text or report required OCR dependencies."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--text-output", type=Path, default=DEFAULT_TEXT_OUTPUT)
    parser.add_argument("--status-output", type=Path, default=DEFAULT_STATUS_OUTPUT)
    args = parser.parse_args()

    status = extract_syllabus_status(args.input, args.text_output)
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0 if status["status"] in {"embedded_text_extracted", "ocr_text_extracted"} else 2


def extract_syllabus_status(input_pdf: Path, text_output: Path) -> dict:
    if not input_pdf.exists():
        return {
            "status": "missing_input",
            "input_pdf": str(input_pdf),
            "message": "Local syllabus PDF was not found.",
        }

    embedded_text = _extract_embedded_text(input_pdf)
    if embedded_text.strip():
        text_output.parent.mkdir(parents=True, exist_ok=True)
        text_output.write_text(embedded_text, encoding="utf-8")
        return {
            "status": "embedded_text_extracted",
            "input_pdf": str(input_pdf),
            "text_output": str(text_output),
            "character_count": len(embedded_text),
        }

    missing_tools = _missing_ocr_tools()
    if missing_tools:
        return {
            "status": "ocr_dependencies_missing",
            "input_pdf": str(input_pdf),
            "missing_tools": missing_tools,
            "message": (
                "The PDF has no embedded text. Install Tesseract and Python OCR/rendering "
                "dependencies, or provide a text syllabus file."
            ),
        }

    try:
        ocr_result = _extract_ocr_text(input_pdf)
    except subprocess.CalledProcessError as exc:
        return {
            "status": "ocr_failed",
            "input_pdf": str(input_pdf),
            "failed_command": exc.cmd,
            "exit_code": exc.returncode,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "message": "OCR command failed while rendering or reading the image-only PDF.",
        }
    if ocr_result.text.strip():
        text_output.parent.mkdir(parents=True, exist_ok=True)
        text_output.write_text(ocr_result.text, encoding="utf-8")
        return {
            "status": "ocr_text_extracted",
            "input_pdf": str(input_pdf),
            "text_output": str(text_output),
            "character_count": len(ocr_result.text),
            "rendered_page_count": ocr_result.rendered_page_count,
            "rendered_image_bytes": ocr_result.rendered_image_bytes,
            "ocr_tools": {
                "pdftoppm": _resolve_tool("pdftoppm"),
                "tesseract": _resolve_tool("tesseract"),
                "tessdata": _resolve_tessdata_prefix(),
            },
        }

    return {
        "status": "ocr_produced_no_text",
        "input_pdf": str(input_pdf),
        "rendered_page_count": ocr_result.rendered_page_count,
        "rendered_image_bytes": ocr_result.rendered_image_bytes,
        "message": (
            "OCR tools ran but produced no text. The rendered PDF appears to "
            "contain no extractable text content."
        ),
    }


def _extract_embedded_text(path: Path) -> str:
    page_texts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                page_texts.append(text)
    return "\n\n".join(page_texts)


def _missing_ocr_tools() -> list[str]:
    missing: list[str] = []
    if not _resolve_tool("tesseract"):
        missing.append("tesseract")
    if not _resolve_tool("pdftoppm"):
        missing.append("pdftoppm")
    if not _resolve_tessdata_prefix():
        missing.append("tesseract_eng_traineddata")
    return missing


def _resolve_tool(name: str) -> str | None:
    scoop_shim = Path.home() / "scoop" / "shims" / f"{name}.exe"
    if scoop_shim.exists():
        return str(scoop_shim)
    return shutil.which(name)


def _resolve_tessdata_prefix() -> str | None:
    candidates = [
        Path.home() / "scoop" / "apps" / "tesseract" / "current" / "tessdata",
        Path.home()
        / "scoop"
        / "apps"
        / "tesseract-languages"
        / "current"
        / "tessdata_fast-4.1.0",
        Path.home()
        / "scoop"
        / "apps"
        / "tesseract-languages"
        / "4.1.0"
        / "tessdata_fast-4.1.0",
    ]
    for candidate in candidates:
        if (candidate / "eng.traineddata").exists():
            return str(candidate)
    return None


def _extract_ocr_text(path: Path) -> OcrExtractionResult:
    pdftoppm = _resolve_tool("pdftoppm")
    tesseract = _resolve_tool("tesseract")
    tessdata = _resolve_tessdata_prefix()
    if pdftoppm is None or tesseract is None:
        raise RuntimeError("OCR tools must be present before extraction.")
    if tessdata is None:
        raise RuntimeError("Tesseract English language data must be present before extraction.")

    with tempfile.TemporaryDirectory() as tmpdir:
        ocr_env = os.environ.copy()
        ocr_env["TESSDATA_PREFIX"] = tessdata
        output_prefix = Path(tmpdir) / "syllabus_page"
        subprocess.run(
            [
                pdftoppm,
                "-r",
                "300",
                "-png",
                str(path),
                str(output_prefix),
            ],
                check=True,
                capture_output=True,
                text=True,
                env=ocr_env,
        )
        page_images = sorted(Path(tmpdir).glob("syllabus_page-*.png"))
        rendered_image_bytes = sum(image_path.stat().st_size for image_path in page_images)
        page_texts: list[str] = []
        for image_path in page_images:
            result = subprocess.run(
                [tesseract, str(image_path), "stdout", "-l", "eng"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=ocr_env,
            )
            if result.stdout.strip():
                page_texts.append(result.stdout.strip())
        return OcrExtractionResult(
            text="\n\n".join(page_texts),
            rendered_page_count=len(page_images),
            rendered_image_bytes=rendered_image_bytes,
        )


if __name__ == "__main__":
    raise SystemExit(main())
