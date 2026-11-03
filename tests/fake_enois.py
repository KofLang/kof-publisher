#!/usr/bin/env python3
"""Fake enois API fixture for the mirror step.

Port and MODE are argv[1] and argv[2]. It serves the exact endpoints the Kof
enois client touches, so the Kof side does REAL HTTP against a controlled
server and nothing in Kof is stubbed:

    GET /api/users/<username>            -> the user (with the id)
    GET /api/users/<id>/posts?limit=N    -> { "items": [ ... ], "nextCursor": ... }
    GET /api/feed/posts/<id>             -> the single post (WITH pageHtml)

Modes:
  normal  -- three posts: a plain INSIGHT, a PAGE whose text lives only in
             pageHtml (so the client must fetch the detail), and a very short
             INSIGHT that has nothing to caption.
  empty   -- the profile answers a well-formed but EMPTY list.

Control endpoint (fixture-only, never part of the real API):
    POST /__add   {"type": ..., "content": ...}  -> appends a NEW post

TEST FIXTURE ONLY. It never talks to the real enois.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

MODE = sys.argv[2] if len(sys.argv) > 2 else "normal"
USERNAME = "aminadojava"
USER_ID = "user_fixture_0001"

# oldest first, like the real API returns newest first — the client sorts
POSTS = []


def seed():
    if MODE == "empty":
        return
    POSTS.append({
        "id": "post_insight_1",
        "type": "INSIGHT",
        "content": "Terminei a integracao com as APIs externas de vagas. Agora o perfil puxa as vagas sozinho.",
        "articleBody": "",
        "pageHtml": "",
        "createdAt": "2026-10-16T10:00:00Z",
        "authorUsername": USERNAME,
        "communityId": "",
    })
    POSTS.append({
        "id": "post_page_1",
        "type": "PAGE",
        "content": "",
        "articleBody": "",
        "pageHtml": "<div><p>Escrevi um texto sobre como eu organizo times de engenharia.</p><p>O ponto central e dar contexto antes de cobrar entrega.</p></div>",
        "createdAt": "2026-10-16T11:00:00Z",
        "authorUsername": USERNAME,
        "communityId": "",
    })
    POSTS.append({
        "id": "post_short_1",
        "type": "INSIGHT",
        "content": "Java",
        "articleBody": "",
        "pageHtml": "",
        "createdAt": "2026-10-16T12:00:00Z",
        "authorUsername": USERNAME,
        "communityId": "",
    })


seed()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b"{}"
        if self.path == "/__add":
            p = json.loads(raw or b"{}")
            POSTS.append({
                "id": p.get("id", "post_new_%d" % (len(POSTS) + 1)),
                "type": p.get("type", "INSIGHT"),
                "content": p.get("content", ""),
                "articleBody": "",
                "pageHtml": p.get("pageHtml", ""),
                "createdAt": p.get("createdAt", "2026-10-17T09:00:00Z"),
                "authorUsername": USERNAME,
                "communityId": "",
            })
            self._send(200, {"ok": True, "count": len(POSTS)})
            return
        self._send(404, {"error": "not found"})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/__health":
            self._send(200, {"ok": True, "mode": MODE, "posts": len(POSTS)})
            return
        if path == "/api/users/" + USERNAME:
            self._send(200, {"id": USER_ID, "username": USERNAME, "name": "melissa monfre dos santos"})
            return
        if path == "/api/users/" + USER_ID + "/posts":
            # newest first, like the real API
            self._send(200, {"items": list(reversed(POSTS)), "nextCursor": None})
            return
        if path.startswith("/api/feed/posts/"):
            pid = path.rsplit("/", 1)[1]
            for p in POSTS:
                if p["id"] == pid:
                    self._send(200, p)
                    return
            self._send(404, {"error": "no such post"})
            return
        self._send(404, {"error": "not found"})


HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
