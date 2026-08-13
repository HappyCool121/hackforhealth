import json
from unittest.mock import MagicMock, patch

from app.ai import AgnesProvider
from app.config import get_settings


class FakeResponse:
    def __init__(self, arguments: dict):
        self.arguments = arguments

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{
                "message": {
                    "tool_calls": [{"function": {"arguments": json.dumps(self.arguments)}}]
                }
            }]
        }


def test_agnes_vision_payload_and_evidence_validation(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "synthetic-test-key")
    get_settings.cache_clear()
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.post.side_effect = [
        FakeResponse({"category": "medical_chit", "reason": "The title identifies a medical chit"}),
        FakeResponse({
            "category": "medical_chit",
            "fields": {"patient_name": "Jamie Tan", "issuer": "Northstar Corporate Benefits"},
            "citations": [
                {"field": "patient_name", "evidence_id": "p1-w1"},
                {"field": "issuer", "evidence_id": "invented-id"},
            ],
            "warnings": [],
        }),
    ]
    evidence = [{"evidence_id": "p1-w1", "page": 1, "text": "Jamie Tan", "bbox": [0, 0, 1, 1]}]
    image = "data:image/jpeg;base64,c3ludGhldGlj"
    try:
        with patch("app.ai.httpx.Client", return_value=client):
            result = AgnesProvider().extract(evidence, "unknown", [image])
    finally:
        get_settings.cache_clear()

    assert result.category == "medical_chit"
    assert [item.evidence_id for item in result.evidence] == ["p1-w1"]
    first_payload = client.post.call_args_list[0].kwargs["json"]
    content = first_payload["messages"][1]["content"]
    assert any(block.get("type") == "image_url" and block["image_url"]["url"] == image for block in content)

