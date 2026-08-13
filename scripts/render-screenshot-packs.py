from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "docs" / "screenshots"
OUTPUT = ROOT / "output" / "submission"

PATIENT = [
    (
        "Simulated Singpass/MyInfo handoff",
        "The entry point is explicitly marked as a simulation, uses a fictional Jamie Tan profile, and preserves in-person identity and e-card checks.",
        "patient-01-singpass-demo.png",
    ),
    (
        "Live AGNES patient-safe summary",
        "A watermarked company medical chit completed live image parsing. The patient sees document type, issuer, validity, and preparation notes without a coverage claim.",
        "patient-02-live-agnes-summary.png",
    ),
    (
        "Real-time queue and room direction",
        "After staff check-in, the same patient view updated automatically to queue Q30499359 and Consultation Room 3.",
        "patient-03-live-queue-room.png",
    ),
]

CLINIC = [
    (
        "Exception-first review queue",
        "Clinic assistants see a prioritized list of synthetic cases with visit purpose, readiness state, and timestamps.",
        "clinic-01-review-queue.png",
    ),
    (
        "Human-controlled readiness review",
        "Case CP-260813-9A1B shows the live AGNES banner, intake declarations, queue destination, deterministic checks, and a staff-controlled decision.",
        "clinic-02-live-agnes-case-review.png",
    ),
    (
        "Grounded extraction and OCR evidence",
        "AGNES-derived administrative fields remain beside page-grounded OCR evidence; the model cannot approve the case itself.",
        "clinic-03-grounded-evidence.png",
    ),
    (
        "Approved destination and on-site controls",
        "Approval routes the patient to Registration Counter 2 while identity, e-card, and originals remain mandatory in-person checks.",
        "clinic-04-approved-check-in.png",
    ),
]

GREEN = colors.HexColor("#0D6B55")
DARK = colors.HexColor("#123B33")
LIME = colors.HexColor("#CCE879")
CREAM = colors.HexColor("#F6F4EC")
MUTED = colors.HexColor("#5F716B")
LINE = colors.HexColor("#D7E1DC")


def wrapped_lines(pdf: canvas.Canvas, value: str, width: float, font: str, size: float) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or pdf.stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def cover(pdf: canvas.Canvas, page_size: tuple[float, float], surface: str, count: int) -> None:
    width, height = page_size
    pdf.setFillColor(DARK)
    pdf.rect(0, height - 54 * mm, width, 54 * mm, fill=True, stroke=False)
    pdf.setFillColor(LIME)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(18 * mm, height - 17 * mm, "CLINICPASS")
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 27 if width < 700 else 29)
    pdf.drawString(18 * mm, height - 35 * mm, f"{surface} surface")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(18 * mm, height - 45 * mm, "Submission screenshot evidence")

    pdf.setFillColor(GREEN)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(18 * mm, height - 70 * mm, f"{count} CAPTURED STATES")
    pdf.setFillColor(DARK)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(18 * mm, height - 83 * mm, "One coherent synthetic journey")
    text = (
        "All screens use the fictional Jamie Tan profile and ClinicPass demonstration data. "
        "The document journey used the configured live AGNES 2.0 Flash endpoint. "
        "No real patient, Singpass, insurer, or government service was contacted."
    )
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 10)
    y = height - 94 * mm
    for line in wrapped_lines(pdf, text, width - 36 * mm, "Helvetica", 10):
        pdf.drawString(18 * mm, y, line)
        y -= 5 * mm

    pdf.setFillColor(CREAM)
    pdf.setStrokeColor(LINE)
    box_height = 42 * mm
    pdf.roundRect(18 * mm, 35 * mm, width - 36 * mm, box_height, 3 * mm, fill=True, stroke=True)
    pdf.setFillColor(DARK)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(25 * mm, 64 * mm, "Safety boundary")
    boundary = "Administrative readiness only. Clinic staff make the decision; identity, e-card, and originals are checked in person."
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9.5)
    line_y = 55 * mm
    for line in wrapped_lines(pdf, boundary, width - 50 * mm, "Helvetica", 9.5):
        pdf.drawString(25 * mm, line_y, line)
        line_y -= 5 * mm

    footer(pdf, page_size, 1, count + 1)
    pdf.showPage()


def footer(pdf: canvas.Canvas, page_size: tuple[float, float], current: int, total: int) -> None:
    width, _ = page_size
    pdf.setStrokeColor(LINE)
    pdf.line(16 * mm, 13 * mm, width - 16 * mm, 13 * mm)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(16 * mm, 8 * mm, "Synthetic demonstration evidence | No coverage or clinical claim")
    pdf.drawRightString(width - 16 * mm, 8 * mm, f"{current} / {total}")


def screenshot_page(
    pdf: canvas.Canvas,
    page_size: tuple[float, float],
    title: str,
    description: str,
    image_path: Path,
    current: int,
    total: int,
) -> None:
    width, height = page_size
    pdf.setFillColor(DARK)
    pdf.rect(0, height - 24 * mm, width, 24 * mm, fill=True, stroke=False)
    pdf.setFillColor(LIME)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(16 * mm, height - 10 * mm, "CLINICPASS")
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(16 * mm, height - 19 * mm, title)

    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8.5)
    text_y = height - 31 * mm
    for line in wrapped_lines(pdf, description, width - 32 * mm, "Helvetica", 8.5):
        pdf.drawString(16 * mm, text_y, line)
        text_y -= 4 * mm

    image = ImageReader(str(image_path))
    image_width, image_height = image.getSize()
    available_width = width - 32 * mm
    available_height = text_y - 20 * mm
    scale = min(available_width / image_width, available_height / image_height)
    draw_width = image_width * scale
    draw_height = image_height * scale
    x = (width - draw_width) / 2
    y = 17 * mm + (available_height - draw_height) / 2
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(LINE)
    pdf.roundRect(x - 1.5 * mm, y - 1.5 * mm, draw_width + 3 * mm, draw_height + 3 * mm, 2 * mm, fill=True, stroke=True)
    pdf.drawImage(image, x, y, width=draw_width, height=draw_height, preserveAspectRatio=True, mask="auto")
    footer(pdf, page_size, current, total)
    pdf.showPage()


def build(filename: str, surface: str, entries: list[tuple[str, str, str]], page_size: tuple[float, float]) -> None:
    paths = [SCREENSHOTS / entry[2] for entry in entries]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise SystemExit("Missing screenshots: " + ", ".join(missing))

    output = OUTPUT / filename
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output), pagesize=page_size)
    pdf.setTitle(f"ClinicPass {surface} Surface")
    pdf.setAuthor("ClinicPass")
    total = len(entries) + 1
    cover(pdf, page_size, surface, len(entries))
    for index, ((title, description, _), path) in enumerate(zip(entries, paths, strict=True), 2):
        screenshot_page(pdf, page_size, title, description, path, index, total)
    pdf.save()
    print(f"Generated {output} ({total} pages)")


def main() -> None:
    build("03-ClinicPass-patient-surface.pdf", "Patient", PATIENT, A4)
    build("04-ClinicPass-clinic-admin-surface.pdf", "Clinic admin", CLINIC, landscape(A4))


if __name__ == "__main__":
    main()
