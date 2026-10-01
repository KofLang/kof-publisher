#!/usr/bin/env python3
"""Deterministic fake chat server for the KofLM E2E tests.

Serves the Ollama/OpenAI-compatible endpoints the Publisher uses:
  GET  /api/tags  -> {"models":[...]}  (lmAvailable probe)
  POST /api/chat  -> {"model":..., "message":{"role":"assistant","content":...}, "done":true}

The reply is chosen by the REQUEST CONTENT so one fixture can play every
role the pipeline needs (generate -> post text, discover -> topic list).
It is a TEST FIXTURE: the Kof side talks real HTTP to it (kof.http +
kof.json) -- no Kof code is stubbed.
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

POST_TEXT = (
    "Migrar um sistema legado comecou por um mapa de dependencias gerado a "
    "partir de logs reais de producao. Em tres semanas a equipe trocou o "
    "camada de acesso a dados sem tocar a interface publica, e cada release "
    "passou a sair com os mesmos dezesseis cenarios de smoke. O ganho apareceu "
    "no estoque de erros evitados e no tempo de resposta medio. Vale comecar "
    "pelo que ja esta rodando e medir antes de reescrever. #legado #backend"
)
TOPICS = "- migracao incremental de legado\n- observabilidade como entrada de design\n- contratos estaveis entre times\n"


def pick_reply(prompt: str) -> str:
    low = prompt.lower()
    if "descobridor de pautas" in low or "responda apenas com a lista" in low:
        return TOPICS
    return POST_TEXT


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
        sys.stderr.write("fake_lm: " + (fmt % args) + "\n")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11555
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
