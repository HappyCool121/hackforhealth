from pathlib import Path
import runpy

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "output" / "submission" / "01-ClinicPass-main-report.pdf"
DOCUMENTS = ROOT / "output" / "submission" / "02-ClinicPass-synthetic-demo-documents.pdf"
PATIENT = ROOT / "output" / "submission" / "03-ClinicPass-patient-surface.pdf"
CLINIC = ROOT / "output" / "submission" / "04-ClinicPass-clinic-admin-surface.pdf"
MAX_BYTES = 10 * 1024 * 1024
WATERMARK = "SYNTHETIC DEMO - NOT VALID FOR CARE, CLAIMS, OR IDENTITY"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def text(reader: PdfReader) -> str:
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def verify_a4(reader: PdfReader, name: str) -> None:
    for index, page in enumerate(reader.pages, 1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        portrait = abs(width - 595.28) < 1 and abs(height - 841.89) < 1
        landscape = abs(width - 841.89) < 1 and abs(height - 595.28) < 1
        require(portrait or landscape, f"{name} page {index} is not A4")


def main() -> None:
    for path in (MAIN, DOCUMENTS, PATIENT, CLINIC):
        require(path.is_file(), f"Missing submission file: {path}")
        require(path.stat().st_size < MAX_BYTES, f"Submission file exceeds 10 MB: {path.name}")

    main_reader = PdfReader(str(MAIN))
    require(len(main_reader.pages) == 4, "Main report must be exactly four pages")
    verify_a4(main_reader, MAIN.name)
    main_text = text(main_reader)
    for phrase in (
        "Team\nClinicPass",
        "APPENDIX: AI TOOLS",
        "AGNES 2.0 Flash",
        "OpenAI Codex",
        "Microsoft Copilot Studio",
        "https://github.com/HappyCool121/hackforhealth",
    ):
        require(phrase in main_text, f"Main report is missing required text: {phrase}")

    source = runpy.run_path(str(ROOT / "scripts" / "render-submission.py"))
    summary_words = len(source["EXECUTIVE_SUMMARY"].split())
    require(summary_words <= 200, f"Executive summary exceeds 200 words: {summary_words}")

    document_reader = PdfReader(str(DOCUMENTS))
    require(len(document_reader.pages) == 6, "Synthetic document pack must contain one cover and five fixtures")
    verify_a4(document_reader, DOCUMENTS.name)
    for index, page in enumerate(document_reader.pages, 1):
        page_text = page.extract_text() or ""
        require(page_text.strip(), f"Synthetic document pack page {index} is blank")
        require(WATERMARK in page_text, f"Synthetic watermark missing from page {index}")

    patient_reader = PdfReader(str(PATIENT))
    require(len(patient_reader.pages) == 4, "Patient surface pack must contain one cover and three screenshots")
    verify_a4(patient_reader, PATIENT.name)
    patient_text = text(patient_reader)
    for phrase in ("Simulated Singpass/MyInfo handoff", "Live AGNES patient-safe summary", "Real-time queue and room direction"):
        require(phrase in patient_text, f"Patient surface pack is missing: {phrase}")

    clinic_reader = PdfReader(str(CLINIC))
    require(len(clinic_reader.pages) == 5, "Clinic admin pack must contain one cover and four screenshots")
    verify_a4(clinic_reader, CLINIC.name)
    clinic_text = text(clinic_reader)
    for phrase in ("Exception-first review queue", "Human-controlled readiness review", "Grounded extraction and OCR evidence", "Approved destination and on-site controls"):
        require(phrase in clinic_text, f"Clinic admin pack is missing: {phrase}")

    print(
        "Submission PDF verification passed: "
        f"main=4 pages/{MAIN.stat().st_size} bytes/{summary_words} summary words; "
        f"documents=6 pages/{DOCUMENTS.stat().st_size} bytes; "
        f"patient=4 pages/{PATIENT.stat().st_size} bytes; "
        f"clinic=5 pages/{CLINIC.stat().st_size} bytes"
    )


if __name__ == "__main__":
    main()
