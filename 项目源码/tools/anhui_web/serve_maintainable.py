"""Serve the external-data maintenance site over local HTTP."""

from __future__ import annotations

import argparse
import mimetypes
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIRECTORY = ROOT / "deliverables" / "maintainable"


def serve(directory: Path = DEFAULT_DIRECTORY, host: str = "127.0.0.1", port: int = 8765) -> None:
    mimetypes.add_type("application/manifest+json", ".webmanifest")
    directory = Path(directory).resolve()
    if not (directory / "index.html").is_file():
        raise FileNotFoundError(f"维护站未构建：{directory / 'index.html'}")
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"maintainable site → http://{host}:{port}/index.html")
    print(f"directory → {directory}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nserver stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="本地 HTTP 服务皖域择岗长期维护站")
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.directory, args.host, args.port)
