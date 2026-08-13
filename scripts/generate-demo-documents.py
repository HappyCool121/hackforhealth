from pathlib import Path
import shutil

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "synthetic" / "tablet-display"
WEB_DIR = ROOT / "apps" / "web" / "public" / "tablet-samples"
WATERMARK = "SYNTHETIC DEMO - NOT VALID FOR CARE, CLAIMS, OR IDENTITY"
GREEN = colors.HexColor("#0D6B55")
DARK = colors.HexColor("#123B33")
MINT = colors.HexColor("#DFF4EA")
CREAM = colors.HexColor("#F6F4EC")
INK = colors.HexColor("#142B27")
MUTED = colors.HexColor("#60716C")
LINE = colors.HexColor("#D7E1DC")
RED = colors.HexColor("#9A3328")


def start_pdf(path: Path, title: str, issuer: str) -> canvas.Canvas:
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    pdf.setTitle(f"Synthetic ClinicPass demo - {title}")
    pdf.setAuthor("ClinicPass synthetic fixture generator")
    width, height = A4
    pdf.setFillColor(RED)
    pdf.rect(0, height - 13 * mm, width, 13 * mm, fill=True, stroke=False)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 8.2)
    pdf.drawCentredString(width / 2, height - 8.2 * mm, WATERMARK)
    pdf.setFillColor(CREAM)
    pdf.rect(0, 0, width, height - 13 * mm, fill=True, stroke=False)
    pdf.setFillColor(DARK)
    pdf.roundRect(16 * mm, height - 53 * mm, width - 32 * mm, 27 * mm, 4 * mm, fill=True, stroke=False)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(23 * mm, height - 39 * mm, title.upper())
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColor(colors.HexColor("#C9DDD7"))
    pdf.drawString(23 * mm, height - 46 * mm, issuer)
    pdf.setStrokeColor(LINE)
    pdf.setFillColor(colors.white)
    pdf.roundRect(16 * mm, 25 * mm, width - 32 * mm, height - 86 * mm, 4 * mm, fill=True, stroke=True)

    pdf.saveState()
    pdf.translate(width / 2, height / 2)
    pdf.rotate(31)
    pdf.setFillColor(colors.Color(0.6, 0.2, 0.17, alpha=0.055))
    pdf.setFont("Helvetica-Bold", 27)
    pdf.drawCentredString(0, 0, "SYNTHETIC DEMO")
    pdf.restoreState()
    return pdf


def draw_fields(pdf: canvas.Canvas, fields: list[tuple[str, str]], note: str) -> None:
    width, height = A4
    left = 25 * mm
    right = width - 25 * mm
    y = height - 68 * mm
    for label, value in fields:
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica-Bold", 7.3)
        pdf.drawString(left, y, label.upper())
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 10.8)
        pdf.drawString(left + 55 * mm, y - 1 * mm, value)
        y -= 12 * mm
        pdf.setStrokeColor(LINE)
        pdf.line(left, y + 5 * mm, right, y + 5 * mm)
    pdf.setFillColor(MINT)
    pdf.roundRect(left, 37 * mm, right - left, 24 * mm, 3 * mm, fill=True, stroke=False)
    pdf.setFillColor(GREEN)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(left + 5 * mm, 53 * mm, "ADMINISTRATIVE NOTE")
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica", 8.2)
    words = note.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdf.stringWidth(candidate, "Helvetica", 8.2) > right - left - 10 * mm:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    for index, line in enumerate(lines[:2]):
        pdf.drawString(left + 5 * mm, 47 * mm - index * 4.5 * mm, line)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 6.8)
    pdf.drawString(left, 19 * mm, "Fictional people, organisations, identifiers, and entitlements. For ClinicPass judging only.")


def finish_pdf(pdf: canvas.Canvas) -> None:
    pdf.showPage()
    pdf.save()


