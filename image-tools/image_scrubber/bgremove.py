"""Background removal using a tiny local AI model.

Uses rembg with the `u2netp` session: a ~5 MB ONNX model that runs on CPU
via onnxruntime. No GPU, no cloud, no account. The model file downloads
once (to ~/.rembg) on first use.

Only rembg + onnxruntime are required, both pure-Python installable:
    pip install rembg onnxruntime
"""
from __future__ import annotations

import io
import os
import threading

_session = None
_session_lock = threading.Lock()

MODEL_NAME = "u2netp"  # ~5MB, the lightweight pick; larger models need no code change


def _get_session():
    global _session
    with _session_lock:
        if _session is None:
            try:
                from rembg import new_session
            except ImportError as exc:
                raise RuntimeError(
                    "Background removal needs extra packages: "
                    "pip install rembg onnxruntime"
                ) from exc
            _session = new_session(MODEL_NAME)
    return _session


def remove_background(data: bytes, filename: str) -> dict:
    """Remove the background from one image.

    Returns {ok: True, data: PNG bytes with alpha, out_filename, note}
    or {ok: False, error}. Raises RuntimeError if rembg isn't installed.
    """
    from PIL import Image

    session = _get_session()  # RuntimeError if rembg missing

    try:
        from rembg import remove
        out_bytes = remove(data, session=session)
    except Exception as exc:
        return {"ok": False, "error": f"Background removal failed: {exc}"}

    try:
        img = Image.open(io.BytesIO(out_bytes))
        img.load()
    except Exception as exc:
        return {"ok": False, "error": f"Background remover returned bad data: {exc}"}

    if img.mode != "RGBA":
        img = img.convert("RGBA")
    # Sanity: warn if the model found no foreground at all
    alpha = img.getchannel("A")
    extrema = alpha.getextrema()
    note = "Background removed."
    if extrema == (0, 0):
        note = "Background removed, but the model found no clear foreground — result is fully transparent."

    buf = io.BytesIO()
    img.save(buf, "PNG")
    base, _ext = os.path.splitext(filename)
    return {
        "ok": True,
        "data": buf.getvalue(),
        "out_filename": f"{base}_nobg.png",
        "note": note,
    }
