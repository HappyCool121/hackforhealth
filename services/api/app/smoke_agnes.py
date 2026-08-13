import base64
from io import BytesIO

from PIL import Image, ImageDraw

from .ai import AgnesProvider


image = Image.new("RGB", (1200, 520), "white")
draw = ImageDraw.Draw(image)
draw.multiline_text(
    (45, 45),
    "SYNTHETIC DEMO - NOT VALID FOR CARE, CLAIMS, OR IDENTITY\n\n"
    "COMPANY MEDICAL CHIT\nPatient: Jamie Tan\nID last four: 123A\n"
    "Clinic: Central Family Clinic\nOrganisation code: ORG-DEMO\nValid to: 31 December 2027",
    fill="black",
    spacing=20,
)
encoded = BytesIO()
image.save(encoded, format="JPEG", quality=90)
data_url = "data:image/jpeg;base64," + base64.b64encode(encoded.getvalue()).decode("ascii")

provider = AgnesProvider()
result = provider.extract([], "unknown", [data_url])
if result.category != "medical_chit" or "jamie" not in str(result.fields.get("patient_name", "")).lower():
    raise RuntimeError("AGNES vision smoke did not classify the medical chit or read the synthetic patient")
print(result.model_dump_json(indent=2))
