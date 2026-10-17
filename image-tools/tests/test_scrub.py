"""Harsh validation for the image scrubber (stdlib + Pillow only)."""
import io
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from image_scrubber.scrub import scrub_image


def make_dirty_jpeg() -> bytes:
    img = Image.new("RGB", (64, 48), (200, 30, 30))
    exif = Image.Exif()
    exif[0x010F] = "FakeCamera"      # Make
    exif[0x0110] = "FakeModel"       # Model
    exif[0x9286] = "secret notes"    # UserComment
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif, quality=95)
    return buf.getvalue()


def make_dirty_png() -> bytes:
    img = Image.new("RGB", (32, 32), (30, 200, 30))
    info = PngInfo()
    info.add_text("Author", "John Doe")
    info.add_text("Comment", "secret")
    buf = io.BytesIO()
    img.save(buf, "PNG", pnginfo=info)
    return buf.getvalue()


def exif_of(data: bytes) -> dict:
    return dict(Image.open(io.BytesIO(data)).getexif())


def png_text_of(data: bytes) -> dict:
    return dict(Image.open(io.BytesIO(data)).info)


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        check.failed = True
check.failed = False

# 1. JPEG scrub removes all EXIF
r = scrub_image(make_dirty_jpeg(), "photo.jpg", ai_tag=False)
check("jpeg scrub ok", r["ok"], r.get("error"))
check("jpeg exif gone", r["ok"] and exif_of(r["data"]) == {}, str(exif_of(r["data"])))
check("jpeg pixels intact", r["ok"] and Image.open(io.BytesIO(r["data"])).size == (64, 48))
check("jpeg renamed", r["ok"] and r["out_filename"] == "photo_clean.jpg", r.get("out_filename"))

# 2. JPEG scrub + AI tag keeps ONLY the tag
r = scrub_image(make_dirty_jpeg(), "photo.jpg", ai_tag=True)
e = exif_of(r["data"]) if r["ok"] else {}
check("jpeg ai-tag ok", r["ok"], r.get("error"))
check("jpeg ai-tag present", r["ok"] and e.get(0x9286) == "AI-generated content", str(e))
check("jpeg ai-tag removed old fields",
      r["ok"] and 0x010F not in e and 0x0110 not in e, str(e))

# 3. PNG scrub removes text chunks
r = scrub_image(make_dirty_png(), "pic.png", ai_tag=False)
t = png_text_of(r["data"]) if r["ok"] else {}
check("png scrub ok", r["ok"], r.get("error"))
check("png text gone", r["ok"] and t == {}, str(t))

# 4. PNG scrub + AI tag adds only the tag
r = scrub_image(make_dirty_png(), "pic.png", ai_tag=True)
t = png_text_of(r["data"]) if r["ok"] else {}
check("png ai-tag ok", r["ok"], r.get("error"))
check("png ai-tag present", r["ok"] and t.get("AI-Generated") == "True", str(t))
check("png old text gone", r["ok"] and "Author" not in t, str(t))

# 5. Garbage input fails cleanly
r = scrub_image(b"not an image at all", "x.jpg")
check("garbage rejected", not r["ok"] and "error" in r, str(r))

# 6. WebP round-trips
img = Image.new("RGB", (16, 16), (30, 30, 200))
buf = io.BytesIO(); img.save(buf, "WEBP", quality=90)
r = scrub_image(buf.getvalue(), "a.webp", ai_tag=True)
check("webp ok", r["ok"], r.get("error"))

print("\nRESULT:", "ALL PASS" if not check.failed else "FAILURES PRESENT")
sys.exit(1 if check.failed else 0)
