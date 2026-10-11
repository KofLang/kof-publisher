#!/usr/bin/env python3
"""Audit fixture: a fake LinkedIn Posts API that RECORDS every request.

Purpose: prove whether any command issues a WRITE (POST) to the publishing
endpoint without explicit authorization. It never talks to the real LinkedIn.

argv[1] = port. It writes one line per request to a log file given by the
environment variable AUDIT_LI_LOG (default ./li_requests.log), and answers
201 with an x-restli-id header for POSTs.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = os.environ.get("AUDIT_LI_LOG", "./li_requests.log")


def record(method, path, headers, body):
    with open(LOG, "a", encoding="utf-8") as fh:
        auth = headers.get("Authorization", "")
        # never write the token value itself: only whether one was present
        fh.write(f"{method} {path} auth_present={bool(auth)} body_len={len(body)}\n")
        if body:
            fh.write("BODY: " + body.replace("\n", " ")[:2000] + "\n")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", extra=None):
        self.send_response(code)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, b"ok")
        record("GET", self.path, self.headers, "")
        self._send(404, b'{"message":"not found"}')

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        record("POST", self.path, self.headers, body)
        self._send(201, b"", {"x-restli-id": "urn:li:share:FAKE999"})

    def log_message(self, fmt, *args):
        sys.stderr.write("audit_linkedin: " + (fmt % args) + "\n")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 12400
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
