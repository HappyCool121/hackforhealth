from pathlib import Path
from shutil import copyfile
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "submission" / "01-ClinicPass-main-report.pdf"
LEGACY_OUTPUT = ROOT / "output" / "pdf" / "ClinicPass-technical-submission.pdf"
GREEN = colors.HexColor("#0D6B55")
DARK = colors.HexColor("#123B33")
MINT = colors.HexColor("#DFF4EA")
LIME = colors.HexColor("#CCE879")
CREAM = colors.HexColor("#F6F4EC")
INK = colors.HexColor("#142B27")
MUTED = colors.HexColor("#5F716B")
LINE = colors.HexColor("#D7E1DC")

EXECUTIVE_SUMMARY = """ClinicPass V2 moves provisional administrative eligibility and pre-registration ahead of arrival. Patients confirm a reusable masked profile, complete a versioned questionnaire, choose requested services, and upload synthetic evidence. AGNES or a labelled fixture provider creates field assertions with page evidence. Eleven deterministic rules compare identity, validity, issuer, organisation, package, panel clinic, service coverage, supporting documents, billing route, and conflicts against immutable synthetic references. Outcomes are provisional, review-required, or blocked—never guaranteed coverage. Staff inspect originals beside extracted fields, preserve audited corrections, and request finding-level manager overrides. Approval rejects stale inputs, active processing, Needs Action, or unresolved findings. Identity, e-card, and originals are attested separately on site. A schema-validating idempotent Clinic Assist V2 mock receives the masked profile, questionnaire, eligibility, services, evidence, corrections, overrides, and attestations. ClinicPass does not make clinical, fitness, remote identity, reimbursement, or final-payment decisions."""


styles = getSampleStyleSheet()
title = ParagraphStyle("Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=29, leading=31, textColor=DARK, alignment=TA_LEFT, spaceAfter=5 * mm)
h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=21, textColor=DARK, spaceAfter=4 * mm)
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=GREEN, spaceBefore=2 * mm, spaceAfter=1.4 * mm)
body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.6, leading=12, textColor=INK, spaceAfter=2.4 * mm)
small = ParagraphStyle("Small", parent=body, fontSize=7.5, leading=10, textColor=MUTED)
white_small = ParagraphStyle("White", parent=small, textColor=colors.white)
label = ParagraphStyle("Label", parent=small, fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=GREEN, uppercase=True, spaceAfter=1 * mm)
center = ParagraphStyle("Center", parent=small, alignment=TA_CENTER, textColor=INK)


def P(text: str, style=body) -> Paragraph:
    return Paragraph(text, style)


def bullet(text: str) -> Paragraph:
    return Paragraph(f"- {text}", body)


def card(heading: str, content: str, width: float) -> Table:
    table = Table([[P(heading, h2)], [P(content, small)]], colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
    ]))
    return table


