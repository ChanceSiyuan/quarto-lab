#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SYNC_SCRIPT = os.path.join(ROOT, "scripts", "sync_giscus_comments.py")


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature)


class WebhookHandler(BaseHTTPRequestHandler):
    server_version = "GiscusWebhook/1.0"

    def do_GET(self):
        if self.path.startswith(self.server.webhook_path):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if not self.path.startswith(self.server.webhook_path):
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        signature = self.headers.get("X-Hub-Signature-256", "")
        if secret:
            if not signature or not verify_signature(secret, body, signature):
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"invalid signature")
                return

        event = self.headers.get("X-GitHub-Event", "")
        if event == "ping":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"pong")
            return

        if event not in ("discussion", "discussion_comment"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ignored")
            return

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"bad json")
            return

        discussion = payload.get("discussion") or {}
        discussion_id = discussion.get("node_id")

        if not discussion_id:
            self.send_response(202)
            self.end_headers()
            self.wfile.write(b"no discussion id")
            return

        cmd = [
            "/usr/bin/flock",
            "-n",
            "/tmp/quarto-giscus-sync.lock",
            SYNC_SCRIPT,
            "--render",
            "--render-scope",
            "changed",
            "--discussion-id",
            discussion_id,
        ]
        try:
            res = subprocess.run(cmd, cwd=ROOT, check=False)
            if res.returncode == 0:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"synced")
            else:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"sync failed")
        except Exception:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"error")


def main():
    parser = argparse.ArgumentParser(description="Giscus webhook receiver")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--path", default="/webhook/giscus")
    args = parser.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), WebhookHandler)
    httpd.webhook_path = args.path
    print(f"Listening on {args.host}:{args.port}{args.path}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
