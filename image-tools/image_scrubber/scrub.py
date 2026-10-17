"""Core scrubbing logic: strip all metadata, optionally tag AI-generated.

Only Pillow is required. Everything runs locally; nothing is uploaded.
"""
from __future__ import annotations

import io
import os

from PIL import Image, ImageOps
from PIL.PngImagePlugin import PngInfo

AI_TAG_TEXT = "AI-generated content"

# Formats we accept, mapped to Pillow save format + output extension.
_FORMATS = {
    "JPEG": ("JPEG", ".jpg"),
    "JPG": ("JPEG", ".jpg"),
    "PNG": ("PNG", ".png"),
    "WEBP": ("WEBP", ".webp"),
    "TIFF": ("TIFF", ".tif"),
    "BMP": ("BMP", ".bmp"),
}

MAX_PIXELS = 120_000_000  # safety cap against decompression bombs


def _clean_pixels(img: Image.Image) -> Image.Image:
    """Return a fresh image with identical pixels and zero metadata.

    Applies EXIF orientation first so the cleaned image looks the same
    as the original did in viewers that honor orientation.
    """
    img = ImageOps.exif_transpose(img)
    img.load()
    # Build a brand-new image so no info dict / exif / icc rides along.
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    return clean


def scrub_image(data: bytes, filename: str, ai_tag: bool = False) -> dict:
    """Scrub one image.

    Returns a dict with keys: ok, out_filename, data (bytes),
    format, size, exif_removed, ai_tagged, note. On failure ok=False
    with an error message instead.
    """
    base, ext = os.path.splitext(filename)
    ext = ext.lower()
    try:
        img = Image.open(io.BytesIO(data))
    except Exception as exc:
        return {"ok": False, "error": f"Could not read as an image: {exc}"}

    fmt = (img.format or "").upper()
    if fmt not in _FORMATS:
        return {"ok": False, "error": f"Unsupported image format: {fmt or 'unknown'}"}

    save_fmt, out_ext = _FORMATS[fmt]
    if img.width * img.height > MAX_PIXELS:
        return {"ok": False, "error": "Image is too large to process safely."}

    had_metadata = bool(img.info.get("exif") or img.getexif() or
                        any(k != "dpi" for k in img.info.keys()))
    clean = _clean_pixels(img)

    buf = io.BytesIO()
    save_kwargs: dict = {}
    ai_tagged = False

    try:
        if save_fmt == "JPEG":
            if clean.mode in ("RGBA", "LA", "PA"):
                clean = clean.convert("RGB")
            elif clean.mode == "P":
                clean = clean.convert("RGB")
            if ai_tag:
                exif = Image.Exif()
                # 0x9286 = EXIF UserComment
                exif[0x9286] = AI_TAG_TEXT
                save_kwargs["exif"] = exif
                ai_tagged = True
            # quality=95 keeps visual fidelity high without ballooning size
            clean.save(buf, "JPEG", quality=95, **save_kwargs)
        elif save_fmt == "PNG":
            pnginfo = PngInfo()
            if ai_tag:
                pnginfo.add_text("AI-Generated", "True")
                pnginfo.add_text("Description", AI_TAG_TEXT)
                ai_tagged = True
            clean.save(buf, "PNG", pnginfo=pnginfo)
        elif save_fmt == "WEBP":
            if ai_tag:
                exif = Image.Exif()
                exif[0x9286] = AI_TAG_TEXT
                save_kwargs["exif"] = exif.tobytes()
                ai_tagged = True
            clean.save(buf, "WEBP", quality=95, **save_kwargs)
        else:  # TIFF, BMP — plain re-encode, no metadata carried
            clean.save(buf, save_fmt)
    except Exception as exc:
        return {"ok": False, "error": f"Failed to re-encode image: {exc}"}

    out_name = f"{base}_clean{out_ext}"
    return {
        "ok": True,
        "out_filename": out_name,
        "data": buf.getvalue(),
        "format": save_fmt,
        "size": clean.size,
        "exif_removed": had_metadata,
        "ai_tagged": ai_tagged,
        "note": "Metadata stripped." + (" Tagged as AI-generated." if ai_tagged else ""),
    }
