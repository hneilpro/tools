"""Local-only web server for the Image Scrubber.

Security posture matches the networking tools: binds 127.0.0.1 only,
random per-run token, pinned Host header. Uploads are parsed with a
small strict multipart reader (stdlib only).
"""
from __future__ import annotations

import io
import secrets
import threading
import time
import uuid
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .scrub import scrub_image
from .web_ui import PAGE

MAX_UPLOAD = 100 * 1024 * 1024  # 100 MB per request
MAX_FILES = 20
BATCH_TTL = 30 * 60  # keep cleaned files for 30 minutes

_batches: dict[str, dict] = {}
_batches_lock = threading.Lock()


def _parse_multipart(body: bytes, boundary: bytes):
    """Parse multipart/form-data. Returns (fields, files).

    fields: dict name -> str. files: list of (fieldname, filename, bytes).
    """
    fields: dict[str, str] = {}
    files: list[tuple[str, str, bytes]] = []
    delimiter = b"--" + boundary
    parts = body.split(delimiter)
    for part in parts[1:]:
        if part.startswith(b"--"):
            break  # closing delimiter
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        head, sep, content = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers: dict[str, str] = {}
        for line in head.split(b"\r\n"):
            if b":" in line:
                k, v = line.split(b":", 1)
                headers[k.strip().lower().decode("latin1")] = v.strip().decode("latin1")
        disp = headers.get("content-disposition", "")
        disp_parts = [p.strip() for p in disp.split(";")]
        if not disp_parts or not disp_parts[0].lower() == "form-data":
            continue
        attrs: dict[str, str] = {}
        for p in disp_parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                attrs[k.strip().lower()] = v.strip().strip('"')
        name = attrs.get("name", "")
        filename = attrs.get("filename")
        if filename is not None:
            files.append((name, filename, content))
        else:
            fields[name] = content.decode("utf-8", "replace")
    return fields, files


def _prune_batches():
    now = time.time()
    with _batches_lock:
        for bid in [b for b, v in _batches.items() if now - v["created"] > BATCH_TTL]:
            del _batches[bid]


def make_handler(token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ImageScrubber/1.0"

        def _query_token_ok(self) -> bool:
            query = parse_qs(urlparse(self.path).query)
            return secrets.compare_digest((query.get("token") or [""])[0], token)

        def _allowed(self, allow_query_token_paths=("/api/download", "/api/download-all")) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0].lower()
            if host not in ("127.0.0.1", "localhost"):
                self._send(403, {"error": "Forbidden host."})
                return False
            path = urlparse(self.path).path
            if path in allow_query_token_paths and self._query_token_ok():
                return True  # <a>/<img> downloads can't set headers
            if self.command == "GET" and path == "/" and self._query_token_ok():
                return True
            if not secrets.compare_digest(self.headers.get("X-Tool-Token") or "", token):
                self._send(403, {"error": "Missing or invalid session token. Reload the page from the app."})
                return False
            return True

        def _send(self, code: int, payload, content_type="application/json"):
            if isinstance(payload, (dict, list)):
                body = __import__("json").dumps(payload).encode()
            elif isinstance(payload, bytes):
                body = payload
            else:
                body = str(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, filename: str, data: bytes, content_type: str):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                if not self._allowed():
                    return
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif path in ("/api/download", "/api/download-all"):
                if not self._allowed():
                    return
                query = parse_qs(urlparse(self.path).query)
                batch_id = (query.get("batch") or [""])[0]
                with _batches_lock:
                    batch = _batches.get(batch_id)
                if not batch:
                    self._send(404, {"error": "Files expired or unknown batch. Scrub again."})
                    return
                if path == "/api/download":
                    file_id = (query.get("id") or [""])[0]
                    entry = batch["files"].get(file_id)
                    if not entry:
                        self._send(404, {"error": "File not found."})
                        return
                    ctype = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                             "png": "image/png", "webp": "image/webp"}.get(
                        entry["filename"].rsplit(".", 1)[-1].lower(), "application/octet-stream")
                    self._send_file(entry["filename"], entry["data"], ctype)
                else:
                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        for entry in batch["files"].values():
                            zf.writestr(entry["filename"], entry["data"])
                    self._send_file("scrubbed-images.zip", buf.getvalue(), "application/zip")
            else:
                self._send(404, {"error": "Not found."})

        def do_POST(self):
            if urlparse(self.path).path != "/api/clean":
                self._send(404, {"error": "Not found."})
                return
            if not self._allowed():
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_UPLOAD:
                self._send(413, {"error": "Upload too large (max 100 MB)."})
                return
            ctype = self.headers.get("Content-Type") or ""
            if "multipart/form-data" not in ctype or "boundary=" not in ctype:
                self._send(400, {"error": "Expected a multipart file upload."})
                return
            boundary = ctype.split("boundary=")[1].strip().strip('"').encode("latin1")
            try:
                body = self.rfile.read(length)
            except Exception:
                self._send(400, {"error": "Could not read upload."})
                return
            try:
                fields, files = _parse_multipart(body, boundary)
            except Exception:
                self._send(400, {"error": "Could not parse upload."})
                return
            if not files:
                self._send(400, {"error": "No image files received."})
                return
            if len(files) > MAX_FILES:
                self._send(400, {"error": f"Too many files (max {MAX_FILES})."})
                return
            ai_tag = fields.get("ai_tag") in ("1", "true", "on", "yes")

            _prune_batches()
            batch_id = uuid.uuid4().hex[:12]
            stored: dict[str, dict] = {}
            items = []
            ok_count = 0
            for _field, filename, data in files:
                safe_name = (filename or "image").rsplit("/", 1)[-1].rsplit("\\", 1)[-1] or "image"
                result = scrub_image(data, safe_name, ai_tag=ai_tag)
                if result["ok"]:
                    fid = uuid.uuid4().hex[:8]
                    stored[fid] = {"filename": result["out_filename"], "data": result["data"]}
                    ok_count += 1
                    items.append({"ok": True, "id": fid, "filename": safe_name,
                                  "out_filename": result["out_filename"],
                                  "note": result["note"], "size": result["size"]})
                else:
                    items.append({"ok": False, "filename": safe_name, "error": result["error"]})
            with _batches_lock:
                _batches[batch_id] = {"created": time.time(), "files": stored}
            summary = (f"Scrubbed {ok_count} of {len(files)} file(s) clean."
                       + (" AI tag applied." if ai_tag and ok_count else ""))
            self._send(200, {"batch": batch_id, "items": items, "summary": summary})

    return Handler


def build_server():
    """Create (server, token, url) without starting it."""
    token = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(token))
    url = f"http://127.0.0.1:{server.server_address[1]}/?token={token}"
    return server, token, url


def serve(open_browser: bool = True) -> None:
    try:
        from PIL import Image  # noqa: F401  (fail fast with a clear message)
    except ImportError:
        raise SystemExit("Pillow is required: python -m pip install Pillow")
    server, _token, url = build_server()
    print(f"Image Scrubber running at {url}", flush=True)
    print("Press Ctrl+C to stop. (Local only: nothing leaves your PC.)", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
