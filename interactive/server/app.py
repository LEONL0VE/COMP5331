"""Serve the ExDBSCAN explorer: the files in web/ plus a small JSON API.

Usage:
    python3 interactive/server/app.py [--port 8765]

Then open http://127.0.0.1:8765. Only NumPy is needed beyond the standard
library; the algorithms come from exdbscan-study/src.
"""

import argparse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

SERVER_DIR = Path(__file__).resolve().parent
WEB_DIR = SERVER_DIR.parent / "web"
sys.path.insert(0, str(SERVER_DIR.parents[1] / "exdbscan-study" / "src"))

import service  # noqa: E402  (needs the group's package on sys.path)

POST_ROUTES = {
    "/api/cluster": service.cluster,
    "/api/why": service.why,
    "/api/explain": service.explain,
    "/api/verify": service.verify,
}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/datasets":
            return self._reply(service.list_datasets)
        if url.path == "/api/points":
            dataset = parse_qs(url.query).get("dataset", [""])[0]
            return self._reply(lambda: service.points(dataset))
        if url.path.startswith("/api/"):
            return self._send(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
        return super().do_GET()

    def do_POST(self):
        route = POST_ROUTES.get(urlparse(self.path).path)
        if route is None:
            return self._send(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self._send(HTTPStatus.BAD_REQUEST, {"error": "The request body must be JSON"})
        if not isinstance(body, dict):
            return self._send(HTTPStatus.BAD_REQUEST, {"error": "The request body must be a JSON object"})
        return self._reply(lambda: route(body))

    def _reply(self, compute):
        try:
            payload = compute()
        except service.RequestError as exc:
            return self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        return self._send(HTTPStatus.OK, payload)

    def _send(self, status, payload):
        data = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_request(self, code="-", size="-"):
        # Static files are quiet; API calls and errors are logged.
        if self.path.startswith("/api/") or str(code)[0] in "45":
            super().log_request(code, size)


def main():
    parser = argparse.ArgumentParser(description="Serve the ExDBSCAN explorer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"ExDBSCAN explorer: http://{args.host}:{args.port}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
