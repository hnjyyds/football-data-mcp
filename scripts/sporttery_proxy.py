from __future__ import annotations

import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SPORTTERY_URL = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchListV1.qry?clientCode=3001"
HOST = os.getenv("SPORTTERY_PROXY_HOST", "127.0.0.1")
PORT = int(os.getenv("SPORTTERY_PROXY_PORT", "8919"))
TIMEOUT_SECONDS = 12


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] != "/sporttery/match-list":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        try:
            process = subprocess.run(
                [
                    "curl",
                    "-sS",
                    "-L",
                    "--max-time",
                    str(TIMEOUT_SECONDS),
                    "-H",
                    (
                        "User-Agent: "
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
                    ),
                    "-H",
                    "Accept: application/json, text/plain, */*",
                    "-H",
                    "Referer: https://www.sporttery.cn/",
                    SPORTTERY_URL,
                ],
                check=True,
                capture_output=True,
            )
            payload = process.stdout
            json.loads(payload.decode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            body = json.dumps({"success": False, "error": f"{type(exc).__name__}: {exc}"}).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"sporttery_proxy - {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Sporttery proxy listening on http://{HOST}:{PORT}/sporttery/match-list")
    server.serve_forever()


if __name__ == "__main__":
    main()
