from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib
import hmac
import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA = json.loads((Path(__file__).parent / "clinic-assist-v2.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
EXPORTS: dict[str, dict] = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "schema_version": "2.0.0"})
            return
        if self.path.startswith("/api/v1/exports/"):
            key = self.path.rsplit("/", 1)[-1]
            record = EXPORTS.get(key)
            self.send_json(200, record) if record else self.send_json(404, {"detail": "Export not found"})
            return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/v1/patients":
            self.send_error(404)
            return
        expected = os.environ.get("CLINIC_ASSIST_SECRET", "")
        supplied = self.headers.get("X-Clinic-Assist-Key", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            self.send_json(401, {"detail": "Clinic Assist authentication required"})
            return
        length = int(self.headers.get("content-length", "0"))
        if length > 256 * 1024:
            self.send_json(413, {"detail": "Payload too large"})
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_json(400, {"detail": "Invalid JSON"})
            return
        errors = sorted(VALIDATOR.iter_errors(payload), key=lambda error: list(error.path))
        if errors:
            self.send_json(422, {
                "detail": "Schema validation failed",
                "errors": [
                    {"path": ".".join(str(item) for item in error.path), "message": error.message}
                    for error in errors[:20]
                ],
            })
            return
        idempotency_key = self.headers.get("Idempotency-Key", "")
        if idempotency_key != payload.get("idempotency_key"):
            self.send_json(422, {"detail": "Idempotency-Key header must match the payload"})
            return
        request_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        existing = EXPORTS.get(idempotency_key)
        if existing:
            existing["attempts"] += 1
            if existing["request_hash"] != request_hash:
                self.send_json(409, {"detail": "Idempotency key reused with a different request"})
                return
            self.send_json(202, existing["response"])
            return
        correlation_id = self.headers.get("X-Correlation-ID", "")
        response = {
            "status": "accepted",
            "reference": f"CA-{payload['case']['reference']}",
            "correlation_id": correlation_id,
        }
        EXPORTS[idempotency_key] = {
            "request_hash": request_hash,
            "response": response,
            "attempts": 1,
            "correlation_id": correlation_id,
        }
        self.send_json(202, response)

    def send_json(self, status, payload):
        response = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *_):
        return


def main():
    port = int(os.environ.get("PORT", "8090"))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
