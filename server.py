import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from cf import (
    ChatbotConfigError,
    PexelsAPIError,
    get_bot_mode,
    get_bot_response,
    get_model,
    has_openai_api_key,
    has_pexels_api_key,
    is_chat_ready,
)


ROOT = Path(__file__).parent
WEB_ROOT = ROOT / "web"
MAX_BODY_SIZE = 64 * 1024


class ChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/api/status":
            self.send_json(
                {
                    "configured": is_chat_ready(),
                    "mode": get_bot_mode(),
                    "model": get_model(),
                    "openaiConfigured": has_openai_api_key(),
                    "pexelsConfigured": has_pexels_api_key(),
                }
            )
            return

        path = self.path.split("?", 1)[0]
        if path == "/":
            self.serve_file(WEB_ROOT / "index.html")
            return

        requested = (WEB_ROOT / unquote(path.lstrip("/"))).resolve()
        if WEB_ROOT.resolve() not in requested.parents:
            self.send_error(404)
            return

        self.serve_file(requested)

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return

        try:
            payload = self.read_json()
            message = str(payload.get("message", "")).strip()
            history = payload.get("history", [])
            response = get_bot_response(message, history=history)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except ChatbotConfigError as exc:
            self.send_json({"error": str(exc)}, status=503)
        except PexelsAPIError as exc:
            self.send_json({"error": f"Pexels request failed: {exc}"}, status=502)
        else:
            self.send_json(response)

    def read_json(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > MAX_BODY_SIZE:
            raise ValueError("Request is too large.")

        raw_body = self.rfile.read(content_length)
        try:
            return json.loads(raw_body or b"{}")
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc

    def serve_file(self, path):
        if not path.is_file():
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.name == "index.html":
            content = self.render_index(path).encode("utf-8")
            content_type = "text/html"
        else:
            content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def render_index(self, path):
        content = path.read_text(encoding="utf-8")
        for asset_name in ["styles.css", "app.js"]:
            asset = WEB_ROOT / asset_name
            version = int(asset.stat().st_mtime) if asset.exists() else 0
            content = content.replace(f'"/{asset_name}"', f'"/{asset_name}?v={version}"')
        return content

    def send_json(self, payload, status=200):
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


def parse_args():
    parser = argparse.ArgumentParser(description="Run the local AI Bot web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main():
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ChatHandler)

    print(f"AI Bot UI running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
