import http.client
import json
import os
import secrets
import threading
import unittest
from http.server import HTTPServer

from server import Handler


VALID_EXPORT = {
    "schema_version": "2.0.0",
    "idempotency_key": "demo-key-001",
    "case": {
        "id": "case-demo",
        "reference": "demo",
        "status": "CHECKED_IN",
        "clinic_id": "clinic-synthetic",
    },
    "patient": {
        "full_name": "Jamie Tan",
        "masked_identity": "••••1234",
        "email": "jamie@example.test",
    },
    "visit": {
        "appointment_type": "scheduled",
        "appointment_date": "2026-08-15",
        "visit_reason": "Synthetic screening",
    },
    "questionnaire": [],
    "eligibility": None,
    "requested_services": ["BASIC_SCREEN"],
    "documents": [],
    "staff_review": [{"decision": "approved"}],
    "corrections": [],
    "overrides": [],
    "on_site_checks": [
        {"kind": "identity"},
        {"kind": "e_card"},
        {"kind": "originals"},
    ],
}


class MockClinicAssistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.secret = secrets.token_urlsafe(24)
        os.environ["CLINIC_ASSIST_SECRET"] = cls.secret
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def request(self, method, path, *, secret=None, payload=None, idempotency_key=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"content-type": "application/json"}
        if secret:
            headers["X-Clinic-Assist-Key"] = secret
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
            headers["X-Correlation-ID"] = "test-correlation"
        body = json.dumps(payload).encode() if payload is not None else None
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        content = response.read()
        connection.close()
        return response.status, json.loads(content)

    def test_health_is_public(self):
        status, payload = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ok", "schema_version": "2.0.0"})

    def test_export_requires_secret(self):
        status, _ = self.request("POST", "/api/v1/patients", payload=VALID_EXPORT)
        self.assertEqual(status, 401)
        status, payload = self.request(
            "POST",
            "/api/v1/patients",
            secret=self.secret,
            payload=VALID_EXPORT,
            idempotency_key="demo-key-001",
        )
        self.assertEqual(status, 202)
        self.assertEqual(payload["reference"], "CA-demo")
        self.assertEqual(payload["correlation_id"], "test-correlation")

        replay_status, replay_payload = self.request(
            "POST",
            "/api/v1/patients",
            secret=self.secret,
            payload=VALID_EXPORT,
            idempotency_key="demo-key-001",
        )
        self.assertEqual(replay_status, 202)
        self.assertEqual(replay_payload, payload)


if __name__ == "__main__":
    unittest.main()
