from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures" / "synthetic" / "tablet-display"
OUTPUT = ROOT / "output" / "submission" / "02-ClinicPass-synthetic-demo-documents.pdf"

DOCUMENTS = [
    ("Company medical chit", "company-medical-chit.pdf", "Clean administrative readiness path"),
    ("Referral letter", "referral-letter.pdf", "Fictional specialist referral example"),
    ("Healthier SG form", "healthier-sg-form.pdf", "Periodic-care administration example"),
    ("Six-month check-up letter", "six-month-checkup-letter.pdf", "Deliberate clinic-location review path"),
    ("Driver's licence renewal form", "drivers-license-renewal-form.pdf", "Renewal medical-administration example"),
]

GREEN = colors.HexColor("#0D6B55")
DARK = colors.HexColor("#123B33")
MINT = colors.HexColor("#DFF4EA")
LIME = colors.HexColor("#CCE879")
CREAM = colors.HexColor("#F6F4EC")
MUTED = colors.HexColor("#5F716B")
LINE = colors.HexColor("#D7E1DC")


def cover_page() -> bytes:
    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    page.setTitle("ClinicPass Synthetic Demo Documents")
    page.setAuthor("ClinicPass")

    page.setFillColor(DARK)
    page.rect(0, height - 43 * mm, width, 43 * mm, fill=True, stroke=False)
    page.setFillColor(LIME)
    page.setFont("Helvetica-Bold", 11)
    page.drawString(17 * mm, height - 15 * mm, "CLINICPASS")
    page.setFillColor(colors.white)
    page.setFont("Helvetica-Bold", 27)
    page.drawString(17 * mm, height - 30 * mm, "Synthetic demo documents")

    page.setFillColor(GREEN)
    page.setFont("Helvetica-Bold", 10)
    page.drawString(17 * mm, height - 58 * mm, "SUPPORTING FILE 1 OF 3")
    page.setFillColor(DARK)
    page.setFont("Helvetica-Bold", 16)
    page.drawString(17 * mm, height - 69 * mm, "Five tablet-ready OCR fixtures")
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 9.5)
    page.drawString(17 * mm, height - 77 * mm, "Each following page is the original one-page fixture used by the live demo.")

    y = height - 94 * mm
    for index, (title, _, note) in enumerate(DOCUMENTS, 1):
        page.setFillColor(CREAM if index % 2 else colors.white)
        page.setStrokeColor(LINE)
        page.roundRect(17 * mm, y - 19 * mm, width - 34 * mm, 17 * mm, 2 * mm, fill=True, stroke=True)
        page.setFillColor(MINT)
        page.circle(28 * mm, y - 10.5 * mm, 5 * mm, fill=True, stroke=False)
        page.setFillColor(GREEN)
        page.setFont("Helvetica-Bold", 10)
        page.drawCentredString(28 * mm, y - 12.3 * mm, str(index))
        page.setFillColor(DARK)
        page.setFont("Helvetica-Bold", 10.5)
        page.drawString(38 * mm, y - 8.5 * mm, title)
        page.setFillColor(MUTED)
        page.setFont("Helvetica", 8.5)
        page.drawString(38 * mm, y - 14 * mm, note)
        y -= 21 * mm

    page.setFillColor(colors.HexColor("#A43127"))
    page.roundRect(17 * mm, 27 * mm, width - 34 * mm, 18 * mm, 2 * mm, fill=True, stroke=False)
    page.setFillColor(colors.white)
    page.setFont("Helvetica-Bold", 9.5)
    page.drawCentredString(width / 2, 37 * mm, "SYNTHETIC DEMO - NOT VALID FOR CARE, CLAIMS, OR IDENTITY")
    page.setFont("Helvetica", 7.5)
    page.drawCentredString(width / 2, 31.7 * mm, "Fictional organisations and identifiers; no government or insurer logos.")

    page.setStrokeColor(LINE)
    page.line(17 * mm, 17 * mm, width - 17 * mm, 17 * mm)
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 7.5)
    page.drawString(17 * mm, 11 * mm, "ClinicPass | Hack4Health 2026 technical submission")
    page.drawRightString(width - 17 * mm, 11 * mm, "1 / 6")
    page.save()
    return buffer.getvalue()


def main() -> None:
    missing = [str(SOURCE / filename) for _, filename, _ in DOCUMENTS if not (SOURCE / filename).is_file()]
    if missing:
        raise SystemExit("Missing fixture files: " + ", ".join(missing))

    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(cover_page())))
    for _, filename, _ in DOCUMENTS:
        reader = PdfReader(str(SOURCE / filename))
        if len(reader.pages) != 1:
            raise SystemExit(f"Expected one page in {filename}, found {len(reader.pages)}")
        writer.append(reader)

    writer.add_metadata({
        "/Title": "ClinicPass Synthetic Demo Documents",
        "/Author": "ClinicPass",
        "/Subject": "Synthetic-only OCR demonstration fixtures",
    })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("wb") as handle:
        writer.write(handle)

    pages = len(PdfReader(str(OUTPUT)).pages)
    if pages != 6:
        raise SystemExit(f"Expected 6 pages, generated {pages}")
    print(f"Generated {OUTPUT} ({pages} pages)")


if __name__ == "__main__":
    main()