def create_pdfs() -> list[Path]:
    definitions = [
        (
            "company-medical-chit.pdf",
            "Company medical chit",
            "Northstar Corporate Benefits - fictional issuer",
            [
                ("Patient", "Jamie Tan"),
                ("ID last four", "123A"),
                ("Clinic", "Central Family Clinic"),
                ("Clinic ID", "clinic-central"),
                ("Organisation code", "ORG-DEMO"),
                ("Package code", "PKG-SCREEN"),
                ("Billing arrangement", "direct"),
                ("Payer", "Demo Health Fund"),
                ("Valid to", "31 December 2027"),
            ],
            "No fasting required. Bring this original medical chit and your identity document for in-person verification.",
        ),
        (
            "referral-letter.pdf",
            "Referral letter",
            "Harbourview Family Practice - fictional clinic",
            [
                ("Patient", "Jamie Tan"),
                ("ID last four", "123A"),
                ("Referred to", "Central Family Clinic"),
                ("Clinic ID", "clinic-central"),
                ("Organisation code", "ORG-DEMO"),
                ("Package code", "PKG-SCREEN"),
                ("Referral purpose", "Preventive screening review"),
                ("Valid to", "31 December 2027"),
            ],
            "Administrative referral only. The receiving clinic must review the request and confirm all original documents in person.",
        ),
        (
            "healthier-sg-form.pdf",
            "Healthier SG administrative form",
            "Community Wellness Network - fictional issuer; no official affiliation",
            [
                ("Patient", "Jamie Tan"),
                ("ID last four", "123A"),
                ("Clinic", "Central Family Clinic"),
                ("Clinic ID", "clinic-central"),
                ("Visit", "Periodic preventive check-up"),
                ("Organisation code", "ORG-DEMO"),
                ("Package code", "PKG-SCREEN"),
                ("Payer", "Demo Health Fund"),
                ("Valid to", "31 December 2027"),
            ],
            "This fictional form is not issued by the Singapore Government. Clinic staff must confirm the visit pathway and originals.",
        ),
        (
            "six-month-checkup-letter.pdf",
            "Six-month government check-up letter",
            "Civic Wellness Office - entirely fictional issuer",
            [
                ("Patient", "Jamie Tan"),
                ("ID last four", "123A"),
                ("Check-up frequency", "Every six months"),
                ("Required clinic", "West Demo Clinic"),
                ("Clinic ID", "clinic-west"),
                ("Organisation code", "ORG-DEMO"),
                ("Package code", "PKG-SCREEN"),
                ("Billing arrangement", "direct"),
                ("Valid to", "31 December 2027"),
            ],
            "Demo exception: this letter names West Demo Clinic, while the ClinicPass registration uses Central Family Clinic.",
        ),
        (
            "drivers-license-renewal-form.pdf",
            "Driver's licence renewal medical form",
            "Road Fitness Renewal Office - entirely fictional issuer; no official affiliation",
            [
                ("Applicant", "Jamie Tan"),
                ("ID last four", "123A"),
                ("Licence class", "Class 3"),
                ("Renewal due", "31 December 2027"),
                ("Assessment clinic", "Central Family Clinic"),
                ("Clinic ID", "clinic-central"),
                ("Organisation code", "ORG-DEMO"),
                ("Package code", "PKG-SCREEN"),
                ("Billing arrangement", "self-pay"),
            ],
            "Administrative renewal demo only. This is not a driving licence, medical clearance, or government form.",
        ),
    ]
    outputs: list[Path] = []
    for filename, title, issuer, fields, note in definitions:
        path = FIXTURE_DIR / filename
        pdf = start_pdf(path, title, issuer)
        draw_fields(pdf, fields, note)
        finish_pdf(pdf)
        outputs.append(path)
    return outputs


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    outputs = create_pdfs()
    for output in outputs:
        shutil.copy2(output, WEB_DIR / output.name)
    print(f"Generated {len(outputs)} synthetic demo documents in {FIXTURE_DIR} and {WEB_DIR}")


if __name__ == "__main__":
    main()
