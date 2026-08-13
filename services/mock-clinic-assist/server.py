from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        response = json.dumps({"status": "accepted", "reference": f"CA-{payload.get('case_id', 'UNKNOWN')}"}).encode()
        self.send_response(202)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *_):
        return


HTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