def header_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.rect(0, A4[1] - 14 * mm, A4[0], 14 * mm, fill=True, stroke=False)
    canvas.setFillColor(LIME)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(16 * mm, A4[1] - 9 * mm, "CLINICPASS")
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(A4[0] - 16 * mm, A4[1] - 9 * mm, "Technical submission | Synthetic-data prototype")
    canvas.setStrokeColor(LINE)
    canvas.line(16 * mm, 12 * mm, A4[0] - 16 * mm, 12 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(16 * mm, 7.5 * mm, "Administrative readiness only. No clinical decisions or coverage guarantee.")
    canvas.drawRightString(A4[0] - 16 * mm, 7.5 * mm, f"{doc.page} / 4")
    canvas.restoreState()


def process_flow() -> Table:
    cells = ["Mock identity + visit", "Camera / file upload", "AGNES vision + OCR", "11 deterministic checks", "Staff decision", "On-site checks + export"]
    row = []
    for index, text in enumerate(cells):
        row.append(P(f"<b>{index + 1}</b><br/>{text}", center))
        if index < len(cells) - 1:
            row.append(P("&gt;", center))
    widths = []
    for index in range(len(row)):
        widths.append(25 * mm if index % 2 == 0 else 4 * mm)
    table = Table([row], colWidths=widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MINT),
        ("BACKGROUND", (1, 0), (-2, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0.5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0.5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))
    return table


def build_story() -> list:
    usable = A4[0] - 32 * mm
    col = (usable - 6 * mm) / 2
    story = []

    # Page 1
    story += [Spacer(1, 3 * mm), P("CLINIC OPERATIONS + RESPONSIBLE AI", label), P("Arrive ready.<br/>Start care sooner.", title)]
    story += [Table([[P("Team", label), P("ClinicPass", body)], [P("Build status", label), P("Runnable MVP; live AGNES vision endpoint verified", body)]], colWidths=[32 * mm, usable - 32 * mm], style=[("BACKGROUND", (0, 0), (-1, -1), CREAM), ("BOX", (0, 0), (-1, -1), .5, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm), ("TOPPADDING", (0, 0), (-1, -1), 2 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm)])]
    story += [Spacer(1, 4 * mm), P("Executive summary", h1), P(EXECUTIVE_SUMMARY)]
    story += [P("The problem", h1), P("The source specification identifies a 13-20 minute administrative block before queueing that is addressable, not the entire 23-32 minute visit-registration journey. Documents often arrive late, formats vary, package knowledge stays tacit, staff retype data, and exceptions lack a consistent workflow.")]
    story += [Table([[card("Late capture", "Eligibility documents surface at the counter, leaving no time to resolve missing pages or expired dates.", col), card("Non-standard evidence", "Referrals, vouchers, and authorizations use inconsistent wording and layouts.", col)], [card("Repeated entry", "Patients and staff re-enter the same identifiers and package details across disconnected steps.", col), card("Exception overload", "Tacit package rules make every case feel manual instead of highlighting only what needs judgement.", col)]], colWidths=[col, col], hAlign="LEFT")]
    story[-1].setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm), ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm)]))
    story += [Spacer(1, 2 * mm), Table([[P("VALUE PROPOSITION", white_small), P("Prepare administrative evidence before arrival; let transparent rules find exceptions; keep staff in control.", ParagraphStyle("VP", parent=body, fontName="Helvetica-Bold", textColor=colors.white, fontSize=10.5, leading=14))]], colWidths=[35 * mm, usable - 35 * mm], style=[("BACKGROUND", (0, 0), (-1, -1), GREEN), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm), ("TOPPADDING", (0, 0), (-1, -1), 4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm)])]
    story.append(PageBreak())

    # Page 2
    story += [P("Solution and user journey", h1), process_flow(), Spacer(1, 4 * mm)]
    story += [Table([[card("Patient surface", "Simulated Singpass/MyInfo or manual entry, visit reason and document declaration, phone camera/file upload, five tablet-ready synthetic forms, immediate parsing, patient-safe summary, live queue/room updates, and documentless review path.", col), card("Clinic surface", "Prioritized queue, patient declarations, field/evidence review, information request, approval with recorded override, on-site check-in, live destination updates, and guarded Clinic Assist export. Managers see references, metrics, and audit.", col)]], colWidths=[col, col], style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm)])]
    story += [P("Clean journey", h2), bullet("Patient confirms reusable profile/questionnaire data and submits before arrival."), bullet("Eleven deterministic checks return a provisional, review-required, or blocked outcome with field citations."), bullet("At arrival, staff separately attest identity, e-card, and originals before schema-valid export.")]
    story += [P("Exception journey", h2), bullet("Expired, conflicting, missing, or unreadable evidence is presented as a focused exception."), bullet("Staff draft and confirm a request; Mailpit simulates delivery; the case moves to NEEDS_ACTION."), bullet("Any approval with a failing check requires an explicit override and reason in the audit trail.")]
    boundary = Table([[P("NON-NEGOTIABLE BOUNDARY", white_small), P("ClinicPass never remotely verifies identity or e-card, makes clinical decisions, or guarantees coverage. Final administrative readiness remains a staff decision; originals are checked on site.", ParagraphStyle("Boundary", parent=body, textColor=colors.white, fontName="Helvetica-Bold"))]], colWidths=[38 * mm, usable - 38 * mm], style=[("BACKGROUND", (0, 0), (-1, -1), DARK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm), ("TOPPADDING", (0, 0), (-1, -1), 4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm)])
    story += [Spacer(1, 4 * mm), boundary, Spacer(1, 4 * mm), P("What is innovative", h2), P("The novelty is not autonomous eligibility. It is a traceable division of labor: local layout evidence, constrained model extraction, transparent administrative rules, exception-first human review, and a controlled handoff. The same domain actions are reusable by Web UI, future Android, and Copilot Studio without moving decision authority into a chatbot.")]
    story.append(PageBreak())

    # Page 3
    story += [P("Architecture, feasibility, and governance", h1)]
    architecture = [
        [P("Interfaces", label), P("Patient Web UI | Clinic assistant + manager Web UI | Future Android | Future Copilot Studio", body)],
        [P("Gateway + API", label), P("Caddy | Next.js 16 / React / TypeScript | FastAPI / Pydantic | secure cookie sessions + role and clinic claims", body)],
        [P("Processing", label), P("PostgreSQL job queue | Python worker | normalized PDF/photo images | Tesseract OCR evidence | AGNES vision + forced tool calls", body)],
        [P("Integrations", label), P("Document volume | Mailpit | mock Clinic Assist HTTP adapter | future managed storage and production connector", body)],
    ]
    arch_table = Table(architecture, colWidths=[35 * mm, usable - 35 * mm])
    arch_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.white), ("BOX", (0, 0), (-1, -1), .6, LINE), ("INNERGRID", (0, 0), (-1, -1), .4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm), ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm)]))
    story += [arch_table, Spacer(1, 3 * mm)]
    story += [Table([[card("AGNES vision + OCR", "Up to six PDF pages or normalized photos are sent as private data URLs beside OCR evidence. Two schema-constrained tool calls classify and extract. Pydantic validates shape; invented evidence IDs are discarded; failures remain visible.", col), card("Deterministic code", "Field assertions preserve support and conflicts. Eleven rules use versioned references and canonical freshness hashes. Every non-pass finding must be resolved or separately overridden by a manager; consequential events enter the chained audit trail.", col)]], colWidths=[col, col], style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm)])]
    story += [P("Copilot Studio controlled action map", h2), P("Seven documented REST actions: search cases; get summary; explain exceptions; locate evidence; draft patient request; submit confirmed request; record confirmed decision. The OpenAPI v2 JSON is ready to import. The production port uses Microsoft Entra OAuth/OBO so role and clinic authorization come from signed-in staff claims, not model text.")]
    story += [P("Governance and security", h2), bullet("Synthetic data only; API keys stay server-side; opaque sessions are hashed at rest; uploads are size/type limited."), bullet("Evidence snippets constrain model context and reduce prompt-injection surface; model output never invokes approval directly."), bullet("Mock Clinic Assist proves the adapter contract. No NEHR write is in scope; any future clinical-record connection requires separate consent, minimization, governance, and interface review.")]
    story += [P("Feasible build path", h2), P("Completed: additive V2 migration, reusable profiles/questionnaires, field assertions and corrections, immutable reference releases, eleven rules, manager overrides, separate attestations, idempotent schema export, benchmark manifest, security controls, Copilot facade, public exporter, CI, and tests. Production dependencies remain: official labelled fixtures, real integrations, tenant identity, operational malware scanning, reviewer study, retention operations, and pricing.")]
    story.append(PageBreak())

    # Page 4
    story += [P("Operational impact, cost, scalability, and ask", h1), P("Measured prototype evidence", h2)]
    metrics = [[P("42", ParagraphStyle("Big", parent=title, fontSize=24, textColor=GREEN)), P("5", ParagraphStyle("Big2", parent=title, fontSize=24, textColor=GREEN)), P("390 px", ParagraphStyle("Big3", parent=title, fontSize=24, textColor=GREEN)), P("0", ParagraphStyle("Big4", parent=title, fontSize=24, textColor=GREEN))], [P("API tests passed", center), P("Tablet demo forms", center), P("Mobile acceptance width", center), P("Silent AI fallbacks", center)]]
    metric_table = Table(metrics, colWidths=[usable / 4] * 4)
    metric_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), MINT), ("BOX", (0, 0), (-1, -1), .5, LINE), ("INNERGRID", (0, 0), (-1, -1), .5, LINE), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, 0), 3 * mm), ("BOTTOMPADDING", (0, 1), (-1, 1), 3 * mm)]))
    story += [metric_table, Spacer(1, 2 * mm), P("The live AGNES endpoint read a synthetic medical-chit image from a private data URL. Automated tests cover intake, uploads, retries, image normalization, evidence validation, and access boundaries. Static checks, the production build, Docker/browser journeys, and public-export checks pass.", small)]
    story += [P("Measurement plan - no unmeasured claim", h2), P("With the official labelled fixture set, report field and evidence accuracy, false-pass rate, ready-before-arrival rate, duplicate-entry reduction, staff time, latency, and cost. The target is only the identified 13-20 minute administrative block; no impact claim is made yet.", small)]
    formula = Table([[P("Observed cost per case", label), P("OCR pages x OCR price/page + AGNES input/output tokens x tested price + messages + storage/retention + platform allocation", body)]], colWidths=[43 * mm, usable - 43 * mm], style=[("BACKGROUND", (0, 0), (-1, -1), CREAM), ("BOX", (0, 0), (-1, -1), .5, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm), ("TOPPADDING", (0, 0), (-1, -1), 3 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm)])
    story += [formula, P("Scale and configuration", h2), P("Clinic, organization, package, and rule data are configuration, not prompt text. Stateless services and independent workers scale horizontally; PostgreSQL locking prevents duplicate jobs. Expansion follows only after organization-specific rules, governance, and contracts are validated.", small)]
    story += [P("Proposed pilot and ask", h2), bullet("Pilot one clinic with synthetic/shadow-mode records and a labelled document set; no production decision automation."), bullet("Confirm official fixtures, pricing, Clinic Assist contract, tenant identity, organization rules, retention, privacy, security review, and operational ownership."), bullet("Go/no-go: zero false passes in the agreed set, auditable evidence, staff acceptance, and measured net time/cost benefit.")]
    disclosure = Table([
        [P("APPENDIX: AI TOOLS USED", white_small), P("<b>AGNES 2.0 Flash</b> performs live classification and administrative extraction from synthetic document images. <b>OpenAI Codex</b> assisted implementation, testing, debugging, and documentation. All generated code, model outputs, and submission claims were reviewed and validated by the team. Microsoft Copilot Studio is documented as a future port and was not implemented.", white_small)],
        [P("PUBLIC REPOSITORY", white_small), P("https://github.com/HappyCool121/hackforhealth", white_small)],
    ], colWidths=[39 * mm, usable - 39 * mm])
    disclosure.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("LINEABOVE", (0, 1), (-1, 1), 0.35, colors.HexColor("#6E9188")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
    ]))
    story += [Spacer(1, 1.5 * mm), disclosure]
    return story


def main() -> None:
    if len(EXECUTIVE_SUMMARY.split()) > 200:
        raise SystemExit("Executive summary exceeds 200 words")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=20 * mm, bottomMargin=16 * mm, title="ClinicPass Main Report", author="ClinicPass")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="four-page", frames=frame, onPage=header_footer)])
    doc.build(build_story())
    pages = len(PdfReader(str(OUTPUT)).pages)
    if pages != 4:
        raise SystemExit(f"Expected exactly 4 pages, generated {pages}")
    LEGACY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    copyfile(OUTPUT, LEGACY_OUTPUT)
    print(f"Generated {OUTPUT} ({pages} pages, {len(EXECUTIVE_SUMMARY.split())}-word executive summary)")


if __name__ == "__main__":
    main()
