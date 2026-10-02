#!/usr/bin/env python3
"""Fake LM fixture for the KOF-Lab daily pipeline (port 11579).

Reacts to the lab facts digest in the prompt: the draft it returns quotes
the FIRST feature subject and the newest decision line, so the E2E test can
assert that what landed in `lab` actually reached the post text. Colons in
commit subjects are converted (the author's style bans them, so the fixture
stays validator-clean on purpose). When the prompt asks to fix the
"travessao" problem it returns another em-dash draft, deterministically
exercising the rejection path. TEST FIXTURE ONLY -- the Kof side talks real
HTTP to it.
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

BAD_DASH = (
    "Cara — isso aqui e serio — a lab entregou coisa demais. kkkk "
    "quem acompanha sabe. #Kof"
)


def compose_facts_draft(prompt: str) -> str:
    feats = re.findall(r"^- (feat[^\n]+)", prompt, re.M)
    fixes = re.findall(r"^- (fix[^\n]+)", prompt, re.M)
    decided = re.findall(r"^DECISAO DO MAINTAINER[^\n]*\n?", prompt, re.M)
    first = feats[0] if feats else "nenhuma feature"
    extra = fixes[0] if fixes else (feats[1] if len(feats) > 1 else None)
    tail = "E ainda rolou " + extra.replace(":", " -") + ", sem frescura. " if extra else ""
    return (
        "Hoje a lab do Kof entregou " + first.replace(":", " -") + ", e na real isso "
        "muda o papo pra quem acompanha o projeto de perto. " + tail +
        "Quem esta construindo linguagem nova em publico sabe que cada uma dessas "
        "entregas custou review, teste e voto do maintainer. Bacana demais ver isso virar "
        "linha de producao. #Kof #DevLang"
    )


def pick_reply(prompt: str) -> str:
    topic = re.search(r"TEMA DESTA PUBLICACAO: (.*)", prompt)
    if topic is not None and "travessao" in topic.group(1):
        return BAD_DASH
    if "usa travessao" in prompt:
        return BAD_DASH
    return compose_facts_draft(prompt)


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/api/tags":
            self._json(json.dumps({"models": [{"name": "fake-lm"}]}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_response(404)
            self.end_headers()
            return
        n = int(self.headers.get("Content-Length", "0"))
        req = json.loads(self.rfile.read(n) or b"{}")
        text = ""
        for msg in req.get("messages", []):
            text += msg.get("content", "") + "\n"
        resp = {
            "model": req.get("model", "fake-lm"),
            "created_at": "2026-01-01T00:00:00Z",
            "message": {"role": "assistant", "content": pick_reply(text)},
            "done": True,
            "done_reason": "stop",
        }
        self._json(json.dumps(resp).encode())

    def log_message(self, fmt, *args):
        sys.stderr.write("fake_lm_koflab: " + (fmt % args) + "\n")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11579
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
