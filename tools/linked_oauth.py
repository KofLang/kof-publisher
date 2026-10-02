#!/usr/bin/env python3
"""One-shot LinkedIn OAuth (authorization code) for the KOF publisher.

Reads client_id/client_secret from ~/.local/share/kof/linkedin-credentials.properties
(chmod 600, NEVER in the repo). Opens NOTHING itself: it prints the
authorization URL, you open it in Firefox while logged into LinkedIn and
authorize; this script listens on http://localhost:8737/callback for the
redirect, exchanges the code, resolves your person URN via OIDC userinfo and
writes:

  ~/.local/share/kof/linkedin-secrets.env   (chmod 600)
      export KOF_LINKEDIN_ACCESS_TOKEN=...
      export KOF_LINKEDIN_AUTHOR_URN=urn:li:person:<sub>

The access token is never printed to stdout. Tokens last ~60 days; rerun
this to refresh. Requires the Redirect URL http://localhost:8737/callback
configured in the LinkedIn app (Auth tab).
"""
import http.server
import json
import os
import secrets
import sys
import threading
import time
import urllib.parse
import urllib.request

PORT = 8737
REDIRECT = f"http://localhost:{PORT}/callback"
CREDS = os.path.expanduser("~/.local/share/kof/linkedin-credentials.properties")
OUT = os.path.expanduser("~/.local/share/kof/linkedin-secrets.env")
SCOPES = "w_member_social profile openid"

code_box = {}


def load_creds():
    kv = {}
    with open(CREDS) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()
    return kv["client_id"], kv["client_secret"]


class CB(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in q:
            code_box["code"] = q["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("Kof publisher: autorizado, pode fechar esta aba.".encode())
        else:
            code_box["error"] = str(q)
            self.send_response(400)
            self.end_headers()

    def log_message(self, *a):
        pass


def post_form(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def main():
    client_id, client_secret = load_creds()
    state = secrets.token_urlsafe(12)
    auth = ("https://www.linkedin.com/oauth/v2/authorization?"
            + urllib.parse.urlencode({"response_type": "code", "client_id": client_id,
                                      "redirect_uri": REDIRECT, "scope": SCOPES, "state": state}))
    print("Abra este link no Firefox (logada no LinkedIn) e autorize:\n")
    print(auth + "\n")
    srv = http.server.HTTPServer(("127.0.0.1", PORT), CB)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    deadline = time.time() + 300
    while "code" not in code_box and time.time() < deadline:
        time.sleep(0.5)
    srv.shutdown()
    if "code" not in code_box:
        sys.exit("timeout/erro: " + str(code_box.get("error", "nenhum codigo recebido")))
    tok = post_form("https://www.linkedin.com/oauth/v2/accessToken", {
        "grant_type": "authorization_code", "code": code_box["code"],
        "client_id": client_id, "client_secret": client_secret, "redirect_uri": REDIRECT})
    at = tok["access_token"]
    req = urllib.request.Request("https://api.linkedin.com/v2/userinfo",
                                 headers={"Authorization": "Bearer " + at})
    with urllib.request.urlopen(req, timeout=20) as r:
        info = json.loads(r.read())
    sub = info.get("sub") or ""
    if not sub:
        sys.exit("OIDC userinfo sem 'sub' — verifique os escopes openid/profile")
    umask = os.umask(0o177)
    with open(OUT, "w") as fh:
        fh.write(f"export KOF_LINKEDIN_ACCESS_TOKEN='{at}'\n")
        fh.write(f"export KOF_LINKEDIN_AUTHOR_URN='urn:li:person:{sub}'\n")
    os.umask(umask)
    print(f"OK token gravado em {OUT} (600). Author URN: urn:li:person:{sub}")
    print("Use: source ~/.local/share/kof/linkedin-secrets.env   (ou o runner diario faz isso)")


if __name__ == "__main__":
    main()
